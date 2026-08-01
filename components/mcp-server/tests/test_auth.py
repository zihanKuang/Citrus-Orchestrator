"""
Bearer token auth — the gate in front of the in-cluster HTTP MCP endpoint.
These are exactly the cases that matter for the RBAC/security story:
wrong scheme, missing token, wrong token, and the happy path.
"""
from mcp_server.auth import extract_bearer_token, is_authorized


def test_extract_bearer_token_happy_path():
    assert extract_bearer_token("Bearer secret-token-123") == "secret-token-123"


def test_extract_bearer_token_is_case_insensitive_on_scheme():
    assert extract_bearer_token("bearer secret-token-123") == "secret-token-123"


def test_extract_bearer_token_rejects_missing_header():
    assert extract_bearer_token(None) is None
    assert extract_bearer_token("") is None


def test_extract_bearer_token_rejects_wrong_scheme():
    assert extract_bearer_token("Basic dXNlcjpwYXNz") is None


def test_extract_bearer_token_rejects_missing_token_value():
    assert extract_bearer_token("Bearer") is None
    assert extract_bearer_token("Bearer ") is None


def test_is_authorized_true_when_token_matches():
    assert is_authorized("Bearer correct-token", "correct-token") is True


def test_is_authorized_false_when_token_does_not_match():
    assert is_authorized("Bearer wrong-token", "correct-token") is False


def test_is_authorized_false_when_expected_token_is_unset():
    # A server misconfigured with an empty secret must fail closed, not open.
    assert is_authorized("Bearer anything", "") is False
    assert is_authorized("Bearer anything", None) is False


def test_is_authorized_false_when_header_missing():
    assert is_authorized(None, "correct-token") is False
