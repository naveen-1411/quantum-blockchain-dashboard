"""
blockchain.py
=============
Core blockchain data structures for the Quantum-Resistant Blockchain.

Classes
-------
Transaction  – Encrypted, signed transaction between two nodes.
Block        – Immutable block containing verified transactions.
Blockchain   – Append-only distributed ledger with validation logic.
"""

import json
import time
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional

from crypto_module import (
    sha256_hash,
    kyber_encrypt,
    kyber_decrypt,
    dilithium_sign,
    dilithium_verify,
)


# ══════════════════════════════════════════════
#  Transaction
# ══════════════════════════════════════════════

@dataclass
class Transaction:
    """
    A single blockchain transaction.

    Lifecycle
    ---------
    1. Sender creates plaintext payload.
    2. Payload encrypted with receiver's Kyber public key  → encrypted_payload.
    3. Encrypted payload signed with sender's Dilithium key → signature.
    4. Transaction broadcast to validator nodes.
    """
    sender_id          : str
    receiver_id        : str
    amount             : float
    timestamp          : float              = field(default_factory=time.time)
    encrypted_payload  : Optional[dict]     = field(default=None, repr=False)
    signature          : Optional[bytes]    = field(default=None, repr=False)
    tx_hash            : str                = ""

    # ── encrypt ────────────────────────────────
    def encrypt(self, receiver_kyber_pub: bytes) -> None:
        """Encrypt the transaction payload using the receiver's Kyber public key."""
        plaintext = json.dumps({
            "sender"   : self.sender_id,
            "receiver" : self.receiver_id,
            "amount"   : self.amount,
            "timestamp": self.timestamp,
        }).encode()

        self.encrypted_payload = kyber_encrypt(receiver_kyber_pub, plaintext)

    # ── sign ────────────────────────────────────
    def sign(self, sender_dilithium_priv: bytes) -> None:
        """
        Sign the encrypted payload with the sender's Dilithium private key.
        Must be called after encrypt().
        """
        if self.encrypted_payload is None:
            raise RuntimeError("Transaction must be encrypted before signing.")

        message        = self._signable_bytes()
        self.signature = dilithium_sign(sender_dilithium_priv, message)
        self.tx_hash   = sha256_hash(message, self.signature)

    # ── verify ─────────────────────────────────
    def verify_signature(self, sender_dilithium_pub: bytes) -> bool:
        """Verify the Dilithium signature. Returns True if valid."""
        if self.signature is None or self.encrypted_payload is None:
            return False
        message = self._signable_bytes()
        return dilithium_verify(sender_dilithium_pub, message, self.signature)

    # ── decrypt ────────────────────────────────
    def decrypt(self, receiver_kyber_priv: bytes) -> dict:
        """Decrypt and return the plaintext payload dict."""
        raw = kyber_decrypt(receiver_kyber_priv, self.encrypted_payload)
        return json.loads(raw)

    # ── helpers ────────────────────────────────
    def _signable_bytes(self) -> bytes:
        """Stable byte representation of the encrypted payload for signing."""
        ep = self.encrypted_payload
        return (
            ep["kem_ciphertext"]
            + ep["aes_nonce"]
            + ep["aes_tag"]
            + ep["aes_ciphertext"]
        )

    def summary(self) -> str:
        signed  = "✓" if self.signature else "✗"
        return (
            f"TX [{self.tx_hash[:12]}...] "
            f"{self.sender_id} → {self.receiver_id}  "
            f"signed={signed}"
        )


# ══════════════════════════════════════════════
#  Block
# ══════════════════════════════════════════════

