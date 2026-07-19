"""
LLM Client - Handles calls to Language Model APIs
"""
from typing import List, Dict, Any, Optional
import google.generativeai as genai

from .exceptions import LLMError
from .logging_utils import log_llm_debug, log_llm_error


class LLMClient:
    """Client for interacting with Language Models"""
    
    def __init__(self, provider: str, model_name: str, api_key: str):
        """
        Args:
            provider: LLM provider ("gemini", "openai", "anthropic")
            model_name: Model name
            api_key: API key
        """
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key
        
        if provider == "gemini":
            self._setup_gemini()
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    def _setup_gemini(self):
        """Setup Gemini client"""
        genai.configure(api_key=self.api_key)
        
        # Gemini function calling configuration
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "max_output_tokens": 8192,
            }
        )
        
        log_llm_debug(f"Initialized Gemini model: {self.model_name}")
    
    async def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate response with function calling
        
        Args:
            messages: Conversation history in standard format
            tools: Available tools in function calling format
            
        Returns:
            Dict with 'content' and optional 'tool_calls'
        """
        try:
            # Convert messages to Gemini format
            gemini_messages = self._convert_messages_to_gemini(messages)
            
            # Convert tools to Gemini format
            gemini_tools = self._convert_tools_to_gemini(tools) if tools else None
            
            # Start chat
            chat = self.model.start_chat(history=gemini_messages[:-1])
            
            # Generate response
            response = chat.send_message(
                gemini_messages[-1],
                tools=gemini_tools
            )
            
            # Parse response
            return self._parse_gemini_response(response)
            
        except Exception as e:
            log_llm_error("LLM generation failed", error=e)
            raise LLMError(f"LLM generation failed: {e}", original_error=e)
    
    def _convert_messages_to_gemini(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Convert standard message format to Gemini format"""
        gemini_messages = []
        
        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")
            
            if role == "user":
                gemini_messages.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                if msg.get("tool_calls"):
                    # Function call response
                    for tool_call in msg["tool_calls"]:
                        function_name = tool_call["function"]["name"]
                        function_args = tool_call["function"]["arguments"]
                        gemini_messages.append({
                            "role": "model",
                            "parts": [{
                                "function_call": {
                                    "name": function_name,
                                    "args": function_args
                                }
                            }]
                        })
                else:
                    gemini_messages.append({"role": "model", "parts": [content]})
            elif role == "tool":
                # Function result
                gemini_messages.append({
                    "role": "function",
                    "parts": [{
                        "function_response": {
                            "name": "tool_result",  # Gemini needs a name
                            "response": {"result": content}
                        }
                    }]
                })
        
        # Extract just the content for chat
        result = []
        for msg in gemini_messages:
            if msg["role"] == "user":
                result.append(msg["parts"][0])
            # Model and function messages are part of history
        
        return result if result else ["Hello"]
    
    def _convert_tools_to_gemini(self, tools: List[Dict[str, Any]]) -> List[Dict]:
        """Convert function calling tools to Gemini format"""
        gemini_tools = []
        
        for tool in tools:
            if tool["type"] == "function":
                func = tool["function"]
                gemini_tools.append({
                    "function_declarations": [{
                        "name": func["name"],
                        "description": func["description"],
                        "parameters": func["parameters"]
                    }]
                })
        
        return gemini_tools
    
    def _parse_gemini_response(self, response) -> Dict[str, Any]:
        """Parse Gemini response into standard format"""
        result = {
            "content": None,
            "tool_calls": []
        }
        
        # Check for function calls
        if response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call'):
                    # Tool call
                    fc = part.function_call
                    result["tool_calls"].append({
                        "id": f"call_{len(result['tool_calls'])}",
                        "type": "function",
                        "function": {
                            "name": fc.name,
                            "arguments": dict(fc.args) if fc.args else {}
                        }
                    })
                elif hasattr(part, 'text'):
                    # Text response
                    result["content"] = part.text
        
        return result
