# MCP Server for Kubernetes Operations

AI-powered Kubernetes operations server using Model Context Protocol (MCP).

## Features

- **get_pod_logs**: Retrieve pod logs by label selector
- **get_pod_status**: Check pod health, restarts, and readiness
- **get_recent_events**: View recent Kubernetes events
- **query_prometheus**: Execute PromQL queries

## Setup

### Install Dependencies

```bash
cd components/mcp-server
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```

### Configure Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "citrus-k8s-ops": {
      "command": "c:\\app\\Projects\\Citrus-Orchestrator\\components\\mcp-server\\.venv\\Scripts\\python.exe",
      "args": [
        "c:\\app\\Projects\\Citrus-Orchestrator\\components\\mcp-server\\server.py"
      ]
    }
  }
}
```

Replace paths with your absolute paths.

### Restart Claude Desktop

After restarting, you should see a 🔨 icon indicating MCP tools are available.

## Usage

Ask Claude in natural language:

```
Show me the logs from frontend pods
What's the status of all pods in citrus namespace?
What are the recent Kubernetes events?
Query Prometheus for service uptime using query: up
```

## Testing

Test tools independently:

```python
python
>>> from tools import KubernetesTools
>>> import asyncio
>>> tools = KubernetesTools(namespace="citrus")
>>> result = asyncio.run(tools.get_pod_logs("app.kubernetes.io/component=frontend", lines=10))
>>> print(result)
```

Test server:

```bash
python server.py
# Should show: "Server ready. Waiting for client connection..."
# Press Ctrl+C to stop
```

## Troubleshooting

**MCP tools not showing in Claude:**
- Verify JSON syntax in config file
- Use absolute paths
- Restart Claude Desktop completely

**kubectl not found:**
- Ensure kubectl is in PATH
- Add KUBECONFIG env var to config if needed

**Permission errors:**
- Verify kubeconfig has read permissions
- Check cluster context: `kubectl config current-context`

## Architecture

```
Claude Desktop (AI Client)
    ↓ stdio (JSON-RPC)
MCP Server (server.py)
    ↓
KubernetesTools (tools/kubernetes.py)
    ↓ subprocess
kubectl → Kubernetes API
```
