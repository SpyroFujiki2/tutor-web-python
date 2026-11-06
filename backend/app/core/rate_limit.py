from collections import OrderedDict
from math import ceil
from threading import Lock
from time import monotonic


class LoginRateLimiter:
    """Bounded, thread-safe per-IP limits for one application process."""

    def __init__(self, attempts: int = 10, window_seconds: int = 60, max_clients: int = 10000):
        if min(attempts, window_seconds, max_clients) <= 0:
            raise ValueError("Rate limit settings must be positive")
        self.attempts = attempts
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self._clients: OrderedDict[str, tuple[float, int]] = OrderedDict()
        self._lock = Lock()

    def consume(self, client: str) -> int | None:
        """Return Retry-After seconds if denied; otherwise consume one attempt."""
        with self._lock:
            now = monotonic()
            while self._clients and next(iter(self._clients.values()))[0] <= now:
                self._clients.popitem(last=False)
            window = self._clients.get(client)
            if window is None:
                if len(self._clients) >= self.max_clients:
                    return max(1, ceil(next(iter(self._clients.values()))[0] - now))
                window = (now + self.window_seconds, 0)
            deadline, count = window
            if count >= self.attempts:
                return max(1, ceil(deadline - now))
            self._clients[client] = (deadline, count + 1)
            return None
