# MLOps & AIOps Scripts

Production automation scripts for canary deployments and AI-powered incident analysis.

## Contents

- `canary-deploy.py` - Automated canary deployment with intelligent rollback (465 lines)
- `canary-demo.py` - Simplified demo version (145 lines)
- `canary-wrapper.sh` - Bash wrapper with mock support for testing (250 lines)
- `aiops-agent.py` - AI-powered incident analysis (398 lines)
- `requirements.txt` - Python dependencies
- `tests/` - BATS test suite for canary wrapper validation

---

## Canary Deployment

Automates ML model upgrades with safety mechanisms:

1. Deploy new version alongside existing (20% traffic)
2. Monitor metrics for 3 minutes (error rate, latency)
3. Auto-rollback if performance degrades
4. Gradual rollout if validation succeeds

### Prerequisites

```bash
# Port-forward to Prometheus
kubectl port-forward -n citrus svc/citrus-kube-prometheus-sta-prometheus 9090:9090

# Verify kubectl access
kubectl cluster-info

# Install dependencies
pip install -r requirements.txt
```

### Usage

```bash
# Basic deployment
python canary-deploy.py \
  --service recommendationservice \
  --baseline ghcr.io/zihankuang/citrus-recommendation:v1.0 \
  --canary ghcr.io/zihankuang/citrus-recommendation:v1.1

# Custom monitoring duration
python canary-deploy.py \
  --service recommendationservice \
  --baseline ghcr.io/zihankuang/citrus-recommendation:v1.0 \
  --canary ghcr.io/zihankuang/citrus-recommendation:v1.1 \
  --duration 300

# Demo mode (simulated metrics)
python canary-demo.py
```

### Decision Thresholds

Automatic rollback triggered when:
- Error rate > 1.2x baseline (20% increase)
- P99 latency > 1.5x baseline (50% increase)
- Deployment fails health checks

### Metrics Queried

| Metric | PromQL Query |
|--------|-------------|
| Error Rate | `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))` |
| P99 Latency | `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))` |

---

## Bash Wrapper (Testing & CI/CD)

Resilient automation wrapper with mocked metric threshold evaluation for testing without live infrastructure.

### Why a Bash Wrapper?

- **CI/CD Integration**: Test deployment logic in GitHub Actions without Kubernetes
- **Local Development**: Validate threshold calculations before production deployment
- **Safety**: Pre-flight checks catch configuration errors early

### Usage

```bash
# Real deployment (calls Python script)
./canary-wrapper.sh \
  --service recommendationservice \
  --baseline ghcr.io/user/app:v1.0 \
  --canary ghcr.io/user/app:v1.1

# Mock mode (for testing threshold logic)
MOCK_MODE=1 \
MOCK_ERROR_RATIO=1.5 \
MOCK_LATENCY_RATIO=0.9 \
./canary-wrapper.sh \
  --service test \
  --baseline v1 \
  --canary v2
```

### BATS Tests

Automated test suite validates all threshold scenarios:

```bash
# Install BATS
npm install -g bats

# Run tests
bats scripts/tests/canary-wrapper.bats

# Expected output:
# ✓ PROCEED decision when metrics are healthy
# ✓ ROLLBACK decision when error ratio exceeds threshold
# ✓ ROLLBACK decision when latency ratio exceeds threshold
# ✓ boundary test: error ratio exactly at threshold
# 
# 15 tests, 0 failures
```

See `tests/README.md` for full test documentation.

---

## AI Operations Agent

Analyzes Prometheus alerts and generates incident reports with root cause analysis.

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Set API key (if using AI mode)
export GEMINI_API_KEY="your-key"
```

### Usage

**Webhook server mode** (receives alerts from Alertmanager):

```bash
python aiops-agent.py --mode server --port 5000
```

**Single alert analysis**:

```bash
python aiops-agent.py --mode analyze --alert-file alert.json
```

### Alertmanager Configuration

```yaml
receivers:
  - name: 'aiops-agent'
    webhook_configs:
      - url: 'http://localhost:5000/webhook'

route:
  receiver: 'aiops-agent'
  group_by: ['alertname']
```

### Analysis Capabilities

The agent gathers:
- Pod status and resource usage
- Recent logs (last 50 lines)
- Kubernetes events
- Related metrics from Prometheus

Output includes:
- Root cause assessment
- Impact analysis
- Remediation commands
- Prevention recommendations

---

## Troubleshooting

**Problem:** `kubectl: command not found`

Solution: Ensure kubectl is in PATH and configured

**Problem:** `Prometheus query failed: Connection refused`

Solution: Verify port-forward is running on port 9090

**Problem:** `ImportError: No module named 'flask'`

Solution: `pip install -r requirements.txt`
