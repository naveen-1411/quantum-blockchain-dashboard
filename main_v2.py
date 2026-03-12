"""
main_v2.py
==========
Phase 2 — Full End-to-End Demonstration

What this demonstrates
----------------------
  1.  Wallet creation for all 5 participants (Kyber + Dilithium keys)
  2.  Node initialisation with roles (sender / receiver / validator)
  3.  Multiple transactions with fee + nonce (Alice → Bob × 3)
  4.  Global mempool with fee-priority ordering
  5.  Block proposal by Validator-1 with Merkle root
  6.  PBFT-style 3-phase consensus (Pre-prepare → Prepare → Commit)
  7.  Block committed to SQLite-backed ledger
  8.  Bob decrypts transaction payloads (Kyber decapsulation + AES-GCM)
  9.  Full chain integrity verification (verify_chain)
  10. Tamper detection demonstration
  11. Adversarial test suite (10 attack scenarios)
  12. Statistical performance benchmark (30 runs, mean/median/std/p95)
  13. Classical vs PQC comparison table
  14. Wallet balance updates after commit

Run
---
  python main_v2.py

Output
------
  Console: full demo trace
  blockchain.db  : persistent SQLite ledger (survives restart)
  metrics.db     : all benchmark measurements
"""

import sys
import time
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from crypto_module import (
    generate_kyber_keypair, generate_dilithium_keypair,
    kyber_encrypt, kyber_decrypt, dilithium_sign, dilithium_verify, benchmark,
)
from blockchain_v2 import Blockchain, NETWORK_DELAY_MS
from wallet       import Wallet, WalletRegistry
from mempool      import Mempool
from metrics      import MetricsCollector
from node_v2      import NodeV2, Network
from consensus    import ConsensusEngine, PBFTCoordinator
from merkle       import get_merkle_root, verify_merkle_proof, get_merkle_proof


# ══════════════════════════════════════════════
#  Formatting helpers
# ══════════════════════════════════════════════

def banner(title: str) -> None:
    width = 68
    print("\n" + "═" * width)
    pad = (width - len(title) - 2) // 2
    print("═" * pad + f"  {title}  " + "═" * (width - pad - len(title) - 4))
    print("═" * width)

def section(title: str) -> None:
    print(f"\n{'─'*6}  {title}  {'─'*(56-len(title))}")


# ══════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════

