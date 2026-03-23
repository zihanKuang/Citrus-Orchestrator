# Citrus-Orchestrator: Production-Ready Microservices on Azure AKS

## Project Overview

This Helm chart orchestrates a cloud-native microservices application originally designed for GKE, successfully migrated to Azure AKS Standard with full observability integration.

**Key Technical Achievements:**
- Migrated 10+ microservices from GKE to AKS without service disruption
- Implemented distributed tracing with Jaeger (gRPC protocol)
- Integrated Prometheus + Grafana monitoring stack
- Resolved critical issues: RBAC conflicts, service discovery, cloud API incompatibilities

---

## Architecture Decisions

### 1. Service Discovery: DNS over Static IPs

**Problem:** Original implementation hardcoded backend IPs, breaking on every pod restart.

**Solution:** Leveraged Kubernetes DNS with dynamically injected service endpoints via Helm templates.

**Files:** `values.yaml` (serviceEndpoints), `all-in.yaml` (env injection loop)

### 2. Tracing: All-In-One vs Distributed

**Initial Approach:** Deployed separate Jaeger Collector, Query, and Agent pods.

**Failure:** Traces sent to Collector were invisible in Query UI due to memory isolation between pods.

**Root Cause Analysis:**
- Helm chart created multiple StatefulSets with independent in-memory storage
- No shared storage backend (Cassandra provisioning failed on AKS)

**Final Solution:** 
- Forced All-In-One mode with explicit component disabling in `values.yaml`
- Created dedicated `jaeger-grpc-solid` ClusterIP service for trace ingestion

**Files:** `values.yaml` (jaeger section), manually created Services

### 3. Frontend Tracing: Non-Standard Implementation

**Discovery:** Frontend ignored standard `OTEL_EXPORTER_OTLP_ENDPOINT` variable.

**Investigation:** Source code inspection revealed hardcoded checks for:
- `ENABLE_TRACING=1` (feature flag)
- `COLLECTOR_SERVICE_ADDR` (custom endpoint variable)

**Implementation:** Added conditional logic in `all-in.yaml` to inject frontend-specific env vars:

```yaml
{{- if eq $name "frontend" }}
- name: ENABLE_TRACING
  value: "1"
- name: COLLECTOR_SERVICE_ADDR
  value: "jaeger-grpc-solid:4317"
{{- end }}
```

**Learning:** Never assume microservices follow standards - always verify in source code.

---

## Troubleshooting History

### Issue 1: Port 7070 vs 8080 Mystery

**Symptom:** Frontend logs showing `connection refused` to `cartservice:8080`

**Investigation:**
- Checked Dockerfile: `EXPOSE 7070`
- Checked source code: Server binds to `PORT` env var (defaults to 7070)
- Checked helm values: Originally set to 8080 (outdated)

**Fix:** Updated `values.yaml` to use port 7070 with inline comment explaining the discrepancy.

### Issue 2: OOMKilled on AI Service

**Symptom:** `shoppingassistantservice` pod restarting every 30 seconds

**Investigation:**
```bash
kubectl describe pod shoppingassistantservice-xxx
# Events: OOMKilled (exit code 137)
```

**Root Cause:** Python AI libraries (transformers, etc.) require >256Mi memory

**Fix:** Increased limits to 512Mi in `values.yaml`

### Issue 3: CrashLoopBackOff on Payment Service

**Symptom:** `paymentservice` failing with "profiler: failed to initialize"

**Root Cause:** Google Cloud Profiler library crashes on non-GCP infrastructure

**Fix:** Injected `DISABLE_PROFILER: "1"` for all services in `all-in.yaml`

### Issue 4: Prometheus Can't Discover Services

**Symptom:** Prometheus Targets page showing 0/0 discovered

**Root Cause Analysis:**
1. Default namespace isolation: Prometheus only scraped its own namespace
2. Missing ServiceMonitor labels: Services lacked `app: {{ $name }}` label

