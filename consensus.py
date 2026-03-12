"""
consensus.py
============
PBFT-inspired Consensus for the Quantum-Resistant Blockchain.

Classic PBFT has 3 phases: Pre-prepare → Prepare → Commit
We implement a simplified version appropriate for a prototype:

  Phase 1 — PRE-PREPARE
    Proposer broadcasts block to all validators.
    Validators verify: PoW, proposer Dilithium signature, Merkle root.

  Phase 2 — PREPARE
    Each validator that accepted pre-prepare broadcasts a signed PREPARE
    message containing the block hash.
    Validator waits until it receives ≥ ⌊(2n+1)/3⌋ matching PREPARE msgs.

  Phase 3 — COMMIT
    Validators that passed prepare broadcast a signed COMMIT message.
    Block is committed once ≥ ⌊(2n+1)/3⌋ matching COMMIT msgs received.

Safety guarantee: a block is committed only if 2/3 of validators agreed.
This tolerates up to ⌊(n-1)/3⌋ Byzantine (malicious/faulty) validators.

Simulation note
---------------
Because all nodes run in one process, "broadcasting" is a direct function
call.  In Phase 2 distributed deployment, replace with HTTP POST to
/consensus/prepare and /consensus/commit endpoints.
"""

import time
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ══════════════════════════════════════════════
#  Message types
# ══════════════════════════════════════════════

class MsgType(Enum):
    PRE_PREPARE = "PRE_PREPARE"
    PREPARE     = "PREPARE"
    COMMIT      = "COMMIT"


@dataclass
class ConsensusMessage:
    """
    Signed consensus message passed between validators.

    In distributed deployment: serialise to JSON and POST to peer nodes.
    """
    msg_type    : MsgType
    block_hash  : str
    block_index : int
    sender_id   : str
    timestamp   : float = field(default_factory=time.time)
    signature   : Optional[bytes] = None   # Dilithium signature of block_hash

    def sign(self, dilithium_priv: bytes, sign_fn) -> None:
        """Sign this message with the sender's Dilithium key."""
        payload = f"{self.msg_type.value}:{self.block_hash}:{self.block_index}".encode()
        self.signature = sign_fn(dilithium_priv, payload)

    def verify(self, dilithium_pub: bytes, verify_fn) -> bool:
        """Verify this message's Dilithium signature."""
        if not self.signature:
            return False
        payload = f"{self.msg_type.value}:{self.block_hash}:{self.block_index}".encode()
        return verify_fn(dilithium_pub, payload, self.signature)


# ══════════════════════════════════════════════
#  ValidatorState  (per-block)
# ══════════════════════════════════════════════

@dataclass
class ValidatorState:
    """Tracks prepare/commit messages received for one block."""
    block_hash      : str
    block_index     : int
    prepare_msgs    : dict = field(default_factory=dict)   # sender_id → ConsensusMessage
    commit_msgs     : dict = field(default_factory=dict)
    prepared        : bool = False
    committed       : bool = False


# ══════════════════════════════════════════════
#  ConsensusEngine
# ══════════════════════════════════════════════

