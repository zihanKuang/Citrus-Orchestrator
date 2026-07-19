"""
Custom exceptions for Agent CLI

Inspired by Cluade-Code/services/api/errors.ts
"""


class AgentException(Exception):
    """Base exception for all agent errors"""
    
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message)
        
        # Preserve original stack trace (inspired by Cluade-Code)
        if original_error and hasattr(original_error, '__traceback__'):
            self.__traceback__ = original_error.__traceback__


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
