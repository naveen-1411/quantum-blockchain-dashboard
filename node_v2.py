"""
node_v2.py
==========
Phase 2 — Upgraded blockchain node.

Improvements over Phase 1 node.py
-----------------------------------
  ✅ Uses Wallet (Dilithium + Kyber keys from wallet.py)
  ✅ Uses Mempool class (double-spend, TTL, fee-priority)
  ✅ Uses MetricsCollector (records every operation timing)
  ✅ Per-sender nonce tracking (replay attack prevention)
  ✅ Fee attached to every transaction
  ✅ PBFT consensus via ConsensusEngine
  ✅ Simulated network delay
  ✅ Public key registry (so validators can verify any sender's sig)
"""

import time
from crypto_module import dilithium_sign, dilithium_verify

from blockchain_v2 import Transaction, Block, Blockchain, NETWORK_DELAY_MS
from wallet   import Wallet
from mempool  import Mempool, MAX_TX_PER_BLOCK
from metrics  import MetricsCollector
from consensus import ConsensusEngine, MsgType


# ══════════════════════════════════════════════
#  Network (shared public key registry)
# ══════════════════════════════════════════════

class Network:
    """
    Shared registry of node public keys and reference to the blockchain.
    In a distributed system this would be discovered via /get_nodes API.

    Attributes
    ----------
    blockchain   : shared Blockchain instance
    nodes        : dict  {node_id → NodeV2}
    pub_key_map  : dict  {node_id → dilithium_pub}  (for sig verification)
    mempool      : shared global Mempool
    """

    def __init__(self, blockchain: Blockchain):
        self.blockchain  = blockchain
        self.nodes       : dict[str, "NodeV2"] = {}
        self.pub_key_map : dict[str, bytes]     = {}
        self.mempool     = Mempool()

    def register(self, node: "NodeV2") -> None:
        self.nodes[node.node_id]       = node
        self.pub_key_map[node.node_id] = node.wallet.dilithium_pub

    def broadcast_tx(self, tx: Transaction, sender_id: str) -> dict:
        """
        Send a transaction to all validator nodes in the network.
        Returns {validator_id: accepted bool}.
        """
        results = {}
        for vid, node in self.nodes.items():
            if node.role == "validator":
                accepted = node.receive_transaction(tx, sender_id)
                results[vid] = accepted
        return results

    def get_validator_nodes(self) -> list:
        return [n for n in self.nodes.values() if n.role == "validator"]


# ══════════════════════════════════════════════
#  NodeV2
# ══════════════════════════════════════════════

