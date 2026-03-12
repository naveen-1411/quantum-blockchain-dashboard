"""
wallet.py
=========
Wallet system for the Quantum-Resistant Blockchain.

Each wallet holds:
  - Dilithium3 key pair  (signing transactions)
  - Kyber1024  key pair  (receiving encrypted payloads)
  - Wallet address       = SHA-256(dilithium_pub)[:20].hex()  (Ethereum-style)
  - Balance              tracked locally (updated from confirmed blocks)

Key persistence:
  Keys are saved to  wallets/<address>.json  encrypted with AES-256-GCM
  using a user-supplied passphrase.  Never stored in plaintext.

Usage
-----
  w = Wallet.create("Alice")
  w.save("my_passphrase")

  w2 = Wallet.load("wallets/alice_address.json", "my_passphrase")
"""

import os
import json
import hashlib
import base64
import time
from pathlib import Path

from crypto_module import (
    generate_kyber_keypair,
    generate_dilithium_keypair,
    KYBER_PUB_SIZE,
    DILITHIUM_PUB_SIZE,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes as crypto_hashes

WALLET_DIR = Path("wallets")


# ══════════════════════════════════════════════
#  Key-derivation helpers (passphrase → AES key)
# ══════════════════════════════════════════════

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 32-byte AES key from a passphrase using PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm  = crypto_hashes.SHA256(),
        length     = 32,
        salt       = salt,
        iterations = 200_000,
    )
    return kdf.derive(passphrase.encode())


def _encrypt_keys(data: bytes, passphrase: str) -> dict:
    """Encrypt raw key bytes with AES-256-GCM using a passphrase-derived key."""
    salt  = os.urandom(16)
    nonce = os.urandom(12)
    key   = _derive_key(passphrase, salt)
    ct    = AESGCM(key).encrypt(nonce, data, None)
    return {
        "salt" : base64.b64encode(salt).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "ct"   : base64.b64encode(ct).decode(),
    }


def _decrypt_keys(enc: dict, passphrase: str) -> bytes:
    """Decrypt AES-256-GCM ciphertext back to raw key bytes."""
    salt  = base64.b64decode(enc["salt"])
    nonce = base64.b64decode(enc["nonce"])
    ct    = base64.b64decode(enc["ct"])
    key   = _derive_key(passphrase, salt)
    return AESGCM(key).decrypt(nonce, ct, None)


# ══════════════════════════════════════════════
#  Wallet
# ══════════════════════════════════════════════

