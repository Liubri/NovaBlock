#!/usr/bin/env python3
"""
Client: CLI tool for interacting with NovaBlock nodes
"""

import argparse
import requests
import sys


class BlockchainClient:
    def __init__(self, node_url: str):
        self.node_url = node_url.rstrip('/')
        self.timeout = 5

    def _request(self, method: str, endpoint: str, json_data=None):
        """Make HTTP request and handle errors"""
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

    def get_chain(self):
        return self._request('GET', '/chain')

    def mine(self):
        return self._request('POST', '/mine')

    def submit_transaction(self, sender: str, recipient: str, amount: float):
        data = {'sender': sender, 'recipient': recipient, 'amount': amount}
        return self._request('POST', '/transactions/new', json_data=data)

    def get_mempool(self):
        return self._request('GET', '/mempool')

    def get_peers(self):
        return self._request('GET', '/peers')

    def register_peers(self, peer_urls: list):
        data = {'nodes': peer_urls}
        return self._request('POST', '/nodes/register', json_data=data)

    def resolve(self):
        return self._request('POST', '/nodes/resolve')

    def print_chain(self, result: dict):
        chain = result.get('chain', [])
        height = result.get('height', 0)
        print(f"\n=== Blockchain (height={height}) ===")
        for block in chain:
            print(f"  [{block['index']}] {block['hash'][:16]}... txns={len(block['transactions'])}")
        print()

    def print_mempool(self, result: dict):
        pending = result.get('pending', [])
        print(f"\n=== Mempool ({len(pending)} pending) ===")
        for tx in pending:
            print(f"  {tx.get('sender','?')} → {tx.get('recipient','?')}: {tx.get('amount','?')}")
        print()

    def print_peers(self, result: dict):
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