**Fix:**
- Set `serviceMonitorSelectorNilUsesHelmValues: false` in `values.yaml`
- Added explicit label injection in Service template

### Issue 5: Helm Template Parse Errors

**Symptom:** `helm template` failing with "unexpected EOF"

**Root Cause:** Missing `{{- end }}` in conditional block for loadgenerator env vars

**Fix:** Verified all `{{- if }}` have matching `{{- end }}` using bracket matching in VS Code

---

## Deployment Instructions

### Prerequisites

```bash
# Install Helm 3.12+
helm version

# Configure kubectl for AKS
az aks get-credentials --resource-group <rg> --name <cluster>

# Verify connectivity
kubectl cluster-info
```

### Initial Deployment

```bash
# Install with all dependencies
helm install citrus ./citrus-app -n citrus --create-namespace

# Wait for all pods to be ready (may take 2-3 minutes)
kubectl wait --for=condition=ready pod --all -n citrus --timeout=300s
```

### Accessing Services

```bash
# Get frontend external IP
kubectl get svc frontend -n citrus -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

# Port-forward to Jaeger UI
kubectl port-forward svc/citrus-jaeger-ui 16686:16686 -n citrus
# Open: http://localhost:16686

# Port-forward to Grafana
kubectl port-forward svc/citrus-grafana 3000:80 -n citrus
# Open: http://localhost:3000 (default: admin/prom-operator)
```

### Upgrading Configuration

```bash
# After modifying values.yaml or templates
helm upgrade citrus ./citrus-app -n citrus

# If encountering conflicts from manual kubectl edits:
kubectl delete deployment <service> -n citrus
helm upgrade citrus ./citrus-app -n citrus
```

### Validating Tracing

```bash
# 1. Generate traffic
curl http://<FRONTEND_IP>/

# 2. Query Jaeger API
curl http://localhost:16686/api/services | jq

# Expected output should include "frontend" in service list
```

---

## Key Files Explained

| File | Purpose | Critical Sections |
|------|---------|-------------------|
| `Chart.yaml` | Helm metadata + dependencies | Sub-chart versions for Prometheus & Jaeger |
| `values.yaml` | Configuration parameters | tracing, jaeger, serviceEndpoints |
| `templates/all-in.yaml` | Main workload definitions | Env var injection, conditional tracing logic |
| `templates/_helpers.tpl` | Reusable Go template functions | Label generators, naming conventions |

---

## Lessons Learned

### 1. Cloud Provider Lock-In is Real

Google's demo images assume GCP infrastructure:
- Cloud Profiler API calls fail outside GCP
- Metadata server endpoints return 404 on Azure
- Solution: Aggressive feature flagging with `ENV_PLATFORM=local`

### 2. In-Memory Tracing Has Limitations

All-In-One mode loses traces on pod restart. For production:
- Deploy Jaeger with Elasticsearch backend
- Use Jaeger Operator for easier lifecycle management

### 3. Helm Template Debugging is an Art

Best practices learned:
- Use `helm template . --debug` to see rendered YAML before applying
- Add inline comments in templates to explain non-obvious logic
- Test range loops with single-item lists first

### 4. Monitoring Requires Explicit Permissions

Default RBAC policies block cross-namespace scraping. Always:
- Verify ServiceMonitor labelSelectors match actual Service labels
- Check Prometheus ConfigMap for discovered targets
- Use `kubectl port-forward` for debugging before enabling ingress

---

## Future Enhancements

- [ ] Migrate from LoadBalancer to Ingress Controller (NGINX)
- [ ] Implement HPA based on custom metrics (order value per second)
- [ ] Replace in-memory Jaeger with persistent Elasticsearch backend
- [ ] Add Grafana dashboards for SLI tracking (p99 latency, error rate)
- [ ] Implement mutual TLS between services using Istio

---

## Contact

For questions about implementation decisions or debugging strategies, please reference:
- Inline comments in `values.yaml` and `all-in.yaml`
- Git commit history showing iterative problem-solving process
- This README's troubleshooting section
