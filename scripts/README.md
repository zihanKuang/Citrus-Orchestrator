# MLOps Scripts Documentation

This directory contains production-grade automation scripts for MLOps and AIOps workflows.

## Contents

- `canary-deploy.py` - Automated canary deployment with intelligent rollback
- `aiops-agent.py` - AI-powered incident analysis agent
- `requirements.txt` - Python dependencies

---

## Canary Deployment

### Overview

The canary deployment script automates ML model upgrades with built-in safety mechanisms:

1. **Deploy new version** alongside existing (20% traffic)
2. **Monitor metrics** for 3 minutes (error rate, latency)
3. **Auto-rollback** if performance degrades
4. **Gradual rollout** if validation succeeds

### Prerequisites

```bash
# 1. Port-forward to Prometheus
kubectl port-forward -n citrus svc/citrus-kube-prometheus-sta-prometheus 9090:9090

# 2. Ensure kubectl is configured
kubectl cluster-info

# 3. Install dependencies
pip install -r requirements.txt
```

### Usage

```bash
# Basic usage: Deploy new recommendation model
python canary-deploy.py \\
  --service recommendationservice \\
  --baseline ghcr.io/zihankuang/citrus-recommendation:v1.0 \\
  --canary ghcr.io/zihankuang/citrus-recommendation:v1.1

# Custom monitoring duration (5 minutes)
python canary-deploy.py \\
  --service recommendationservice \\
  --baseline ghcr.io/zihankuang/citrus-recommendation:v1.0 \\
  --canary ghcr.io/zihankuang/citrus-recommendation:v1.1 \\
  --duration 300

# Custom canary percentage (50% instead of default 20%)
python canary-deploy.py \\
  --service recommendationservice \\
  --baseline ghcr.io/zihankuang/citrus-recommendation:latest \\
  --canary ghcr.io/zihankuang/citrus-recommendation:${{github.sha}} \\
  --canary-percent 50
```

### Decision Logic

**Automatic Rollback Triggered When:**
- Error rate > 1.2x baseline (20% worse)
- P99 latency > 1.5x baseline (50% slower)
- Deployment fails to become ready

**Example Output:**

```
============================================================
Starting Canary Deployment: recommendationservice
============================================================

Deploying canary version...
   Baseline replicas: 2
   Canary replicas: 1
Canary deployed successfully

Monitoring for 180s...

Evaluating canary performance...

Error Rate:
   Baseline: 0.0012%
   Canary:   0.0015%

P99 Latency:
   Baseline: 145ms
   Canary:   158ms

Performance Ratios:
   Error ratio: 1.25x (threshold: 1.2x)
   Latency ratio: 1.09x (threshold: 1.5x)

DECISION: ROLLBACK (error rate too high)

Rolling back to baseline version...
Rollback complete.
```

### Metrics Queried

| Metric | PromQL Query | Purpose |
|--------|--------------|---------|
| Error Rate | `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))` | Detect increased failures |
| P99 Latency | `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))` | Catch performance regression |

---

## AI Operations Agent (Simplified)

### Overview

The AIOps agent automatically analyzes Prometheus alerts using **rule-based analysis**, providing:

- **Root cause analysis** from logs and metrics
- **Plain English explanations** for non-technical stakeholders
- **Actionable remediation steps** with kubectl commands
- **Automatic context gathering** (pod status, logs, events)

**Note**: AI functionality (Google Gemini) has been removed to simplify the demo.  
For production use with AI:
1. Uncomment AI-related code in `aiops-agent.py`
2. Install: `pip install google-generativeai`
3. Set `GEMINI_API_KEY` environment variable

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt
```

### Usage - Webhook Server Mode

Start agent to receive alerts from Prometheus Alertmanager:

```bash
# Start webhook server
python aiops-agent.py --mode server --port 5000

# Output:
# AIOps Agent listening on port 5000
# Webhook URL: http://localhost:5000/webhook
```

**Configure Alertmanager** (`alertmanager.yml`):

```yaml
receivers:
  - name: 'aiops-agent'
    webhook_configs:
      - url: 'http://localhost:5000/webhook'
        send_resolved: true

route:
  receiver: 'aiops-agent'
  group_by: ['alertname', 'cluster']
  group_interval: 5m
```

### Usage - Single Alert Analysis

Analyze a saved alert from JSON file:

```bash
# Save alert from Alertmanager UI
curl http://localhost:9093/api/v2/alerts > alert.json

