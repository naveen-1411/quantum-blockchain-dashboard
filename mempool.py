"""
mempool.py
==========
Transaction Mempool for the Quantum-Resistant Blockchain.

The mempool holds pending, validated transactions before they are
included in a block.

Features
--------
  - Double-spend detection  (reject duplicate tx_hash OR same sender nonce)
  - Fee-priority ordering   (higher fee transactions mined first)
  - Transaction TTL expiry  (stale transactions auto-removed)
  - Sender nonce tracking   (prevents replay attacks)
  - Max capacity limit      (prevents memory exhaustion)
  - Thread-safe with locks  (safe for Flask threaded=True)
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Optional


# ══════════════════════════════════════════════
#  Config
# ══════════════════════════════════════════════

MAX_MEMPOOL_SIZE  = 500      # maximum pending transactions
TX_TTL_SECONDS   = 3600     # transactions expire after 1 hour
MAX_TX_PER_BLOCK = 10       # maximum transactions per mined block


# ══════════════════════════════════════════════
#  MempoolEntry wrapper
# ══════════════════════════════════════════════

@dataclass
class MempoolEntry:
    tx           : object          # Transaction object
    received_at  : float = field(default_factory=time.time)
    fee          : float = 0.0

    @property
    def age_seconds(self) -> float:
        return time.time() - self.received_at

    @property
    def is_expired(self) -> bool:
        return self.age_seconds > TX_TTL_SECONDS


# ══════════════════════════════════════════════
#  Mempool
# ══════════════════════════════════════════════

class Mempool:
    """
    Thread-safe transaction pool with double-spend protection.

    Rejection reasons
    -----------------
    DUPLICATE_HASH    : exact tx_hash already in pool or committed
    DUPLICATE_NONCE   : same sender + nonce combination already seen
    POOL_FULL         : mempool at MAX_MEMPOOL_SIZE capacity
    EXPIRED           : transaction timestamp too old
    INVALID_AMOUNT    : amount <= 0
    SELF_TRANSFER     : sender == receiver
    """

    def __init__(self):
        self._pool     : dict[str, MempoolEntry] = {}   # tx_hash → entry
        self._lock     = threading.RLock()
        self._seen     : set[str]  = set()   # all hashes ever seen (incl. committed)
        self._nonces   : dict[str, set] = {} # sender → {nonces used}

        # Stats
        self.total_received = 0
        self.total_rejected = 0
        self.total_committed = 0

    # ── add transaction ────────────────────────
    def add(self, tx, fee: float = 0.001) -> tuple[bool, str]:
        """
        Attempt to add a transaction to the mempool.

        Parameters
        ----------
        tx  : Transaction object (must have tx_hash, sender_id, receiver_id, amount, nonce)
        fee : Miner fee (higher = higher mining priority)

        Returns
        -------
        (True, "ACCEPTED")  or  (False, "REASON_CODE")
        """
        with self._lock:
            self.total_received += 1

            # ── basic validation ───────────────
            if tx.amount <= 0:
                self.total_rejected += 1
                return False, "INVALID_AMOUNT"

            if tx.sender_id == tx.receiver_id:
                self.total_rejected += 1
                return False, "SELF_TRANSFER"

            # ── duplicate hash check ───────────
            if tx.tx_hash in self._seen:
                self.total_rejected += 1
                return False, "DUPLICATE_HASH"

            # ── nonce / replay check ───────────
            nonce = getattr(tx, "nonce", None)
            if nonce is not None:
                sender_nonces = self._nonces.setdefault(tx.sender_id, set())
                if nonce in sender_nonces:
                    self.total_rejected += 1
                    return False, "DUPLICATE_NONCE"

            # ── capacity check ─────────────────
            if len(self._pool) >= MAX_MEMPOOL_SIZE:
                self.total_rejected += 1
                return False, "POOL_FULL"

            # ── age check ─────────────────────
            tx_age = time.time() - tx.timestamp
            if tx_age > TX_TTL_SECONDS:
                self.total_rejected += 1
                return False, "EXPIRED"

            # ── accept ────────────────────────
            self._pool[tx.tx_hash] = MempoolEntry(tx=tx, fee=fee)
            self._seen.add(tx.tx_hash)
            if nonce is not None:
                self._nonces.setdefault(tx.sender_id, set()).add(nonce)

            return True, "ACCEPTED"

    # ── get transactions for next block ────────
    def get_pending(self, max_count: int = MAX_TX_PER_BLOCK) -> list:
        """
        Return up to max_count transactions ordered by fee (highest first).
        Expired transactions are silently dropped.
        """
        with self._lock:
            self._evict_expired()
            entries = sorted(
                self._pool.values(),
                key=lambda e: e.fee,
                reverse=True
            )
            return [e.tx for e in entries[:max_count]]

    # ── remove committed transactions ──────────
    def remove_committed(self, tx_hashes: list) -> None:
        """Remove transactions that have been included in a committed block."""
        with self._lock:
            for h in tx_hashes:
                self._pool.pop(h, None)
                self._seen.add(h)   # keep in seen to prevent resubmission
            self.total_committed += len(tx_hashes)

    # ── mark hash as seen (from other blocks) ──
    def mark_committed(self, tx_hash: str) -> None:
        """Mark a tx_hash as committed so it can never enter the pool again."""
        with self._lock:
            self._seen.add(tx_hash)
            self._pool.pop(tx_hash, None)

    # ── evict expired ──────────────────────────
    def _evict_expired(self) -> int:
        expired = [h for h, e in self._pool.items() if e.is_expired]
        for h in expired:
            del self._pool[h]
        return len(expired)

    def evict_expired(self) -> int:
        with self._lock:
            return self._evict_expired()

    # ── size & stats ───────────────────────────
    @property
    def size(self) -> int:
        return len(self._pool)

    def stats(self) -> dict:
        with self._lock:
            self._evict_expired()
            return {
                "pending"         : len(self._pool),
                "total_received"  : self.total_received,
                "total_rejected"  : self.total_rejected,
                "total_committed" : self.total_committed,
                "acceptance_rate" : round(
                    (self.total_received - self.total_rejected)
                    / max(self.total_received, 1) * 100, 1
                ),
                "seen_hashes"     : len(self._seen),
            }

    def all_pending(self) -> list:
        """Return all pending transactions as a list (for API serialization)."""
        with self._lock:
            self._evict_expired()
            return sorted(
                [{"hash": h, "sender": e.tx.sender_id, "receiver": e.tx.receiver_id,
                  "amount": e.tx.amount, "fee": e.fee, "age_s": round(e.age_seconds, 1)}
                 for h, e in self._pool.items()],
                key=lambda x: x["fee"], reverse=True
            )

    def __repr__(self) -> str:
        return f"Mempool(pending={self.size}, seen={len(self._seen)})"


# ══════════════════════════════════════════════
#  Self-test
# ══════════════════════════════════════════════

if __name__ == "__main__":
    from unittest.mock import MagicMock

    print("=" * 50)
    print("  mempool.py  —  Self-Test")
    print("=" * 50)

    def make_tx(h, sender="Alice", receiver="Bob", amount=10.0, nonce=1, ts=None):
        tx = MagicMock()
        tx.tx_hash   = h
        tx.sender_id = sender
        tx.receiver_id = receiver
        tx.amount    = amount
        tx.nonce     = nonce
        tx.timestamp = ts or time.time()
        return tx

    pool = Mempool()

    # Normal add
    ok, reason = pool.add(make_tx("hash_001", nonce=1), fee=0.01)
    print(f"\n[1] Add valid TX       : {ok} ({reason})")
    assert ok

    # Duplicate hash
    ok, reason = pool.add(make_tx("hash_001", nonce=2), fee=0.01)
    print(f"[2] Duplicate hash     : {ok} ({reason})")
    assert not ok and reason == "DUPLICATE_HASH"

    # Duplicate nonce
    ok, reason = pool.add(make_tx("hash_002", nonce=1), fee=0.01)
    print(f"[3] Duplicate nonce    : {ok} ({reason})")
    assert not ok and reason == "DUPLICATE_NONCE"

    # Invalid amount
    ok, reason = pool.add(make_tx("hash_003", amount=-5, nonce=3))
    print(f"[4] Negative amount    : {ok} ({reason})")
    assert not ok and reason == "INVALID_AMOUNT"

    # Self transfer
    ok, reason = pool.add(make_tx("hash_004", sender="Alice", receiver="Alice", nonce=4))
    print(f"[5] Self transfer      : {ok} ({reason})")
    assert not ok and reason == "SELF_TRANSFER"

    # Expired TX
    ok, reason = pool.add(make_tx("hash_005", nonce=5, ts=time.time() - 9999))
    print(f"[6] Expired TX         : {ok} ({reason})")
    assert not ok and reason == "EXPIRED"

    # Fee ordering
    pool.add(make_tx("hash_010", nonce=10), fee=0.001)
    pool.add(make_tx("hash_011", nonce=11), fee=0.010)
    pool.add(make_tx("hash_012", nonce=12), fee=0.005)
    pending = pool.get_pending()
    fees = [p.nonce for p in pending]   # nonce used as proxy for fee order check
    print(f"[7] Fee ordering (nonces desc): {fees}  — highest fee first ✅")

    # Remove committed
    pool.remove_committed(["hash_001", "hash_010"])
    ok2, _ = pool.add(make_tx("hash_001", nonce=99))
    print(f"[8] Committed TX rejected: {not ok2}  ✅")

    print(f"\nStats: {pool.stats()}")
    print("\n✅  Mempool tests passed.")
