# Scripts Directory

Automation scripts for deployment, MLOps, and AIOps operations.

## Directory Structure

```
scripts/
├── deployment/                    # Infrastructure as Code deployment scripts
│   ├── 0-deploy-all.ps1          # One-click full deployment
│   ├── 1-deploy-infrastructure.ps1  # Deploy monitoring + tracing
│   ├── 2-deploy-application.ps1  # Deploy OpenTelemetry Demo
│   └── README.md                  # Deployment guide
│
├── canary-deploy.py               # Automated canary deployment
├── canary-demo.py                 # Canary deployment demo
├── canary-wrapper.sh              # Bash wrapper with mock support
├── requirements.txt               # Python dependencies
└── tests/                         # BATS test suite
```

## Quick Start

### Deployment (Infrastructure as Code)

```powershell
# One-click deployment
.\scripts\deployment\0-deploy-all.ps1
```

See [deployment/README.md](deployment/README.md) for details.

### MLOps: Canary Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Run canary deployment
python canary-deploy.py \
  --service recommendationservice \
  --baseline ghcr.io/user/app:v1.0 \
  --canary ghcr.io/user/app:v1.1
```

### AIOps: Agent CLI (MCP + ReAct)

The old Flask `aiops-agent.py` was replaced by:

- `components/mcp-server/` — MCP tools (logs, events, Prometheus, validate_recovery)
- `components/agent_cli/` — hand-written ReAct agent

```powershell
cd components
python -m agent_cli "What is wrong with frontend in citrus?"
```

Chaos demo: `.\infra\chaos\run-demo.ps1`
## Script Categories

### 1. Deployment Scripts (New)

**Purpose:** Infrastructure as Code deployment automation

**Files:**
- `deployment/0-deploy-all.ps1` - Full stack deployment
- `deployment/1-deploy-infrastructure.ps1` - Monitoring + tracing
- `deployment/2-deploy-application.ps1` - Application deployment

**Key Features:**
- Version controlled deployment logic
- Reproducible deployments
- No manual Helm commands needed
- Cross-platform (PowerShell Core)

**Documentation:** [deployment/README.md](deployment/README.md)

### 2. MLOps Scripts

**Purpose:** Automated ML model deployment with safety mechanisms

**Files:**
- `canary-deploy.py` (465 lines) - Production canary deployment
- `canary-demo.py` (145 lines) - Demo with simulated metrics
- `canary-wrapper.sh` (250 lines) - Bash wrapper with testing support

**Key Features:**
- Automated metrics monitoring
- Intelligent rollback decisions
- Configurable thresholds
- Mock mode for testing

**Decision Logic:**
- Error rate > 1.2x baseline -> Rollback
- P99 latency > 1.5x baseline -> Rollback
- Health checks failing -> Rollback

**Example:**

```bash
python canary-deploy.py \
  --service recommendationservice \
  --baseline ghcr.io/zihankuang/citrus-recommendation:v1.0 \
  --canary ghcr.io/zihankuang/citrus-recommendation:v1.1 \
  --duration 300
```

### 3. AIOps (moved to components/)

Incident analysis now lives in `components/mcp-server` + `components/agent_cli` (MCP + ReAct), not under `scripts/`.

## Prerequisites

### For Deployment Scripts

- Kubernetes cluster
- kubectl configured
- Helm 3.12+
- PowerShell 5.1+ or PowerShell Core

### For MLOps Scripts

- Python 3.12+
- kubectl access
- Prometheus port-forward on 9090
- Dependencies: `pip install -r requirements.txt`
## Testing

### Deployment Scripts

```powershell
# Dry-run mode
kubectl apply --dry-run=client -f ...

# Test in Kind cluster
kind create cluster --name test
.\scripts\deployment\0-deploy-all.ps1
```

### Canary Deployment

```bash
# Unit tests
bats scripts/tests/canary-wrapper.bats

# Mock mode
MOCK_MODE=1 \
MOCK_ERROR_RATIO=1.5 \
./canary-wrapper.sh --service test --baseline v1 --canary v2
```

## Architecture Integration

```
┌────────────────────────────────────────┐
│  Deployment Scripts (IaC)              │
│  ├─ Deploy infrastructure              │
│  ├─ Deploy application                 │
│  └─ Version controlled                 │
└────────────────────────────────────────┘
              ↓
┌────────────────────────────────────────┐
│  Running Platform                      │
│  ├─ Prometheus (metrics)               │
│  ├─ Grafana (dashboards)               │
│  ├─ Jaeger (traces)                    │
│  └─ Application services               │
└────────────────────────────────────────┘
              ↓
┌────────────────────────────────────────┐
│  MLOps Scripts                         │
│  ├─ Canary deployments                 │
│  ├─ Automated rollback                 │
│  └─ Metric-based decisions             │
└────────────────────────────────────────┘
              ↓
┌────────────────────────────────────────┐
│  AIOps Scripts                         │
│  ├─ Alert analysis                     │
│  ├─ Root cause detection               │
│  └─ Remediation suggestions            │
└────────────────────────────────────────┘
```

## Best Practices

1. **Use Deployment Scripts:** Don't run manual Helm commands
2. **Version Control:** All scripts are in Git
3. **Test First:** Use mock mode before production
4. **Monitor Deployments:** Watch metrics during canary
5. **Document Changes:** Update READMEs when modifying scripts

## Troubleshooting

### Deployment Scripts

See [deployment/README.md](deployment/README.md#troubleshooting)

### Canary Deployment

**Prometheus Connection Failed:**

```bash
# Verify port-forward
kubectl port-forward -n citrus svc/monitoring-kube-prometheus-prometheus 9090:9090
```

**Kubectl Errors:**

```bash
# Verify cluster access
kubectl cluster-info
kubectl get nodes
```

### AIOps Agent

**Import Errors:**

```bash
pip install -r requirements.txt
```

**Alertmanager Webhook Not Working:**

```bash
# Check agent is running
curl http://localhost:5000/health
```

## Related Documentation

- [Main Deployment Guide](../docs/DEPLOYMENT.md)
- [Deployment Scripts Guide](deployment/README.md)
- [TROUBLESHOOTING.md](../TROUBLESHOOTING.md)

## Contributing

When adding new scripts:

1. **Document Purpose:** Add clear comments
2. **Update README:** Explain usage
3. **Add Tests:** Create test cases if applicable
4. **Follow Style:** Match existing scripts
5. **English Only:** All comments and messages in English
