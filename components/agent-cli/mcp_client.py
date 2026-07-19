"""
MCP Client - Handles connection to MCP Server

Inspired by Cluade-Code/services/mcp/client.ts
"""
import asyncio
from typing import List, Dict, Any
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .exceptions import MCPConnectionError, ToolNotFoundError, ToolExecutionError
from .logging_utils import log_mcp_debug, log_mcp_error


class MCPClient:
    """Client for connecting to and interacting with MCP Server"""
    
    def __init__(self, command: str, args: List[str]):
        """
        Args:
            command: Command to start MCP server (e.g., "python")
            args: Arguments for the command (e.g., ["server.py"])
        """
        self.command = command
        self.args = args
        self.session: ClientSession = None
        self.exit_stack = AsyncExitStack()
        self._tools_cache: Dict[str, Dict] = {}
    
    async def connect(self):
        """Connect to MCP server"""
        try:
            log_mcp_debug(f"Connecting to MCP server: {self.command} {' '.join(self.args)}")
            
            server_params = StdioServerParameters(
                command=self.command,
                args=self.args,
                env=None
            )
            
            # Start stdio client
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read_stream, write_stream = stdio_transport
            
            # Create session
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            
            # Initialize session
            await self.session.initialize()
            
            log_mcp_debug("Connected to MCP server")
            
            # Fetch available tools
            await self._fetch_tools()
            
        except Exception as e:
            log_mcp_error("Failed to connect to MCP server", error=e)
            raise MCPConnectionError(f"MCP connection failed: {e}", original_error=e)
    
    async def disconnect(self):
        """Disconnect from MCP server"""
        try:
            await self.exit_stack.aclose()
            log_mcp_debug("Disconnected from MCP server")
        except Exception as e:
            log_mcp_error("Error during disconnect", error=e)
    
    async def _fetch_tools(self):
        """Fetch available tools from MCP server"""
        try:
            response = await self.session.list_tools()
            
            for tool in response.tools:
                self._tools_cache[tool.name] = {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                }
            
            log_mcp_debug(f"Fetched {len(self._tools_cache)} tools from MCP server")
            log_mcp_debug(f"Available tools: {list(self._tools_cache.keys())}")
            
        except Exception as e:
            log_mcp_error("Failed to fetch tools", error=e)
            raise MCPConnectionError(f"Failed to fetch tools: {e}", original_error=e)
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools in LLM function calling format"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"]
                }
            }
            for tool in self._tools_cache.values()
        ]
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Call a tool through MCP
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool result as string
            
        Raises:
            ToolNotFoundError: If tool doesn't exist
            ToolExecutionError: If tool execution fails
        """
        if tool_name not in self._tools_cache:
            raise ToolNotFoundError(f"Tool '{tool_name}' not found. Available: {list(self._tools_cache.keys())}")
        
        try:
            log_mcp_debug(f"Calling tool: {tool_name} with args: {arguments}")
            
            result = await self.session.call_tool(tool_name, arguments)
            
            # Extract text content from result
            if hasattr(result, 'content') and len(result.content) > 0:
                # MCP returns list of Content objects
                content_parts = []
                for content in result.content:
                    if hasattr(content, 'text'):
                        content_parts.append(content.text)
                    else:
                        content_parts.append(str(content))
                
                result_text = "\n".join(content_parts)
            else:
                result_text = str(result)
            
            log_mcp_debug(f"Tool result: {result_text[:200]}{'...' if len(result_text) > 200 else ''}")
            
            return result_text
            
        except Exception as e:
            log_mcp_error(f"Tool execution failed: {tool_name}", error=e)
            raise ToolExecutionError(f"Tool '{tool_name}' execution failed: {e}", original_error=e)
