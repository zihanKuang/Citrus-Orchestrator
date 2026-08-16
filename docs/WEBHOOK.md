# Alertmanager webhook (incident card)

A small HTTP service **outside** the ReAct loop. Auth, idempotency, rate limit,
degrade, and a fixed card template are the engineering story. The model only
fills the RCA body after live tools run.

## Run

```powershell
cd components
$env:CITRUS_WEBHOOK_TOKEN="change-me"
python -m agent_cli.webhook --port 8088
```

Alertmanager is disabled in `deploy/helm/monitoring-stack-values.yaml`. Until
that is enabled, POST a sample payload:

```powershell
curl -s -X POST http://127.0.0.1:8088/webhook `
  -H "Authorization: Bearer change-me" `
  -H "Content-Type: application/json" `
  -d '{"groupKey":"{}/{alertname=PodNotReady}","status":"firing","commonLabels":{"service":"frontend","alertname":"PodNotReady"},"alerts":[{"status":"firing","labels":{"service":"frontend","alertname":"PodNotReady"},"annotations":{"summary":"frontend is not ready"}}]}'
```

## Gates

| gate | behavior |
|------|----------|
| auth | `Authorization: Bearer` or `X-Webhook-Token`; empty secret fails closed |
| idempotency | same `groupKey` within 15 minutes → `duplicate`, no second agent run |
| rate limit | same `service` label within 5 minutes → `rate_limited` |
| degrade | agent exception → HTTP 200 + raw alert appended to `data/webhook/degraded.jsonl` and stdout |
| LOW stamp | `suspected_root_cause` is `null`; the card says the analysis is not published |

## Topology

If several services fire in one payload, `agent_cli/topology.py` asks Jaeger
`/api/dependencies` and attaches undirected edges as a **hint** in the query.
Jaeger down → empty adjacency, alerts still processed. Not Neo4j.

## Writes

Webhook sessions set `writes_interactive=False`. `restart_deployment` /
`scale_deployment` are denied even if the model proposes them.
