import requests
from block import Block
from blockchain import Blockchain


class Consensus:
    def __init__(self, blockchain, mempool, peers):
        """
        Initialise the consensus engine.

        Args:
            blockchain (Blockchain): The local node's blockchain instance.
            mempool    (Mempool):    The local node's mempool instance.
            peers      (set):        Set of peer URLs e.g. {"http://localhost:5001"}.
        """
        self.blockchain = blockchain
        self.mempool    = mempool
        self.peers      = peers

    # ------------------------------------------------------------------
    # Chain fetching
    # ------------------------------------------------------------------

    def _fetch_chain(self, peer):
        """
        Fetch and reconstruct the blockchain from a peer node.

        Args:
            peer (str): Base URL of the peer e.g. "http://localhost:5001".

        Returns:
            Blockchain | None: Reconstructed Blockchain if successful, else None.
        """
        try:
            response = requests.get(f"{peer}/chain", timeout=5)
            if response.status_code == 200:
                chain_data = response.json().get("chain", [])
                return Blockchain.from_list(chain_data)
        except requests.exceptions.RequestException as e:
            print(f"[Consensus] Could not reach peer {peer}: {e}")
        return None

    # ------------------------------------------------------------------
    # Fork resolution — longest-chain rule
    # ------------------------------------------------------------------

    def resolve(self):
        """
        Query all known peers for their chains. If any peer has a longer
        valid chain than ours, replace our local chain with it.

        This implements the longest-chain consensus rule:
          - Fetch chains from all peers.
          - Validate each chain fully.
          - Adopt the longest valid chain found, if longer than our own.
          - If the chain is replaced, clear the mempool to avoid including
            transactions that may already be in the adopted chain.

        Returns:
            bool: True if our chain was replaced, False if ours was already
                  the longest valid chain.
        """
        best_chain  = self.blockchain.chain
        best_length = self.blockchain.height
        replaced    = False

        print(f"[Consensus] Starting resolve — our chain height: {best_length}")

        for peer in self.peers:
            print(f"[Consensus] Fetching chain from {peer}...")
            peer_blockchain = self._fetch_chain(peer)

            if peer_blockchain is None:
                continue  # peer unreachable, skip

            peer_length = peer_blockchain.height

            if peer_length > best_length:
                # Validate the peer's chain before accepting it
                if peer_blockchain.is_chain_valid(peer_blockchain.chain):
                    print(
                        f"[Consensus] Longer valid chain found at {peer} "
                        f"(height={peer_length}). Adopting."
                    )
                    best_chain  = peer_blockchain.chain
                    best_length = peer_length
                    replaced    = True
                else:
                    print(f"[Consensus] Chain from {peer} is invalid — discarding.")
            else:
                print(f"[Consensus] Chain from {peer} is not longer (height={peer_length}) — keeping ours.")

        if replaced:
            self.blockchain.chain = best_chain
            # Clear mempool — the adopted chain may already contain pending txns
            self.mempool.clear()
            print("[Consensus] Local chain replaced. Mempool cleared.")
        else:
            print("[Consensus] Our chain is authoritative — no replacement needed.")

        return replaced

    # ------------------------------------------------------------------
    # Block broadcast
    # ------------------------------------------------------------------

    def broadcast_block(self, block):
        """
        Broadcast a newly mined block to all known peers via their
        POST /blocks/new endpoint.

        Peers validate the block independently on receipt. Unreachable
        peers are logged and skipped — they will sync via /nodes/resolve
        when they come back online.

        Args:
            block (Block): The freshly mined block to broadcast.
        """
        for peer in self.peers:
            url = f"{peer}/blocks/new"
            try:
                response = requests.post(url, json=block.to_dict(), timeout=3)
                if response.status_code == 201:
                    print(f"[Consensus] Block {block.index} broadcast OK → {peer}")
                else:
                    print(
                        f"[Consensus] Block {block.index} broadcast unexpected "
                        f"status {response.status_code} → {peer}"
                    )
            except requests.exceptions.RequestException as e:
                print(f"[Consensus] Block broadcast failed → {peer} ({e})")

    def __repr__(self):
        return f"<Consensus peers={len(self.peers)} chain_height={self.blockchain.height}>"