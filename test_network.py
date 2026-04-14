#!/usr/bin/env python3
"""
test_network.py: Automated two-node test for the system

Setup (3 terminals):
    Terminal 1:  python node.py --port 5000
    Terminal 2:  python node.py --port 5001 --seed-peers http://localhost:5000
    Terminal 3:  python test_network.py
"""

import sys
from client import BlockchainClient

NODE_A = "http://localhost:5000"
NODE_B = "http://localhost:5001"

passed = 0
failed = 0


def section(title):
    print(f"\n{'=' * 52}")
    print(f"  {title}")
    print(f"{'=' * 52}")


def check(label, condition, detail=""):
    """Print a PASS/FAIL line and update the global counters."""
    global passed, failed
    status = "PASS" if condition else "FAIL"
    suffix = f": {detail}" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    if condition:
        passed += 1
    else:
        failed += 1
    return condition

def test_connectivity(a, b):
    section("1. Connectivity")

    chain_a = a.get_chain()
    if not check("Node A reachable (port 5000)", chain_a is not None):
        print("\n  Node A is not running. Start it with:")
        print("    python node.py --port 5000")
        sys.exit(1)

    chain_b = b.get_chain()
    if not check("Node B reachable (port 5001)", chain_b is not None):
        print("\n  Node B is not running. Start it with:")
        print("    python node.py --port 5001 --seed-peers http://localhost:5000")
        sys.exit(1)

    check("Node A starts at height 1 (StellarOrigin only)",
          chain_a.get("height") == 1)

    check("Node B starts at height 1 (StellarOrigin only)",
          chain_b.get("height") == 1)


def test_peer_registration(a, b):
    section("2. Peer Registration")

    result = a.register_peers([NODE_B])
    check("Node A accepted registration of Node B", result is not None)

    peers_a = a.get_peers()
    check("Node B appears in Node A's peer list",
          NODE_B in peers_a.get("peers", []))

    peers_b = b.get_peers()
    check("Node A appears in Node B's peer list",
          NODE_A in peers_b.get("peers", []),
          "Node B registered Node A on startup via --seed-peers")


def test_transaction(a):
    section("3. Submit Transaction → Node A")

    result = a.submit_transaction("Alice", "Bob", 50)
    check("Transaction accepted by Node A", result is not None and "tx_id" in result)

    tx_id = result.get("tx_id", "") if result else ""
    check("tx_id is a 64-char SHA-256 hex string", len(tx_id) == 64,
          f"tx_id={tx_id[:16]}...")

    mp = a.get_mempool()
    check("Node A mempool has 1 pending transaction",
          mp.get("pending_count") == 1)

    return tx_id


def test_mining(a):
    section("4. Mine on Node A")

    result = a.mine()
    check("Mine returned a block", result is not None and "hash" in result)

    block_hash = result.get("hash", "") if result else ""
    check("Mined block hash meets difficulty (has 3 leading zeros)",
          block_hash.startswith("000"),
          f"hash={block_hash[:16]}...")

    chain = a.get_chain()
    check("Node A chain height is 2 after mining",
          chain.get("height") == 2)

    mp = a.get_mempool()
    check("Node A mempool is empty after mining",
          mp.get("pending_count") == 0)

    return block_hash


def test_consensus(a, b, expected_block_hash):
    section("5. Consensus: Node B resolves against Node A")

    result = b.resolve()
    check("Resolve returned a result", result is not None)
    check("Node B adopted Node A's chain (chain_updated=True)",
          result.get("chain_updated") is True if result else False)
    check("Node B height is now 2",
          result.get("height") == 2 if result else False)


def test_chain_sync(b, expected_block_hash):
    section("6. Verify Node B Chain State After Sync")

    chain_b = b.get_chain()
    blocks  = chain_b.get("chain", [])

    check("Node B chain height is 2", chain_b.get("height") == 2)
    check("Block[0] is the StellarOrigin (0 transactions)",
          len(blocks) > 0 and len(blocks[0]["transactions"]) == 0)
    check("Block[1] contains 1 transaction",
          len(blocks) > 1 and len(blocks[1]["transactions"]) == 1)
    check("Block[1] hash matches the hash Node A mined",
          len(blocks) > 1 and blocks[1]["hash"] == expected_block_hash,
          f"expected={expected_block_hash[:16]}...")

    mp = b.get_mempool()
    check("Node B mempool is empty after sync",
          mp.get("pending_count") == 0)


def test_resolve_idempotent(b):
    section("7. Second Resolve: No Change Expected")

    result = b.resolve()
    check("chain_updated is False (already longest chain)",
          result.get("chain_updated") is False if result else False)
    check("Height stays at 2",
          result.get("height") == 2 if result else False)


# ============================================================

def main():
    a = BlockchainClient(NODE_A)
    b = BlockchainClient(NODE_B)

    test_connectivity(a, b)
    test_peer_registration(a, b)
    tx_id       = test_transaction(a)
    block_hash  = test_mining(a)
    test_consensus(a, b, block_hash)
    test_chain_sync(b, block_hash)
    test_resolve_idempotent(b)

    section("Results")
    print(f"  {passed} passed   {failed} failed\n")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
