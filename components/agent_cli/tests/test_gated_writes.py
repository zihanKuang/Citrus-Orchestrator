"""Gated writes — deny by default, audit on both paths. No cluster."""
from pathlib import Path

from agent_cli.gated_writes import audit, decide, has_live_evidence


def test_no_evidence_blocks_write():
    reason = decide(
        "restart_deployment",
        {"name": "frontend"},
        {"tool_calls": {}},
        interactive=True,
        approve_fn=lambda *_: True,
    )
    assert reason.startswith("DENIED")
    assert "evidence" in reason.lower()


def test_non_interactive_blocks_even_with_evidence():
    reason = decide(
        "restart_deployment",
        {"name": "frontend"},
        {"tool_calls": {"list_pods": 1}},
        interactive=False,
        approve_fn=None,
    )
    assert "non-interactive" in reason


def test_human_no_blocks():
    reason = decide(
        "scale_deployment",
        {"name": "frontend", "replicas": 2},
        {"tool_calls": {"get_recent_events": 1}},
        interactive=True,
        approve_fn=lambda *_: False,
    )
    assert "rejected" in reason


def test_human_yes_allows():
    reason = decide(
        "restart_deployment",
        {"name": "frontend"},
        {"tool_calls": {"list_pods": 1, "validate_recovery": 1}},
        interactive=True,
        approve_fn=lambda *_: True,
    )
    assert reason == ""


def test_read_tools_are_not_gated():
    reason = decide(
        "list_pods",
        {},
        {"tool_calls": {}},
        interactive=False,
    )
    assert reason == ""


def test_has_live_evidence():
    assert not has_live_evidence({"tool_calls": {"restart_deployment": 1}})
    assert has_live_evidence({"tool_calls": {"list_pods": 1}})


def test_rollback_is_gated_non_interactive():
    reason = decide(
        "rollback_deployment",
        {"name": "frontend"},
        {"tool_calls": {"list_pods": 1}},
        interactive=False,
    )
    assert "non-interactive" in reason


def test_audit_appends_jsonl(tmp_path: Path):
    path = tmp_path / "writes.jsonl"
    audit(
        tool_name="restart_deployment",
        arguments={"name": "frontend"},
        decision="denied",
        result="DENIED: human rejected the write (or no approval).",
        path=path,
    )
    text = path.read_text(encoding="utf-8")
    assert "restart_deployment" in text
    assert "denied" in text
