"""
ReAct Agent CLI Package

Architecture inspired by Cluade-Code patterns
"""

from .agent import ReActAgent
from .config import AgentConfig
from .mcp_client import MCPClient
from .llm_client import LLMClient
from .retry_utils import get_retry_delay
from .logging_utils import (
    log_agent_debug,
    log_agent_info,
    log_agent_error,
    log_mcp_debug,
    log_mcp_error,
    log_llm_debug,
    log_llm_error,
)
from .exceptions import (
    AgentException,
    ToolNotFoundError,
    ToolTimeoutError,
    ToolExecutionError,
    LLMError,
    MCPConnectionError,
    MaxStepsExceededError
)

__version__ = "0.2.0"  # Bumped for Cluade-Code inspired improvements

__all__ = [
    "ReActAgent",
    "AgentConfig",
    "MCPClient",
    "LLMClient",
    "get_retry_delay",
    "log_agent_debug",
    "log_agent_info",
    "log_agent_error",
    "log_mcp_debug",
    "log_mcp_error",
    "log_llm_debug",
    "log_llm_error",
    "AgentException",
    "ToolNotFoundError",
    "ToolTimeoutError",
    "ToolExecutionError",
    "LLMError",
    "MCPConnectionError",
    "MaxStepsExceededError",
]
