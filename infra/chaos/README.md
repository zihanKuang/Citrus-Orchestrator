# One-shot chaos + agent reminder (after platform is up)

```powershell
# 0) cluster + citrus namespace already deployed
kubectl get pods -n citrus

# 1) chaos (once)
.\infra\chaos\install-chaos-mesh.ps1

# 2) inject + wait
.\infra\chaos\run-demo.ps1

# 3) diagnose
cd components
python -m agent_cli "What happened to frontend in citrus? RCA + validate_recovery."
```