# Analyze
python aiops-agent.py --mode analyze --alert-file alert.json
```

### Example AI Analysis

**Input Alert:**
```
Alert: RecommendationServiceHighLatency
Severity: critical
Description: P99 latency is 450ms (threshold: 200ms)
```

**AI-Generated Report:**
```
============================================================
INCIDENT REPORT
============================================================

**Root Cause**: The recommendation service's ML model inference
is taking longer than expected. Recent logs show increased
database query times to the product catalog.

**Impact**: Users experiencing 2-3 second page load delays when
viewing product recommendations. Checkout process affected.

**Immediate Action**:
```bash
# Check database connection pool
kubectl logs -n citrus -l app=recommendationservice --tail=50 | grep -i "pool"

# Temporarily scale up to handle load
kubectl scale deployment/recommendationservice --replicas=5 -n citrus

# Monitor for improvement
watch kubectl top pods -n citrus -l app=recommendationservice
```

**Prevention**: 
1. Implement caching for frequently recommended products
2. Add database connection pool monitoring
3. Set up autoscaling based on inference latency metric

============================================================
```

### Analysis Mode

The agent uses **rule-based analysis** (no AI dependencies required):

```
Using rule-based analysis (simplified demo version)
```

The rule-based analyzer still provides useful guidance including root cause analysis,
impact assessment, and actionable kubectl commands.

---

## 🔗 Integration Examples

### GitHub Actions Integration

```yaml
# .github/workflows/deploy-with-canary.yml
- name: Canary Deployment
  run: |
    python scripts/canary-deploy.py \\
      --service recommendationservice \\
      --baseline ${{ env.BASELINE_IMAGE }} \\
      --canary ${{ env.CANARY_IMAGE }} \\
      --prometheus http://prometheus-server:9090
```

### Kubernetes CronJob for Health Checks

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: aiops-health-check
spec:
  schedule: "*/30 * * * *"  # Every 30 minutes
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: aiops-agent
            image: python:3.12-alpine
            command:
            - python
            - /scripts/aiops-agent.py
            - --mode
            - analyze
            volumeMounts:
            - name: scripts
              mountPath: /scripts
          volumes:
          - name: scripts
            configMap:
              name: aiops-scripts
```

---

## Troubleshooting

### Canary Script Issues

**Problem**: `kubectl: command not found`

**Solution**:
```bash
# Ensure kubectl is in PATH
kubectl version --client

# If not installed, download:
# https://kubernetes.io/docs/tasks/tools/
```

**Problem**: `Prometheus query failed: Connection refused`

**Solution**:
```bash
# Verify port-forward is running
ps aux | grep "port-forward.*9090"

# Restart port-forward
kubectl port-forward -n citrus svc/citrus-kube-prometheus-sta-prometheus 9090:9090
```

### AIOps Agent Issues

**Problem**: `ImportError: No module named 'flask'` or `'requests'`

**Solution**:
```bash
pip install -r scripts/requirements.txt
```

**Problem**: Analysis results are too generic

**Solution**:
- Verify pod logs contain actual error messages (not just warnings)
- Increase `--tail` parameter to gather more log context
- Check Kubernetes events for additional clues

---

## Metrics & Monitoring

Both scripts emit structured logs suitable for monitoring:

| Event | Log Format | Use Case |
|-------|------------|----------|
| Canary Start | `Starting Canary Deployment: <service>` | Track deployment frequency |
| Rollback Triggered | `DECISION: ROLLBACK (error rate too high)` | Alert on model quality issues |
| AI Analysis | `Consulting AI for analysis...` | Monitor AIOps usage |

**Example Prometheus metrics** (can be added):

```python
from prometheus_client import Counter, Histogram

canary_deployments = Counter('canary_deployments_total', 'Number of canary deployments')
canary_rollbacks = Counter('canary_rollbacks_total', 'Number of automatic rollbacks')
aiops_analyses = Counter('aiops_analyses_total', 'Number of AI incident analyses')
```

---

## Learning Resources

- **Canary Deployments**: https://martinfowler.com/bliki/CanaryRelease.html
- **SRE Best Practices**: https://sre.google/sre-book/table-of-contents/
- **Prometheus Querying**: https://prometheus.io/docs/prometheus/latest/querying/basics/
- **Kubernetes Patterns**: https://kubernetes.io/docs/concepts/cluster-administration/manage-deployment/