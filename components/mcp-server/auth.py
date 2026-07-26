"""Bearer token helpers for MCP HTTP transport."""

from __future__ import annotations

import hmac
from typing import Optional


def extract_bearer_token(authorization_header: Optional[str]) -> Optional[str]:
    """Return the token from `Authorization: Bearer <token>`, or None."""
    if not authorization_header:
        return None

    parts = authorization_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        return None
    return parts[1]


def is_authorized(authorization_header: Optional[str], expected_token: str) -> bool:
    """True if the Bearer token matches expected_token (constant-time compare)."""
    if not expected_token:
        return False
    got = extract_bearer_token(authorization_header)
    if got is None:
        return False
    return hmac.compare_digest(got, expected_token)
