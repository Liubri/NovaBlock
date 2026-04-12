#!/usr/bin/env python3
"""
Node: Flask REST API server for blockchain node
Manages blockchain, mempool, and peer communication
"""

import argparse
from flask import Flask, request, jsonify
from blockchain import Blockchain
from mempool import Mempool
from network import broadcast_block, broadcast_transaction, announce_self
import consensus

app = Flask(__name__)

# Global state
blockchain = Blockchain()
mempool = Mempool()
peers = set()  # Set of peer URLs (strings)


# ============================================================================
# REST Endpoints
# ============================================================================

@app.route('/chain', methods=['GET'])
def get_chain():
    """
    GET /chain
    Return the full blockchain as a list of block dicts.
    """
    return jsonify(blockchain.to_list()), 200


@app.route('/chain', methods=['POST'])
def receive_block():
    """
    POST /chain
    Receive a block from a peer, validate it, and add to chain if valid.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        from block import Block
        block = Block.from_dict(data)
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"error": f"Invalid block: {e}"}), 400

    # Validate and add the block
    if blockchain.add_block(block):
        # Remove mined transactions from mempool
        mempool.remove(block.transactions)
        return jsonify(block.to_dict()), 201
    else:
        return jsonify({"error": "Block validation failed"}), 400


@app.route('/mine', methods=['POST'])
def mine():
    """
    POST /mine
    Mine all pending transactions from mempool and broadcast the block.
    """
    pending = mempool.get_all()
    if not pending:
        return jsonify({"error": "No pending transactions"}), 400

    # Mine the block
    new_block = blockchain.mine_pending_transactions(pending)

    # Remove mined transactions from mempool
    mempool.remove(pending)

    # Broadcast the block to all peers
    broadcast_block(new_block.to_dict(), peers)

    return jsonify(new_block.to_dict()), 201


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    """
    POST /transactions/new
    Receive a transaction, add to mempool, and broadcast to peers.
    Request: {"sender": "...", "recipient": "...", "amount": N}
    """
    data = request.get_json()
    if not data or not all(k in data for k in ['sender', 'recipient', 'amount']):
        return jsonify({"error": "Missing transaction fields"}), 400

    transaction = {
        'sender': data['sender'],
        'recipient': data['recipient'],
        'amount': data['amount'],
    }

    # Add to mempool
    tx_id = mempool.add(transaction)
    if tx_id is None:
        return jsonify({"error": "Duplicate transaction"}), 400

    # Broadcast to peers
    broadcast_transaction(transaction, peers)

    return jsonify({"tx_id": tx_id}), 201


@app.route('/nodes/register', methods=['POST'])
def register_node():
    """
    POST /nodes/register
    Register a new peer node (push-based discovery).
    Request: {"node_url": "http://..."}
    Response: {"peers": [list of peer URLs]}
    """
    data = request.get_json()
    if not data or 'node_url' not in data:
        return jsonify({"error": "Missing node_url"}), 400

    new_peer = data['node_url']

    # Add the new peer to our set
    if new_peer not in peers:
        peers.add(new_peer)
        print(f"[Node] Registered new peer: {new_peer}")

    # Return current list of peers so the new node can learn about them
    return jsonify({"peers": list(peers)}), 200


@app.route('/nodes/resolve', methods=['POST'])
def resolve():
    """
    POST /nodes/resolve
    Trigger consensus: fetch chains from peers, validate, adopt longest if valid.
    Response: {"chain_updated": bool, "height": int}
    """
    chain_updated = consensus.resolve_chain(blockchain, peers)

    if chain_updated:
        # Clear mempool when chain is replaced
        mempool.clear()
        print("[Node] Consensus: chain updated, mempool cleared")

    return jsonify({
        "chain_updated": chain_updated,
        "height": blockchain.height
    }), 200


@app.route('/mempool', methods=['GET'])
def get_mempool():
    """
    GET /mempool
    Return pending transactions (for debugging/testing).
    """
    return jsonify(mempool.to_list()), 200


@app.route('/peers', methods=['GET'])
def get_peers():
    """
    GET /peers
    Return list of known peers (for debugging/testing).
    """
    return jsonify(list(peers)), 200


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='NovaBlock Node')
    parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
    parser.add_argument('--seed-peers', nargs='*', default=[],
                        help='Space-separated list of seed peer URLs')
    parser.add_argument('--host', default='localhost', help='Host to bind to')
    args = parser.parse_args()

    # Announce ourselves to seed peers
    if args.seed_peers:
        my_url = f"http://{args.host}:{args.port}"
        print(f"[Node] Announcing self to {len(args.seed_peers)} seed peers...")
        result = announce_self(my_url, set(args.seed_peers))
        print(f"[Node] Registered with {len(result.get('registered_with', []))} peers")
        peers.update(result.get('registered_with', []))

    print(f"[Node] Starting on {args.host}:{args.port}")
    print(f"[Node] Known peers: {list(peers)}")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
