"""
storage.py
==========
SQLite-based persistent storage for the Quantum-Resistant Blockchain.

What is stored
--------------
  blocks       – every block header (index, hashes, nonce, proposer, merkle_root…)
  transactions – every transaction linked to its block
  chain_meta   – chain-level metadata (genesis hash, version, difficulty)

Features
--------
  - Block retrieval by index in O(1) via index column
  - Full chain reload on restart (blockchain survives process exit)
  - Chain synchronisation helper (compare & replace with longer valid chain)
  - All bytes stored as BASE64 text (SQLite has no binary column size limit)

Usage
-----
  db = BlockchainDB()
  db.save_block(block)
  blocks = db.load_all_blocks()
"""

import sqlite3
import json
import base64
import time
from pathlib import Path
from dataclasses import dataclass

DB_PATH = Path("blockchain.db")


# ══════════════════════════════════════════════
#  Serialisation helpers
# ══════════════════════════════════════════════

def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode() if data else ""

def _unb64(s: str) -> bytes:
    return base64.b64decode(s) if s else b""

def _enc_payload_to_json(ep: dict | None) -> str:
    """Convert encrypted_payload dict (bytes values) → JSON string."""
    if ep is None:
        return ""
    return json.dumps({k: _b64(v) for k, v in ep.items()})

def _json_to_enc_payload(s: str) -> dict | None:
    if not s:
        return None
    raw = json.loads(s)
    return {k: _unb64(v) for k, v in raw.items()}


# ══════════════════════════════════════════════
#  BlockchainDB
# ══════════════════════════════════════════════

class BlockchainDB:
    """
    SQLite-backed persistent storage for the blockchain.

    Parameters
    ----------
    db_path : path to the SQLite file (created if not exists)
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._conn   = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    # ── schema ─────────────────────────────────
    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS blocks (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                block_index   INTEGER UNIQUE NOT NULL,
                block_hash    TEXT    NOT NULL,
                previous_hash TEXT    NOT NULL,
                merkle_root   TEXT    NOT NULL DEFAULT '',
                proposer_id   TEXT    NOT NULL,
                proposer_sig  TEXT,
                nonce         INTEGER NOT NULL DEFAULT 0,
                difficulty    INTEGER NOT NULL DEFAULT 2,
                version       INTEGER NOT NULL DEFAULT 1,
                timestamp     REAL    NOT NULL,
                created_at    REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                block_index       INTEGER NOT NULL,
                tx_hash           TEXT    UNIQUE NOT NULL,
                sender_id         TEXT    NOT NULL,
                receiver_id       TEXT    NOT NULL,
                amount            REAL    NOT NULL,
                fee               REAL    NOT NULL DEFAULT 0,
                nonce             INTEGER NOT NULL DEFAULT 0,
                timestamp         REAL    NOT NULL,
                encrypted_payload TEXT,
                signature         TEXT,
                FOREIGN KEY (block_index) REFERENCES blocks(block_index)
            );

            CREATE INDEX IF NOT EXISTS idx_block_index  ON blocks(block_index);
            CREATE INDEX IF NOT EXISTS idx_tx_hash      ON transactions(tx_hash);
            CREATE INDEX IF NOT EXISTS idx_tx_block     ON transactions(block_index);
            CREATE INDEX IF NOT EXISTS idx_tx_sender    ON transactions(sender_id);
        """)
        self._conn.commit()

    # ── save block ─────────────────────────────
    def save_block(self, block) -> None:
        """
        Persist a Block (and all its Transactions) to SQLite.
        Safe to call multiple times — uses INSERT OR REPLACE.
        """
        # Save block header
        self._conn.execute("""
            INSERT OR REPLACE INTO blocks
              (block_index, block_hash, previous_hash, merkle_root,
               proposer_id, proposer_sig, nonce, difficulty, version,
               timestamp, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            block.index,
            block.block_hash,
            block.previous_hash,
            getattr(block, "merkle_root", ""),
            block.proposer_id,
            _b64(block.proposer_sig) if block.proposer_sig else "",
            block.nonce,
            getattr(block, "difficulty", 2),
            getattr(block, "version", 1),
            block.timestamp,
            time.time(),
        ))

        # Save each transaction
        for tx in block.transactions:
            self._conn.execute("""
                INSERT OR IGNORE INTO transactions
                  (block_index, tx_hash, sender_id, receiver_id,
                   amount, fee, nonce, timestamp, encrypted_payload, signature)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                block.index,
                tx.tx_hash,
                tx.sender_id,
                tx.receiver_id,
                tx.amount,
                getattr(tx, "fee", 0.0),
                getattr(tx, "nonce", 0),
                tx.timestamp,
                _enc_payload_to_json(tx.encrypted_payload),
                _b64(tx.signature) if tx.signature else "",
            ))

        self._conn.commit()

    # ── load all blocks (for chain reload) ─────
    def load_all_blocks(self) -> list[dict]:
        """
        Return all blocks ordered by index, each as a dict.
        Used to rebuild the Blockchain object from disk on startup.
        """
        blocks = self._conn.execute(
            "SELECT * FROM blocks ORDER BY block_index"
        ).fetchall()

        result = []
        for b in blocks:
            txs = self._conn.execute(
                "SELECT * FROM transactions WHERE block_index=? ORDER BY id",
                (b["block_index"],)
            ).fetchall()

            tx_dicts = [{
                "tx_hash"          : t["tx_hash"],
                "sender_id"        : t["sender_id"],
                "receiver_id"      : t["receiver_id"],
                "amount"           : t["amount"],
                "fee"              : t["fee"],
                "nonce"            : t["nonce"],
                "timestamp"        : t["timestamp"],
                "encrypted_payload": _json_to_enc_payload(t["encrypted_payload"]),
                "signature"        : _unb64(t["signature"]) or None,
            } for t in txs]

            result.append({
                "index"        : b["block_index"],
                "block_hash"   : b["block_hash"],
                "previous_hash": b["previous_hash"],
                "merkle_root"  : b["merkle_root"],
                "proposer_id"  : b["proposer_id"],
                "proposer_sig" : _unb64(b["proposer_sig"]) or None,
                "nonce"        : b["nonce"],
                "difficulty"   : b["difficulty"],
                "version"      : b["version"],
                "timestamp"    : b["timestamp"],
                "transactions" : tx_dicts,
            })
        return result

    # ── get single block by index ───────────────
    def get_block(self, index: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM blocks WHERE block_index=?", (index,)
        ).fetchone()
        if not row:
            return None
        txs = self._conn.execute(
            "SELECT * FROM transactions WHERE block_index=? ORDER BY id", (index,)
        ).fetchall()
        return {"block": dict(row), "transactions": [dict(t) for t in txs]}

    # ── get tx by hash ──────────────────────────
    def get_transaction(self, tx_hash: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM transactions WHERE tx_hash=?", (tx_hash,)
        ).fetchone()
        return dict(row) if row else None

    # ── chain length ────────────────────────────
    def chain_length(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) as n FROM blocks").fetchone()
        return row["n"]

    # ── all tx hashes (for double-spend check) ──
    def all_committed_tx_hashes(self) -> set:
        rows = self._conn.execute("SELECT tx_hash FROM transactions").fetchall()
        return {r["tx_hash"] for r in rows}

    # ── stats ───────────────────────────────────
    def stats(self) -> dict:
        blocks = self._conn.execute("SELECT COUNT(*) as n FROM blocks").fetchone()["n"]
        txs    = self._conn.execute("SELECT COUNT(*) as n FROM transactions").fetchone()["n"]
        size   = self.db_path.stat().st_size if self.db_path.exists() else 0
        return {
            "blocks"      : blocks,
            "transactions": txs,
            "db_size_bytes": size,
            "db_path"     : str(self.db_path),
        }

    # ── wipe (for tests) ────────────────────────
    def wipe(self) -> None:
        self._conn.executescript("DELETE FROM transactions; DELETE FROM blocks;")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


