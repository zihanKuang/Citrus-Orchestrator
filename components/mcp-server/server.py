#!/usr/bin/env python3
"""
MCP Server for Kubernetes Operations

Exposes Kubernetes inspection tools via Model Context Protocol (MCP).
AI clients can discover and invoke these tools automatically.
"""

import asyncio
import logging
import os
from typing import Any, Sequence

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from tools import KubernetesTools

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

server = Server("citrus-k8s-ops")
k8s_tools = KubernetesTools(namespace="citrus")

logger.info("MCP Server initialized: citrus-k8s-ops")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return list of available tools for AI client."""
    logger.info("Client requested tool list")
    
    return [
        Tool(
            name="list_pods",
            description=(
                "List all pods in the citrus namespace with phase, readiness, "
                "restart counts, and component labels. "
                "Use this first during incident triage to discover which workloads exist "
                "and which look unhealthy. Namespace is fixed to citrus."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        Tool(
            name="get_pod_logs",
            description=(
                "Retrieve recent logs from pods in the citrus namespace matching a label selector. "
                "Namespace is fixed to citrus; do not ask the user about namespaces. "
                "Useful for debugging errors, checking application output, or investigating incidents."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pod_selector": {
                        "type": "string",
                        "description": (
                            "Kubernetes label selector "
                            "(e.g., 'app.kubernetes.io/component=frontend')"
                        )
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of recent log lines to retrieve",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 1000
                    }
                },
                "required": ["pod_selector"]
            }
        ),
        
        Tool(
            name="get_pod_status",
            description=(
                "Get status for pods in the citrus namespace matching a label selector "
                "(pod name, phase, restart count, readiness). "
                "Namespace is fixed to citrus; call this tool directly instead of asking about namespaces."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pod_selector": {
                        "type": "string",
                        "description": (
                            "Kubernetes label selector "
                            "(e.g., 'app.kubernetes.io/component=frontend')"
                        )
                    }
                },
                "required": ["pod_selector"]
            }
        ),
        
        Tool(
            name="get_recent_events",
            description=(
                "Get recent Kubernetes events from the citrus namespace. "
                "Shows timestamp, type, reason, and message. "
                "Look for Killing, Started, Pulled, BackOff, Unhealthy after chaos experiments."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "minutes": {
                        "type": "integer",
                        "description": "Time window in minutes",
                        "default": 10,
                        "minimum": 1
                    }
                },
                "required": []
            }
        ),
        
        Tool(
            name="query_prometheus",
            description=(
                "Execute a PromQL query against Prometheus. "
                "Returns metric values for the given query."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "promql": {
                        "type": "string",
                        "description": "Prometheus Query Language expression"
                    },
                    "prometheus_url": {
                        "type": "string",
                        "description": "Prometheus server URL",
                        "default": "http://localhost:9090"
                    }
                },
                "required": ["promql"]
            }
        ),

        Tool(
            name="validate_recovery",
            description=(
                "Closed-loop verification after an incident or chaos experiment. "
                "Checks that pods matching a selector are Running and Ready "
                "(ReplicaSet self-heal). Returns PASS or FAIL. "
                "Always call this before declaring an incident resolved. "
                "This tool is read-only and cannot mutate the cluster."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pod_selector": {
                        "type": "string",
                        "description": (
                            "Kubernetes label selector "
                            "(e.g., 'app.kubernetes.io/component=frontend')"
                        )
                    },
                    "min_ready": {
                        "type": "integer",
                        "description": "Minimum Ready pods required to PASS",
                        "default": 1,
                        "minimum": 1
                    }
                },
                "required": ["pod_selector"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
    """
    Route tool calls to appropriate methods.
    
    Args:
        name: Tool name
        arguments: Tool parameters
        
    Returns:
        Tool output wrapped in TextContent
    """
    logger.info(f"Tool called: {name} with arguments: {arguments}")
    
    try:
        if name == "list_pods":
            result = await k8s_tools.list_pods()

        elif name == "get_pod_logs":
            result = await k8s_tools.get_pod_logs(
                pod_selector=arguments["pod_selector"],
                lines=arguments.get("lines", 50)
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
                prometheus_url=arguments.get("prometheus_url", "http://localhost:9090")
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
        error_message = f"Tool execution failed: {str(e)}"
        return [TextContent(type="text", text=error_message)]


async def main():
    """Start the MCP server with stdio transport."""
    logger.info("Starting MCP server on stdio...")
    
    try:
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Server ready. Waiting for client connection...")
            
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    except Exception as e:
        logger.warning(f"stdio_server closed: {e}")
    
    # In Kubernetes Pods, stdin closes immediately and the process would exit.
    # Keep alive only when running in-cluster so local stdio clients can exit cleanly.
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        logger.info("In-cluster mode: keeping process alive after stdio closed")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            logger.info("Server shutdown requested")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server crashed: {e}", exc_info=True)
        raise