class ConsensusEngine:
    """
    PBFT-inspired consensus engine.

    One ConsensusEngine per validator node.  Each engine tracks the
    current round state and decides when thresholds are met.

    Parameters
    ----------
    node_id         : str     – this validator's identifier
    total_validators: int     – total number of validators in the network
    dilithium_priv  : bytes   – this node's signing key (for messages)
    dilithium_pub   : bytes   – this node's verification key (shared with peers)
    sign_fn         : callable – dilithium_sign
    verify_fn       : callable – dilithium_verify
    """

    def __init__(
        self,
        node_id          : str,
        total_validators : int,
        dilithium_priv   : bytes,
        dilithium_pub    : bytes,
        sign_fn,
        verify_fn,
    ):
        self.node_id           = node_id
        self.n                 = total_validators
        self.dilithium_priv    = dilithium_priv
        self.dilithium_pub     = dilithium_pub
        self._sign             = sign_fn
        self._verify           = verify_fn
        self._state : dict[str, ValidatorState] = {}   # block_hash → state

        # Quorum = ceil(2n/3)  — PBFT 2/3 majority
        self.quorum = self._compute_quorum(total_validators)

    @staticmethod
    def _compute_quorum(n: int) -> int:
        """Minimum votes needed: ⌊2n/3⌋ + 1  (strict majority of 2/3)."""
        return (2 * n) // 3 + 1

    # ── Phase 1: Pre-Prepare ────────────────────
    def pre_prepare(self, block, proposer_dilithium_pub: bytes) -> tuple[bool, str]:
        """
        Validate the proposed block (Phase 1).

        Checks:
          1. PoW difficulty satisfied
          2. Proposer Dilithium signature valid
          3. Merkle root matches stored transactions
          4. Block not already in state (no duplicate rounds)

        Returns (accepted: bool, reason: str)
        """
        bh = block.block_hash

        if bh in self._state:
            return False, "DUPLICATE_ROUND"

        if not block.block_hash.startswith("0" * block.difficulty):
            return False, "POW_FAILED"

        if not block.verify_proposer_sig(proposer_dilithium_pub):
            return False, "INVALID_PROPOSER_SIG"

        if not block.verify_merkle_root():
            return False, "MERKLE_MISMATCH"

        # Initialise state for this block
        self._state[bh] = ValidatorState(block_hash=bh, block_index=block.index)
        return True, "ACCEPTED"

    # ── Phase 2: Prepare ────────────────────────
    def prepare(self, msg: ConsensusMessage, sender_pub: bytes) -> bool:
        """
        Receive and record a PREPARE message from another validator.
        Returns True when quorum is reached (node should move to commit).
        """
        if msg.block_hash not in self._state:
            return False
        if not msg.verify(sender_pub, self._verify):
            return False

        state = self._state[msg.block_hash]
        state.prepare_msgs[msg.sender_id] = msg

        if not state.prepared and len(state.prepare_msgs) >= self.quorum:
            state.prepared = True
            return True
        return False

    # ── Phase 3: Commit ─────────────────────────
    def commit(self, msg: ConsensusMessage, sender_pub: bytes) -> bool:
        """
        Receive and record a COMMIT message from another validator.
        Returns True when commit quorum is reached (block is final).
        """
        if msg.block_hash not in self._state:
            return False
        if not msg.verify(sender_pub, self._verify):
            return False

        state = self._state[msg.block_hash]
        if not state.prepared:
            return False

        state.commit_msgs[msg.sender_id] = msg

        if not state.committed and len(state.commit_msgs) >= self.quorum:
            state.committed = True
            return True
        return False

    # ── Create signed message ───────────────────
    def make_message(self, msg_type: MsgType, block_hash: str, block_index: int) -> ConsensusMessage:
        msg = ConsensusMessage(
            msg_type    = msg_type,
            block_hash  = block_hash,
            block_index = block_index,
            sender_id   = self.node_id,
        )
        msg.sign(self.dilithium_priv, self._sign)
        return msg

    # ── State query ─────────────────────────────
    def is_committed(self, block_hash: str) -> bool:
        return self._state.get(block_hash, ValidatorState("","")).committed

    def round_state(self, block_hash: str) -> dict:
        s = self._state.get(block_hash)
        if not s:
            return {"error": "unknown block"}
        return {
            "block_hash"   : block_hash[:16] + "…",
            "block_index"  : s.block_index,
            "prepare_count": len(s.prepare_msgs),
            "commit_count" : len(s.commit_msgs),
            "quorum"       : self.quorum,
            "prepared"     : s.prepared,
            "committed"    : s.committed,
        }


# ══════════════════════════════════════════════
#  PBFTCoordinator  (orchestrates a full round)
# ══════════════════════════════════════════════

