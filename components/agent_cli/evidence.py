"""Deterministic evidence check. No LLM. Appended after the agent's answer.

Why this exists:
  The system prompt already says "gather live evidence before answering".
  That is a request, not a guarantee. This module looks at what actually
  happened (tool-call counts, errors, whether recovery was verified) and
  stamps HIGH / MEDIUM / LOW onto the answer. The model cannot rewrite it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


RCA_HINTS = (
    "rca",
    "what happened",
    "what just happened",
    "incident",
    "killed",
    "crash",
    "recover",
    "outage",
    "unhealthy",
)

EVIDENCE_TOOLS = (
    "list_pods",
    "get_recent_events",
    "get_pod_status",
    "get_pod_logs",
    "query_prometheus",
    "validate_recovery",
)


@dataclass(frozen=True)
class EvidenceCheck:
    level: str  # HIGH | MEDIUM | LOW
    reasons: List[str]
    tool_calls: int
    errors: int
    tools_used: Dict[str, int]

    def footer(self) -> str:
        lines = [f"Evidence check: {self.level}"]
        for reason in self.reasons:
            lines.append(f"- {reason}")
        used = ", ".join(f"{name}×{n}" for name, n in sorted(self.tools_used.items())) or "none"
        lines.append(f"- tools used: {used}  errors: {self.errors}")
        return "\n".join(lines)


def _is_rca_query(query: str) -> bool:
    q = query.lower()
    return any(hint in q for hint in RCA_HINTS)


def assess(query: str, answer: str, stats: Dict[str, Any]) -> EvidenceCheck:
    """Grade one agent run from recorded stats. Pure function, safe to unit-test."""
    tools_used: Dict[str, int] = dict(stats.get("tool_calls") or {})
    tool_calls = sum(tools_used.values())
    errors = int(stats.get("errors") or 0)
    reasons: List[str] = []
    level = "HIGH"

    if not (answer or "").strip():
        return EvidenceCheck("LOW", ["empty answer"], tool_calls, errors, tools_used)

    if tool_calls == 0:
        return EvidenceCheck(
            "LOW",
            ["0 live tool calls — answer is not grounded in cluster state"],
            tool_calls,
            errors,
            tools_used,
        )

    if errors * 2 >= tool_calls:
        level = "LOW"
        reasons.append(
            f"tool/LLM error rate high ({errors} errors / {tool_calls} tool calls)"
        )

    evidence_calls = sum(tools_used.get(name, 0) for name in EVIDENCE_TOOLS)
    if evidence_calls == 0:
        level = "LOW"
        reasons.append("called tools, but none of them inspect cluster state")

    if _is_rca_query(query) and tools_used.get("validate_recovery", 0) == 0:
        if level == "HIGH":
            level = "MEDIUM"
        reasons.append(
            "RCA-style question but validate_recovery was never called"
        )

    if _is_rca_query(query) and tools_used.get("get_recent_events", 0) == 0:
        if level == "HIGH":
            level = "MEDIUM"
        reasons.append("RCA-style question but get_recent_events was never called")

    if not reasons:
        reasons.append("live tools succeeded; recovery verified" if tools_used.get("validate_recovery") else "live tools succeeded")

    return EvidenceCheck(level, reasons, tool_calls, errors, tools_used)


def attach_footer(answer: str, check: EvidenceCheck) -> str:
    return f"{answer.rstrip()}\n\n---\n{check.footer()}\n"
