"""Human gate + audit trail for low-risk write tools.

The MCP tools can mutate the cluster. This module is the CLI-side lock:
evidence already gathered this run, y/n on a TTY, then a JSONL audit line.
Full automation is intentionally not implemented.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_AUDIT_PATH = _REPO_ROOT / "data" / "audit" / "writes.jsonl"

GATED_TOOLS = frozenset({
    "restart_deployment",
    "scale_deployment",
    "rollback_deployment",
})
EVIDENCE_BEFORE_WRITE = (
    "list_pods",
    "get_recent_events",
    "get_pod_status",
    "get_pod_logs",
    "query_prometheus",
    "validate_recovery",
)


ApproveFn = Callable[[str, Dict[str, Any]], bool]


def has_live_evidence(stats: Dict[str, Any]) -> bool:
    tools = stats.get("tool_calls") or {}
    return any(tools.get(name, 0) > 0 for name in EVIDENCE_BEFORE_WRITE)


def format_proposal(tool_name: str, arguments: Dict[str, Any]) -> str:
    args = ", ".join(f"{k}={v!r}" for k, v in sorted((arguments or {}).items()))
    return f"{tool_name}({args})"


def confirm_tty(tool_name: str, arguments: Dict[str, Any]) -> bool:
    prompt = f"Approve gated write {format_proposal(tool_name, arguments)}? [y/N] "
    try:
        answer = input(prompt)
    except EOFError:
        return False
    return answer.strip().lower() in {"y", "yes"}


def decide(
    tool_name: str,
    arguments: Dict[str, Any],
    stats: Dict[str, Any],
    *,
    interactive: bool,
    approve_fn: Optional[ApproveFn] = None,
) -> str:
    """Return empty string to allow, or a DENIED reason to block."""
    if tool_name not in GATED_TOOLS:
        return ""
    if not has_live_evidence(stats):
        return (
            "DENIED: gather live evidence first "
            "(list_pods / get_recent_events / …). Write tools stay locked until then."
        )
    checker = approve_fn
    if checker is None:
        if not interactive:
            return "DENIED: non-interactive session — write tools require an explicit y/n."
        checker = confirm_tty
    if not checker(tool_name, arguments):
        return "DENIED: human rejected the write (or no approval)."
    return ""


def audit(
    *,
    tool_name: str,
    arguments: Dict[str, Any],
    decision: str,
    result: str = "",
    path: Optional[Path] = None,
) -> Path:
    dest = path or DEFAULT_AUDIT_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": tool_name,
        "arguments": arguments or {},
        "decision": decision,
        "result": (result or "")[:1000],
    }
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return dest


def stdin_is_tty() -> bool:
    return bool(getattr(sys.stdin, "isatty", lambda: False)())
