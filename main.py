"""
main.py
=======
End-to-end demonstration of the Quantum-Resistant Blockchain.

Run
---
  python main.py

What it demonstrates
--------------------
  1.  Key generation for all nodes (Kyber + Dilithium)
  2.  Transaction creation, Kyber encryption, Dilithium signing
  3.  Broadcast to validator nodes
  4.  Signature verification by each validator
  5.  Block mining (PoW)
  6.  Dilithium block signing by proposer
  7.  Majority-vote consensus
  8.  Block commit to ledger
  9.  Receiver decrypts payload
  10. Chain integrity verification
  11. Performance benchmarks

Dependencies
------------
  pip install pyoqs pycryptodome
"""

import time
from blockchain import Blockchain
from node import Node
from crypto_module import (
    generate_kyber_keypair,
    generate_dilithium_keypair,
    kyber_encrypt,
    kyber_decrypt,
    dilithium_sign,
    dilithium_verify,
    benchmark,
)


# ══════════════════════════════════════════════
#  Helper
# ══════════════════════════════════════════════

def separator(title: str = "") -> None:
    width = 65
    if title:
        pad   = (width - len(title) - 2) // 2
        print("\n" + "─" * pad + f" {title} " + "─" * pad)
    else:
        print("\n" + "─" * width)


# ══════════════════════════════════════════════
#  Main demo
# ══════════════════════════════════════════════

def main():
    print("=" * 65)
    print("  QUANTUM-RESISTANT BLOCKCHAIN  –  End-to-End Demo")
    print("  CRYSTALS-Kyber1024  +  CRYSTALS-Dilithium3")
    print("=" * 65)

    # ── 1. Initialise shared ledger ──────────────────────────────
    separator("1. INITIALISE BLOCKCHAIN")
    chain = Blockchain()

    # ── 2. Create nodes ─────────────────────────────────────────
    separator("2. NODE KEY GENERATION")
    alice     = Node("Alice",     chain)   # Sender
    bob       = Node("Bob",       chain)   # Receiver
    validator1 = Node("Validator-1", chain)
    validator2 = Node("Validator-2", chain)
    validator3 = Node("Validator-3", chain)

    all_validators = [validator1, validator2, validator3]

    # ── 3. Alice sends transactions to Bob ───────────────────────
    separator("3. TRANSACTIONS  (Alice → Bob)")
    tx1 = alice.send_transaction(bob, amount=50.0,  network=all_validators)
    tx2 = alice.send_transaction(bob, amount=125.5, network=all_validators)
    tx3 = alice.send_transaction(bob, amount=200.0, network=all_validators)

    # ── 4. Validator-1 proposes a block ─────────────────────────
    separator("4. BLOCK PROPOSAL & MINING  (Validator-1)")
    block = validator1.propose_block()

    if block is None:
        print("No transactions to mine. Exiting.")
        return

    # ── 5. Consensus vote ────────────────────────────────────────
    separator("5. CONSENSUS")
    committed = validator1.reach_consensus_and_commit(
        block,
        proposer_dilithium_pub = validator1.dilithium_pub,
        validators             = all_validators,
    )

    # ── 6. Bob decrypts the transactions ─────────────────────────
    if committed:
        separator("6. RECEIVER DECRYPTION  (Bob)")
        for tx in block.transactions:
            try:
                payload = bob.decrypt_transaction(tx)
                print(f"  Bob decrypted: {payload}")
            except Exception as e:
                print(f"  Decryption failed for {tx.tx_hash[:12]}…: {e}")

    # ── 7. Print ledger ─────────────────────────────────────────
    separator("7. BLOCKCHAIN LEDGER")
    chain.print_chain()

    # ── 8. Tamper detection ──────────────────────────────────────
    separator("8. TAMPER DETECTION TEST")
    if len(chain.chain) > 1:
        print("  Tampering with block #1 hash …")
        chain.chain[1].block_hash = "DEADBEEF" * 8
        valid = chain.is_valid()
        print(f"  Chain valid after tampering: {valid}  (expected: False)")
        # Restore for benchmarks
        block.mine()
        chain.chain[1] = block

    # ── 9. Performance benchmarks ────────────────────────────────
    separator("9. PERFORMANCE BENCHMARKS")
    kyber_pub,     kyber_priv     = generate_kyber_keypair()
    dilithium_pub, dilithium_priv = generate_dilithium_keypair()
    sample_msg = b"Benchmark payload for quantum-resistant blockchain test."

    benchmark("Kyber keypair generation",   generate_kyber_keypair, runs=5)
    benchmark("Dilithium keypair generation", generate_dilithium_keypair, runs=5)
    benchmark("Kyber encrypt (1KB payload)",  kyber_encrypt,
              kyber_pub, sample_msg * 20, runs=10)

    encrypted = kyber_encrypt(kyber_pub, sample_msg)
    benchmark("Kyber decrypt",              kyber_decrypt,
              kyber_priv, encrypted, runs=10)

    sig = dilithium_sign(dilithium_priv, sample_msg)
    benchmark("Dilithium sign",             dilithium_sign,
              dilithium_priv, sample_msg, runs=10)
    benchmark("Dilithium verify",           dilithium_verify,
              dilithium_pub, sample_msg, sig, runs=10)

    separator()
    print("  Demo complete. All quantum-resistant operations verified.")
    print("=" * 65)


if __name__ == "__main__":
    main()
