"""
Logging utilities

Inspired by Cluade-Code's specialized logging functions
"""
import logging


# Create specialized loggers
mcp_logger = logging.getLogger("agent_cli.mcp")
llm_logger = logging.getLogger("agent_cli.llm")
agent_logger = logging.getLogger("agent_cli.agent")


def log_mcp_debug(message: str, **kwargs):
    """Log MCP-related debug info"""
    mcp_logger.debug(message, **kwargs)


def log_mcp_error(message: str, error: Exception = None, **kwargs):
    """Log MCP-related errors"""
    if error:
        mcp_logger.error(f"{message}: {error}", exc_info=error, **kwargs)
    else:
        mcp_logger.error(message, **kwargs)


def log_llm_debug(message: str, **kwargs):
    """Log LLM-related debug info"""
    llm_logger.debug(message, **kwargs)


def log_llm_error(message: str, error: Exception = None, **kwargs):
    """Log LLM-related errors"""
    if error:
        llm_logger.error(f"{message}: {error}", exc_info=error, **kwargs)
    else:
        llm_logger.error(message, **kwargs)


def log_agent_debug(message: str, **kwargs):
    """Log agent-related debug info"""
    agent_logger.debug(message, **kwargs)


def log_agent_info(message: str, **kwargs):
    """Log agent-related info"""
    agent_logger.info(message, **kwargs)


def log_agent_error(message: str, error: Exception = None, **kwargs):
    """Log agent-related errors"""
    if error:
        agent_logger.error(f"{message}: {error}", exc_info=error, **kwargs)
    else:
        agent_logger.error(message, **kwargs)
