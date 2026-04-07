from block import Block


class Blockchain:
    DIFFICULTY = 3  # Number of leading zeros required for a valid PoW hash

    def __init__(self):
        """
        Initialise the chain with the hardcoded genesis block.
        The genesis block has no real previous hash — it uses a string of
        64 zeros as a sentinel value, as specified in the system design.
        """
        self.chain = []
        self._create_genesis_block()

    # ------------------------------------------------------------------
    # Genesis block
    # ------------------------------------------------------------------

    def _create_genesis_block(self):
        """
        Build and mine the genesis block (index=0).
        It is hardcoded with:
          - an empty transaction list
          - previous_hash of "0" * 64
          - timestamp fixed to 0 so every node produces the identical block
        """
        genesis = Block(
            index=0,
            transactions=[],
            previous_hash="0" * 64,
            timestamp=0,
        )
        genesis.hash = self._mine_block(genesis)
        self.chain.append(genesis)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def last_block(self):
        """Return the most recently added block."""
        return self.chain[-1]

    @property
    def height(self):
        """Return the number of blocks in the chain (including genesis)."""
        return len(self.chain)

    # ------------------------------------------------------------------
    # Mining (Proof of Work)
    # ------------------------------------------------------------------

    def _mine_block(self, block):
        """
        Proof-of-Work loop: increment the block's nonce until its SHA-256
        hash starts with DIFFICULTY leading zeros.

        Args:
            block (Block): The block to mine (mutated in place via nonce).

        Returns:
            str: The winning hash that satisfies the difficulty target.
        """
        block.nonce = 0
        computed = block.compute_hash()

        while not computed.startswith("0" * self.DIFFICULTY):
            block.nonce += 1
            computed = block.compute_hash()

        print(f"[Mining] Block {block.index} mined — nonce={block.nonce} hash={computed[:16]}...")
        return computed

    def mine_pending_transactions(self, transactions):
        """
        Create a new block from the given transaction list, mine it, and
        append it to the chain.

        Args:
            transactions (list): Transactions to include (taken from mempool).

        Returns:
            Block: The newly mined and appended block.
        """
        new_block = Block(
            index=self.height,
            transactions=transactions,
            previous_hash=self.last_block.hash,
        )
        new_block.hash = self._mine_block(new_block)
        self.chain.append(new_block)
        return new_block

    # ------------------------------------------------------------------
    # Block addition (from network peers)
    # ------------------------------------------------------------------

    def add_block(self, block):
        """
        Validate and append a block received from a peer.

        Checks:
          1. The block's previous_hash matches our current last block's hash.
          2. The block itself is structurally valid (hash integrity + PoW).

        Args:
            block (Block): A Block reconstructed from a peer's JSON payload.

        Returns:
            bool: True if the block was accepted and appended, False otherwise.
        """
        if block.previous_hash != self.last_block.hash:
            print(f"[Chain] Rejected block {block.index} — previous_hash mismatch.")
            return False

        if not block.is_valid(self.DIFFICULTY):
            print(f"[Chain] Rejected block {block.index} — failed validation.")
            return False

        self.chain.append(block)
        print(f"[Chain] Accepted block {block.index} from peer.")
        return True

    # ------------------------------------------------------------------
    # Chain validation
    # ------------------------------------------------------------------

    def is_chain_valid(self, chain=None):
        """
        Walk every block in the chain and verify:
          1. Each block's stored hash matches a fresh recomputation.
          2. Each block's previous_hash matches the actual hash of the prior block.
          3. Every block satisfies the PoW difficulty target.

        Args:
            chain (list, optional): A list of Block objects to validate.
                                    Defaults to self.chain if omitted.

        Returns:
            bool: True if the entire chain is valid.
        """
        chain = chain or self.chain

        for i in range(1, len(chain)):
            current  = chain[i]
            previous = chain[i - 1]

            # Check hash integrity
            if current.hash != current.compute_hash():
                print(f"[Validation] Block {i} hash is invalid.")
                return False

            # Check chain linkage
            if current.previous_hash != previous.hash:
                print(f"[Validation] Block {i} is not linked to block {i - 1}.")
                return False

            # Check PoW
            if not current.hash.startswith("0" * self.DIFFICULTY):
                print(f"[Validation] Block {i} does not meet difficulty target.")
                return False

        return True

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_list(self):
        """Serialise the full chain to a list of dicts for HTTP responses."""
        return [block.to_dict() for block in self.chain]

    @classmethod
    def from_list(cls, chain_data):
        """
        Reconstruct a Blockchain from a list of block dicts received over
        the network. Used by consensus.py when evaluating a peer's chain.

        Args:
            chain_data (list): List of block dicts from a peer's /chain endpoint.

        Returns:
            Blockchain: A new Blockchain instance with the reconstructed chain.
        """
        bc = cls.__new__(cls)   # skip __init__ so we don't auto-create genesis
        bc.chain = [Block.from_dict(b) for b in chain_data]
        return bc

    def __repr__(self):
        return f"<Blockchain height={self.height} tip={self.last_block.hash[:12]}...>"