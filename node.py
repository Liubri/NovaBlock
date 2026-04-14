#!/usr/bin/env python3
"""
node.py: Flask REST API server for a NovaBlock node.
Wires together Blockchain, Mempool, Consensus, and Network
and exposes all REST endpoints for peer communication.
"""

import argparse
from flask import Flask, request, jsonify
from block import Block
from blockchain import Blockchain
from mempool import Mempool
from consensus import Consensus
from network import Network


app = Flask(__name__)

# Global state — one instance of each module per node process
blockchain = Blockchain()
mempool    = Mempool()
network    = Network()
consensus  = Consensus(blockchain, mempool, network.peers)


# Chain endpoints

@app.route('/chain', methods=['GET'])
def get_chain():
    """
    GET /chain
    Return the full blockchain as a list of block dicts.
    """
    return jsonify({
        "chain":  blockchain.to_list(),
        "height": blockchain.height,
    }), 200


@app.route('/blocks/new', methods=['POST'])
def receive_block():
    """
    POST /blocks/new
    Receive a mined block broadcast from a peer.
    Validate and append it if valid; remove its transactions from the mempool.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        block = Block.from_dict(data)
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"error": f"Invalid block data: {e}"}), 400

    if blockchain.add_block(block):
        mempool.remove(block.transactions)
        return jsonify(block.to_dict()), 201
    else:
        return jsonify({"error": "Block validation failed"}), 400


# Mining endpoint

@app.route('/mine', methods=['POST'])
def mine():
    """
    POST /mine
    Mine all pending transactions from the mempool into a new block,
    then broadcast the block to all known peers.
    """
    pending = mempool.get_all()
    if not pending:
        return jsonify({"error": "No pending transactions to mine"}), 400

    new_block = blockchain.mine_pending_transactions(pending)
    mempool.remove(pending)
    consensus.broadcast_block(new_block)

    return jsonify(new_block.to_dict()), 201


# Transaction endpoints

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    """
    POST /transactions/new
    Accept a new transaction, add it to the mempool, and broadcast to peers.
    Request body: {"sender": "...", "recipient": "...", "amount": N}
    """
    data = request.get_json()
    required = {'sender', 'recipient', 'amount'}

    if not data or not required.issubset(data.keys()):
        return jsonify({"error": f"Missing fields. Required: {required}"}), 400

    transaction = {
        "sender":    data["sender"],
        "recipient": data["recipient"],
        "amount":    data["amount"],
    }

    tx_id = mempool.add(transaction)
    if tx_id is None:
        return jsonify({"error": "Duplicate transaction"}), 400

    mempool.broadcast(transaction, network.peers)

    return jsonify({"tx_id": tx_id}), 201


@app.route('/mempool', methods=['GET'])
def get_mempool():
    """
    GET /mempool
    Return all pending transactions (useful for testing and debugging).
    """
    return jsonify({
        "pending":      mempool.to_list(),
        "pending_count": mempool.size,
    }), 200


# Node / peer endpoints

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    """
    POST /nodes/register
    Register one or more peer nodes.
    Request body: {"nodes": ["http://localhost:5001", ...]}
    Returns the full current peer list so the caller can discover other peers.
    """
    data = request.get_json()
    if not data or "nodes" not in data:
        return jsonify({"error": "Missing 'nodes' list"}), 400

    nodes = data["nodes"]
    if not isinstance(nodes, list):
        return jsonify({"error": "'nodes' must be a list"}), 400

    added = network.register_peers(nodes)
    # Keep consensus in sync with the updated peer set
    consensus.peers = network.peers

    return jsonify({
        "message": f"{added} new peer(s) registered.",
        "peers":   network.peer_list(),
    }), 201


@app.route('/nodes/resolve', methods=['POST'])
def resolve():
    """
    POST /nodes/resolve
    Trigger the longest-chain consensus algorithm.
    Fetches chains from all known peers and adopts the longest valid one.
    """
    replaced = consensus.resolve()

    return jsonify({
        "chain_updated": replaced,
        "height":        blockchain.height,
        "message":       "Chain replaced by longer peer chain." if replaced
                         else "Our chain is already the longest.",
    }), 200


@app.route('/peers', methods=['GET'])
def get_peers():
    """
    GET /peers
    Return all known peer URLs (useful for testing and debugging).
    """
    return jsonify({
        "peers": network.peer_list(),
        "count": network.peer_count,
    }), 200


# Main

def main():
    parser = argparse.ArgumentParser(description="NovaBlock Node")
    parser.add_argument("--port",       type=int, default=5000,
                        help="Port to listen on (default: 5000)")
    parser.add_argument("--host",       default="localhost",
                        help="Host to bind to (default: localhost)")
    parser.add_argument("--seed-peers", nargs="*", default=[],
                        help="Space-separated seed peer URLs to register on startup")
    args = parser.parse_args()

    self_url = f"http://{args.host}:{args.port}"

    # Register any seed peers provided at startup
    if args.seed_peers:
        network.register_peers(args.seed_peers)
        consensus.peers = network.peers
        print(f"[Node] Registered {len(args.seed_peers)} seed peer(s).")
        # Announce ourselves so peers know about us too
        network.announce(self_url)

    print(f"[Node] NovaBlock node starting at {self_url}")
    print(f"[Node] Known peers: {network.peer_list()}")
    print(f"[Node] Chain height: {blockchain.height} (StellarOrigin block ready)")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()