"""
ReAct Agent CLI Package

Architecture inspired by Claude Code patterns
"""

from .exceptions import (
    AgentException,
    ToolNotFoundError,
    ToolTimeoutError,
    ToolExecutionError,
    LLMError,
    MCPConnectionError,
    MaxStepsExceededError,
)

__version__ = "0.2.0"

__all__ = [
    "ReActAgent",
    "AgentConfig",
    "MCPClient",
    "LLMClient",
    "get_retry_delay",
    "AgentException",
    "ToolNotFoundError",
    "ToolTimeoutError",
    "ToolExecutionError",
    "LLMError",
    "MCPConnectionError",
    "MaxStepsExceededError",
]


def __getattr__(name: str):
    """Lazy imports so importing config does not pull Gemini SDK."""
    if name == "ReActAgent":
        from .agent import ReActAgent
        return ReActAgent
    if name == "AgentConfig":
        from .config import AgentConfig
        return AgentConfig
    if name == "MCPClient":
        from .mcp_client import MCPClient
        return MCPClient
    if name == "LLMClient":
        from .llm_client import LLMClient
        return LLMClient
    if name == "get_retry_delay":
        from .retry_utils import get_retry_delay
        return get_retry_delay
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
