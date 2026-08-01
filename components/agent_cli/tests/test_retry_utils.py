"""Exponential backoff math — the actual formula, not a mock of it."""
import random

import pytest

from agent_cli.retry_utils import get_retry_delay


def test_delay_grows_exponentially_before_hitting_the_cap():
    random.seed(0)  # jitter is random; pin it so the base trend is checkable
    delays = [get_retry_delay(attempt=a, base_delay_ms=500, max_delay_ms=32000) for a in (1, 2, 3)]
    # each attempt should be roughly double the previous (base_delay doubles;
    # jitter only adds up to 25% on top), so ordering must hold even with jitter.
    assert delays[0] < delays[1] < delays[2]


def test_delay_is_capped_at_max_delay_ms():
    # attempt=10 would be 500 * 2**9 = 256_000ms without a cap — must clamp to 32s (+jitter).
    delay = get_retry_delay(attempt=10, base_delay_ms=500, max_delay_ms=32000, jitter_factor=0.25)
    assert delay <= 32.0 * 1.25  # capped base + at most 25% jitter on top of the cap


def test_delay_never_goes_below_the_uncapped_base():
    for attempt in range(1, 6):
        delay = get_retry_delay(attempt=attempt, base_delay_ms=500, max_delay_ms=32000, jitter_factor=0.0)
        expected_base_seconds = min(500 * (2 ** (attempt - 1)), 32000) / 1000.0
        assert delay == pytest.approx(expected_base_seconds)


def test_zero_jitter_factor_is_deterministic():
    d1 = get_retry_delay(attempt=3, jitter_factor=0.0)
    d2 = get_retry_delay(attempt=3, jitter_factor=0.0)
    assert d1 == d2
