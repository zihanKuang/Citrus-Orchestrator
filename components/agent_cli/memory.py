"""JSONL postmortem memory. Keyword overlap only — no embeddings, no graph DB.

Write: after a run, if the evidence stamp is not LOW.
Read: before the next query, inject recent overlapping summaries as hints.

LOW runs are never stored. That is the link between the evidence stamp and memory:
the system refuses to remember ungrounded answers.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PATH = _REPO_ROOT / "data" / "memory" / "postmortems.jsonl"
ANSWER_CAP = 2048
DEFAULT_LIMIT = 3

_TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]{2,}")
_STOP = {
    "the", "and", "for", "that", "this", "with", "from", "was", "were",
    "are", "not", "but", "you", "your", "into", "then", "than", "what",
    "just", "happened", "short", "pods", "pod", "in", "of", "to", "a",
    "an", "is", "it", "on", "or", "be", "as", "at", "by", "if",
}


def tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN.findall((text or "").lower()) if t not in _STOP}


def overlap_score(query: str, record: Dict[str, Any]) -> int:
    q = tokenize(query)
    blob = " ".join(
        str(record.get(k) or "")
        for k in ("scenario", "query", "answer", "tools")
    )
    r = tokenize(blob)
    if not q or not r:
        return 0
    return len(q & r)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_postmortem(
    *,
    query: str,
    answer: str,
    tools_used: Dict[str, int],
    evidence_level: str,
    scenario: str = "unknown",
    hit: Optional[bool] = None,
    path: Optional[Path] = None,
) -> Optional[Path]:
    """Append one record. Returns None if skipped (LOW stamp)."""
    level = (evidence_level or "").upper()
    if level == "LOW":
        return None

    dest = path or DEFAULT_PATH
    _ensure_parent(dest)
    record = {
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scenario": scenario or "unknown",
        "query": (query or "")[:500],
        "tools": sorted((tools_used or {}).keys()),
        "answer": (answer or "")[:ANSWER_CAP],
        "evidence_level": level,
        "hit": hit,
    }
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return dest


def load_records(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    src = path or DEFAULT_PATH
    if not src.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in src.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def retrieve(
    query: str,
    *,
    path: Optional[Path] = None,
    limit: int = DEFAULT_LIMIT,
    min_score: int = 1,
) -> List[Dict[str, Any]]:
    scored = []
    for rec in load_records(path):
        score = overlap_score(query, rec)
        if score >= min_score:
            scored.append((score, rec))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [rec for _score, rec in scored[:limit]]


def format_prefix(records: Iterable[Dict[str, Any]]) -> str:
    items = list(records)
    if not items:
        return ""
    lines = [
        "[Prior postmortems — keyword overlap only, not live evidence. "
        "Always gather live cluster state before answering.]",
    ]
    for rec in items:
        scenario = rec.get("scenario") or "unknown"
        tools = ",".join(rec.get("tools") or []) or "none"
        snippet = (rec.get("answer") or "").replace("\n", " ").strip()[:280]
        lines.append(f"- ({scenario}, tools={tools}) {snippet}")
    lines.append("")
    return "\n".join(lines)


def annotate_latest_hit(
    scenario: str,
    hit: bool,
    *,
    path: Optional[Path] = None,
) -> bool:
    """Set hit on the last record matching scenario. Eval uses this after scoring."""
    src = path or DEFAULT_PATH
    records = load_records(src)
    for rec in reversed(records):
        if rec.get("scenario") == scenario:
            rec["hit"] = hit
            _ensure_parent(src)
            with src.open("w", encoding="utf-8") as fh:
                for row in records:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            return True
    return False
