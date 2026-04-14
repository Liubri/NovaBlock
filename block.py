import hashlib
import json
import time

class Block:
    def __init__(self, index, transactions, previous_hash, nonce=0, timestamp=None):
        """
        Args:
            index       (int):  Position of this block in the chain
            transactions(list): List of transaction dicts included in this block
            previous_hash(str): SHA-256 hash of the preceding block
            nonce       (int):  Proof-of-Work counter; incremented during mining
            timestamp   (float):Unix timestamp; defaults to current time if omitted
        """
        self.index         = index
        self.timestamp     = timestamp if timestamp is not None else time.time()
        self.transactions  = transactions
        self.previous_hash = previous_hash
        self.nonce         = nonce
        self.hash          = self.compute_hash()

    # Hashing

    def compute_hash(self):
        """
        Serialise the block's core fields to a JSON string and return its SHA-256 hex

        sort_keys=True guarantees the same byte order on every node so
        that independently computed hashes always agree
        """
        block_data = {
            "index":         self.index,
            "timestamp":     self.timestamp,
            "transactions":  self.transactions,
            "previous_hash": self.previous_hash,
            "nonce":         self.nonce,
        }
        block_string = json.dumps(block_data, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    # Validation

    def is_valid(self, difficulty):
        """
        Check that this block's stored hash:
          1. Actually matches a fresh recomputation of the block data
          2. Satisfies the proof of work target (ie: N leading zeros)

        Args:
            difficulty (int): Number of leading zero characters required

        Returns:
            bool: True if the block is structurally sound and PoW valid
        """
        recomputed = self.compute_hash()

        if self.hash != recomputed:
            print(f"[Block {self.index}] Hash mismatch: data may have been tampered with.")
            return False

        if not self.hash.startswith("0" * difficulty):
            print(f"[Block {self.index}] Hash does not meet difficulty target.")
            return False

        return True

    # Serialisation helpers

    def to_dict(self):
        """Return a plain dict so the block can be JSON serialised over HTTP"""
        return {
            "index":         self.index,
            "timestamp":     self.timestamp,
            "transactions":  self.transactions,
            "previous_hash": self.previous_hash,
            "nonce":         self.nonce,
            "hash":          self.hash,
        }

    @classmethod
    def from_dict(cls, data):
        """
        Reconstruct a Block from a dict received over the network
        The stored hash is preserved so peers can verify it without re mining
        """
        block = cls(
            index         = data["index"],
            transactions  = data["transactions"],
            previous_hash = data["previous_hash"],
            nonce         = data["nonce"],
            timestamp     = data["timestamp"],
        )
        block.hash = data["hash"]   # restore the original hash
        return block

    def __repr__(self):
        return (
            f"<Block index={self.index} "
            f"nonce={self.nonce} "
            f"hash={self.hash[:12]}...>"
        )