class PBFTCoordinator:
    """
    Coordinates a full PBFT consensus round across all validator engines.

    In a single-process simulation this runs all 3 phases synchronously.
    In distributed deployment, each phase would involve HTTP round-trips.

    Parameters
    ----------
    validators : list of (node_id, ConsensusEngine, dilithium_pub)
    """

    def __init__(self, validators: list):
        """
        validators: list of (node_id: str, engine: ConsensusEngine, dil_pub: bytes)
        """
        self.validators = validators   # [(id, engine, pub), ...]

    # ── full consensus round ─────────────────────
    def run(self, block, proposer_id: str, proposer_dil_pub: bytes) -> dict:
        """
        Execute a full 3-phase PBFT consensus round.

        Returns
        -------
        {
            "approved"        : bool,
            "phase_results"   : {...},
            "prepare_votes"   : {node_id: bool},
            "commit_votes"    : {node_id: bool},
            "quorum"          : int,
            "total_validators": int,
            "latency_ms"      : float,
        }
        """
        t0 = time.perf_counter()
        bh = block.block_hash
        n  = len(self.validators)

        result = {
            "block_hash"       : bh[:16] + "…",
            "block_index"      : block.index,
            "proposer"         : proposer_id,
            "total_validators" : n,
            "quorum"           : self.validators[0][1].quorum if self.validators else 0,
            "phase_results"    : {},
            "prepare_votes"    : {},
            "commit_votes"     : {},
            "approved"         : False,
        }

        # ── Phase 1: PRE-PREPARE ──────────────────
        print(f"\n[PBFT]  ── Phase 1: PRE-PREPARE  Block #{block.index} ──")
        pre_results = {}
        for vid, engine, _ in self.validators:
            accepted, reason = engine.pre_prepare(block, proposer_dil_pub)
            pre_results[vid] = {"accepted": accepted, "reason": reason}
            status = "✓" if accepted else f"✗ ({reason})"
            print(f"         {vid}: {status}")

        accepted_validators = [
            (vid, eng, pub)
            for (vid, eng, pub), r in zip(self.validators, pre_results.values())
            if r["accepted"]
        ]

        if len(accepted_validators) < self.validators[0][1].quorum:
            result["phase_results"]["pre_prepare"] = pre_results
            result["approved"] = False
            result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            print(f"[PBFT]  Pre-prepare quorum NOT reached → ABORT")
            return result

        result["phase_results"]["pre_prepare"] = pre_results

        # ── Phase 2: PREPARE ─────────────────────
        print(f"\n[PBFT]  ── Phase 2: PREPARE ──")
        prepare_msgs = {}
        for vid, engine, _ in accepted_validators:
            msg = engine.make_message(MsgType.PREPARE, bh, block.index)
            prepare_msgs[vid] = msg

        pub_map = {vid: pub for vid, _, pub in self.validators}
        prepare_quorum_reached = {}

        for vid, engine, _ in accepted_validators:
            reached = False
            for sender_id, msg in prepare_msgs.items():
                if sender_id != vid:   # don't count own message
                    sender_pub = pub_map.get(sender_id)
                    if sender_pub:
                        if engine.prepare(msg, sender_pub):
                            reached = True
            # Also count self in prepare
            engine._state[bh].prepare_msgs[vid] = prepare_msgs[vid]
            if len(engine._state[bh].prepare_msgs) >= engine.quorum:
                engine._state[bh].prepared = True
                reached = True

            prepare_quorum_reached[vid] = reached
            result["prepare_votes"][vid] = reached
            print(f"         {vid}: prepare={'✓' if reached else '✗'}")

        prepared_validators = [
            (vid, eng, pub)
            for (vid, eng, pub) in accepted_validators
            if eng._state.get(bh) and eng._state[bh].prepared
        ]

        # ── Phase 3: COMMIT ──────────────────────
        print(f"\n[PBFT]  ── Phase 3: COMMIT ──")
        commit_msgs = {}
        for vid, engine, _ in prepared_validators:
            msg = engine.make_message(MsgType.COMMIT, bh, block.index)
            commit_msgs[vid] = msg

        commit_quorum_reached = {}
        for vid, engine, _ in prepared_validators:
            reached = False
            for sender_id, msg in commit_msgs.items():
                if sender_id != vid:
                    sender_pub = pub_map.get(sender_id)
                    if sender_pub:
                        if engine.commit(msg, sender_pub):
                            reached = True
            # Count self
            engine._state[bh].commit_msgs[vid] = commit_msgs[vid]
            if len(engine._state[bh].commit_msgs) >= engine.quorum:
                engine._state[bh].committed = True
                reached = True

            commit_quorum_reached[vid] = reached
            result["commit_votes"][vid] = reached
            status = "✓ COMMITTED" if reached else "✗"
            print(f"         {vid}: commit={status}")

        # ── Decision ─────────────────────────────
        committed_count = sum(1 for v in commit_quorum_reached.values() if v)
        quorum = self.validators[0][1].quorum
        approved = committed_count >= quorum

        result["approved"]    = approved
        result["latency_ms"]  = round((time.perf_counter() - t0) * 1000, 2)
        result["commit_count"] = committed_count

        print(f"\n[PBFT]  Result: {committed_count}/{n} committed  "
              f"quorum={quorum}  → {'APPROVED ✓' if approved else 'REJECTED ✗'}")
        print(f"[PBFT]  Consensus latency: {result['latency_ms']}ms")

        return result


# ══════════════════════════════════════════════
#  Self-test
# ══════════════════════════════════════════════

if __name__ == "__main__":
    from crypto_module import (
        generate_dilithium_keypair, dilithium_sign, dilithium_verify,
        generate_kyber_keypair,
    )
    from blockchain_v2 import Block

    print("=" * 58)
    print("  consensus.py  —  Self-Test  (3 validators)")
    print("=" * 58)

    N = 3
    keys = [generate_dilithium_keypair() for _ in range(N)]
    names = [f"V{i+1}" for i in range(N)]

    engines = [
        ConsensusEngine(
            node_id          = names[i],
            total_validators = N,
            dilithium_priv   = keys[i][1],
            dilithium_pub    = keys[i][0],
            sign_fn          = dilithium_sign,
            verify_fn        = dilithium_verify,
        )
        for i in range(N)
    ]
    validators = [(names[i], engines[i], keys[i][0]) for i in range(N)]
    coordinator = PBFTCoordinator(validators)

    # Create a mock block
    block = Block(index=1, transactions=[], previous_hash="0"*64, proposer_id="V1")
    block.mine()
    block.sign(keys[0][1])

    result = coordinator.run(block, proposer_id="V1", proposer_dil_pub=keys[0][0])
    print(f"\nApproved: {result['approved']}")
    print(f"Quorum: {result['quorum']}/{N}")
    assert result["approved"], "Consensus should be approved with 3/3 honest validators"
    print("\n✅  Consensus tests passed.")
