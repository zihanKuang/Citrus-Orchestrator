"""
ReAct Agent - Hand-written implementation
Orchestrates LLM reasoning with tool execution

Architecture inspired by Source-Code patterns
"""
import asyncio
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from .config import AgentConfig
from .mcp_client import MCPClient
from .llm_client import LLMClient
from .retry_utils import get_retry_delay
from .logging_utils import log_agent_debug, log_agent_info, log_agent_error
from .exceptions import (
    MaxStepsExceededError,
    ToolExecutionError,
    ToolTimeoutError,
    ToolNotFoundError,
    LLMError
)


class ReActAgent:
    """
    ReAct (Reasoning + Acting) Agent
    
    Implements agentic loop:
    1. LLM reasons about next action
    2. Execute tool calls
    3. Observe results
    4. Repeat until conclusion
    """
    
    def __init__(self, config: AgentConfig):
        """
        Args:
            config: Agent configuration
        """
        self.config = config
        
        # Clients
        self.mcp_client = MCPClient(
            command=config.mcp_server_command,
            args=config.mcp_server_args
        )
        self.llm_client = LLMClient(
            provider=config.llm_provider,
            model_name=config.model_name,
            api_key=config.api_key
        )
        
        # State
        self.messages: List[Dict[str, Any]] = []
        self.tools: List[Dict[str, Any]] = []
        
        # Statistics
        self.stats = {
            "total_steps": 0,
            "tool_calls": {},
            "errors": 0,
            "start_time": None,
            "end_time": None,
            "tokens_used": 0
        }
        
        # Setup logging
        self._setup_logging()
        
        log_agent_info("Agent initialized")
    
    def _setup_logging(self):
        """Setup logging configuration"""
        level = getattr(logging, self.config.log_level)
        
        handlers = [logging.StreamHandler()]
        
        if self.config.log_to_file:
            log_file = f"agent_{datetime.now():%Y%m%d_%H%M%S}.log"
            handlers.append(logging.FileHandler(log_file))
        
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers,
            force=True
        )
    
    async def initialize(self):
        """Initialize agent (connect to MCP server, fetch tools)"""
        log_agent_info("Initializing agent...")
        
        # Connect to MCP server
        await self.mcp_client.connect()
        
        # Get available tools
        self.tools = self.mcp_client.get_tools()
        log_agent_info(f"Agent ready with {len(self.tools)} tools")
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.mcp_client.disconnect()
    
    async def run(self, user_query: str) -> str:
        """
        Run ReAct loop for user query
        
        Args:
            user_query: User's question or request
            
        Returns:
            Final answer from agent
        """
        self.stats["start_time"] = time.time()
        
        # Initialize conversation
        self.messages = [
            {"role": "user", "content": user_query}
        ]
        
        log_agent_info(f"Starting ReAct loop for: {user_query}")
        
        try:
            result = await self._react_loop()
            return result
        except MaxStepsExceededError:
            log_agent_error(f"Exceeded max steps ({self.config.max_steps})")
            return "Agent exceeded maximum reasoning steps without reaching a conclusion."
        except Exception as e:
            log_agent_error("Agent error", error=e)
            return f"Agent encountered an error: {str(e)}"
        finally:
            self.stats["end_time"] = time.time()
            self._print_stats()
    
    async def _react_loop(self) -> str:
        """Core ReAct reasoning loop"""
        
        for step in range(self.config.max_steps):
            self.stats["total_steps"] = step + 1
            
            log_agent_info(f"\n{'='*80}")
            log_agent_info(f"Step {step + 1}/{self.config.max_steps}")
            log_agent_info(f"{'='*80}")
            
            # 1. Get LLM response
            try:
                response = await self.llm_client.generate_with_tools(
                    messages=self.messages,
                    tools=self.tools
                )
            except LLMError as e:
                log_agent_error("LLM error", error=e)
                self.stats["errors"] += 1
                
                # Add error to conversation and retry
                self.messages.append({
                    "role": "assistant",
                    "content": f"Error calling LLM: {e}. Retrying..."
                })
                continue
            
            # 2. Check if LLM wants to call tools
            if response.get("tool_calls"):
                # Execute tool calls
                await self._handle_tool_calls(response["tool_calls"])
                
                # Continue loop for next reasoning step
                continue
            
            # 3. LLM provided final answer
            final_answer = response.get("content", "").strip()
            
            if not final_answer:
                log_agent_error("LLM returned empty response")
                continue
            
            log_agent_info(f"\nFinal Answer:\n{final_answer}")
            return final_answer
        
        # Exceeded max steps
        raise MaxStepsExceededError(f"Exceeded {self.config.max_steps} steps")
    
    async def _handle_tool_calls(self, tool_calls: List[Dict[str, Any]]):
        """
        Execute tool calls with retry logic
        
        Args:
            tool_calls: List of tool calls from LLM
        """
        log_agent_info(f"Executing {len(tool_calls)} tool call(s)")
        
        # Add assistant message with tool calls
        self.messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls
        })
        
        # Execute each tool
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            arguments = tool_call["function"]["arguments"]
            
            log_agent_debug(f"  -> {tool_name}({arguments})")
            
            # Execute with retry
            result = await self._execute_tool_with_retry(tool_name, arguments)
            
            # Truncate if too long
            result = self._truncate_if_needed(result)
            
            # Add result to conversation
            self.messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result
            })
            
            # Update stats
            self.stats["tool_calls"][tool_name] = \
                self.stats["tool_calls"].get(tool_name, 0) + 1
            
            log_agent_debug(f"  <- Result: {result[:200]}{'...' if len(result) > 200 else ''}")
    
    async def _execute_tool_with_retry(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> str:
        """
        Execute tool with exponential backoff retry
        
        Args:
            tool_name: Tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool result or error message
        """
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                # Execute tool
                result = await self.mcp_client.call_tool(tool_name, arguments)
                return result
                
            except ToolNotFoundError as e:
                # Tool doesn't exist - don't retry
                log_agent_error("Tool not found", error=e)
                self.stats["errors"] += 1
                return f"ERROR: {str(e)}"
            
            except ToolTimeoutError as e:
                # Timeout - retry with exponential backoff and jitter
                # (inspired by Source-Code/services/api/withRetry.ts)
                last_error = e
                
                if attempt < self.config.max_retries - 1:
                    delay = get_retry_delay(
                        attempt=attempt + 1,
                        base_delay_ms=self.config.base_retry_delay_ms,
                        max_delay_ms=self.config.max_retry_delay_ms,
                        jitter_factor=self.config.retry_jitter_factor
                    )
                    log_agent_error(
                        f"Tool timeout, retrying in {delay:.2f}s... (attempt {attempt + 1}/{self.config.max_retries})",
                        error=e
                    )
                    await asyncio.sleep(delay)
                else:
                    log_agent_error(f"Tool timeout after {self.config.max_retries} attempts")
                    self.stats["errors"] += 1
                    return f"ERROR: Tool timed out after {self.config.max_retries} attempts"
            
            except ToolExecutionError as e:
                # Execution error - return to LLM
                log_agent_error("Tool execution error", error=e)
                self.stats["errors"] += 1
                return f"ERROR: {str(e)}"
            
            except Exception as e:
                # Unexpected error
                log_agent_error("Unexpected error during tool execution", error=e)
                self.stats["errors"] += 1
                return f"ERROR: Unexpected error: {str(e)}"
        
        # All retries exhausted
        return f"ERROR: Max retries exceeded. Last error: {last_error}"
    
    def _truncate_if_needed(self, content: str) -> str:
        """
        Truncate content if too long (preserve head and tail)
        
        Args:
            content: Content to potentially truncate
            
        Returns:
            Truncated or original content
        """
        max_length = self.config.max_content_length
        
        if len(content) <= max_length:
            return content
        
        # Keep head and tail
        head_size = max_length // 2
        tail_size = max_length - head_size - 100  # Reserve space for truncation message
        
        truncated = (
            content[:head_size]
            + f"\n\n... [TRUNCATED {len(content) - max_length} characters] ...\n\n"
            + content[-tail_size:]
        )
        
        log_agent_debug(f"Truncated content from {len(content)} to {len(truncated)} chars")
        
        return truncated
    
    def _print_stats(self):
        """Print agent execution statistics"""
        duration = self.stats["end_time"] - self.stats["start_time"]
        
        print(f"\n{'='*80}")
        print("Agent Statistics")
        print(f"{'='*80}")
        print(f"Duration:     {duration:.2f}s")
        print(f"Total steps:  {self.stats['total_steps']}")
        print(f"Tool calls:   {sum(self.stats['tool_calls'].values())}")
        
        if self.stats['tool_calls']:
            print(f"\n  Tool usage:")
            for tool, count in sorted(self.stats['tool_calls'].items()):
                print(f"    - {tool}: {count}x")
        
        print(f"\n  Errors:       {self.stats['errors']}")
        print(f"{'='*80}\n")
