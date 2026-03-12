"""
node.py
=======
Simulated blockchain node for the Quantum-Resistant Blockchain.

Each Node holds:
  - A Kyber key pair   (encryption / decryption of transaction payloads)
  - A Dilithium key pair (signing / verifying transactions and blocks)
  - A local copy of the shared Blockchain ledger

Node roles
----------
  Sender Node        – creates and broadcasts transactions
  Receiver Node      – decrypts incoming transactions
  Validator Node     – verifies signatures, proposes blocks, reaches consensus
"""

import time
from crypto_module import (
    generate_kyber_keypair,
    generate_dilithium_keypair,
    dilithium_verify,
)
from blockchain import Transaction, Block, Blockchain


class Node:
    """
    Represents a participant in the quantum-resistant blockchain network.

    Parameters
    ----------
    node_id   : str        – unique human-readable identifier
    blockchain : Blockchain – shared ledger (same object passed to all nodes)
    """

    def __init__(self, node_id: str, blockchain: Blockchain):
        self.node_id    = node_id
        self.blockchain = blockchain
        self.mempool: list[Transaction] = []   # pending validated transactions

        # Generate post-quantum key pairs on node initialisation
        print(f"[NODE]  Generating PQ keys for '{node_id}' …", end=" ", flush=True)
        t0 = time.perf_counter()
        self.kyber_pub,     self.kyber_priv     = generate_kyber_keypair()
        self.dilithium_pub, self.dilithium_priv = generate_dilithium_keypair()
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"done ({elapsed:.1f} ms)")

    # ──────────────────────────────────────────
    #  Sending (Sender role)
    # ──────────────────────────────────────────

    def send_transaction(
        self,
        receiver: "Node",
        amount: float,
        network: list["Node"],
    ) -> Transaction:
        """
        Create, encrypt, sign, and broadcast a transaction.

        Parameters
        ----------
        receiver : Node   – destination node
        amount   : float  – value being transferred
        network  : list   – all validator nodes to broadcast to

        Returns
        -------
        The signed Transaction object.
        """
        tx = Transaction(
            sender_id   = self.node_id,
            receiver_id = receiver.node_id,
            amount      = amount,
        )

        # Step 1: Encrypt with receiver's Kyber public key
        t_enc = time.perf_counter()
        tx.encrypt(receiver.kyber_pub)
        enc_ms = (time.perf_counter() - t_enc) * 1000

        # Step 2: Sign with sender's Dilithium private key
        t_sign = time.perf_counter()
        tx.sign(self.dilithium_priv)
        sign_ms = (time.perf_counter() - t_sign) * 1000

        print(
            f"[TX]    {self.node_id} → {receiver.node_id}  "
            f"amount={amount}  "
            f"enc={enc_ms:.1f}ms  sign={sign_ms:.1f}ms  "
            f"hash={tx.tx_hash[:12]}…"
        )

        # Step 3: Broadcast to all validator nodes
        for validator in network:
            validator.receive_transaction(tx, sender_dilithium_pub=self.dilithium_pub)

        return tx

    # ──────────────────────────────────────────
    #  Receiving & Validation (Validator role)
    # ──────────────────────────────────────────

    def receive_transaction(
        self,
        tx: Transaction,
        sender_dilithium_pub: bytes,
    ) -> bool:
        """
        Validate and add a transaction to the mempool.

        Checks
        ------
        1. Dilithium signature is valid.
        2. Transaction not already in mempool.

        Returns True if accepted.
        """
        t_ver = time.perf_counter()
        valid = tx.verify_signature(sender_dilithium_pub)
        ver_ms = (time.perf_counter() - t_ver) * 1000

        if valid:
            # Avoid duplicates
            existing_hashes = {t.tx_hash for t in self.mempool}
            if tx.tx_hash not in existing_hashes:
                self.mempool.append(tx)
            print(
                f"[VAL]   {self.node_id}: TX {tx.tx_hash[:12]}… "
                f"signature ✓  verify={ver_ms:.1f}ms"
            )
        else:
            print(
                f"[VAL]   {self.node_id}: TX {tx.tx_hash[:12]}… "
                f"signature ✗  REJECTED"
            )
        return valid

    # ──────────────────────────────────────────
    #  Block Proposal (Proposer role)
    # ──────────────────────────────────────────

    def propose_block(self) -> Block | None:
        """
        Collect mempool transactions, mine a block, and sign it.

        Returns the mined Block, or None if mempool is empty.
        """
        if not self.mempool:
            print(f"[PROP]  {self.node_id}: mempool empty, nothing to propose.")
            return None

        txs = list(self.mempool)
        block = self.blockchain.create_block(txs, self.node_id)

        print(f"[PROP]  {self.node_id}: Mining block #{block.index} ({len(txs)} txs)…", end=" ")
        t_mine = time.perf_counter()
        block.mine()
        mine_ms = (time.perf_counter() - t_mine) * 1000
        print(f"done  nonce={block.nonce}  hash={block.block_hash[:16]}…  ({mine_ms:.1f}ms)")

        block.sign(self.dilithium_priv)
        return block

    # ──────────────────────────────────────────
    #  Consensus & Ledger Update
    # ──────────────────────────────────────────

    def reach_consensus_and_commit(
        self,
        block: Block,
        proposer_dilithium_pub: bytes,
        validators: list["Node"],
        threshold: float = 0.67,
    ) -> bool:
        """
        Simple majority-vote consensus.

        Each validator node independently verifies the block signature.
        If ≥ *threshold* fraction approve, the block is added to the ledger
        and the mempool is cleared.

        Parameters
        ----------
        block                 : Block  – proposed block
        proposer_dilithium_pub: bytes  – proposer's Dilithium public key
        validators            : list   – all nodes casting votes
        threshold             : float  – minimum approval ratio (default 2/3)

        Returns
        -------
        True if consensus reached and block committed.
        """
        votes_for = 0
        print(f"\n[CON]   Consensus vote for Block #{block.index}:")
        for v in validators:
            ok = block.verify_proposer_sig(proposer_dilithium_pub)
            vote = "YES" if ok else "NO"
            print(f"         {v.node_id}: {vote}")
            if ok:
                votes_for += 1

        ratio = votes_for / len(validators)
        approved = ratio >= threshold
        print(
            f"[CON]   Result: {votes_for}/{len(validators)} "
            f"({ratio*100:.0f}%)  → {'APPROVED ✓' if approved else 'REJECTED ✗'}"
        )

        if approved:
            success = self.blockchain.add_block(block, proposer_dilithium_pub)
            if success:
                # Clear committed transactions from all validators' mempools
                committed_hashes = {tx.tx_hash for tx in block.transactions}
                for v in validators:
                    v.mempool = [t for t in v.mempool
                                 if t.tx_hash not in committed_hashes]
            return success

        return False

    # ──────────────────────────────────────────
    #  Decryption (Receiver role)
    # ──────────────────────────────────────────

    def decrypt_transaction(self, tx: Transaction) -> dict:
        """
        Decrypt an incoming transaction payload using this node's Kyber private key.
        Only works if this node is the intended receiver.
        """
        return tx.decrypt(self.kyber_priv)

    # ──────────────────────────────────────────
    #  Display
    # ──────────────────────────────────────────

    def __repr__(self) -> str:
        return f"Node(id={self.node_id!r}, mempool={len(self.mempool)} txs)"
