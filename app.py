"""
app.py  —  Flask API Server
============================
Connects the quantum-resistant blockchain Python code to the web UI.

Run:
    python app.py

Then open:
    http://localhost:5000

Endpoints
---------
POST /api/init            Initialize blockchain + generate keys for all nodes
POST /api/transaction     Create, encrypt, sign & validate a transaction
POST /api/mine            Validator-1 mines a block (PoW)
POST /api/consensus       Run majority-vote consensus
POST /api/commit          Commit approved block to ledger
GET  /api/state           Return full current state as JSON
POST /api/reset           Wipe all state (fresh start)
GET  /                    Serve index.html
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))   # find sibling modules

import json
import time
import threading

from flask import Flask, jsonify, request, send_from_directory
from flask import Response

# ── import our blockchain modules ────────────────────────────
from crypto_module import (
    generate_kyber_keypair, generate_dilithium_keypair,
    kyber_encrypt, kyber_decrypt,
    dilithium_sign, dilithium_verify,
    sha256_hash,
    KYBER_PUB_SIZE, KYBER_CT_SIZE,
    DILITHIUM_PUB_SIZE, DILITHIUM_SIG_SIZE,
)
from blockchain import Blockchain, Transaction, Block
from node import Node

app = Flask(__name__, static_folder=".")

# ════════════════════════════════════════════════════════════
#  Global state  (single-user demo — not thread-safe for prod)
# ════════════════════════════════════════════════════════════

STATE = {
    "blockchain"    : None,
    "nodes"         : {},      # name -> Node
    "pending_block" : None,
    "consensus_ok"  : False,
    "tx_count"      : 0,
    "initialized"   : False,
}

NODE_NAMES = ["Alice", "Bob", "Validator-1", "Validator-2", "Validator-3"]


# ════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════

def ok(data=None, **kw):
    payload = {"status": "ok"}
    if data:    payload.update(data)
    if kw:      payload.update(kw)
    return jsonify(payload)

def err(msg, code=400):
    return jsonify({"status": "error", "message": msg}), code

def ms(t0):
    return round((time.perf_counter() - t0) * 1000, 1)

def serialize_block(b: Block) -> dict:
    return {
        "index"       : b.index,
        "hash"        : b.block_hash,
        "prev_hash"   : b.previous_hash,
        "nonce"       : b.nonce,
        "proposer"    : b.proposer_id,
        "tx_count"    : len(b.transactions),
        "timestamp"   : round(b.timestamp, 2),
        "transactions": [serialize_tx(tx) for tx in b.transactions],
    }

def serialize_tx(tx: Transaction) -> dict:
    return {
        "hash"     : tx.tx_hash,
        "sender"   : tx.sender_id,
        "receiver" : tx.receiver_id,
        "amount"   : tx.amount,
        "timestamp": round(tx.timestamp, 2),
        "signed"   : tx.signature is not None,
        "encrypted": tx.encrypted_payload is not None,
        "kem_ct_size": KYBER_CT_SIZE,
        "sig_size"   : DILITHIUM_SIG_SIZE,
    }

def serialize_node(name: str, node: Node) -> dict:
    return {
        "name"           : name,
        "role"           : "Sender" if name=="Alice" else
                           "Receiver" if name=="Bob" else "Validator",
        "kyber_pub_size" : KYBER_PUB_SIZE,
        "dil_pub_size"   : DILITHIUM_PUB_SIZE,
        "kyber_pub_hex"  : node.kyber_pub.hex()[:32] + "...",
        "dil_pub_hex"    : node.dilithium_pub.hex()[:32] + "...",
        "mempool_count"  : len(node.mempool),
    }


# ════════════════════════════════════════════════════════════
#  Routes
# ════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# ── POST /api/init ───────────────────────────────────────────
@app.route("/api/init", methods=["POST"])
def init_network():
    """
    Create a fresh blockchain and generate Kyber + Dilithium
    key pairs for every node. Returns per-node timing.
    """
    chain = Blockchain()
    nodes = {}
    timings = {}

    for name in NODE_NAMES:
        t0 = time.perf_counter()
        node = Node(name, chain)
        timings[name] = ms(t0)
        nodes[name] = node

    STATE["blockchain"]  = chain
    STATE["nodes"]       = nodes
    STATE["pending_block"] = None
    STATE["consensus_ok"]  = False
    STATE["tx_count"]      = 0
    STATE["initialized"]   = True

    return ok(
        message="Network initialized — 5 nodes online",
        timings=timings,
        nodes={n: serialize_node(n, nd) for n, nd in nodes.items()},
        chain=[serialize_block(b) for b in chain.chain],
    )


# ── POST /api/transaction ────────────────────────────────────
@app.route("/api/transaction", methods=["POST"])
def send_transaction():
    """
    Body: { "amount": 50.0 }
    Alice encrypts (Kyber) and signs (Dilithium) a TX to Bob.
    All validators verify the signature.
    Returns TX details + per-validator verify latency.
    """
    if not STATE["initialized"]:
        return err("Network not initialized. Call /api/init first.")

    body   = request.get_json(force=True) or {}
    amount = float(body.get("amount", 100.0))
    nodes  = STATE["nodes"]
    alice  = nodes["Alice"]
    bob    = nodes["Bob"]
    validators = [nodes[n] for n in ["Validator-1","Validator-2","Validator-3"]]

    # Create TX
    tx = Transaction(sender_id="Alice", receiver_id="Bob", amount=amount)

    # Step 1: Kyber encrypt
    t0 = time.perf_counter()
    tx.encrypt(bob.kyber_pub)
    enc_ms = ms(t0)

    # Step 2: Dilithium sign
    t0 = time.perf_counter()
    tx.sign(alice.dilithium_priv)
    sign_ms = ms(t0)

    # Step 3: Validators verify
    verify_results = {}
    for v in validators:
        t0 = time.perf_counter()
        valid = v.receive_transaction(tx, alice.dilithium_pub)
        verify_results[v.node_id] = {"valid": valid, "latency_ms": ms(t0)}

    STATE["tx_count"] += 1

    return ok(
        transaction=serialize_tx(tx),
        enc_ms=enc_ms,
        sign_ms=sign_ms,
        verify_results=verify_results,
        mempool_size=len(validators[0].mempool),
    )


# ── POST /api/mine ───────────────────────────────────────────
@app.route("/api/mine", methods=["POST"])
def mine_block():
    """
    Validator-1 collects mempool TXs, runs PoW, and signs the block.
    Returns block details + mining latency.
    """
    if not STATE["initialized"]:
        return err("Network not initialized.")

    v1 = STATE["nodes"]["Validator-1"]
    if not v1.mempool:
        return err("Mempool is empty. Send at least one transaction first.")

    t0    = time.perf_counter()
    block = v1.propose_block()
    mine_ms = ms(t0)

    if block is None:
        return err("Mining failed — no transactions in mempool.")

    STATE["pending_block"] = block
    STATE["consensus_ok"]  = False

    return ok(
        block=serialize_block(block),
        mine_ms=mine_ms,
    )


# ── POST /api/consensus ──────────────────────────────────────
@app.route("/api/consensus", methods=["POST"])
def run_consensus():
    """
    Each validator verifies the pending block's Dilithium signature.
    Returns per-validator vote + overall result.
    """
    if not STATE["initialized"]:
        return err("Network not initialized.")
    if STATE["pending_block"] is None:
        return err("No pending block. Mine a block first.")

    block      = STATE["pending_block"]
    nodes      = STATE["nodes"]
    validators = [nodes[n] for n in ["Validator-1","Validator-2","Validator-3"]]
    v1         = nodes["Validator-1"]

    votes = {}
    for v in validators:
        t0    = time.perf_counter()
        valid = block.verify_proposer_sig(v1.dilithium_pub)
        votes[v.node_id] = {"vote": "YES" if valid else "NO", "latency_ms": ms(t0)}

    yes_count = sum(1 for r in votes.values() if r["vote"] == "YES")
    ratio     = yes_count / len(validators)
    approved  = ratio >= 0.67

    STATE["consensus_ok"] = approved

    return ok(
        votes=votes,
        yes_count=yes_count,
        total=len(validators),
        ratio=round(ratio * 100, 1),
        approved=approved,
    )


# ── POST /api/commit ─────────────────────────────────────────
@app.route("/api/commit", methods=["POST"])
def commit_block():
    """
    Append the consensus-approved block to the ledger.
    Bob decrypts all transaction payloads to confirm receipt.
    Returns updated chain + decrypted payloads.
    """
    if not STATE["initialized"]:
        return err("Network not initialized.")
    if STATE["pending_block"] is None:
        return err("No pending block.")
    if not STATE["consensus_ok"]:
        return err("Consensus not reached. Run /api/consensus first.")

    block = STATE["pending_block"]
    chain = STATE["blockchain"]
    nodes = STATE["nodes"]
    v1    = nodes["Validator-1"]
    bob   = nodes["Bob"]

    success = chain.add_block(block, v1.dilithium_pub)
    if not success:
        return err("Block rejected by ledger validation.")

    # Clear mempools
    committed = {tx.tx_hash for tx in block.transactions}
    for n in nodes.values():
        n.mempool = [t for t in n.mempool if t.tx_hash not in committed]

    # Bob decrypts each TX
    decrypted = []
    for tx in block.transactions:
        try:
            payload = bob.decrypt_transaction(tx)
            decrypted.append({"hash": tx.tx_hash, "payload": json.loads(payload), "ok": True})
        except Exception as e:
            decrypted.append({"hash": tx.tx_hash, "error": str(e), "ok": False})

    STATE["pending_block"] = None
    STATE["consensus_ok"]  = False

    return ok(
        block=serialize_block(block),
        decrypted=decrypted,
        chain=[serialize_block(b) for b in chain.chain],
        chain_length=len(chain.chain),
    )


# ── GET /api/state ───────────────────────────────────────────
@app.route("/api/state", methods=["GET"])
def get_state():
    """Return full current state as JSON."""
    if not STATE["initialized"]:
        return ok(initialized=False)

    nodes = STATE["nodes"]
    chain = STATE["blockchain"]

    return ok(
        initialized=True,
        chain=[serialize_block(b) for b in chain.chain],
        chain_valid=chain.is_valid(),
        nodes={n: serialize_node(n, nd) for n, nd in nodes.items()},
        mempool_size=len(nodes["Validator-1"].mempool),
        pending_block=serialize_block(STATE["pending_block"])
                      if STATE["pending_block"] else None,
        consensus_ok=STATE["consensus_ok"],
        tx_count=STATE["tx_count"],
    )


# ── POST /api/reset ──────────────────────────────────────────
@app.route("/api/reset", methods=["POST"])
def reset():
    """Wipe all state for a fresh demo."""
    STATE["blockchain"]    = None
    STATE["nodes"]         = {}
    STATE["pending_block"] = None
    STATE["consensus_ok"]  = False
    STATE["tx_count"]      = 0
    STATE["initialized"]   = False
    return ok(message="State reset. Call /api/init to restart.")


# ════════════════════════════════════════════════════════════
#  Entry point
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("  Quantum-Resistant Blockchain — Web UI")
    print("  Open http://localhost:5000 in your browser")
    print("=" * 55)
    app.run(debug=False, port=5000, threaded=False)