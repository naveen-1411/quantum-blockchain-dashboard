"""
adversarial_tests.py
====================
Security test suite for the Quantum-Resistant Blockchain.

Each test simulates a specific attack and asserts the system rejects it.
Run all tests:
    python adversarial_tests.py

Tests
-----
  T1 — Replay Attack          Submit same signed TX twice
  T2 — Double-Spend           Same amount from same sender twice
  T3 — Invalid Signature      TX signed with wrong private key
  T4 — Block Tampering        Alter block hash after mining
  T5 — Merkle Tampering       Alter a transaction inside a mined block
  T6 — Wrong Proposer Key     Verify block with wrong Dilithium pub key
  T7 — Chain Fork Injection   Insert a forged block with mismatched prev_hash
  T8 — Expired Transaction    Submit TX with timestamp too far in the past
  T9 — Self-Transfer          Sender == Receiver
  T10 — Negative Amount       Negative transaction amount
"""

import sys
import time
import traceback
from pathlib import Path

# ── Path setup ───────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from crypto_module import (
    generate_kyber_keypair, generate_dilithium_keypair,
    kyber_encrypt, dilithium_sign, dilithium_verify,
)
from blockchain_v2 import Transaction, Block, Blockchain
from mempool import Mempool
from storage import BlockchainDB


# ══════════════════════════════════════════════
#  Test framework helpers
# ══════════════════════════════════════════════

PASS  = "✅  PASS"
FAIL  = "❌  FAIL"
results = []

def test(name: str, fn) -> bool:
    try:
        fn()
        print(f"  {PASS}  {name}")
        results.append((name, True, None))
        return True
    except AssertionError as e:
        print(f"  {FAIL}  {name}  →  {e}")
        results.append((name, False, str(e)))
        return False
    except Exception as e:
        print(f"  {FAIL}  {name}  →  UNEXPECTED: {e}")
        traceback.print_exc()
        results.append((name, False, str(e)))
        return False


# ══════════════════════════════════════════════
#  Shared fixtures  (generated once, reused)
# ══════════════════════════════════════════════

print("Setting up test fixtures…")
alice_kpub, alice_kpriv = generate_kyber_keypair()
alice_dpub, alice_dpriv = generate_dilithium_keypair()
bob_kpub,   bob_kpriv   = generate_kyber_keypair()
bob_dpub,   bob_dpriv   = generate_dilithium_keypair()
eve_dpub,   eve_dpriv   = generate_dilithium_keypair()   # attacker


def make_valid_tx(amount=50.0, nonce=1, age_seconds=0) -> Transaction:
    """Create a fully encrypted and signed transaction."""
    tx = Transaction(
        sender_id   = "Alice",
        receiver_id = "Bob",
        amount      = amount,
        fee         = 0.001,
        nonce       = nonce,
        timestamp   = time.time() - age_seconds,
    )
    tx.encrypt(bob_kpub)
    tx.sign(alice_dpriv)
    return tx


def make_valid_block(txs, prev_hash="0"*64, index=1) -> tuple:
    """Create a mined and signed block. Returns (block, proposer_pub, proposer_priv)."""
    vpub, vpriv = generate_dilithium_keypair()
    block = Block(
        index         = index,
        transactions  = txs,
        previous_hash = prev_hash,
        proposer_id   = "Validator-1",
    )
    block.mine()
    block.sign(vpriv)
    return block, vpub, vpriv


print("Fixtures ready.\n")


# ══════════════════════════════════════════════
#  T1 — Replay Attack
# ══════════════════════════════════════════════

def t1_replay_attack():
    """
    Submit the same signed transaction twice to the mempool.
    Second submission must be rejected as DUPLICATE_HASH.
    """
    pool = Mempool()
    tx   = make_valid_tx(nonce=1)

    ok1, r1 = pool.add(tx, fee=0.001)
    assert ok1, f"First submission should be accepted, got {r1}"

    ok2, r2 = pool.add(tx, fee=0.001)
    assert not ok2,            "Second submission should be rejected"
    assert r2 == "DUPLICATE_HASH", f"Expected DUPLICATE_HASH, got {r2}"


# ══════════════════════════════════════════════
#  T2 — Double-Spend (same nonce)
# ══════════════════════════════════════════════

