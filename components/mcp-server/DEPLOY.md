# MCP Server Deployment Guide (Phase 2.4)

Complete step-by-step guide to deploy MCP Server with RBAC security into your Kubernetes cluster.

##  Prerequisites

- Kubernetes cluster running (Docker Desktop, kind, or minikube)
- kubectl configured and connected
- Docker installed
- citrus namespace exists

Verify:
```bash
kubectl cluster-info
kubectl get namespace citrus
```

---

##  Step 1: Build Docker Image

Navigate to MCP Server directory:
```powershell
cd components/mcp-server
```

Build the multi-stage distroless image:
```bash
docker build -t mcp-server:v1 .
```

**Verify build:**
```bash
docker images | findstr mcp-server

# Expected output:
# mcp-server    v1    <image-id>   <size>   <time>
```

**Check image size** (should be ~50-100 MB, not 900 MB):
```bash
docker images mcp-server:v1 --format "{{.Size}}"
```

---

##  Step 2: Load Image into Cluster

### For Docker Desktop (Kubernetes)
```bash
# Image is already available (Docker Desktop shares images with K8s)
# No additional steps needed
```

### For kind
```bash
kind load docker-image mcp-server:v1
```

### For minikube
```bash
minikube image load mcp-server:v1
```

**Verify image in cluster:**
```bash
# For kind/minikube, check the image is loaded:
docker exec -it <kind-control-plane-node> crictl images | findstr mcp-server

# For Docker Desktop, the image should be directly available
```

---

##  Step 3: Apply RBAC Configuration

Deploy ServiceAccount, Role, and RoleBinding:
```bash
kubectl apply -f ../../infra/rbac/mcp-server-rbac.yaml
```

**Verify RBAC resources created:**
```bash
# Check ServiceAccount
kubectl get serviceaccount mcp-server-sa -n citrus
# Expected: NAME              SECRETS   AGE
#           mcp-server-sa     0         <time>

# Check Role
kubectl get role mcp-server-readonly -n citrus
# Expected: NAME                    CREATED AT
#           mcp-server-readonly     <timestamp>

# Check RoleBinding
kubectl get rolebinding mcp-server-readonly-binding -n citrus
# Expected: NAME                               ROLE                         AGE
#           mcp-server-readonly-binding        Role/mcp-server-readonly     <time>
```

**Verify RBAC permissions** (before deploying Pod):
```bash
# Should be allowed (get pods)
kubectl auth can-i get pods --as=system:serviceaccount:citrus:mcp-server-sa -n citrus
# Expected: yes

# Should be denied (delete pods)
kubectl auth can-i delete pods --as=system:serviceaccount:citrus:mcp-server-sa -n citrus
# Expected: no

# Should be denied (other namespace)
kubectl auth can-i get pods --as=system:serviceaccount:citrus:mcp-server-sa -n kube-system
# Expected: no
```

If you see unexpected results, review `infra/rbac/mcp-server-rbac.yaml`.

---

##  Step 4: Deploy MCP Server

Deploy the Pod:
```bash
kubectl apply -f ../../infra/manifests/mcp-server-deployment.yaml
```

**Watch deployment progress:**
```bash
kubectl get pods -n citrus -l app=mcp-server -w
# Press Ctrl+C to stop watching
```

**Expected output:**
```
NAME                          READY   STATUS    RESTARTS   AGE
mcp-server-xxxxxxxxxx-xxxxx   1/1     Running   0          30s
```

**If Pod is not Running, check events:**
```bash
kubectl describe pod -n citrus -l app=mcp-server

# Look for error messages in the Events section
```

**Common issues:**
- `ImagePullBackOff`: Image not loaded into cluster (redo Step 2)
- `CrashLoopBackOff`: Application error (check logs in Step 5)
- `Pending`: Resource constraints (check cluster has enough CPU/memory)

---

##  Step 5: Verify Deployment

### Check Pod Logs
```bash
kubectl logs -n citrus -l app=mcp-server --tail=50
```

**Expected log output:**
```
[OK] Kubernetes client initialized (in-cluster mode)
     Using ServiceAccount token from /var/run/secrets/...
     Permissions controlled by RBAC
[INFO] MCP Server initialized: citrus-k8s-ops
[INFO] Starting MCP server on stdio...
[INFO] Server ready. Waiting for client connection...
```

### Verify In-Cluster Config
```bash
# Get Pod name
$POD_NAME = kubectl get pods -n citrus -l app=mcp-server -o jsonpath='{.items[0].metadata.name}'

# Check ServiceAccount token is mounted
kubectl exec -n citrus $POD_NAME -- cat /var/run/secrets/kubernetes.io/serviceaccount/token
# Expected: Long JWT token string (starts with "eyJ...")

# Check namespace
kubectl exec -n citrus $POD_NAME -- cat /var/run/secrets/kubernetes.io/serviceaccount/namespace
# Expected: citrus
```

