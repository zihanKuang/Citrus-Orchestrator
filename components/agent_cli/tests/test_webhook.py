"""Alertmanager webhook gates — no live agent, no cluster."""
import json
from pathlib import Path

from agent_cli.topology import ServiceGraph
from agent_cli.webhook import Gate, WebhookApp, build_query, render_card


def _frozen_graph() -> ServiceGraph:
    graph = ServiceGraph()
    graph._graph = {}
    graph._fetched_at = 1.0
    graph.ttl_s = 10**9
    return graph


def _payload(service="frontend", group_key="{}/frontend", status="firing"):
    return {
        "groupKey": group_key,
        "status": status,
        "commonLabels": {"service": service, "alertname": "PodNotReady"},
        "alerts": [
            {
                "status": status,
                "labels": {"service": service, "alertname": "PodNotReady"},
                "annotations": {"summary": f"{service} is not ready"},
            }
        ],
    }


def _app(runner, token="secret", tmp_path=None, graph=None):
    return WebhookApp(
        token=token,
        runner=runner,
        graph=graph or _frozen_graph(),
        gate=Gate(idempotency_ttl_s=600, rate_limit_s=600),
        degrade_path=(tmp_path / "degraded.jsonl") if tmp_path else None,
    )


def test_unauthorized_without_token():
    app = _app(lambda q: ("ok", {"tool_calls": {}}), token="secret")
    code, body = app.handle({}, b"{}")
    assert code == 401
    assert body["error"] == "unauthorized"


def test_bearer_auth_and_card_high():
    answer = (
        "frontend pod was killed; ReplicaSet recovered it.\n\n"
        "---\nEvidence check: HIGH\n- live tools succeeded\n"
    )
    stats = {
        "tool_calls": {"list_pods": 1, "get_recent_events": 1, "validate_recovery": 1},
        "errors": 0,
    }
    app = _app(lambda q: (answer, stats))
    code, card = app.handle(
        {"Authorization": "Bearer secret"},
        json.dumps(_payload()).encode("utf-8"),
    )
    assert code == 200
    assert card["status"] == "ok"
    assert card["evidence_level"] == "HIGH"
    assert card["suspected_root_cause"]
    assert "frontend" in (card["suspected_root_cause"] or "")


def test_low_stamp_does_not_publish_root_cause():
    answer = "I am sure it is DNS.\n\n---\nEvidence check: LOW\n- 0 live tool calls\n"
    app = _app(lambda q: (answer, {"tool_calls": {}, "errors": 0}))
    _code, card = app.handle(
        {"X-Webhook-Token": "secret"},
        json.dumps(_payload()).encode("utf-8"),
    )
    assert card["evidence_level"] == "LOW"
    assert card["suspected_root_cause"] is None
    assert "not published" in card["note"]


def test_idempotent_group_key():
    app = _app(lambda q: ("ok\n\n---\nEvidence check: LOW\n", {"tool_calls": {}}))
    headers = {"Authorization": "Bearer secret"}
    body = json.dumps(_payload(group_key="g1")).encode("utf-8")
    first = app.handle(headers, body)
    second = app.handle(headers, body)
    assert first[0] == 200
    assert second[1]["status"] == "duplicate"


def test_rate_limit_same_service_different_group():
    app = _app(lambda q: ("ok\n\n---\nEvidence check: LOW\n", {"tool_calls": {}}))
    headers = {"Authorization": "Bearer secret"}
    a = json.dumps(_payload(group_key="g-a")).encode("utf-8")
    b = json.dumps(_payload(group_key="g-b")).encode("utf-8")
    app.handle(headers, a)
    code, body = app.handle(headers, b)
    assert code == 200
    assert body["status"] == "rate_limited"


def test_agent_failure_degrades_and_logs_raw(tmp_path: Path):
    def boom(_query):
        raise RuntimeError("llm down")

    app = _app(boom, tmp_path=tmp_path)
    code, body = app.handle(
        {"Authorization": "Bearer secret"},
        json.dumps(_payload()).encode("utf-8"),
    )
    assert code == 200
    assert body["status"] == "degraded"
    logged = (tmp_path / "degraded.jsonl").read_text(encoding="utf-8")
    assert "llm down" in logged
    assert "frontend" in logged


def test_build_query_includes_topology_edges():
    payload = _payload()
    payload["alerts"].append({
        "status": "firing",
        "labels": {"service": "checkout"},
        "annotations": {"summary": "checkout errors"},
    })
    q = build_query(payload, [("checkout", "frontend")])
    assert "checkout↔frontend" in q
    assert "not live evidence" in q


def test_render_card_records_topology_edges():
    card = render_card(
        payload=_payload(),
        answer="x\n\n---\nEvidence check: LOW\n",
        stats={"tool_calls": {}},
        query="q",
        edges=[("checkout", "frontend")],
    )
    assert card["related_via_topology"] == [["checkout", "frontend"]]
