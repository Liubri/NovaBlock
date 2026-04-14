#!/usr/bin/env python3
"""
client.py: CLI tool for interacting with NovaBlock nodes.
"""

import argparse
import requests
import sys


class BlockchainClient:
    def __init__(self, node_url: str):
        """
        Initialise the client pointed at a single NovaBlock node.

        Args:
            node_url (str): Base URL of the target node e.g. "http://localhost:5000".
        """
        self.node_url = node_url.rstrip('/')
        self.timeout = 5

    # HTTP helpers

    def _request(self, method: str, endpoint: str, json_data=None):
        """
        Send an HTTP request to the node and return the parsed JSON response.

        Args:
            method    (str):  HTTP verb — "GET" or "POST".
            endpoint  (str):  API path e.g. "/chain".
            json_data (dict): Optional JSON payload for POST requests.

        Returns:
            dict | None: Parsed JSON response body, or None on error.
        """
        url = f"{self.node_url}{endpoint}"
        try:
            if method == 'GET':
                response = requests.get(url, timeout=self.timeout)
            elif method == 'POST':
                response = requests.post(url, json=json_data, timeout=self.timeout)
            else:
                print(f"Error: Unknown method {method}")
                return None

            if response.status_code in [200, 201]:
                return response.json()
            else:
                print(f"Error: Status {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            return None

    # API wrappers

    def get_chain(self):
        """Fetch the full blockchain from the node."""
        return self._request('GET', '/chain')

    def mine(self):
        """Trigger the node to mine all pending mempool transactions."""
        return self._request('POST', '/mine')

    def submit_transaction(self, sender: str, recipient: str, amount: float):
        """
        Submit a new transaction to the node's mempool.

        Args:
            sender    (str):   Sender identifier.
            recipient (str):   Recipient identifier.
            amount    (float): Amount to transfer.

        Returns:
            dict | None: Response containing tx_id, or None on error.
        """
        data = {'sender': sender, 'recipient': recipient, 'amount': amount}
        return self._request('POST', '/transactions/new', json_data=data)

    def get_mempool(self):
        """Fetch all pending transactions from the node's mempool."""
        return self._request('GET', '/mempool')

    def get_peers(self):
        """Fetch the list of known peer nodes."""
        return self._request('GET', '/peers')

    def register_peers(self, peer_urls: list):
        """
        Register one or more peer nodes with the target node.

        Args:
            peer_urls (list): List of peer base URLs to register.

        Returns:
            dict | None: Response containing the updated peer list, or None on error.
        """
        data = {'nodes': peer_urls}
        return self._request('POST', '/nodes/register', json_data=data)

    def resolve(self):
        """Trigger the longest-chain consensus resolution on the node."""
        return self._request('POST', '/nodes/resolve')

    # Display helpers

    def print_chain(self, result: dict):
        """
        Pretty-print a blockchain response to stdout.

        Args:
            result (dict): Response from GET /chain.
        """
        chain = result.get('chain', [])
        height = result.get('height', 0)
        print(f"\n=== Blockchain (height={height}) ===")
        for block in chain:
            print(f"  [{block['index']}] {block['hash'][:16]}... txns={len(block['transactions'])}")
        print()

    def print_mempool(self, result: dict):
        """
        Pretty-print a mempool response to stdout.

        Args:
            result (dict): Response from GET /mempool.
        """
        pending = result.get('pending', [])
        print(f"\n=== Mempool ({len(pending)} pending) ===")
        for tx in pending:
            print(f"  {tx.get('sender','?')} → {tx.get('recipient','?')}: {tx.get('amount','?')}")
        print()

    def print_peers(self, result: dict):
        """
        Pretty-print a peer list response to stdout.

        Args:
            result (dict): Response from GET /peers.
        """
        peers = result.get('peers', [])
        print(f"\n=== Peers ({len(peers)}) ===")
        for peer in peers:
            print(f"  {peer}")
        print()


def main():
    parser = argparse.ArgumentParser(description='NovaBlock Client')
    parser.add_argument('--node', required=True, help='Node URL')
    subparsers = parser.add_subparsers(dest='command')

    sp_tx = subparsers.add_parser('submit-tx')
    sp_tx.add_argument('sender')
    sp_tx.add_argument('recipient')
    sp_tx.add_argument('amount', type=float)

    subparsers.add_parser('mine')
    subparsers.add_parser('get-chain')
    subparsers.add_parser('show-mempool')
    subparsers.add_parser('show-peers')

    sp_register = subparsers.add_parser('register-peers')
    sp_register.add_argument('peers', nargs='+')

    subparsers.add_parser('resolve')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = BlockchainClient(args.node)

    if args.command == 'submit-tx':
        result = client.submit_transaction(args.sender, args.recipient, args.amount)
        if result:
            print(f"Transaction submitted: {result.get('tx_id', 'unknown')[:16]}...")

    elif args.command == 'mine':
        result = client.mine()
        if result:
            print(f"Block mined: {result['hash'][:16]}...")

    elif args.command == 'get-chain':
        result = client.get_chain()
        if result:
            client.print_chain(result)

    elif args.command == 'show-mempool':
        result = client.get_mempool()
        if result:
            client.print_mempool(result)

    elif args.command == 'show-peers':
        result = client.get_peers()
        if result:
            client.print_peers(result)

    elif args.command == 'register-peers':
        result = client.register_peers(args.peers)
        if result:
            print(f"Peers registered")

    elif args.command == 'resolve':
        result = client.resolve()
        if result:
            print(f"Consensus: height={result.get('height')}")


if __name__ == '__main__':
    main()
