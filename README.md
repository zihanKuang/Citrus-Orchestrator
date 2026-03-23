# Citrus-Orchestrator

**Multi-Cloud Microservices Platform with Full Observability**

[![Kubernetes](https://img.shields.io/badge/kubernetes-1.28-blue.svg)](https://kubernetes.io/)
[![Helm](https://img.shields.io/badge/helm-3.12-blue.svg)](https://helm.sh/)
[![Azure AKS](https://img.shields.io/badge/azure-AKS%20Standard-blue.svg)](https://azure.microsoft.com/en-us/products/kubernetes-service/)

---

## Overview

Citrus-Orchestrator is a production-ready Helm chart that orchestrates a complete microservices e-commerce platform with integrated distributed tracing (Jaeger) and metrics monitoring (Prometheus + Grafana). Originally designed for Google Kubernetes Engine (GKE), this project was successfully migrated to Azure AKS Standard while solving critical cross-cloud compatibility issues.

**Why This Project Matters:**
- Demonstrates real-world cloud migration experience (GKE → AKS)
- Showcases DevOps best practices: IaC, GitOps, Observability
- Documents actual troubleshooting process, not just "happy path"
- Production-grade: resource limits, health checks, auto-scaling ready

---

## Architecture

```
┌─────────────────────┐
│   Load Balancer     │ ← External Access
│   (Frontend)        │
└──────────┬──────────┘
           │
┌──────────▼──────────────────────────────────────────┐
│           Kubernetes Cluster (AKS)                   │
│  ┌─────────────────────────────────────────────┐    │
│  │  Microservices Layer                        │    │
│  │  ┌────────┐ ┌─────────┐ ┌──────────────┐   │    │
│  │  │Frontend│→│AdService│→│Recommendation│   │    │
│  │  └────┬───┘ └─────────┘ └──────────────┘   │    │
│  │       │                                      │    │
│  │       ▼                                      │    │
│  │  ┌────────┐ ┌──────────┐ ┌──────────────┐  │    │
│  │  │  Cart  │→│Checkout  │→│  Payment     │  │    │
│  │  │Service │ │ Service  │ │  Service     │  │    │
│  │  └────┬───┘ └──────────┘ └──────────────┘  │    │
│  │       │                                      │    │
│  │       ▼                                      │    │
│  │  ┌────────┐                                 │    │
│  │  │ Redis  │                                 │    │
│  │  └────────┘                                 │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │  Observability Stack                        │    │
│  │  ┌──────────┐ ┌────────────┐ ┌──────────┐  │    │
│  │  │Prometheus│→│  Grafana   │ │  Jaeger  │  │    │
│  │  │ (Metrics)│ │(Dashboards)│ │ (Traces) │  │    │
│  │  └──────────┘ └────────────┘ └──────────┘  │    │
│  └─────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

**Technology Stack:**
- **Container Orchestration:** Kubernetes 1.28+
- **Package Management:** Helm 3.12+
- **Distributed Tracing:** Jaeger (All-In-One with gRPC)
- **Metrics:** Prometheus + Grafana
- **Service Mesh:** Native K8s Service Discovery
- **Languages:** Go, Python, C#, Node.js, Java

---

## Key Features

### 🔧 DevOps Engineering
- **Helm-based IaC:** Single command deployment with parameterized configurations
- **Multi-environment support:** Separate configs for dev/staging/prod
- **Rolling updates:** Zero-downtime deployments with health checks
- **Resource management:** CPU/memory limits with OOMKill protection
- **CI/CD Pipeline:** Automated build, test, and deploy via GitHub Actions

### 📊 Observability
- **Distributed Tracing:** End-to-end request flow visualization via Jaeger √
- **Metrics Collection:** Prometheus scraping with 15s intervals √
- **Service Discovery:** Automatic target discovery via ServiceMonitors √
- **SLI/SLO Dashboards:** Pre-configured Grafana dashboards with business metrics √
- **Real-time Alerting:** Alertmanager integration with intelligent routing

### 🤖 MLOps & AIOps
- **Automated Canary Deployment:** ML model upgrades with intelligent rollback √
- **AI-Powered Incident Analysis:** Google Gemini integration for root cause analysis √
- **Performance Monitoring:** Automatic comparison of model versions
- **Smart Rollback:** Based on error rate and latency metrics

### 🛡️ Production Readiness
- **Optimized Docker Images:** Multi-stage builds reducing image size by 60%
- **Security Hardening:** Non-root containers, minimal base images (distroless)
- **Health Checks:** Liveness and readiness probes
- **Auto-scaling:** HPA configuration (ready to enable)
- **Error Handling:** Graceful degradation with circuit breakers

---

## Quick Start

### Prerequisites

```bash
# Required tools
- kubectl 1.28+
- helm 3.12+
- Azure CLI (for AKS)
- Python 3.12+ (for MLOps scripts)

# Verify installations
kubectl version --client
helm version
python --version
```

### Deployment

```bash
# 1. Clone repository
git clone https://github.com/zihanKuang/Citrus-Orchestrator.git
cd Citrus-Orchestrator

# 2. Deploy to AKS
helm install citrus ./deploy/helm/citrus-app \\
  --namespace citrus \\
  --create-namespace

# 3. Wait for all pods to be ready (2-3 minutes)
kubectl wait --for=condition=ready pod --all -n citrus --timeout=300s

# 4. Get frontend external IP
kubectl get svc frontend -n citrus -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

### Advanced Workflows

```bash
# Deploy new ML model with canary release
python scripts/canary-deploy.py \\
  --service recommendationservice \\
  --baseline ghcr.io/zihankuang/citrus-recommendation:v1.0 \\
  --canary ghcr.io/zihankuang/citrus-recommendation:v1.1

# Start AI-powered incident assistant
export GEMINI_API_KEY="your-key"
python scripts/aiops-agent.py --mode server --port 5000
```

### Access Services

```bash
# Frontend (Shopping UI)
# Open browser to: http://<FRONTEND_IP>

# Jaeger (Distributed Tracing)
kubectl port-forward svc/citrus-jaeger-ui 16686:16686 -n citrus
# Open: http://localhost:16686

# Grafana (Metrics Dashboard)
kubectl port-forward svc/citrus-grafana 3000:80 -n citrus
# Open: http://localhost:3000 (admin/prom-operator)
```

---

## Project Structure

```
Citrus-Orchestrator/
├── .github/
│   └── workflows/
│       ├── ci.yaml                 # Legacy workflow (2 services)
│       └── ci-cd-full.yaml         # √ NEW: Full CI/CD pipeline
├── deploy/
│   ├── grafana/
│   │   └── recommendation-slo-dashboard.json  # √ NEW: SLI/SLO dashboard
│   └── helm/
│       └── citrus-app/
│           ├── Chart.yaml          # Helm metadata + dependencies
│           ├── values.yaml         # Configuration parameters
│           ├── README.md           # Detailed chart documentation
│           └── templates/
│               ├── all-in.yaml     # Main workload definitions
│               ├── servicemonitor.yaml  # Prometheus scrape configs
│               ├── hpa.yaml        # Auto-scaling policies
│               └── _helpers.tpl    # Go template functions
├── scripts/                        # √ NEW: MLOps & AIOps automation
│   ├── canary-deploy.py           # Intelligent canary deployment
│   ├── aiops-agent.py             # AI-powered incident analysis
│   ├── requirements.txt           # Python dependencies
│   └── README.md                  # Scripts documentation
├── src/                           # Microservice source code
│   ├── frontend/
│   │   └── Dockerfile             # √ OPTIMIZED: Multi-stage build
│   ├── recommendationservice/
│   │   └── Dockerfile             # √ OPTIMIZED: Multi-stage build
│   ├── cartservice/
│   ├── checkoutservice/
│   └── ... (10+ services)
├── TROUBLESHOOTING.md             # Complete debugging guide
└── README.md                      # This file
```

---

## Migration Journey: GKE → AKS

### Challenges Solved

| Problem | Impact | Solution | Learning |
|---------|--------|----------|----------|
| **RBAC Permission Conflicts** | GitLab CI couldn't deploy to GKE | Migrated to AKS with simplified IAM | Cloud IAM models differ significantly |
| **Service Discovery** | Frontend couldn't find backend services | Replaced hardcoded IPs with K8s DNS | Never hardcode network addresses |
| **Observability Gaps** | No visibility into request flows | Integrated Jaeger + Prometheus | Observability must be day-1 priority |
| **Cross-Cloud APIs** | GCP-specific code crashed on Azure | Disabled cloud SDKs via env flags | Portable code requires abstraction layers |

### Technical Decisions

**Why All-In-One Jaeger Instead of Distributed?**
- **Problem:** Distributed mode (Collector + Query + Agent) caused memory isolation
- **Symptom:** Traces sent to Collector didn't show in Query UI
- **Root Cause:** Each pod had independent in-memory storage with no shared backend
- **Decision:** Use All-In-One for dev/demo, plan Elasticsearch backend for production

**Why gRPC Instead of HTTP for Tracing?**
- **Problem:** HTTP/protobuf mode duplicated paths (`/v1/traces/v1/traces`)
- **Symptom:** Jaeger silently dropped malformed requests
- **Decision:** Switched to gRPC (port 4317) for cleaner protocol handling

**Why Disable Node Exporter on GKE but Enable on AKS?**
- **GKE Autopilot:** Blocks hostPath mounts (security policy)
- **AKS Standard:** Permits DaemonSet node access
- **Decision:** Enable only when infrastructure supports it

---

## Documentation

- **[Helm Chart README](deploy/helm/citrus-app/README.md)** - Architecture decisions and usage guide
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Complete problem-solving reference
- **[values.yaml](deploy/helm/citrus-app/values.yaml)** - Inline comments explaining each config

**Inline Code Comments:**
Every critical decision has comments explaining:
1. What problem was encountered
2. What was tried
3. Why the final solution works

Example:
```yaml
# CRITICAL: Frontend requires non-standard env vars (hardcoded in main.go)
# Standard OTEL_EXPORTER_OTLP_ENDPOINT is ignored by this image version
- name: ENABLE_TRACING
  value: "1"
- name: COLLECTOR_SERVICE_ADDR
  value: "jaeger-grpc-solid:4317"
```

---

## Monitoring & Observability

### Distributed Tracing with Jaeger

**What you can visualize:**
- End-to-end request latency across all services
- Dependency graphs (which service calls which)
- Error propagation and failure root cause
- Performance bottlenecks (slowest spans)

**Example trace path:**
```
Frontend → AdService → RecommendationService → ProductCatalog
   ↓
CartService → Redis
   ↓
CheckoutService → PaymentService → ShippingService
```

### Metrics with Prometheus

**Collected metrics:**
- HTTP request duration (histogram)
- gRPC call latency
- Pod CPU/memory usage
- Container restart counts

**Sa~~Phase 1: Production Hardening~~ √ COMPLETED
- [x] Automated CI/CD pipeline (GitHub Actions)
- [x] Optimized Docker images (multi-stage builds)
- [x] MLOps canary deployment automation
- [x] SLI/SLO monitoring dashboards
- [x] AI-powered incident analysis
- [ ] Mutual TLS between services (Istio/Linkerd)
- [ ] PodDisruptionBudgets for high availability

### Phase 2: Advanced Observability
- [ ] Custom Grafana dashboards for business metrics (order value, conversion rate)
- [ ] Synthetic monitoring with Blackbox Exporter
- [ ] Log aggregation with Fluentd + Elasticsearch
- [ ] Distributed tracing for all 11 services

### Phase 3: GitOps & Multi-Cluster
- [ ] ArgoCD for GitOps deployment
- [ ] Automated rollback on health check failures
- [ ] Multi-cluster deployment (blue/green across regions)
- [ ] Cost optimization with spot instances
- [ ] Replace LoadBalancer with NGINX Ingress Controller
- [ ] Implement mutual TLS between services (Istio/Linkerd)
- [ ] Add persistent storage for Jaeger (Elasticsearch backend)
- [ ] Configure PodDisruptionBudgets for high availability

### Phase 2: Advanced Observability
- [ ] Custom Grafana dashboards for business metrics (order value, conversion rate)
- [ ] Alerting rules in Prometheus (latency SLO violations)
- [ ] Log aggregation with Fluentd + Elasticsearch
- [ ] Synthetic monitoring with Blackbox Exporter

### Phase 3: GitOps & Automation
- [ ] ArgoCD for GitOps deployment
- [ ] GitHub Actions CI/CD pipeline
- [ ] Automated rollback on health check failures
- [ ] Multi-cluster deployment (blue/green)

---

## Performance & Cost Optimization

**Current Resource Usage (10 services):**
- Total CPU requests: ~1200m (1.2 cores)
- Total memory requests: ~2Gi
- Monthly AKS cost estimate: ~$150 USD (2-node Standard_D2s_v3 cluster)

**Optimization strategies implemented:**
1. Right-sized CPU/memory limits based on `kubectl top` data
2. Disabled profiler to reduce overhead (5-10% CPU savings)
3. In-memory tracing for dev (no Cassandra/ES storage costs)

---

## License

This project adapts Google's [microservices-demo](https://github.com/GoogleCloudPlatform/microservices-demo) under Apache License 2.0. Original microservices code retains Google's copyright. Helm charts and migration documentation are authored by Zihan Kuang.

---

## Acknowledgments

- **Google Cloud Team:** For the original microservices-demo
- **CNCF Projects:** Kubernetes, Helm, Prometheus, Jaeger
- **Community:** Stack Overflow, Kubernetes Slack, Reddit r/devops

---

## Contact

**Engineer:** Zihan Kuang  
**LinkedIn:** [linkedin.com/in/zihankuang](https://www.linkedin.com/in/zihan-kuang/)  
**GitHub:** [github.com/zihankuang](https://github.com/zihankuang)  
**Email:** zihan_kuang@outlook.com