# Quantum-Resistant Blockchain
### CRYSTALS-Kyber1024 + CRYSTALS-Dilithium3

**B.V. Raju Institute of Technology — AI&DS Department**  
Major Project Phase-1 | 2025-26

---

## Project Overview

A modular, quantum-resistant blockchain framework that replaces classical ECDSA/RSA cryptography with NIST-selected post-quantum algorithms:

| Component | Algorithm | Purpose |
|-----------|-----------|---------|
| Key Exchange | CRYSTALS-Kyber1024 | Secure key encapsulation + AES-GCM payload encryption |
| Digital Signatures | CRYSTALS-Dilithium3 | Transaction authentication + block signing |
| Hashing | SHA-256 | Block chaining + integrity |
| Consensus | Majority Vote (≥67%) | Distributed block approval |

---

## File Structure

```
quantum_blockchain/
├── crypto_module.py    # Kyber + Dilithium operations, AES-GCM, SHA-256
├── blockchain.py       # Transaction, Block, Blockchain classes
├── node.py             # Node simulation (sender / receiver / validator)
├── main.py             # End-to-end demo + benchmarks
└── requirements.txt    # Python dependencies
```

---

## Setup & Installation

### Prerequisites

**Step 1: Install liboqs (C library)**
```bash
# Ubuntu / Debian
sudo apt-get install liboqs-dev

# macOS
brew install liboqs

# Windows — download from: https://github.com/open-quantum-safe/liboqs
```

**Step 2: Install Python dependencies**
```bash
pip install -r requirements.txt
```

---

## Running the Demo

```bash
python main.py
```

### Expected Output Flow

```
=================================================================
  QUANTUM-RESISTANT BLOCKCHAIN  –  End-to-End Demo
  CRYSTALS-Kyber1024  +  CRYSTALS-Dilithium3
=================================================================

──── 1. INITIALISE BLOCKCHAIN ────
[CHAIN] Genesis block created.

──── 2. NODE KEY GENERATION ────
[NODE]  Generating PQ keys for 'Alice' … done (12.3 ms)
[NODE]  Generating PQ keys for 'Bob' … done (11.8 ms)
...

──── 3. TRANSACTIONS (Alice → Bob) ────
[TX]    Alice → Bob  amount=50.0  enc=8.2ms  sign=3.1ms  hash=a3f1c8d2e9b7…
[VAL]   Validator-1: TX a3f1c8d2e9b7… signature ✓  verify=2.4ms
...

──── 4. BLOCK PROPOSAL & MINING ────
[PROP]  Validator-1: Mining block #1 (3 txs)… done  nonce=142  hash=0031ab…

──── 5. CONSENSUS ────
[CON]   Consensus vote for Block #1:
         Validator-1: YES
         Validator-2: YES
         Validator-3: YES
[CON]   Result: 3/3 (100%) → APPROVED ✓

──── 6. RECEIVER DECRYPTION ────
  Bob decrypted: {'sender': 'Alice', 'receiver': 'Bob', 'amount': 50.0, ...}
...

──── 9. PERFORMANCE BENCHMARKS ────
[BENCH] Kyber keypair generation             avg =  11.23 ms
[BENCH] Dilithium keypair generation         avg =   9.47 ms
[BENCH] Kyber encrypt (1KB payload)          avg =   8.15 ms
[BENCH] Kyber decrypt                        avg =   7.92 ms
[BENCH] Dilithium sign                       avg =   3.14 ms
[BENCH] Dilithium verify                     avg =   2.83 ms
```

---

## System Architecture

```
Application Layer
    └── User Transactions

Consensus Layer
    ├── Kyber Key Encapsulation  →  Transaction Encryption
    ├── Dilithium Signing        →  Authentication + Non-repudiation
    ├── Block Formation          →  PoW Mining (difficulty=2)
    └── Majority Vote Consensus  →  Block Approval (≥67%)

Storage Layer
    └── Blockchain Ledger (SHA-256 chained blocks)
```

---

## Security Properties

| Attack | Classical Defense | Our PQ Defense |
|--------|-----------------|---------------|
| Private key recovery | RSA/ECDSA (broken by Shor's) | Kyber lattice hardness |
| Signature forgery | ECDSA (broken by Shor's) | Dilithium lattice hardness |
| Brute-force | SHA-256 (weakened by Grover's) | SHA-256 + PoW (still viable) |
| Man-in-the-middle | DH/RSA key exchange | Kyber KEM |

---

## Team

| Name | Roll No |
|------|---------|
| Ch Nitheesh Kumar | 22211A7216 |
| P Revanth Kumar | 22211A7263 |
| P Naveen | 23215A7203 |

**Guide:** Dr. M. Amarendhar Reddy, Assistant Professor, AI&DS  
**Institution:** B.V. Raju Institute of Technology, Narsapur
