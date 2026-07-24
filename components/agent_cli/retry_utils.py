"""Exponential backoff with jitter for tool/LLM retries."""

import random


def get_retry_delay(
    attempt: int,
    base_delay_ms: int = 500,
    max_delay_ms: int = 32000,
    jitter_factor: float = 0.25,
) -> float:
    """Return delay in seconds for the given 1-based attempt."""
    base_delay = min(base_delay_ms * (2 ** (attempt - 1)), max_delay_ms)
    jitter = random.random() * jitter_factor * base_delay
    return (base_delay + jitter) / 1000.0
