"""
Configuration for Agent CLI
"""
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from .prompts import DEFAULT_SRE_SYSTEM_INSTRUCTION

# Load .env from this package directory (if present)
_PACKAGE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE_DIR.parent.parent
_MCP_SERVER_DIR = _PACKAGE_DIR.parent / "mcp-server"

load_dotenv(_PACKAGE_DIR / ".env", encoding="utf-8-sig")
load_dotenv(_REPO_ROOT / ".env", encoding="utf-8-sig")


def _default_mcp_server_args() -> list[str]:
    """Absolute path to MCP server entrypoint."""
    return [str(_MCP_SERVER_DIR / "server.py")]


@dataclass
class AgentConfig:
    """Agent configuration"""

    # LLM settings
    llm_provider: str = "gemini"
    model_name: str = "gemini-2.5-flash"
    api_key: Optional[str] = None
    system_instruction: str = DEFAULT_SRE_SYSTEM_INSTRUCTION

    # MCP settings
    mcp_server_command: str = field(default_factory=lambda: sys.executable)
    mcp_server_args: list[str] = field(default_factory=_default_mcp_server_args)
    mcp_server_cwd: Optional[str] = None
    tool_timeout_seconds: float = 60.0

    # Agent settings
    max_steps: int = 10

    # Retry settings (inspired by Claude Code withRetry patterns)
    max_retries: int = 3
    base_retry_delay_ms: int = 500
    max_retry_delay_ms: int = 32000
    retry_jitter_factor: float = 0.25

    # Context settings
    max_content_length: int = 4000

    # Logging
    log_level: str = "INFO"
    log_to_file: bool = False

    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")

        if self.mcp_server_cwd is None:
            self.mcp_server_cwd = str(_MCP_SERVER_DIR)

        env_timeout = os.getenv("TOOL_TIMEOUT_SECONDS")
        if env_timeout:
            self.tool_timeout_seconds = float(env_timeout)

        env_prompt = os.getenv("AGENT_SYSTEM_INSTRUCTION")
        if env_prompt:
            self.system_instruction = env_prompt

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create config from environment variables"""
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "gemini"),
            model_name=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
            api_key=os.getenv("GEMINI_API_KEY"),
            max_steps=int(os.getenv("MAX_STEPS", "10")),
        )
