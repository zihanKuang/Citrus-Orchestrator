"""Write-tool guards — no cluster. Name/replica checks only."""
import asyncio

from mcp_server.tools.kubernetes import KubernetesTools


def test_restart_rejects_path_injection():
    tools = KubernetesTools(namespace="citrus", use_kubectl=True)
    result = asyncio.run(tools.restart_deployment("../kube-system"))
    assert result.startswith("ERROR: invalid")


def test_scale_rejects_out_of_range():
    tools = KubernetesTools(namespace="citrus", use_kubectl=True)
    high = asyncio.run(tools.scale_deployment("frontend", 9))
    zero = asyncio.run(tools.scale_deployment("frontend", 0))
    assert "out of low-risk range" in high
    assert "out of low-risk range" in zero
