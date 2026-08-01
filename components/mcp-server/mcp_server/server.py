#!/usr/bin/env python3
"""
MCP server for Kubernetes ops tools.

Transports: stdio (local Agent child) or streamable-http (in-cluster Service).
"""

import asyncio
import logging
import os
from typing import Any, Sequence

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .tools import KubernetesTools
from .tools.kubernetes import default_prometheus_url, resolve_namespace

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

NAMESPACE = resolve_namespace()
PROMETHEUS_URL = default_prometheus_url()

server = Server("citrus-k8s-ops")
k8s_tools = KubernetesTools(namespace=NAMESPACE)

logger.info(
    "MCP Server initialized: citrus-k8s-ops "
    f"(namespace={NAMESPACE}, prometheus={PROMETHEUS_URL})"
)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return list of available tools for AI client."""
    logger.info("Client requested tool list")

    return [
        Tool(
            name="list_pods",
            description=(
                f"List all pods in the '{NAMESPACE}' namespace with phase, readiness, "
                "restart counts, and component labels. "
                "Use this first during incident triage. "
                f"Namespace is fixed to {NAMESPACE}."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_pod_logs",
            description=(
                f"Retrieve recent logs from pods in '{NAMESPACE}' matching a label selector. "
                f"Namespace is fixed to {NAMESPACE}. "
                "Useful for debugging errors or investigating incidents."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pod_selector": {
                        "type": "string",
                        "description": (
                            "Kubernetes label selector "
                            "(e.g., 'app.kubernetes.io/component=frontend')"
                        ),
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of recent log lines to retrieve",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 1000,
                    },
                },
                "required": ["pod_selector"],
            },
        ),
        Tool(
            name="get_pod_status",
            description=(
                f"Get status for pods in '{NAMESPACE}' matching a label selector "
                "(pod name, phase, restart count, readiness)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pod_selector": {
                        "type": "string",
                        "description": (
                            "Kubernetes label selector "
                            "(e.g., 'app.kubernetes.io/component=frontend')"
                        ),
                    }
                },
                "required": ["pod_selector"],
            },
        ),
        Tool(
            name="get_recent_events",
            description=(
                f"Get Kubernetes events from '{NAMESPACE}' within a time window. "
                "Shows timestamp, type, reason, and message. "
                "Look for Killing, Started, Pulled, BackOff, Unhealthy after chaos."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "minutes": {
                        "type": "integer",
                        "description": "Only include events from the last N minutes",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 1440,
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="query_prometheus",
            description=(
                "Execute a PromQL query against Prometheus. "
                f"Default URL: {PROMETHEUS_URL}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "promql": {
                        "type": "string",
                        "description": "Prometheus Query Language expression",
                    },
                    "prometheus_url": {
                        "type": "string",
                        "description": "Override Prometheus server URL",
                        "default": PROMETHEUS_URL,
                    },
                },
                "required": ["promql"],
            },
        ),
        Tool(
            name="validate_recovery",
            description=(
                "Closed-loop verification after an incident or chaos experiment. "
                "Checks that pods matching a selector are Running and Ready. "
                "Returns PASS or FAIL. Read-only; cannot mutate the cluster."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pod_selector": {
                        "type": "string",
                        "description": (
                            "Kubernetes label selector "
                            "(e.g., 'app.kubernetes.io/component=frontend')"
                        ),
                    },
                    "min_ready": {
                        "type": "integer",
                        "description": "Minimum Ready pods required to PASS",
                        "default": 1,
                        "minimum": 1,
                    },
                },
                "required": ["pod_selector"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
    """Route tool calls to KubernetesTools methods."""
    logger.info(f"Tool called: {name} with arguments: {arguments}")
    arguments = arguments or {}

    try:
        if name == "list_pods":
            result = await k8s_tools.list_pods()

        elif name == "get_pod_logs":
            result = await k8s_tools.get_pod_logs(
                pod_selector=arguments["pod_selector"],
                lines=arguments.get("lines", 50),
            )

        elif name == "get_pod_status":
            result = await k8s_tools.get_pod_status(
                pod_selector=arguments["pod_selector"]
            )

        elif name == "get_recent_events":
            result = await k8s_tools.get_recent_events(
                minutes=arguments.get("minutes", 10)
            )

        elif name == "query_prometheus":
            result = await k8s_tools.query_prometheus(
                promql=arguments["promql"],
                prometheus_url=arguments.get("prometheus_url") or PROMETHEUS_URL,
            )

        elif name == "validate_recovery":
            result = await k8s_tools.validate_recovery(
                pod_selector=arguments["pod_selector"],
                min_ready=arguments.get("min_ready", 1),
            )

        else:
            raise ValueError(f"Unknown tool: {name}")

        return [TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error executing {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Tool execution failed: {str(e)}")]


async def run_stdio() -> None:
    logger.info("Starting MCP server on stdio...")
    try:
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Server ready. Waiting for client connection...")
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    except Exception as e:
        logger.warning(f"stdio_server closed: {e}")


async def run_http(host: str, port: int) -> None:
    from .http_transport import run_streamable_http

    logger.info(f"Starting MCP server on http://{host}:{port}/mcp")
    await run_streamable_http(server, host=host, port=port)


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Citrus MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="stdio for local child process; streamable-http for K8s Service",
    )
    parser.add_argument("--host", default=os.getenv("MCP_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8080")))
    return parser.parse_args()


async def main():
    args = _parse_args()
    if args.transport == "stdio":
        await run_stdio()
        # Keep the container alive if someone still runs stdio in-cluster
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            logger.info("In-cluster + stdio: idling (prefer streamable-http)")
            await asyncio.Event().wait()
    else:
        await run_http(args.host, args.port)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server crashed: {e}", exc_info=True)
        raise