class Wallet:
    """
    A Quantum-Resistant blockchain wallet.

    Attributes
    ----------
    name            : Human-readable owner name
    address         : 40-char hex address derived from Dilithium public key
    kyber_pub       : Kyber1024  public key  (share with senders)
    kyber_priv      : Kyber1024  private key (keep secret)
    dilithium_pub   : Dilithium3 public key  (share for sig verification)
    dilithium_priv  : Dilithium3 private key (keep secret, sign with this)
    balance         : Tracked token balance (updated from confirmed blocks)
    created_at      : Unix timestamp of wallet creation
    """

    def __init__(
        self,
        name         : str,
        kyber_pub    : bytes,
        kyber_priv   : bytes,
        dilithium_pub: bytes,
        dilithium_priv: bytes,
        balance      : float = 0.0,
        created_at   : float = None,
    ):
        self.name           = name
        self.kyber_pub      = kyber_pub
        self.kyber_priv     = kyber_priv
        self.dilithium_pub  = dilithium_pub
        self.dilithium_priv = dilithium_priv
        self.balance        = balance
        self.created_at     = created_at or time.time()
        self.address        = self._derive_address()

    # ── address derivation ─────────────────────
    def _derive_address(self) -> str:
        """
        Address = first 20 bytes of SHA-256(dilithium_pub) as hex.
        Same approach as Ethereum: keccak256(pub_key)[-20 bytes].
        We use SHA-256 since keccak is not in stdlib.
        """
        return hashlib.sha256(self.dilithium_pub).hexdigest()[:40]

    # ── factory: create new wallet ─────────────
    @classmethod
    def create(cls, name: str, initial_balance: float = 0.0) -> "Wallet":
        """Generate fresh Kyber + Dilithium key pairs and return a new Wallet."""
        kpub,  kpriv  = generate_kyber_keypair()
        dpub,  dpriv  = generate_dilithium_keypair()
        return cls(name, kpub, kpriv, dpub, dpriv, balance=initial_balance)

    # ── save to disk (encrypted) ───────────────
    def save(self, passphrase: str, directory: Path = WALLET_DIR) -> Path:
        """
        Save wallet keys encrypted to  <directory>/<address>.json.

        Private keys are AES-256-GCM encrypted with the passphrase.
        Public keys are stored as-is (they're public).
        """
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.address}.json"

        # Bundle private keys together before encrypting
        priv_bundle = json.dumps({
            "kyber_priv"    : base64.b64encode(self.kyber_priv).decode(),
            "dilithium_priv": base64.b64encode(self.dilithium_priv).decode(),
        }).encode()

        enc = _encrypt_keys(priv_bundle, passphrase)

        wallet_json = {
            "name"          : self.name,
            "address"       : self.address,
            "created_at"    : self.created_at,
            "balance"       : self.balance,
            "kyber_pub"     : base64.b64encode(self.kyber_pub).decode(),
            "dilithium_pub" : base64.b64encode(self.dilithium_pub).decode(),
            "encrypted_priv": enc,
        }
        path.write_text(json.dumps(wallet_json, indent=2))
        print(f"[WALLET] Saved → {path}")
        return path

    # ── load from disk ─────────────────────────
    @classmethod
    def load(cls, path, passphrase: str) -> "Wallet":
        """Load and decrypt a wallet from a JSON file."""
        data = json.loads(Path(path).read_text())
        priv_bundle = json.loads(
            _decrypt_keys(data["encrypted_priv"], passphrase)
        )
        return cls(
            name            = data["name"],
            kyber_pub       = base64.b64decode(data["kyber_pub"]),
            kyber_priv      = base64.b64decode(priv_bundle["kyber_priv"]),
            dilithium_pub   = base64.b64decode(data["dilithium_pub"]),
            dilithium_priv  = base64.b64decode(priv_bundle["dilithium_priv"]),
            balance         = data.get("balance", 0.0),
            created_at      = data.get("created_at"),
        )

    # ── balance helpers ────────────────────────
    def credit(self, amount: float) -> None:
        self.balance = round(self.balance + amount, 8)

    def debit(self, amount: float) -> None:
        if amount > self.balance:
            raise ValueError(f"Insufficient balance: have {self.balance}, need {amount}")
        self.balance = round(self.balance - amount, 8)

    def can_afford(self, amount: float, fee: float = 0.0) -> bool:
        return self.balance >= (amount + fee)

    # ── display ────────────────────────────────
    def info(self) -> dict:
        return {
            "name"             : self.name,
            "address"          : self.address,
            "balance"          : self.balance,
            "kyber_pub_hex"    : self.kyber_pub.hex()[:32] + "...",
            "dilithium_pub_hex": self.dilithium_pub.hex()[:32] + "...",
            "kyber_pub_size"   : len(self.kyber_pub),
            "dil_pub_size"     : len(self.dilithium_pub),
            "created_at"       : self.created_at,
        }

    def __repr__(self) -> str:
        return f"Wallet(name={self.name!r}, addr={self.address[:12]}…, balance={self.balance})"


# ══════════════════════════════════════════════
#  WalletRegistry  (in-memory, for multi-node demo)
# ══════════════════════════════════════════════