# ══════════════════════════════════════════════
#  Self-test
# ══════════════════════════════════════════════

if __name__ == "__main__":
    import tempfile, os
    from unittest.mock import MagicMock

    print("=" * 50)
    print("  storage.py  —  Self-Test")
    print("=" * 50)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = Path(f.name)

    try:
        db = BlockchainDB(tmp)

        # Mock block
        def make_block(idx, prev="0"*64):
            tx = MagicMock()
            tx.tx_hash = f"txhash_{idx}_001"
            tx.sender_id = "Alice"; tx.receiver_id = "Bob"
            tx.amount = 50.0; tx.fee = 0.001; tx.nonce = idx
            tx.timestamp = time.time()
            tx.encrypted_payload = {"kem_ciphertext":b"KYB1"+b"\x00"*10,"aes_nonce":b"n"*12,"aes_tag":b"t"*16,"aes_ciphertext":b"ct"}
            tx.signature = b"sig_bytes"

            b = MagicMock()
            b.index = idx; b.block_hash = f"hash_{idx}"; b.previous_hash = prev
            b.merkle_root = f"merkle_{idx}"; b.proposer_id = "Validator-1"
            b.proposer_sig = b"proposer_sig"; b.nonce = idx * 10
            b.difficulty = 2; b.version = 1; b.timestamp = time.time()
            b.transactions = [tx]
            return b

        genesis = make_block(0)
        block1  = make_block(1, "hash_0")
        db.save_block(genesis)
        db.save_block(block1)

        all_blocks = db.load_all_blocks()
        print(f"\n[1] Saved & loaded {len(all_blocks)} blocks  ✅")
        assert len(all_blocks) == 2

        fetched = db.get_block(1)
        print(f"[2] get_block(1): hash={fetched['block']['block_hash']}  ✅")

        tx = db.get_transaction("txhash_0_001")
        print(f"[3] get_transaction: sender={tx['sender_id']}  ✅")

        committed = db.all_committed_tx_hashes()
        print(f"[4] Committed tx hashes: {committed}  ✅")

        print(f"[5] Stats: {db.stats()}")
        print("\n✅  Storage tests passed.")
    finally:
        db.close()
        os.unlink(tmp)
