"""Rate limit em memória (janela deslizante) por cliente e categoria de rota."""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable

_MAX_KEYS = 10_000


class SlidingWindowRateLimiter:
    """Adequado a uma instância; com várias réplicas use um limitador compartilhado."""

    def __init__(
        self, limit: int, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> int | None:
        """Registra uma tentativa; devolve segundos de espera se o limite foi excedido."""
        now = self._clock()
        cutoff = now - self.window
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, math.ceil(hits[0] + self.window - now))
            hits.append(now)
            if len(self._hits) > _MAX_KEYS:
                self._prune(cutoff)
            return None

    def _prune(self, cutoff: float) -> None:
        stale = [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]
        for key in stale:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