---

##  Step 6: RBAC Security Verification

This is the **most important step** - verify that RBAC correctly blocks dangerous operations.

### Copy test script to Pod
```bash
$POD_NAME = kubectl get pods -n citrus -l app=mcp-server -o jsonpath='{.items[0].metadata.name}'

kubectl cp test-rbac.py citrus/${POD_NAME}:/tmp/test-rbac.py
```

### Run RBAC verification
```bash
kubectl exec -n citrus $POD_NAME -- python3 /tmp/test-rbac.py
```

**Expected output:**
```
==================================================================
  MCP Server RBAC Verification
==================================================================

Environment:
  Namespace: citrus
  ServiceAccount Token: Found

==================================================================
  TEST 1: Read Operations (Should SUCCEED)
==================================================================

 PASS - List Pods (27 items)
 PASS - Get Pod Logs (1 items)
 PASS - List Events (X items)
 PASS - List Services (X items)

Read Operations: 4 passed, 0 failed

==================================================================
  TEST 2: Write Operations (Should FAIL with 403)
==================================================================

 PASS (Correctly blocked by RBAC) - Delete Pod
      Reason: Forbidden
 PASS (Correctly blocked by RBAC) - Create Pod
      Reason: Forbidden
 PASS (Correctly blocked by RBAC) - Patch Pod
      Reason: Forbidden

Write Operations: 3 correctly blocked, 0 issues

==================================================================
  TEST 3: Cross-Namespace Access (Should FAIL)
==================================================================

 PASS (Correctly blocked) - Namespace: kube-system
 PASS (Correctly blocked) - Namespace: default

Cross-Namespace: 2 correctly blocked, 0 issues

==================================================================
  FINAL SUMMARY
==================================================================

Total Tests Passed: 9
Total Tests Failed: 0

 ALL TESTS PASSED!
   RBAC is correctly configured:
    Read operations allowed
    Write operations blocked
    Cross-namespace access blocked
    Privileged operations blocked

   Your MCP Server is properly secured! 
```

### If tests FAIL

**Scenario 1: Write operations succeed (delete/create work)**
```
❌ FAIL - Operation succeeded (RBAC too permissive!)
   SECURITY ISSUE: This operation should be blocked!
```

**Fix:**
- Check that Pod is using `serviceAccountName: mcp-server-sa` in deployment YAML
- Verify RBAC Role only has verbs `["get", "list", "watch"]`
- Re-apply RBAC configuration

**Scenario 2: Read operations fail (get/list blocked)**
```
❌ FAIL (403 Forbidden - RBAC blocked) - List Pods
```

**Fix:**
- Check that RoleBinding correctly references the ServiceAccount
- Verify Role includes `pods` and `pods/log` in resources
- Check namespace matches everywhere (should be `citrus`)

---

##  Step 7: Manual Verification (The "Demo Story")

This is what you tell in interviews: "I intentionally tried to delete a pod to verify RBAC works."

### Test 1: Verify you CAN read pods
```bash
kubectl exec -n citrus $POD_NAME -- python3 -c "
from kubernetes import client, config
config.load_incluster_config()
v1 = client.CoreV1Api()
pods = v1.list_namespaced_pod('citrus', limit=5)
print(f'Found {len(pods.items)} pods')
for pod in pods.items:
    print(f'  - {pod.metadata.name}: {pod.status.phase}')
"
```

**Expected:**
```
Found 5 pods
  - frontend-xxx: Running
  - cart-xxx: Running
  - checkout-xxx: Running
  ...
```

### Test 2: Verify you CANNOT delete pods
```bash
kubectl exec -n citrus $POD_NAME -- python3 -c "
from kubernetes import client, config
from kubernetes.client.rest import ApiException
config.load_incluster_config()
v1 = client.CoreV1Api()
try:
    v1.delete_namespaced_pod('frontend-xxx', 'citrus')
    print('❌ SECURITY ISSUE: Delete succeeded!')
except ApiException as e:
    if e.status == 403:
        print(' RBAC correctly blocked delete operation')
        print(f'   Reason: {e.reason}')
    else:
        print(f'  Unexpected error: {e.status} {e.reason}')
"
```

**Expected:**
```
 RBAC correctly blocked delete operation
   Reason: Forbidden: User "system:serviceaccount:citrus:mcp-server-sa" 
           cannot delete resource "pods" in API group "" in the namespace "citrus"
```

