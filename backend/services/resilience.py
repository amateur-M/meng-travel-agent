"""External API resilience: retry + circuit breaker (P3.4).

Provides a shared circuit breaker registry and tenacity retry decorator
factory so Amap and QWeather calls get uniform resilience behaviour:
- Exponential backoff retry (3 attempts) on transient errors
- Circuit breaker: 5 consecutive failures → open for 30s → half-open probe
"""

import time
import logging
from typing import Any, Callable, TypeVar

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

logger = logging.getLogger("coupletrip")

T = TypeVar("T")


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open and calls are short-circuited."""


class CircuitBreaker:
    """Simple circuit breaker with closed / open / half-open states.

    After *failure_threshold* consecutive failures the breaker opens for
    *recovery_timeout* seconds. The next call after that enters half-open:
    a single success closes the breaker, a single failure re-opens it.
    """

    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self.recovery_timeout:
            # Transition to half-open: allow a probe call
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()
            logger.warning(
                "CircuitBreaker[%s] opened after %d consecutive failures",
                self.name,
                self._failures,
            )

    def call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute *fn* through the breaker, short-circuiting when open."""
        if self.is_open:
            raise CircuitBreakerOpen(f"CircuitBreaker[{self.name}] is open")
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result


# Shared breaker instances per external service
_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(name: str) -> CircuitBreaker:
    """Return (or create) the shared breaker for a named external service."""
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name)
    return _breakers[name]


def resilient_call(
    breaker_name: str,
    fn: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    **kwargs: Any,
) -> T:
    """Call *fn* with tenacity retry + circuit breaker.

    Retries on httpx.HTTPError and RuntimeError (Amap/QWeather raise
    RuntimeError on API-level failures). The circuit breaker short-
    circuits if the service has been consistently failing.
    """
    breaker = get_breaker(breaker_name)

    @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    def _attempt():
        return breaker.call(fn, *args, **kwargs)

    try:
        return _attempt()
    except CircuitBreakerOpen:
        raise
    except RetryError as exc:
        # Last attempt's exception is already reraised via reraise=True,
        # but guard just in case.
        raise exc.last_attempt.exception() if exc.last_attempt else RuntimeError("retry failed")


async def resilient_call_async(
    breaker_name: str,
    fn: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    **kwargs: Any,
) -> Any:
    """Async variant: call an async *fn* with retry + circuit breaker."""
    import asyncio

    breaker = get_breaker(breaker_name)

    async def _attempt():
        if breaker.is_open:
            raise CircuitBreakerOpen(f"CircuitBreaker[{breaker_name}] is open")
        try:
            result = await fn(*args, **kwargs)
        except Exception:
            breaker.record_failure()
            raise
        breaker.record_success()
        return result

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await _attempt()
        except CircuitBreakerOpen:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts:
                wait = min(2 ** (attempt - 1), 8)
                logger.info("resilient_call_async[%s] attempt %d failed, retrying in %ds", breaker_name, attempt, wait)
                await asyncio.sleep(wait)
    raise last_exc if last_exc else RuntimeError("retry failed")