class NodeV2:
    """
    Phase 2 blockchain node.

    Parameters
    ----------
    wallet   : Wallet       – holds this node's Kyber + Dilithium keys
    role     : str          – "sender" | "receiver" | "validator"
    network  : Network      – shared network object
    metrics  : MetricsCollector – shared metrics recorder
    """

    def __init__(
        self,
        wallet   : Wallet,
        role     : str,
        network  : Network,
        metrics  : MetricsCollector,
    ):
        self.wallet    = wallet
        self.node_id   = wallet.name
        self.role      = role
        self.network   = network
        self.metrics   = metrics
        self._nonce    = 0          # per-sender nonce counter

        # PBFT consensus engine (validators only)
        self.consensus_engine : ConsensusEngine | None = None
        if role == "validator":
            self.consensus_engine = ConsensusEngine(
                node_id          = self.node_id,
                total_validators = 0,   # updated when network is built
                dilithium_priv   = wallet.dilithium_priv,
                dilithium_pub    = wallet.dilithium_pub,
                sign_fn          = dilithium_sign,
                verify_fn        = dilithium_verify,
            )

        # Register with network
        network.register(self)
        print(f"[NODE]  {role.upper():<10} '{self.node_id}'  "
              f"addr={wallet.address[:16]}…  "
              f"Kyber={len(wallet.kyber_pub)}B  Dil={len(wallet.dilithium_pub)}B")

    def _next_nonce(self) -> int:
        self._nonce += 1
        return self._nonce

    # ──────────────────────────────────────────
    #  Sending  (Sender role)
    # ──────────────────────────────────────────

    def send_transaction(
        self,
        receiver_id  : str,
        amount       : float,
        fee          : float = 0.001,
    ) -> tuple["Transaction | None", str]:
        """
        Create, encrypt, and sign a transaction then submit to global mempool.

        Returns (tx, status)  where status is ACCEPTED / rejection reason.
        """
        receiver_node = self.network.nodes.get(receiver_id)
        if not receiver_node:
            return None, f"RECEIVER_NOT_FOUND: {receiver_id}"

        if not self.wallet.can_afford(amount, fee):
            return None, f"INSUFFICIENT_BALANCE: have {self.wallet.balance}"

        nonce = self._next_nonce()
        tx    = Transaction(
            sender_id   = self.node_id,
            receiver_id = receiver_id,
            amount      = amount,
            fee         = fee,
            nonce       = nonce,
        )

        # Step 1: Kyber encrypt with receiver's public key
        with self.metrics.measure("kyber_encrypt"):
            tx.encrypt(receiver_node.wallet.kyber_pub)

        # Step 2: Dilithium sign
        with self.metrics.measure("dilithium_sign"):
            tx.sign(self.wallet.dilithium_priv)

        print(
            f"[TX]    {self.node_id} → {receiver_id}  "
            f"₹{amount}  fee={fee}  nonce={nonce}  "
            f"hash={tx.tx_hash[:12]}…"
        )

        # Step 3: Submit to mempool
        accepted, reason = self.network.mempool.add(tx, fee=fee)

        # Step 4: Broadcast to validators
        if accepted:
            broadcast_results = self.network.broadcast_tx(tx, self.node_id)
            accepted_by = sum(1 for v in broadcast_results.values() if v)
            print(f"         Broadcast: {accepted_by}/{len(broadcast_results)} validators accepted")
        else:
            print(f"         Mempool rejected: {reason}")

        return tx, reason

    # ──────────────────────────────────────────
    #  Receiving / Validation  (Validator role)
    # ──────────────────────────────────────────

    def receive_transaction(self, tx: "Transaction", sender_id: str) -> bool:
        """
        Validate a received transaction:
          1. Verify Dilithium signature
          2. Check for double-spend against committed ledger
          3. Simulate network delay
        """
        if NETWORK_DELAY_MS > 0:
            time.sleep(NETWORK_DELAY_MS / 1000)

        # Get sender's public key from network registry
        sender_pub = self.network.pub_key_map.get(sender_id)
        if not sender_pub:
            print(f"[VAL]   {self.node_id}: Unknown sender {sender_id}")
            return False

        # Double-spend check against committed ledger
        if self.network.blockchain.is_double_spend(tx.tx_hash):
            print(f"[VAL]   {self.node_id}: TX {tx.tx_hash[:12]}… DOUBLE-SPEND rejected")
            return False

        with self.metrics.measure("dilithium_verify"):
            valid = tx.verify_signature(sender_pub)

        status = "✓" if valid else "✗ INVALID SIG"
        print(f"[VAL]   {self.node_id}: TX {tx.tx_hash[:12]}… sig={status}")
        return valid

    # ──────────────────────────────────────────
    #  Block Proposal  (Proposer/Validator role)
    # ──────────────────────────────────────────

    def propose_block(self) -> "Block | None":
        """
        Pull transactions from mempool, mine a block, and sign it.
        """
        pending = self.network.mempool.get_pending(MAX_TX_PER_BLOCK)
        if not pending:
            print(f"[PROP]  {self.node_id}: mempool empty — nothing to propose")
            return None

        block = self.network.blockchain.create_block(pending, self.node_id)

        print(f"[PROP]  {self.node_id}: Mining block #{block.index} "
              f"({len(pending)} txs, merkle={block.merkle_root[:12]}…)…", end=" ", flush=True)

        with self.metrics.measure("block_mine"):
            block.mine()

        print(f"nonce={block.nonce}  hash={block.block_hash[:16]}…")

        with self.metrics.measure("dilithium_sign", extra="block_sign"):
            block.sign(self.wallet.dilithium_priv)

        return block

    # ──────────────────────────────────────────
    #  Commit block to ledger
    # ──────────────────────────────────────────

    def commit_block(self, block: "Block") -> tuple[bool, str]:
        """
        Add a consensus-approved block to the ledger.
        Updates wallet balances and clears mempool.
        """
        sender_pub_map = self.network.pub_key_map

        with self.metrics.measure("block_validate"):
            success, reason = self.network.blockchain.add_block(
                block,
                proposer_dilithium_pub = self.wallet.dilithium_pub,
                sender_pub_map         = sender_pub_map,
            )

        if success:
            committed_hashes = [tx.tx_hash for tx in block.transactions]
            self.network.mempool.remove_committed(committed_hashes)
            print(f"[NODE]  Mempool: {self.network.mempool.size} pending after commit")

        return success, reason

    # ──────────────────────────────────────────
    #  Decryption  (Receiver role)
    # ──────────────────────────────────────────

    def decrypt_transaction(self, tx: "Transaction") -> dict:
        """Decrypt an incoming transaction using this node's Kyber private key."""
        with self.metrics.measure("kyber_decrypt"):
            result = tx.decrypt(self.wallet.kyber_priv)
        return result

    def __repr__(self) -> str:
        return (f"NodeV2(id={self.node_id!r}, role={self.role!r}, "
                f"balance={self.wallet.balance})")
