"""
merkle.py
=========
Merkle Tree implementation for transaction integrity verification.

A Merkle tree allows:
  - Compact proof that a transaction is included in a block (Merkle proof)
  - Detection of any single transaction tampering (root hash changes)
  - Efficient partial verification without downloading entire block

Structure
---------
          Root
         /    \\
      H(AB)  H(CD)
      /  \\   /  \\
    H(A) H(B) H(C) H(D)

If TX count is odd, the last hash is duplicated.
"""

import hashlib


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def _sha256_pair(left: str, right: str) -> str:
    return _sha256(left + right)


# ══════════════════════════════════════════════
#  Core tree builder
# ══════════════════════════════════════════════

def build_merkle_tree(tx_hashes: list) -> list:
    """
    Build full Merkle tree from a list of transaction hashes.

    Returns
    -------
    List of levels, index 0 = leaf level, last = [root].
    Returns [[EMPTY_ROOT]] for empty transaction list.
    """
    if not tx_hashes:
        return [[_sha256("EMPTY")]]

    level = list(tx_hashes)
    tree  = [level]

    while len(level) > 1:
        # Duplicate last element if odd count
        if len(level) % 2 == 1:
            level = level + [level[-1]]

        next_level = [
            _sha256_pair(level[i], level[i + 1])
            for i in range(0, len(level), 2)
        ]
        tree.append(next_level)
        level = next_level

    return tree


def get_merkle_root(tx_hashes: list) -> str:
    """
    Compute and return just the Merkle root hash.

    Parameters
    ----------
    tx_hashes : list of hex-digest strings (tx.tx_hash values)

    Returns
    -------
    Root hash as hex string.
    """
    tree = build_merkle_tree(tx_hashes)
    return tree[-1][0]


# ══════════════════════════════════════════════
#  Merkle Proof (inclusion proof)
# ══════════════════════════════════════════════

def get_merkle_proof(tx_hashes: list, target_hash: str) -> list:
    """
    Generate a Merkle inclusion proof for target_hash.

    Returns
    -------
    List of (sibling_hash, direction) tuples where direction is 'L' or 'R'.
    Empty list if target_hash not found.

    Proof allows verification without revealing other transactions:
        verifier computes root from proof and checks it matches block root.
    """
    if target_hash not in tx_hashes:
        return []

    tree  = build_merkle_tree(tx_hashes)
    proof = []
    idx   = tx_hashes.index(target_hash)

    for level in tree[:-1]:   # skip root level
        # Pad if odd
        if len(level) % 2 == 1:
            level = level + [level[-1]]

        sibling_idx = idx ^ 1   # XOR with 1 → get sibling index
        direction   = "R" if idx % 2 == 0 else "L"
        proof.append((level[sibling_idx], direction))
        idx //= 2

    return proof


def verify_merkle_proof(
    target_hash : str,
    proof       : list,
    expected_root: str
) -> bool:
    """
    Verify a Merkle inclusion proof.

    Parameters
    ----------
    target_hash   : hash of the transaction being proven
    proof         : list of (sibling_hash, direction) from get_merkle_proof()
    expected_root : the block's merkle_root to verify against

    Returns
    -------
    True if the proof is valid and transaction is in the block.
    """
    current = target_hash
    for sibling, direction in proof:
        if direction == "R":
            current = _sha256_pair(current, sibling)
        else:
            current = _sha256_pair(sibling, current)
    return current == expected_root


# ══════════════════════════════════════════════
#  Self-test
# ══════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 50)
    print("  merkle.py  —  Self-Test")
    print("=" * 50)

    hashes = [_sha256(f"tx_{i}") for i in range(5)]
    root   = get_merkle_root(hashes)
    print(f"\nLeaf hashes : {len(hashes)}")
    print(f"Merkle root : {root[:24]}...")

    target = hashes[2]
    proof  = get_merkle_proof(hashes, target)
    valid  = verify_merkle_proof(target, proof, root)
    print(f"\nProof for TX[2]:  {len(proof)} siblings")
    print(f"Proof valid       : {valid}  (expected True)")

    bad_hash = _sha256("tampered")
    bad_proof = get_merkle_proof(hashes, bad_hash)
    print(f"Proof for tampered: {bad_proof}  (expected [])")

    # Tamper test
    hashes_tampered    = list(hashes)
    hashes_tampered[2] = _sha256("tampered")
    root_tampered      = get_merkle_root(hashes_tampered)
    print(f"\nRoot changed after tamper: {root != root_tampered}  (expected True)")
    print("\n✅  Merkle tree tests passed.")