def t2_double_spend():
    """
    Submit two different transactions with the same sender nonce.
    Mempool must reject the second one.
    """
    pool = Mempool()
    tx1  = make_valid_tx(amount=50.0,  nonce=5)
    tx2  = make_valid_tx(amount=999.0, nonce=5)   # same nonce — replay attempt

    ok1, _ = pool.add(tx1, fee=0.001)
    assert ok1, "First TX should be accepted"

    ok2, r2 = pool.add(tx2, fee=0.002)
    assert not ok2,              "Same-nonce TX should be rejected"
    assert r2 == "DUPLICATE_NONCE", f"Expected DUPLICATE_NONCE, got {r2}"


# ══════════════════════════════════════════════
#  T3 — Invalid Signature  (wrong signer)
# ══════════════════════════════════════════════

def t3_invalid_signature():
    """
    Eve signs Alice's transaction with her own (wrong) private key.
    Verification against Alice's public key must return False.
    """
    tx = Transaction(
        sender_id   = "Alice",
        receiver_id = "Bob",
        amount      = 100.0,
        fee         = 0.001,
        nonce       = 10,
    )
    tx.encrypt(bob_kpub)
    # Eve signs with her key, not Alice's
    tx.sign(eve_dpriv)

    # Verify against Alice's public key — must fail
    valid = tx.verify_signature(alice_dpub)
    assert not valid, "Invalid signature should be rejected"


# ══════════════════════════════════════════════
#  T4 — Block Hash Tampering
# ══════════════════════════════════════════════

def t4_block_hash_tamper():
    """
    After a block is mined, overwrite its hash with a forged value.
    Blockchain.verify_chain() must detect the tampering.
    """
    import tempfile, os
    tx    = make_valid_tx(nonce=20)

    # Build a fresh blockchain FIRST so we have the real genesis hash
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    try:
        chain = Blockchain(db_path=db_path, load_from_disk=False)
        # Mine block using real genesis hash as prev_hash
        block, vpub, _ = make_valid_block([tx], prev_hash=chain.last_block.block_hash)
        success, reason = chain.add_block(block, vpub)
        assert success, f"Block should be added: {reason}"

        # Tamper with the hash
        chain.chain[1].block_hash = "DEADBEEF" * 8

        valid, issues = chain.verify_chain(verbose=False)
        assert not valid, "Tampered chain should fail verify_chain()"
        assert any("PoW" in i or "mismatch" in i for i in issues), \
            f"Expected PoW/hash issue, got: {issues}"
    finally:
        chain.db.close()
        os.unlink(db_path)


# ══════════════════════════════════════════════
#  T5 — Merkle Root Tampering
# ══════════════════════════════════════════════

def t5_merkle_tamper():
    """
    After mining, alter a transaction hash inside the block.
    Block.verify_merkle_root() must detect the inconsistency.
    """
    tx      = make_valid_tx(nonce=30)
    block, vpub, _ = make_valid_block([tx])

    # Tamper: change a tx hash inside the block
    block.transactions[0].tx_hash = "00" * 32   # forged hash

    valid = block.verify_merkle_root()
    assert not valid, "Merkle root check should fail after tx tampering"


# ══════════════════════════════════════════════
#  T6 — Wrong Proposer Public Key
# ══════════════════════════════════════════════

def t6_wrong_proposer_key():
    """
    Verify a valid block against Eve's public key (not the real proposer's).
    verify_proposer_sig() must return False.
    """
    tx      = make_valid_tx(nonce=40)
    block, vpub, _ = make_valid_block([tx])

    # Verify with wrong key (Eve's)
    valid = block.verify_proposer_sig(eve_dpub)
    assert not valid, "Block verification with wrong key must fail"


# ══════════════════════════════════════════════
#  T7 — Chain Fork Injection
# ══════════════════════════════════════════════

def t7_chain_fork_injection():
    """
    Try to inject a forged block whose previous_hash doesn't match
    the current chain tip. add_block() must reject it.
    """
    import tempfile, os
    tx      = make_valid_tx(nonce=50)
    block, vpub, _ = make_valid_block([tx], prev_hash="FORGED" + "0"*58)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    try:
        chain = Blockchain(db_path=db_path, load_from_disk=False)
        success, reason = chain.add_block(block, vpub)
        assert not success, "Forged prev_hash block must be rejected"
        assert "hash" in reason.lower(), f"Expected hash mismatch reason, got: {reason}"
    finally:
        chain.db.close()
        os.unlink(db_path)


