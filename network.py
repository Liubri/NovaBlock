import requests


class Network:
    def __init__(self):
        """
        Initialise the peer registry.

        Peers are stored as a set of base URLs to automatically
        deduplicate repeated registrations.
        e.g. {"http://localhost:5001", "http://localhost:5002"}
        """
        self.peers = set()

    # ------------------------------------------------------------------
    # Peer registration
    # ------------------------------------------------------------------

    def register_peer(self, address):
        """
        Add a peer to the known peer set.

        Normalises the address to ensure consistent formatting —
        strips trailing slashes so "http://localhost:5001/" and
        "http://localhost:5001" are treated as the same peer.

        Args:
            address (str): Full base URL of the peer node.

        Returns:
            bool: True if the peer was newly added, False if already known.
        """
        normalised = address.rstrip("/")

        if normalised in self.peers:
            print(f"[Network] Peer already known: {normalised}")
            return False

        self.peers.add(normalised)
        print(f"[Network] Peer registered: {normalised} (total peers: {len(self.peers)})")
        return True

    def register_peers(self, addresses):
        """
        Register multiple peers at once.

        Args:
            addresses (list): List of peer base URL strings.

        Returns:
            int: Number of newly added peers.
        """
        added = sum(1 for addr in addresses if self.register_peer(addr))
        return added

    def remove_peer(self, address):
        """
        Remove a peer from the registry (e.g. after repeated failures).

        Args:
            address (str): Base URL of the peer to remove.

        Returns:
            bool: True if removed, False if peer was not registered.
        """
        normalised = address.rstrip("/")
        if normalised in self.peers:
            self.peers.discard(normalised)
            print(f"[Network] Peer removed: {normalised}")
            return True
        return False

    # ------------------------------------------------------------------
    # Peer discovery — announce self to peers
    # ------------------------------------------------------------------

    def announce(self, self_url):
        """
        Announce this node's existence to all known peers by registering
        with each peer's POST /nodes/register endpoint.

        This enables bidirectional discovery — after calling announce(),
        peers know about us without us needing to be manually registered
        on each one.

        Args:
            self_url (str): This node's own base URL e.g. "http://localhost:5000".
        """
        for peer in self.peers:
            url = f"{peer}/nodes/register"
            try:
                response = requests.post(url, json={"nodes": [self_url]}, timeout=3)
                if response.status_code == 201:
                    print(f"[Network] Announced self to {peer}")
                else:
                    print(f"[Network] Announce unexpected status {response.status_code} → {peer}")
            except requests.exceptions.RequestException as e:
                print(f"[Network] Announce failed → {peer} ({e})")

    # ------------------------------------------------------------------
    # Generic broadcast helpers
    # ------------------------------------------------------------------

    def broadcast_get(self, endpoint):
        """
        Send a GET request to all peers at the given endpoint and collect
        their responses.

        Args:
            endpoint (str): Path to request e.g. "/chain".

        Returns:
            list: List of (peer_url, response_json) tuples for successful responses.
        """
        results = []
        for peer in self.peers:
            url = f"{peer}{endpoint}"
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    results.append((peer, response.json()))
                    print(f"[Network] GET {endpoint} OK ← {peer}")
                else:
                    print(f"[Network] GET {endpoint} status {response.status_code} ← {peer}")
            except requests.exceptions.RequestException as e:
                print(f"[Network] GET {endpoint} failed ← {peer} ({e})")
        return results

    def broadcast_post(self, endpoint, payload):
        """
        Send a POST request with a JSON payload to all peers at the given
        endpoint.

        Args:
            endpoint (str):  Path to post to e.g. "/transactions/new".
            payload  (dict): JSON-serialisable payload to send.

        Returns:
            list: List of peer URLs that responded with a 2xx status code.
        """
        successes = []
        for peer in self.peers:
            url = f"{peer}{endpoint}"
            try:
                response = requests.post(url, json=payload, timeout=3)
                if 200 <= response.status_code < 300:
                    successes.append(peer)
                    print(f"[Network] POST {endpoint} OK → {peer}")
                else:
                    print(f"[Network] POST {endpoint} status {response.status_code} → {peer}")
            except requests.exceptions.RequestException as e:
                print(f"[Network] POST {endpoint} failed → {peer} ({e})")
        return successes

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def peer_count(self):
        """Return the number of currently registered peers."""
        return len(self.peers)

    def peer_list(self):
        """Return peers as a sorted list for consistent API responses."""
        return sorted(self.peers)

    # ------------------------------------------------------------------
    # Specific broadcast methods for blocks and transactions
    # ------------------------------------------------------------------

    def broadcast_block(self, block_dict):
        """
        Broadcast a mined block to all known peers via POST /blocks/new.

        Args:
            block_dict (dict): Block data to broadcast.

        Returns:
            list: Peer URLs that accepted the block.
        """
        return self.broadcast_post("/blocks/new", block_dict)

    def broadcast_transaction(self, transaction_dict):
        """
        Broadcast a transaction to all known peers via POST /transactions/new.

        Args:
            transaction_dict (dict): Transaction data to broadcast.

        Returns:
            list: Peer URLs that accepted the transaction.
        """
        return self.broadcast_post("/transactions/new", transaction_dict)

    def fetch_chain(self, peer_url):
        """
        Fetch the full blockchain from a specific peer.

        Args:
            peer_url (str): URL of the peer to fetch from.

        Returns:
            dict: Response from GET /chain, or None on failure.
        """
        url = f"{peer_url}/chain"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"[Network] Fetched chain from {peer_url}")
                return response.json()
            else:
                print(f"[Network] Failed to fetch chain from {peer_url}: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"[Network] Failed to fetch chain from {peer_url}: {e}")
            return None

    def __repr__(self):
        return f"<Network peers={self.peer_count}>"