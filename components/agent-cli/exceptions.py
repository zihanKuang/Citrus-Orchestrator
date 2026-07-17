"""
Custom exceptions for Agent CLI
"""


class AgentException(Exception):
    """Base exception for all agent errors"""
    pass


class ToolNotFoundError(AgentException):
    """Raised when requested tool doesn't exist"""
    pass


class ToolTimeoutError(AgentException):
    """Raised when tool execution times out"""
    pass


class ToolExecutionError(AgentException):
    """Raised when tool execution fails"""
    pass


class LLMError(AgentException):
    """Raised when LLM API call fails"""
    pass


class MCPConnectionError(AgentException):
    """Raised when MCP server connection fails"""
    pass


class MaxStepsExceededError(AgentException):
    """Raised when agent exceeds maximum reasoning steps"""
    pass