class WalletRegistry:
    """
    Central registry mapping address → Wallet.
    In a real distributed system each node would manage its own wallets.
    For the prototype we keep a shared registry for simplicity.
    """

    def __init__(self):
        self._wallets: dict[str, Wallet] = {}   # address → Wallet
        self._by_name: dict[str, Wallet] = {}   # name → Wallet
        self.wallets: dict[str, Wallet] = {}    # Alias for compatibility

    def register(self, wallet: Wallet) -> None:
        self._wallets[wallet.address]   = wallet
        self._by_name[wallet.name]      = wallet
        self.wallets[wallet.name]       = wallet  # Keep wallets dict in sync

    def get_by_address(self, address: str) -> Wallet | None:
        return self._wallets.get(address)

    def get_by_name(self, name: str) -> Wallet | None:
        return self._by_name.get(name)

    def all_wallets(self) -> list:
        return list(self._wallets.values())

    def update_balances_from_block(self, block) -> None:
        """
        Scan confirmed block transactions and update sender/receiver balances.
        Called after a block is committed to the ledger.
        """
        for tx in block.transactions:
            sender   = self.get_by_name(tx.sender_id)
            receiver = self.get_by_name(tx.receiver_id)
            if sender:
                try:   sender.debit(tx.amount + tx.fee)
                except ValueError: pass   # already debited or insufficient
            if receiver:
                receiver.credit(tx.amount)

    def print_balances(self) -> None:
        print("\n  WALLET BALANCES")
        print("  " + "─" * 40)
        for w in self._wallets.values():
            print(f"  {w.name:<15} {w.address[:12]}…  balance={w.balance:.4f}")


# ══════════════════════════════════════════════
#  Helper function to create default wallets
# ══════════════════════════════════════════════

def create_default_wallets(initial_balances: dict = None) -> WalletRegistry:
    """
    Create a registry with default wallets (Alice, Bob, Validators).
    
    Parameters
    ----------
    initial_balances : dict, optional
        Map of wallet name → initial balance.
        Default: Alice=1000, Bob=500, Validators=0
    
    Returns
    -------
    WalletRegistry
        Registry with all default wallets registered.
    """
    if initial_balances is None:
        initial_balances = {
            "Alice": 1000,
            "Bob": 500,
            "Validator-1": 0,
            "Validator-2": 0,
            "Validator-3": 0,
        }
    
    registry = WalletRegistry()
    for name, balance in initial_balances.items():
        wallet = Wallet.create(name, initial_balance=balance)
        registry.register(wallet)
    
    return registry


# ══════════════════════════════════════════════
#  Self-test
# ══════════════════════════════════════════════

if __name__ == "__main__":
    import tempfile
    print("=" * 55)
    print("  wallet.py  —  Self-Test")
    print("=" * 55)

    print("\n[1] Creating wallet for Alice...")
    alice = Wallet.create("Alice", initial_balance=1000.0)
    print(f"    Address : {alice.address}")
    print(f"    Balance : {alice.balance}")
    print(f"    Kyber pub size    : {len(alice.kyber_pub)} B")
    print(f"    Dilithium pub size: {len(alice.dilithium_pub)} B")

    print("\n[2] Saving encrypted to temp file...")
    with tempfile.TemporaryDirectory() as tmp:
        path = alice.save("test_passphrase_123", Path(tmp))

        print("[3] Loading back from disk...")
        alice2 = Wallet.load(path, "test_passphrase_123")
        assert alice2.address        == alice.address
        assert alice2.kyber_pub      == alice.kyber_pub
        assert alice2.dilithium_pub  == alice.dilithium_pub
        assert alice2.kyber_priv     == alice.kyber_priv
        assert alice2.dilithium_priv == alice.dilithium_priv
        print(f"    Keys match: ✅")

        print("[4] Testing wrong passphrase...")
        try:
            Wallet.load(path, "wrong_passphrase")
            print("    ❌ Should have raised!")
        except Exception:
            print("    Wrong passphrase rejected: ✅")

    print("\n[5] Balance operations...")
    alice.debit(100.0)
    alice.credit(50.0)
    assert alice.balance == 950.0
    print(f"    Balance after debit 100 + credit 50 = {alice.balance}  ✅")

    print("\n✅  Wallet tests passed.")
    print("=" * 55)
