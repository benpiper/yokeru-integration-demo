import asyncio
import time
from enum import StrEnum


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class BreakerOpenError(Exception):
    """Raised when a request is fast-failed because the breaker is OPEN."""


class CircuitBreaker:
    """Async-friendly circuit breaker.

    State machine:
      CLOSED ──(consecutive failures ≥ threshold)──▶ OPEN
      OPEN   ──(reset_timeout elapsed)──────────────▶ HALF_OPEN
      HALF_OPEN ──(probe succeeds)──────────────────▶ CLOSED
      HALF_OPEN ──(probe fails)─────────────────────▶ OPEN

    The breaker counts only transient/server failures, never permanent
    classification errors — those should be raised before reaching the breaker.
    """

    def __init__(self, name: str, failure_threshold: int, reset_timeout_s: float):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout_s = reset_timeout_s

        self._state: BreakerState = BreakerState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> BreakerState:
        return self._state

    async def call(self, fn, *args, **kwargs):
        async with self._lock:
            if self._state is BreakerState.OPEN:
                if self._opened_at is not None and (
                    time.monotonic() - self._opened_at >= self.reset_timeout_s
                ):
                    self._state = BreakerState.HALF_OPEN
                else:
                    raise BreakerOpenError(f"breaker {self.name!r} is OPEN")

        try:
            result = await fn(*args, **kwargs)
        except Exception:
            await self._on_failure()
            raise
        else:
            await self._on_success()
            return result

    async def _on_success(self) -> None:
        async with self._lock:
            self._consecutive_failures = 0
            if self._state is not BreakerState.CLOSED:
                self._state = BreakerState.CLOSED
                self._opened_at = None

    async def _on_failure(self) -> None:
        async with self._lock:
            self._consecutive_failures += 1
            if self._state is BreakerState.HALF_OPEN:
                self._state = BreakerState.OPEN
                self._opened_at = time.monotonic()
            elif self._consecutive_failures >= self.failure_threshold:
                self._state = BreakerState.OPEN
                self._opened_at = time.monotonic()
