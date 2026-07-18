"""
Retry utilities

Inspired by Cluade-Code/services/api/withRetry.ts
"""
import random


def get_retry_delay(
    attempt: int,
    base_delay_ms: int = 500,
    max_delay_ms: int = 32000,
    jitter_factor: float = 0.25,
) -> float:
    """
    Calculate retry delay with exponential backoff and jitter
    
    Inspired by Cluade-Code's getRetryDelay function which adds jitter
    to avoid thundering herd problem.
    
    Args:
        attempt: Current attempt number (1-indexed)
        base_delay_ms: Base delay in milliseconds
        max_delay_ms: Maximum delay cap
        jitter_factor: Random jitter factor (0-1)
        
    Returns:
        Delay in seconds
    """
    # Exponential backoff
    base_delay = min(
        base_delay_ms * (2 ** (attempt - 1)),
        max_delay_ms
    )
    
    # Add jitter (Cluade-Code: const jitter = Math.random() * 0.25 * baseDelay)
    jitter = random.random() * jitter_factor * base_delay
    
    # Return in seconds
    return (base_delay + jitter) / 1000.0
