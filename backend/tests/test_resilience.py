"""Tests for P3.4 external API resilience: retry + circuit breaker."""

import pytest

from services.resilience import (
    CircuitBreaker,
    CircuitBreakerOpen,
    resilient_call,
    get_breaker,
)


class TestCircuitBreaker:
    """CircuitBreaker opens after 5 consecutive failures, recovers after 30s."""

    def test_closed_by_default(self):
        cb = CircuitBreaker("test-svc")
        assert not cb.is_open

    def test_opens_after_threshold(self):
        cb = CircuitBreaker("test-open", failure_threshold=5, recovery_timeout=30.0)
        for _ in range(5):
            cb.record_failure()
        assert cb.is_open

    def test_not_open_below_threshold(self):
        cb = CircuitBreaker("test-below", failure_threshold=5, recovery_timeout=30.0)
        for _ in range(4):
            cb.record_failure()
        assert not cb.is_open

    def test_success_resets_failures(self):
        cb = CircuitBreaker("test-reset", failure_threshold=5, recovery_timeout=30.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert not cb.is_open
        # After reset, 4 more failures should NOT open (count restarted)
        for _ in range(4):
            cb.record_failure()
        assert not cb.is_open

    def test_call_raises_when_open(self):
        cb = CircuitBreaker("test-shortcircuit", failure_threshold=1, recovery_timeout=999.0)
        cb.record_failure()  # 1 failure → open
        with pytest.raises(CircuitBreakerOpen):
            cb.call(lambda: 1)

    def test_call_passes_through_on_success(self):
        cb = CircuitBreaker("test-success")
        result = cb.call(lambda x: x * 2, 21)
        assert result == 42
        assert not cb.is_open


class TestResilientCall:
    """resilient_call retries on failure, short-circuits when breaker open."""

    def test_success_no_retry(self):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = resilient_call("test-success-svc", fn, max_attempts=3)
        assert result == "ok"
        assert call_count == 1

    def test_retries_then_succeeds(self):
        attempts = 0

        def fn():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RuntimeError("transient")
            return "recovered"

        # Use a fresh breaker to avoid cross-test state
        from services.resilience import _breakers
        _breakers.pop("test-retry-svc", None)

        result = resilient_call("test-retry-svc", fn, max_attempts=3)
        assert result == "recovered"
        assert attempts == 3

    def test_exhausted_retries_raises(self):
        from services.resilience import _breakers
        _breakers.pop("test-exhaust-svc", None)

        with pytest.raises(RuntimeError):
            resilient_call("test-exhaust-svc", lambda: (_ for _ in ()).throw(RuntimeError("boom")), max_attempts=2)

    def test_breaker_short_circuits_after_repeated_failures(self):
        from services.resilience import _breakers
        svc = "test-circuit-svc"
        _breakers.pop(svc, None)

        breaker = get_breaker(svc)
        breaker.failure_threshold = 5

        # Fail 5 times to trip the breaker
        for _ in range(5):
            try:
                resilient_call(svc, lambda: (_ for _ in ()).throw(RuntimeError("fail")), max_attempts=1)
            except RuntimeError:
                pass

        assert breaker.is_open
        # Next call should short-circuit without invoking fn
        def fn():
            raise AssertionError("should not be called when breaker open")

        with pytest.raises(CircuitBreakerOpen):
            resilient_call(svc, fn, max_attempts=1)
