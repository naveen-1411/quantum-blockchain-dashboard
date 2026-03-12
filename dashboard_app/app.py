"""
Blockchain Dashboard — Flask Web Application
=============================================

A professional web interface for the Quantum-Resistant Blockchain system.

Connects to the blockchain backend via:
  1. SQLite database (blockchain.db, metrics.db)
  2. In-memory objects (if running with main_v2.py in same process)

Endpoints
---------
  GET  /                         → Dashboard HTML
  GET  /api/blocks               → All blocks
  GET  /api/blocks/<index>       → Single block with transactions
  GET  /api/transactions         → All confirmed transactions
  GET  /api/mempool              → Pending transactions
  GET  /api/wallets              → Wallet info
  GET  /api/nodes                → Network nodes
  GET  /api/metrics              → Performance metrics
  GET  /api/chain_stats          → Chain statistics
  POST /api/create_transaction   → Add pending transaction
  GET  /api/verify_chain         → Verify blockchain integrity
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

from flask import Flask, render_template, jsonify, request
import traceback

# Add parent directory to path to import blockchain modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from blockchain_v2 import Blockchain, Transaction, Block
from wallet import Wallet, WalletRegistry
from mempool import Mempool
from metrics import MetricsCollector
from node_v2 import NodeV2, Network
from consensus import ConsensusEngine
from storage import BlockchainDB
from crypto_module import (
    generate_kyber_keypair, generate_dilithium_keypair,
    dilithium_sign, dilithium_verify
)

# ══════════════════════════════════════════════
#  Flask App Setup
# ══════════════════════════════════════════════

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
app.config['JSON_SORT_KEYS'] = False

# Global objects (can be set by main_v2.py or loaded from database)
blockchain: Optional[Blockchain] = None
network: Optional[Network] = None
wallets: Dict[str, Wallet] = {}
metrics_collector: Optional[MetricsCollector] = None
wallet_registry: Optional[WalletRegistry] = None

# Track state for consensus visualization
consensus_state = {
    "current_block": None,
    "phase": "IDLE",  # PRE-PREPARE, PREPARE, COMMIT, IDLE
    "validators_status": {}
}

# Default wallet balances for in-memory tracking
default_wallets_data = {
    "Alice": {"balance": 1000.0},
    "Bob": {"balance": 500.0},
    "Validator-1": {"balance": 0.0},
    "Validator-2": {"balance": 0.0},
    "Validator-3": {"balance": 0.0},
}


# ══════════════════════════════════════════════
#  Initialization Functions
# ══════════════════════════════════════════════

def initialize_from_database():
    """Load blockchain from SQLite database."""
    global blockchain, metrics_collector, wallets
    
    if not Path("blockchain.db").exists():
        print("[DASHBOARD] blockchain.db not found — creating new chain")
    
    blockchain = Blockchain(db_path=Path("blockchain.db"), load_from_disk=True)
    metrics_collector = MetricsCollector()
    
    # Initialize wallets if not already set by main_v2
    if not wallets:
        wallets = init_wallets()
    
    print(f"[DASHBOARD] Blockchain loaded: {blockchain}")
    print(f"[DASHBOARD] Wallets initialized: {list(wallets.keys())}")


def init_wallets() -> Dict[str, Dict[str, float]]:
    """Initialize wallet balances from default data."""
    return default_wallets_data.copy()


def apply_transaction(sender: str, receiver: str, amount: float, fee: float = 0.0):
    """
    Apply a transaction by updating sender and receiver balances.
    Distribute fees to validators.
    
    Parameters
    ----------
    sender : str
        Name of sending wallet
    receiver : str
        Name of receiving wallet
    amount : float
        Transaction amount
    fee : float
        Transaction fee (distributed to validators)
    """
    global wallets
    
    if not wallets:
        wallets = init_wallets()
    
    # Debit sender
    if sender not in wallets:
        raise ValueError(f"Sender wallet '{sender}' not found")
    wallets[sender]["balance"] -= (amount + fee)
    
    # Credit receiver
    if receiver not in wallets:
        raise ValueError(f"Receiver wallet '{receiver}' not found")
    wallets[receiver]["balance"] += amount
    
    # Distribute fee equally to validators
    validators = ["Validator-1", "Validator-2", "Validator-3"]
    fee_per_validator = fee / len(validators)
    
    for validator in validators:
        if validator in wallets:
            wallets[validator]["balance"] += fee_per_validator
    
    print(f"[TRANSACTION] {sender} → {receiver}: ₹{amount} (fee: ₹{fee})")
    print(f"[BALANCES] {sender}={wallets[sender]['balance']:.2f}, {receiver}={wallets[receiver]['balance']:.2f}")


def set_shared_objects(bc, net, wlt, metric, reg):
    """
    Called by main_v2.py to share live objects.
    
    Usage from main_v2.py:
        from dashboard_app.app import set_shared_objects
        set_shared_objects(chain, network, wallets, metrics, wallet_registry)
    """
    global blockchain, network, wallets, metrics_collector, wallet_registry
    blockchain = bc
    network = net
    wallets = wlt
    metrics_collector = metric
    wallet_registry = reg
    print("[DASHBOARD] Shared objects set from main_v2")


# ══════════════════════════════════════════════
#  Routes — Dashboard
# ══════════════════════════════════════════════

@app.route('/')
def index():
    """Serve the main dashboard HTML."""
    if blockchain is None:
        initialize_from_database()
    return render_template('dashboard.html')


# ══════════════════════════════════════════════
#  API Routes — Blockchain Data
# ══════════════════════════════════════════════

@app.route('/api/blocks', methods=['GET'])
def get_blocks():
    """Get all blocks in the blockchain."""
    try:
        if blockchain is None:
            initialize_from_database()
        
        blocks = []
        for block in blockchain.chain:
            blocks.append({
                'index': block.index,
                'hash': block.block_hash,
                'previous_hash': block.previous_hash,
                'merkle_root': block.merkle_root,
                'proposer': block.proposer_id,
                'nonce': block.nonce,
                'difficulty': block.difficulty,
                'version': block.version,
                'timestamp': block.timestamp,
                'tx_count': len(block.transactions),
                'timestamp_str': datetime.fromtimestamp(block.timestamp).strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return jsonify({
            'success': True,
            'total_blocks': len(blocks),
            'chain_height': blockchain.height,
            'blocks': blocks
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/blocks/<int:block_index>', methods=['GET'])
def get_block_detail(block_index: int):
    """Get detailed view of a single block with all transactions."""
    try:
        if blockchain is None:
            initialize_from_database()
        
        if block_index < 0 or block_index >= len(blockchain.chain):
            return jsonify({'success': False, 'error': 'Block not found'}), 404
        
        block = blockchain.chain[block_index]
        
        transactions = []
        for tx in block.transactions:
            transactions.append({
                'hash': tx.tx_hash,
                'sender': tx.sender_id,
                'receiver': tx.receiver_id,
                'amount': tx.amount,
                'fee': tx.fee,
                'nonce': tx.nonce,
                'timestamp': tx.timestamp,
                'timestamp_str': datetime.fromtimestamp(tx.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                'signed': tx.signature is not None,
                'encrypted': tx.encrypted_payload is not None
            })
        
        return jsonify({
            'success': True,
            'block': {
                'index': block.index,
                'hash': block.block_hash,
                'previous_hash': block.previous_hash,
                'merkle_root': block.merkle_root,
                'proposer': block.proposer_id,
                'nonce': block.nonce,
                'difficulty': block.difficulty,
                'version': block.version,
                'timestamp': block.timestamp,
                'timestamp_str': datetime.fromtimestamp(block.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                'tx_count': len(block.transactions),
                'transactions': transactions
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    """Get all confirmed transactions across all blocks."""
    try:
        if blockchain is None:
            initialize_from_database()
        
        transactions = []
        for block in blockchain.chain[1:]:  # Skip genesis block
            for tx in block.transactions:
                transactions.append({
                    'hash': tx.tx_hash,
                    'sender': tx.sender_id,
                    'receiver': tx.receiver_id,
                    'amount': tx.amount,
                    'fee': tx.fee,
                    'nonce': tx.nonce,
                    'timestamp': tx.timestamp,
                    'timestamp_str': datetime.fromtimestamp(tx.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                    'block_index': block.index,
                    'signed': tx.signature is not None,
                    'encrypted': tx.encrypted_payload is not None
                })
        
        return jsonify({
            'success': True,
            'total_confirmed': len(transactions),
            'transactions': transactions
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/mempool', methods=['GET'])
def get_mempool():
    """Get pending transactions in the mempool."""
    try:
        if network is None or network.mempool is None:
            return jsonify({
                'success': True,
                'total_pending': 0,
                'mempool_size': 0,
                'transactions': []
            })
        
        mempool = network.mempool
        transactions = []
        
        for tx_hash, entry in mempool._pool.items():
            tx = entry.tx
            transactions.append({
                'hash': tx.tx_hash,
                'sender': tx.sender_id,
                'receiver': tx.receiver_id,
                'amount': tx.amount,
                'fee': tx.fee,
                'nonce': tx.nonce,
                'timestamp': tx.timestamp,
                'timestamp_str': datetime.fromtimestamp(tx.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                'age_seconds': entry.age_seconds,
                'signed': tx.signature is not None,
                'encrypted': tx.encrypted_payload is not None
            })
        
        # Sort by fee (descending) — fee priority order
        transactions.sort(key=lambda x: x['fee'], reverse=True)
        
        return jsonify({
            'success': True,
            'total_pending': len(transactions),
            'mempool_size': mempool.size if hasattr(mempool, 'size') else len(transactions),
            'transactions': transactions
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/wallets', methods=['GET'])
def get_wallets():
    """Get wallet information."""
    try:
        if not wallets:
            init_wallets()
        
        wallet_info = []
        
        if wallet_registry is not None:
            # Use live wallet registry from main_v2
            for name, wallet in wallet_registry.wallets.items():
                wallet_info.append({
                    'name': name,
                    'address': wallet.address,
                    'balance': wallet.balance,
                    'kyber_pub_size': len(wallet.kyber_pub),
                    'dilithium_pub_size': len(wallet.dilithium_pub),
                    'role': 'Validator' if 'Validator' in name else 'User'
                })
        else:
            # Use in-memory wallet balances
            default_addresses = {
                'Alice': '32770ba866763c2f1e5e5e5e5e5e5e5e',
                'Bob': 'bb3619e1840c440055555555555555555',
                'Validator-1': 'e68b676ed977777777777777777777777',
                'Validator-2': 'f79c787fe088888888888888888888888',
                'Validator-3': 'a8ad898af199999999999999999999999',
            }
            
            for name, balance_info in wallets.items():
                wallet_info.append({
                    'name': name,
                    'address': default_addresses.get(name, f"0x{name.lower().replace('-', '')}"),
                    'balance': balance_info['balance'],
                    'kyber_pub_size': 1568,
                    'dilithium_pub_size': 1312,
                    'role': 'Validator' if 'Validator' in name else 'User'
                })
        
        return jsonify({
            'success': True,
            'total_wallets': len(wallet_info),
            'wallets': wallet_info
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/nodes', methods=['GET'])
def get_nodes():
    """Get network nodes information."""
    try:
        nodes = []
        
        if network is not None and network.nodes:
            for node_id, node in network.nodes.items():
                nodes.append({
                    'name': node.node_id,
                    'role': node.role,
                    'status': 'online',
                    'address': node.wallet.address if node.wallet else 'N/A',
                    'balance': node.wallet.balance if node.wallet else 0.0
                })
        else:
            # Fallback default nodes
            default_nodes = [
                {'name': 'Alice', 'role': 'sender', 'status': 'online'},
                {'name': 'Bob', 'role': 'receiver', 'status': 'online'},
                {'name': 'Validator-1', 'role': 'validator', 'status': 'online'},
                {'name': 'Validator-2', 'role': 'validator', 'status': 'online'},
                {'name': 'Validator-3', 'role': 'validator', 'status': 'online'},
            ]
            for node_info in default_nodes:
                nodes.append({
                    'name': node_info['name'],
                    'role': node_info['role'],
                    'status': node_info['status'],
                    'address': f"0x{node_info['name'].lower().replace('-', '')}",
                    'balance': 0.0
                })
        
        return jsonify({
            'success': True,
            'total_nodes': len(nodes),
            'nodes': nodes
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    """Get performance metrics from the metrics database."""
    try:
        if metrics_collector is None:
            metrics_collector_local = MetricsCollector()
        else:
            metrics_collector_local = metrics_collector
        
        metric_categories = [
            'kyber_keygen',
            'dilithium_keygen',
            'kyber_encrypt',
            'kyber_decrypt',
            'dilithium_sign',
            'dilithium_verify',
            'block_mine',
            'consensus'
        ]
        
        metrics_data = {}
        for category in metric_categories:
            stats = metrics_collector_local.stats(category)
            if stats:
                metrics_data[category] = {
                    'mean': stats.get('mean', 0),
                    'median': stats.get('median', 0),
                    'std_dev': stats.get('std_dev', 0),
                    'p95': stats.get('p95', 0),
                    'min': stats.get('min', 0),
                    'max': stats.get('max', 0),
                    'count': stats.get('count', 0)
                }
        
        return jsonify({
            'success': True,
            'metrics': metrics_data
        })
    except Exception as e:
        print(f"[ERROR] get_metrics: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e), 'metrics': {}}), 500


@app.route('/api/chain_stats', methods=['GET'])
def get_chain_stats():
    """Get blockchain statistics."""
    try:
        if blockchain is None:
            initialize_from_database()
        
        total_txs = sum(len(block.transactions) for block in blockchain.chain)
        
        return jsonify({
            'success': True,
            'stats': {
                'total_blocks': len(blockchain.chain),
                'chain_height': blockchain.height,
                'total_transactions': total_txs,
                'genesis_hash': blockchain.chain[0].block_hash if blockchain.chain else 'N/A',
                'latest_block_hash': blockchain.last_block.block_hash,
                'latest_block_index': blockchain.last_block.index,
                'timestamp': time.time()
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ══════════════════════════════════════════════
#  API Routes — Blockchain Actions
# ══════════════════════════════════════════════

@app.route("/api/transaction", methods=["POST"])
def create_transaction():
    """Create a transaction and update wallet balances."""
    try:
        data = request.get_json()

        sender = data.get("sender")
        receiver = data.get("receiver")
        amount = data.get("amount")
        fee = data.get("fee", 0.0)

        # Validate required fields
        if not sender or not receiver or amount is None:
            return jsonify({
                "success": False,
                "error": "Missing required fields: sender, receiver, amount"
            }), 400

        amount = float(amount)
        fee = float(fee)

        # Validate transaction
        if amount <= 0:
            return jsonify({
                "success": False,
                "error": "Amount must be positive"
            }), 400

        if sender == receiver:
            return jsonify({
                "success": False,
                "error": "Sender and receiver cannot be the same"
            }), 400

        # Check sufficient balance
        if not wallets:
            init_wallets()
        
        if sender not in wallets:
            return jsonify({
                "success": False,
                "error": f"Sender wallet '{sender}' not found"
            }), 400

        if receiver not in wallets:
            return jsonify({
                "success": False,
                "error": f"Receiver wallet '{receiver}' not found"
            }), 400

        if wallets[sender]["balance"] < (amount + fee):
            return jsonify({
                "success": False,
                "error": f"Insufficient balance. Have ₹{wallets[sender]['balance']:.2f}, need ₹{amount + fee:.2f}"
            }), 400

        # Apply the transaction and update balances
        apply_transaction(sender, receiver, amount, fee)

        # Create transaction dict for response
        tx = {
            "sender": sender,
            "receiver": receiver,
            "amount": amount,
            "fee": fee,
            "timestamp": time.time()
        }

        # Add to mempool if available
        if network and network.mempool:
            network.mempool.add_transaction(tx)

        return jsonify({
            "success": True,
            "transaction": tx,
            "balances": {
                sender: wallets[sender]["balance"],
                receiver: wallets[receiver]["balance"]
            }
        }), 200

    except Exception as e:
        print(f"[ERROR] create_transaction: {e}")
        print(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/verify_chain', methods=['GET'])
def verify_chain():
    """Verify blockchain integrity."""
    try:
        if blockchain is None:
            initialize_from_database()
        
        is_valid, issues = blockchain.verify_chain(verbose=False)
        
        return jsonify({
            'success': True,
            'valid': is_valid,
            'total_blocks': len(blockchain.chain),
            'total_transactions': sum(len(b.transactions) for b in blockchain.chain),
            'issues': issues,
            'issue_count': len(issues)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/consensus_state', methods=['GET'])
def get_consensus_state():
    """Get current consensus state."""
    return jsonify({
        'success': True,
        'consensus': consensus_state
    })


# ══════════════════════════════════════════════
#  Error Handlers
# ══════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(e):
    print(f"[ERROR] 500: {e}")
    print(traceback.format_exc())
    return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ══════════════════════════════════════════════
#  Main Entry Point
# ══════════════════════════════════════════════

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)