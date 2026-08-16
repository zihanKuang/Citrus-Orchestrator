"""Postmortem JSONL — no cluster, no LLM."""
from pathlib import Path

from agent_cli.memory import (
    append_postmortem,
    annotate_latest_hit,
    format_prefix,
    retrieve,
    tokenize,
)


def test_tokenize_drops_stopwords_and_short_tokens():
    tokens = tokenize("What just happened to the frontend pods in citrus?")
    assert "frontend" in tokens
    assert "citrus" in tokens
    assert "the" not in tokens
    assert "to" not in tokens


def test_low_stamp_is_never_written(tmp_path: Path):
    path = tmp_path / "pm.jsonl"
    written = append_postmortem(
        query="what happened",
        answer="I guessed it was frontend",
        tools_used={},
        evidence_level="LOW",
        path=path,
    )
    assert written is None
    assert not path.exists()


def test_medium_is_written_and_retrieved_by_overlap(tmp_path: Path):
    path = tmp_path / "pm.jsonl"
    append_postmortem(
        query="What just happened to the frontend pods?",
        answer="PodChaos killed frontend; ReplicaSet recreated it.",
        tools_used={"list_pods": 1, "get_recent_events": 1},
        evidence_level="HIGH",
        scenario="pod-kill-frontend",
        path=path,
    )
    append_postmortem(
        query="checkout status",
        answer="checkout is Ready",
        tools_used={"list_pods": 1},
        evidence_level="MEDIUM",
        scenario="pod-kill-checkout",
        path=path,
    )
    hits = retrieve("frontend chaos kill", path=path, limit=3)
    assert hits
    assert hits[0]["scenario"] == "pod-kill-frontend"
    prefix = format_prefix(hits)
    assert "Prior postmortems" in prefix
    assert "pod-kill-frontend" in prefix


def test_annotate_latest_hit(tmp_path: Path):
    path = tmp_path / "pm.jsonl"
    append_postmortem(
        query="q",
        answer="a",
        tools_used={"list_pods": 1},
        evidence_level="HIGH",
        scenario="healthy-baseline",
        path=path,
    )
    assert annotate_latest_hit("healthy-baseline", True, path=path)
    hits = retrieve("healthy-baseline citrus namespace", path=path)
    assert hits[0]["hit"] is True
