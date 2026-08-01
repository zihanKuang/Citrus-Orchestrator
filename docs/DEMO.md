# Interview / local demo

Cluster must be running (`kubectl get ns citrus` works). If not, start Kind/Docker Desktop Kubernetes first, then deploy.

## A. Platform up

```powershell
.\scripts\deployment\0-deploy-all.ps1
kubectl get pods -n citrus
```

Expect otel-demo + monitoring pods Running (may take several minutes).

## B. Agent (stdio) smoke test

```powershell
cd components
# one-time in this venv (if you see No module named mcp / agent_cli):
#   pip install -e ".[test]"
#   pip install -e "mcp-server[test]"
# agent_cli/.env with GEMINI_API_KEY=
python -m agent_cli "List pods in citrus and summarize unhealthy ones."
```

Expect: tool calls (`list_pods` / `get_pod_status` / …) then a short summary.

## C. Chaos + RCA (main showcase)

```powershell
# once per cluster
.\infra\chaos\install-chaos-mesh.ps1

.\infra\chaos\run-demo.ps1

cd components
python -m agent_cli "What just happened to the frontend pods in citrus? Short RCA, then validate_recovery."
```

What you should be able to say in interview:

1. Chaos Mesh killed one frontend pod  
2. ReplicaSet recreated it (infra self-heal)  
3. Agent used MCP tools: events → status → `validate_recovery` → PASS/FAIL  
4. Agent cannot delete pods (RBAC) — that is intentional  

Cleanup:

```powershell
kubectl delete -f infra/chaos/pod-kill-frontend.yaml
```

## D. Optional HTTP MCP

```powershell
cd components\mcp-server
docker build -t mcp-server:v4 .
# Kind: kind load docker-image mcp-server:v4
# Docker Desktop K8s: image usually already visible

kubectl apply -f ..\..\infra\rbac\mcp-server-rbac.yaml
kubectl apply -f ..\..\infra\manifests\mcp-server-secret.yaml
kubectl apply -f ..\..\infra\manifests\mcp-server-service.yaml
kubectl apply -f ..\..\infra\manifests\mcp-server-networkpolicy.yaml
kubectl apply -f ..\..\infra\manifests\mcp-server-deployment.yaml

kubectl port-forward -n citrus svc/mcp-server 8080:8080
curl http://127.0.0.1:8080/health

cd ..
$env:MCP_AUTH_TOKEN="change-me-citrus-mcp"
python -m agent_cli --mcp-url http://127.0.0.1:8080/mcp "List pods"
```

## If something fails

| Symptom | Check |
|---------|--------|
| kubectl connection refused | Start local cluster; fix kubecontext |
| No frontend pods | `2-deploy-application.ps1` |
| Chaos CRD missing | `install-chaos-mesh.ps1` (Docker Desktop may need docker runtime socket — see script footer) |
| Agent no GEMINI key | `agent_cli/.env` |
| HTTP 401 | `MCP_AUTH_TOKEN` must match Secret |
| MCP pod CrashLoop | `kubectl logs -n citrus -l app=mcp-server` |