# ══════════════════════════════════════════════
#  T8 — Expired Transaction
# ══════════════════════════════════════════════

def t8_expired_transaction():
    """
    Submit a transaction with a timestamp older than TX_TTL_SECONDS.
    Mempool must reject it as EXPIRED.
    """
    from mempool import TX_TTL_SECONDS
    pool = Mempool()
    old_tx = make_valid_tx(nonce=60, age_seconds=TX_TTL_SECONDS + 10)

    ok, reason = pool.add(old_tx, fee=0.001)
    assert not ok,           "Expired TX must be rejected"
    assert reason == "EXPIRED", f"Expected EXPIRED, got {reason}"


# ══════════════════════════════════════════════
#  T9 — Self-Transfer
# ══════════════════════════════════════════════

def t9_self_transfer():
    """
    Sender == Receiver is economically meaningless.
    Mempool must reject it as SELF_TRANSFER.
    """
    pool = Mempool()
    tx   = Transaction(
        sender_id   = "Alice",
        receiver_id = "Alice",   # self-transfer
        amount      = 10.0,
        fee         = 0.001,
        nonce       = 70,
    )
    tx.encrypted_payload = {"kem_ciphertext":b"x","aes_nonce":b"x","aes_tag":b"x","aes_ciphertext":b"x"}
    tx.signature = b"fake"
    tx.tx_hash   = "selfhash_" + "0" * 55

    ok, reason = pool.add(tx)
    assert not ok,                "Self-transfer must be rejected"
    assert reason == "SELF_TRANSFER", f"Expected SELF_TRANSFER, got {reason}"


# ══════════════════════════════════════════════
#  T10 — Negative Amount
# ══════════════════════════════════════════════

def t10_negative_amount():
    """
    A transaction with amount <= 0 must be rejected by the mempool.
    """
    pool = Mempool()
    tx   = Transaction(
        sender_id   = "Alice",
        receiver_id = "Bob",
        amount      = -100.0,   # negative
        fee         = 0.001,
        nonce       = 80,
    )
    tx.encrypted_payload = {"kem_ciphertext":b"x","aes_nonce":b"x","aes_tag":b"x","aes_ciphertext":b"x"}
    tx.signature = b"fake"
    tx.tx_hash   = "neghash_" + "0" * 56

    ok, reason = pool.add(tx)
    assert not ok,                 "Negative amount must be rejected"
    assert reason == "INVALID_AMOUNT", f"Expected INVALID_AMOUNT, got {reason}"


# ══════════════════════════════════════════════
#  Run all tests
# ══════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  ADVERSARIAL TEST SUITE")
    print("  Quantum-Resistant Blockchain — Phase 2")
    print("=" * 60 + "\n")

    test("T1  Replay Attack",          t1_replay_attack)
    test("T2  Double-Spend (nonce)",   t2_double_spend)
    test("T3  Invalid Signature",      t3_invalid_signature)
    test("T4  Block Hash Tampering",   t4_block_hash_tamper)
    test("T5  Merkle Root Tampering",  t5_merkle_tamper)
    test("T6  Wrong Proposer Key",     t6_wrong_proposer_key)
    test("T7  Chain Fork Injection",   t7_chain_fork_injection)
    test("T8  Expired Transaction",    t8_expired_transaction)
    test("T9  Self-Transfer",          t9_self_transfer)
    test("T10 Negative Amount",        t10_negative_amount)

    # Summary
    passed = sum(1 for _, ok, _ in results if ok)
    total  = len(results)
    print("\n" + "=" * 60)
    print(f"  RESULTS: {passed}/{total} tests passed")
    if passed == total:
        print("  ✅ All adversarial attacks correctly rejected.")
    else:
        print("  ❌ Some tests failed — review above.")
        for name, ok, err in results:
            if not ok:
                print(f"     FAIL: {name}  →  {err}")
    print("=" * 60)

    sys.exit(0 if passed == total else 1)
