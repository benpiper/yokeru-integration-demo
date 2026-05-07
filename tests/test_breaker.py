import asyncio

import pytest

from src.breaker import BreakerOpenError, BreakerState, CircuitBreaker


async def _boom():
    raise RuntimeError("upstream down")


async def _ok():
    return "ok"


@pytest.mark.asyncio
async def test_opens_after_threshold_failures():
    cb = CircuitBreaker("t", failure_threshold=3, reset_timeout_s=10.0)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await cb.call(_boom)
    assert cb.state is BreakerState.OPEN
    with pytest.raises(BreakerOpenError):
        await cb.call(_ok)


@pytest.mark.asyncio
async def test_half_open_probe_success_closes():
    cb = CircuitBreaker("t", failure_threshold=2, reset_timeout_s=0.05)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(_boom)
    assert cb.state is BreakerState.OPEN

    await asyncio.sleep(0.06)
    result = await cb.call(_ok)
    assert result == "ok"
    assert cb.state is BreakerState.CLOSED


@pytest.mark.asyncio
async def test_half_open_probe_failure_reopens():
    cb = CircuitBreaker("t", failure_threshold=2, reset_timeout_s=0.05)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(_boom)

    await asyncio.sleep(0.06)
    with pytest.raises(RuntimeError):
        await cb.call(_boom)
    assert cb.state is BreakerState.OPEN