**This 403 error is EXACTLY what you want!** 

---

##  Success Criteria

Phase 2.4 is complete when:

-  Docker image built with distroless base (~50-100 MB)
-  RBAC ServiceAccount, Role, RoleBinding applied
-  MCP Server Pod running in `citrus` namespace
-  Pod logs show "in-cluster mode" (not kubectl mode)
-  RBAC test script: all tests pass
-  Manual verification: read works, delete fails with 403

---

##  Interview Talking Points

After completing this phase, you can confidently say:

### Security Architecture
> "I deployed the MCP Server inside the cluster using a dedicated ServiceAccount with RBAC restrictions. The server can read pod logs and events (necessary for diagnostics) but cannot delete, create, or modify resources. Even if the AI hallucinates a dangerous command, Kubernetes physically blocks it with a 403 error."

### Distroless Benefits
> "I used Google's distroless Python image, which contains only the Python runtime—no shell, no package manager, no system utilities. This reduces the attack surface by 90%. If an attacker exploits a vulnerability, they have no tools to escalate privileges or move laterally."

### In-Cluster Config
> "Instead of mounting my personal kubeconfig (which has cluster-admin rights), I use in-cluster config. Kubernetes automatically injects a ServiceAccount token with minimal permissions. The token auto-rotates and is scoped to exactly what the application needs."

### Verification Story
> "To verify RBAC works, I intentionally added code to delete a pod. When deployed, Kubernetes returned 403 Forbidden, proving that even with malicious code or AI hallucinations, the RBAC policy acts as a physical barrier."

---

##  Cleanup (Optional)

To remove everything:
```bash
# Delete deployment
kubectl delete -f ../../infra/manifests/mcp-server-deployment.yaml

# Delete RBAC
kubectl delete -f ../../infra/rbac/mcp-server-rbac.yaml

# Delete image (if needed)
docker rmi mcp-server:v1
```

---

##  Troubleshooting

### Pod stuck in ImagePullBackOff
```bash
# Check if image exists locally
docker images | findstr mcp-server

# Reload image into cluster
# For kind:
kind load docker-image mcp-server:v1

# For minikube:
minikube image load mcp-server:v1
```

### Pod stuck in CrashLoopBackOff
```bash
# Check logs for Python errors
kubectl logs -n citrus -l app=mcp-server --tail=100

# Common issues:
# - Missing dependencies in requirements.txt
# - Syntax error in server.py or tools/kubernetes.py
# - Import error (check PYTHONPATH in Dockerfile)
```

### RBAC test fails: "Read operations blocked"
```bash
# Check ServiceAccount is bound to correct Role
kubectl get rolebinding mcp-server-readonly-binding -n citrus -o yaml

# Verify subjects.name matches ServiceAccount
# Verify roleRef.name matches Role

# Check Pod is using correct ServiceAccount
kubectl get pod -n citrus -l app=mcp-server -o jsonpath='{.items[0].spec.serviceAccountName}'
# Expected: mcp-server-sa
```

### Testing RBAC Permissions

To verify that RBAC correctly restricts the MCP Server:

```bash
# Run the RBAC test Pod
kubectl apply -f ../../infra/manifests/rbac-test-pod.yaml

# Wait for test to complete (10-15 seconds)
kubectl wait --for=condition=Ready pod/rbac-test -n citrus --timeout=30s || true

# View test results
kubectl logs -n citrus rbac-test

# Clean up
kubectl delete pod -n citrus rbac-test
```

**Expected output:**
- ✅ Read operations (list pods, get logs): PASS
- ❌ Write operations (delete, create): PASS (blocked with 403)
- ✅ Cross-namespace access: PASS (blocked with 403)

---

##  Related Files

- `Dockerfile` - Single-stage Python slim image
- `DOCKER-STRATEGY.md` - Docker image strategy comparison (Distroless vs Slim vs Alpine)
- `../../infra/rbac/mcp-server-rbac.yaml` - RBAC configuration
- `../../infra/manifests/mcp-server-deployment.yaml` - Kubernetes deployment
- `../../infra/manifests/rbac-test-pod.yaml` - RBAC verification test Pod
- `tools/kubernetes.py` - Updated with in-cluster config support

---

##  Next Steps

After Phase 2.4 is complete:

**Option A: Update README and Notes**
- Document Phase 2 learnings
- Add "What I learned" section
- Update project README with security features

**Option B: Proceed to Phase 3**
- Hand-write ReAct Agent loop (CLI tool)
- Implement tool calling orchestration
- Add error handling and retry logic

**Decision:** Complete all implementation first, then write comprehensive documentation at the end (your preference).