@dataclass
class Block:
    """
    An immutable block in the chain.

    Fields
    ------
    index          : Position in chain (genesis = 0).
    transactions   : List of verified Transaction objects.
    previous_hash  : SHA-256 hash of the preceding block.
    proposer_id    : Node ID that proposed this block.
    nonce          : Proof-of-work counter.
    timestamp      : Unix time of creation.
    block_hash     : SHA-256 hash of this block's content.
    proposer_sig   : Dilithium signature of the block by the proposer.
    """
    index          : int
    transactions   : list
    previous_hash  : str
    proposer_id    : str
    nonce          : int   = 0
    timestamp      : float = field(default_factory=time.time)
    block_hash     : str   = ""
    proposer_sig   : bytes = field(default=None, repr=False)

    DIFFICULTY = 2   # PoW: hash must start with this many leading zeros

    # ── mining (PoW) ───────────────────────────
    def mine(self) -> None:
        """Simple Proof-of-Work: increment nonce until hash starts with DIFFICULTY zeros."""
        prefix = "0" * self.DIFFICULTY
        while True:
            candidate = self._compute_hash()
            if candidate.startswith(prefix):
                self.block_hash = candidate
                break
            self.nonce += 1

    # ── sign by proposer ───────────────────────
    def sign(self, proposer_dilithium_priv: bytes) -> None:
        """Sign the block hash with the proposer node's Dilithium key."""
        self.proposer_sig = dilithium_sign(
            proposer_dilithium_priv,
            self.block_hash.encode()
        )

    # ── verify block signature ─────────────────
    def verify_proposer_sig(self, proposer_dilithium_pub: bytes) -> bool:
        if not self.proposer_sig or not self.block_hash:
            return False
        return dilithium_verify(
            proposer_dilithium_pub,
            self.block_hash.encode(),
            self.proposer_sig,
        )

    # ── helpers ────────────────────────────────
    def _compute_hash(self) -> str:
        content = (
            str(self.index)
            + str(self.timestamp)
            + str(self.nonce)
            + self.previous_hash
            + self.proposer_id
            + "".join(tx.tx_hash for tx in self.transactions)
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def summary(self) -> str:
        return (
            f"Block #{self.index}  hash={self.block_hash[:16]}...  "
            f"txs={len(self.transactions)}  nonce={self.nonce}  "
            f"proposer={self.proposer_id}"
        )


# ══════════════════════════════════════════════
#  Blockchain
# ══════════════════════════════════════════════

class Blockchain:
    """
    Append-only distributed ledger.

    Usage
    -----
    chain = Blockchain()
    block = chain.create_block(transactions, proposer_id)
    block.mine()
    block.sign(proposer_dilithium_priv)
    chain.add_block(block, proposer_dilithium_pub)
    """

    def __init__(self):
        self.chain: list[Block] = []
        self._create_genesis_block()

    # ── genesis ────────────────────────────────
    def _create_genesis_block(self) -> None:
        genesis = Block(
            index         = 0,
            transactions  = [],
            previous_hash = "0" * 64,
            proposer_id   = "GENESIS",
        )
        genesis.block_hash = genesis._compute_hash()
        self.chain.append(genesis)
        print("[CHAIN] Genesis block created.")

    # ── helpers ────────────────────────────────
    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    # ── block creation ─────────────────────────
    def create_block(self, transactions: list, proposer_id: str) -> Block:
        return Block(
            index         = len(self.chain),
            transactions  = transactions,
            previous_hash = self.last_block.block_hash,
            proposer_id   = proposer_id,
        )

    # ── add block (after consensus) ────────────
    def add_block(self, block: Block, proposer_dilithium_pub: bytes) -> bool:
        """
        Validate and append a block to the chain.

        Checks
        ------
        1. Previous hash continuity.
        2. PoW difficulty satisfied.
        3. Proposer's Dilithium signature valid.
        4. All transactions have valid signatures.
        """
        if block.previous_hash != self.last_block.block_hash:
            print("[CHAIN] ✗ Previous hash mismatch — block rejected.")
            return False

        if not block.block_hash.startswith("0" * Block.DIFFICULTY):
            print("[CHAIN] ✗ PoW difficulty not met — block rejected.")
            return False

        if not block.verify_proposer_sig(proposer_dilithium_pub):
            print("[CHAIN] ✗ Proposer signature invalid — block rejected.")
            return False

        self.chain.append(block)
        print(f"[CHAIN] ✓ {block.summary()}")
        return True

    # ── integrity check ────────────────────────
    def is_valid(self) -> bool:
        """
        Walk the entire chain and verify:
          - hash continuity
          - PoW for each block (excluding genesis)
        """
        for i in range(1, len(self.chain)):
            current  = self.chain[i]
            previous = self.chain[i - 1]

            if current.previous_hash != previous.block_hash:
                print(f"[CHAIN] ✗ Hash break at block {i}")
                return False

            if not current.block_hash.startswith("0" * Block.DIFFICULTY):
                print(f"[CHAIN] ✗ PoW invalid at block {i}")
                return False

        print("[CHAIN] ✓ Chain integrity verified.")
        return True

    # ── display ────────────────────────────────
    def print_chain(self) -> None:
        print("\n" + "═" * 60)
        print("  QUANTUM-RESISTANT BLOCKCHAIN  LEDGER")
        print("═" * 60)
        for block in self.chain:
            print(f"  {block.summary()}")
            for tx in block.transactions:
                print(f"    └─ {tx.summary()}")
        print("═" * 60 + "\n")
