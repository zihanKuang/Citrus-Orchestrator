"""Agent CLI exceptions."""


class AgentException(Exception):
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message)
        if original_error and hasattr(original_error, "__traceback__"):
            self.__traceback__ = original_error.__traceback__


class ToolNotFoundError(AgentException):
    pass


class ToolTimeoutError(AgentException):
    pass


class ToolExecutionError(AgentException):
    pass


class LLMError(AgentException):
    pass


class MCPConnectionError(AgentException):
    pass


class MaxStepsExceededError(AgentException):
    pass
