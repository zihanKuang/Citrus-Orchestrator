"""
Configuration for Agent CLI
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentConfig:
    """Agent configuration"""
    
    # LLM settings
    llm_provider: str = "gemini"  # "gemini", "openai", "anthropic"
    model_name: str = "gemini-2.0-flash-exp"
    api_key: Optional[str] = None
    
    # MCP settings
    mcp_server_command: str = "python"
    mcp_server_args: list[str] = ["./components/mcp-server/server.py"]
    
    # Agent settings
    max_steps: int = 10
    max_retries: int = 3
    base_retry_delay: float = 1.0
    max_retry_delay: float = 16.0
    
    # Context settings
    max_content_length: int = 4000
    
    # Logging
    log_level: str = "INFO"
    log_to_file: bool = True
    
    def __post_init__(self):
        """Load from environment variables if not provided"""
        if self.api_key is None:
            self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        if self.mcp_server_args is None:
            # Default: local MCP server
            server_path = os.path.join(
                os.path.dirname(__file__),
                "..", "mcp-server", "server.py"
            )
            self.mcp_server_args = [server_path]
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create config from environment variables"""
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "gemini"),
            model_name=os.getenv("MODEL_NAME", "gemini-2.0-flash-exp"),
            api_key=os.getenv("GEMINI_API_KEY"),
            max_steps=int(os.getenv("MAX_STEPS", "10")),
        )