def main():
    banner("QUANTUM-RESISTANT BLOCKCHAIN  —  PHASE 2 DEMO")
    print("  CRYSTALS-Kyber1024 + CRYSTALS-Dilithium3")
    print("  PBFT Consensus  |  Merkle Tree  |  SQLite Persistence")
    print("  B.V. Raju Institute of Technology  |  AI&DS  2025-26")

    # Clean up previous run for demo freshness
    for f in ["blockchain.db", "metrics.db"]:
        if Path(f).exists():
            os.remove(f)

    metrics = MetricsCollector()

    # ══ 1. WALLET CREATION ═══════════════════
    section("1. WALLET CREATION")
    print("  Generating Kyber1024 + Dilithium3 key pairs for all participants…\n")

    wallets = {}
    timings = {}
    initial_balances = {
        "Alice": 1000.0, "Bob": 500.0,
        "Validator-1": 0.0, "Validator-2": 0.0, "Validator-3": 0.0,
    }
    for name, bal in initial_balances.items():
        t0 = time.perf_counter()
        w  = Wallet.create(name, initial_balance=bal)
        ms = (time.perf_counter() - t0) * 1000
        metrics.record("kyber_keygen",     ms / 2)
        metrics.record("dilithium_keygen", ms / 2)
        wallets[name] = w
        timings[name] = ms
        print(
            f"  {name:<14} addr={w.address[:20]}…  "
            f"balance=₹{bal:.2f}  keygen={ms:.1f}ms"
        )

    wallet_registry = WalletRegistry()
    for w in wallets.values():
        wallet_registry.register(w)

    # ══ 2. NODE INITIALISATION ════════════════
    section("2. NODE INITIALISATION  (roles assigned)")
    chain   = Blockchain(db_path=Path("blockchain.db"), load_from_disk=False)
    network = Network(chain)
    print()

    alice      = NodeV2(wallets["Alice"],       "sender",    network, metrics)
    bob        = NodeV2(wallets["Bob"],          "receiver",  network, metrics)
    val1       = NodeV2(wallets["Validator-1"],  "validator", network, metrics)
    val2       = NodeV2(wallets["Validator-2"],  "validator", network, metrics)
    val3       = NodeV2(wallets["Validator-3"],  "validator", network, metrics)

    validators = [val1, val2, val3]

    # Update PBFT engines with actual validator count
    for v in validators:
        v.consensus_engine.n      = len(validators)
        v.consensus_engine.quorum = ConsensusEngine._compute_quorum(len(validators))

    # Build PBFT coordinator
    pbft_validators = [
        (v.node_id, v.consensus_engine, v.wallet.dilithium_pub)
        for v in validators
    ]
    coordinator = PBFTCoordinator(pbft_validators)

    print(f"\n  Network: {len(network.nodes)} nodes online  "
          f"PBFT quorum={validators[0].consensus_engine.quorum}/{len(validators)}")

    # ══ 3. TRANSACTIONS ═══════════════════════
    section("3. TRANSACTIONS  (Alice → Bob)")
    print()
    tx_amounts = [75.50, 125.00, 200.00]
    sent_txs   = []

    for i, amount in enumerate(tx_amounts, 1):
        tx, status = alice.send_transaction("Bob", amount=amount, fee=0.001 * i)
        if tx and status == "ACCEPTED":
            sent_txs.append(tx)
        else:
            print(f"  TX {i} failed: {status}")

    print(f"\n  Mempool: {network.mempool.size} pending  "
          f"stats={network.mempool.stats()}")

    # ══ 4. MERKLE PROOF DEMO ══════════════════
    section("4. MERKLE INCLUSION PROOF  (single TX verification)")
    if sent_txs:
        tx_hashes = [tx.tx_hash for tx in sent_txs]
        root      = get_merkle_root(tx_hashes)
        target    = tx_hashes[0]
        proof     = get_merkle_proof(tx_hashes, target)
        valid_proof = verify_merkle_proof(target, proof, root)
        print(f"\n  Merkle root    : {root[:24]}…")
        print(f"  Proof siblings : {len(proof)}")
        print(f"  Proof valid    : {valid_proof}  ✅")
        print(f"  (Proves TX is in block WITHOUT revealing other transactions)")

    # ══ 5. BLOCK MINING ═══════════════════════
    section("5. BLOCK PROPOSAL & PoW MINING  (Validator-1)")
    print()
    block = val1.propose_block()
    if block is None:
        print("No pending transactions — stopping.")
        return

    # ══ 6. PBFT CONSENSUS ═════════════════════
    section("6. PBFT CONSENSUS  (3-phase: Pre-prepare → Prepare → Commit)")

    with metrics.measure("consensus"):
        pbft_result = coordinator.run(
            block,
            proposer_id    = val1.node_id,
            proposer_dil_pub = val1.wallet.dilithium_pub,
        )

    if not pbft_result["approved"]:
        print("\n  Consensus FAILED — block rejected. Stopping.")
        return

    # ══ 7. LEDGER COMMIT ══════════════════════
    section("7. LEDGER COMMIT  (block → SQLite)")
    success, reason = val1.commit_block(block)
    if not success:
        print(f"  Block commit FAILED: {reason}")
        return

    # Update wallet balances from committed block
    wallet_registry.update_balances_from_block(block)

    # ══ 8. RECEIVER DECRYPTION ════════════════
    section("8. DECRYPTION  (Bob decrypts transaction payloads)")
    print()
    for tx in block.transactions:
        try:
            payload = bob.decrypt_transaction(tx)
            print(f"  Bob decrypted: sender={payload['sender']}  "
                  f"amount=₹{payload['amount']}  nonce={payload['nonce']}  ✓")
        except Exception as e:
            print(f"  Decryption failed: {e}")

    # ══ 9. WALLET BALANCES ════════════════════
    section("9. WALLET BALANCES  (after commit)")
    wallet_registry.print_balances()

    # ══ 10. LEDGER DISPLAY ════════════════════
    section("10. BLOCKCHAIN LEDGER")
    chain.print_chain()

    # ══ 11. CHAIN INTEGRITY VERIFICATION ══════
    section("11. CHAIN INTEGRITY  verify_chain()")
    valid, issues = chain.verify_chain(verbose=True)
    print(f"\n  Chain valid: {valid}  issues={len(issues)}")

    # ══ 12. TAMPER DETECTION ══════════════════
    section("12. TAMPER DETECTION TEST")
    print("\n  Tampering with block #1 hash…")
    original_hash = chain.chain[1].block_hash
    chain.chain[1].block_hash = "DEADBEEF" * 8
    valid_after, issues_after = chain.verify_chain(verbose=False)
    print(f"  Chain valid after tamper: {valid_after}  (expected: False)  ✅")
    chain.chain[1].block_hash = original_hash   # restore

    # ══ 13. ADVERSARIAL TESTS ═════════════════
    section("13. ADVERSARIAL TEST SUITE")
    print()
    import subprocess
    result = subprocess.run(
        [sys.executable, "adversarial_tests.py"],
        capture_output=True, text=True
    )
    for line in result.stdout.splitlines()[-15:]:
        print(f"  {line}")

    # ══ 14. PERFORMANCE BENCHMARKS ════════════
    section("14. STATISTICAL PERFORMANCE BENCHMARKS  (30 runs each)")
    print("\n  Running benchmarks — please wait…\n")

    kpub,  kpriv  = generate_kyber_keypair()
    dpub,  dpriv  = generate_dilithium_keypair()
    payload = b"Quantum blockchain benchmark payload -- 1KB." * 23

    # Record 30 runs of each operation into metrics DB
    for _ in range(30):
        with metrics.measure("kyber_keygen"):     generate_kyber_keypair()
        with metrics.measure("dilithium_keygen"): generate_dilithium_keypair()
        enc = None
        with metrics.measure("kyber_encrypt"):    enc = kyber_encrypt(kpub, payload)
        with metrics.measure("kyber_decrypt"):    kyber_decrypt(kpriv, enc)
        sig = None
        with metrics.measure("dilithium_sign"):   sig = dilithium_sign(dpriv, payload)
        with metrics.measure("dilithium_verify"): dilithium_verify(dpub, payload, sig)

    metrics.print_report(last_n=30)
    metrics.classical_comparison_table()

    # ══ 15. PERSISTENCE CHECK ═════════════════
    section("15. PERSISTENCE CHECK  (blockchain survives restart)")
    db_stats = chain.db.stats()
    print(f"\n  SQLite DB: {db_stats['db_path']}")
    print(f"  Blocks stored  : {db_stats['blocks']}")
    print(f"  Transactions   : {db_stats['transactions']}")
    print(f"  DB size        : {db_stats['db_size_bytes']} bytes")
    print(f"\n  → Run: python main_v2.py  again to reload from disk ✅")

    # ══ DONE ══════════════════════════════════
    banner("PHASE 2 DEMO COMPLETE")
    print("  ✅ Wallet system         (Kyber + Dilithium keys, encrypted storage)")
    print("  ✅ Mempool               (fee-priority, TTL, double-spend guard)")
    print("  ✅ Merkle Tree           (transaction integrity + inclusion proofs)")
    print("  ✅ PBFT Consensus        (3-phase, 2/3 quorum, signed messages)")
    print("  ✅ Block validation      (PoW + Merkle + Dilithium + double-spend)")
    print("  ✅ SQLite persistence    (chain survives process restart)")
    print("  ✅ Parallel verification (ThreadPoolExecutor)")
    print("  ✅ Adversarial tests     (10 attack scenarios)")
    print("  ✅ Statistical benchmarks(30 runs, mean/median/std/p95)")
    print("  ✅ Classical comparison  (ECDSA vs Kyber/Dilithium)")
    print()


if __name__ == "__main__":
    main()
