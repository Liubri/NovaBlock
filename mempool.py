import hashlib
import json
import requests


class Mempool:
    def __init__(self):
        """
        Initialise an empty mempool

        Transactions are stored in a dict keyed by their deterministic ID
        (SHA-256 of the transaction contents) to allow O(1) deduplication
        and removal.
        """
        self._pool = {}   # { tx_id: transaction_dict }

    # Internal helpers

    def _tx_id(self, transaction):
        """
        Compute a deterministic ID for a transaction dict

        Args:
            transaction (dict): e.g. {"sender": "Alice", "recipient": "Bob", "amount": 50}

        Returns:
            str: SHA-256 hex digest of the canonical JSON representation
        """
        tx_string = json.dumps(transaction, sort_keys=True)
        return hashlib.sha256(tx_string.encode()).hexdigest()

    # Core operations

    def add(self, transaction):
        """
        Add a transaction to the mempool

        Args:
            transaction (dict): Transaction with at least sender, recipient, amount

        Returns:
            str | None: The transaction ID if added, None if it was a duplicate.
        """
        tx_id = self._tx_id(transaction)

        if tx_id in self._pool:
            print(f"[Mempool] Duplicate transaction ignored: {tx_id[:12]}...")
            return None

        self._pool[tx_id] = transaction
        print(f"[Mempool] Transaction added: {tx_id[:12]}...  {transaction}")
        return tx_id

    def remove(self, transactions):
        """
        Remove a list of transactions from the mempool after they have been
        mined into a block

        Args:
            transactions (list): The transaction dicts included in a mined block.
        """
        for tx in transactions:
            tx_id = self._tx_id(tx)
            if tx_id in self._pool:
                del self._pool[tx_id]
                print(f"[Mempool] Transaction cleared after mining: {tx_id[:12]}...")

    def get_all(self):
        """
        Return all pending transactions as a list

        Returns:
            list: All pending transaction dicts
        """
        return list(self._pool.values())

    def clear(self):
        """Wipe the entire mempool"""
        self._pool.clear()
        print("[Mempool] Cleared.")

    # Broadcast

    def broadcast(self, transaction, peers):
        """
        Push a new transaction to all known peer nodes

        Args:
            transaction (dict): The transaction to broadcast
            peers       (set):  Set of peer URLs
        """
        for peer in peers:
            url = f"{peer}/transactions/new"
            try:
                response = requests.post(url, json=transaction, timeout=3)
                if response.status_code == 201:
                    print(f"[Mempool] Broadcast OK → {peer}")
                else:
                    print(f"[Mempool] Broadcast unexpected status {response.status_code} → {peer}")
            except requests.exceptions.RequestException as e:
                print(f"[Mempool] Broadcast failed → {peer} ({e})")

    # Properties

    @property
    def size(self):
        """Return the number of pending transactions."""
        return len(self._pool)

    # Serialisation helpers

    def to_list(self):
        """Return pending transactions as a list of dicts for API responses."""
        return self.get_all()

    def __repr__(self):
        return f"<Mempool pending={self.size}>"