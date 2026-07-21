"""
LLM Client - Handles calls to Language Model APIs

Supports Gemini with function calling for the ReAct loop.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from .exceptions import LLMError
from .logging_utils import log_llm_debug, log_llm_error


def _import_genai():
    """Lazy import so MCP-only paths do not load the Gemini SDK."""
    import google.generativeai as genai
    return genai


SRE_SYSTEM_INSTRUCTION = (
    "You are an SRE diagnostic agent for the citrus Kubernetes namespace "
    "(OpenTelemetry Demo + monitoring stack).\n"
    "Rules:\n"
    "1. Always gather live evidence with tools before answering; never invent cluster state.\n"
    "2. Namespace is fixed to citrus — do not ask the user about namespaces.\n"
    "3. Preferred incident workflow:\n"
    "   list_pods → get_recent_events → get_pod_status → get_pod_logs → "
    "validate_recovery (and query_prometheus if useful).\n"
    "4. For otel-demo workloads prefer label selectors like "
    "'app.kubernetes.io/component=frontend'.\n"
    "5. Before declaring an incident resolved, call validate_recovery and report PASS/FAIL.\n"
    "6. You are read-only: you cannot delete/restart pods. Recovery after chaos "
    "comes from Kubernetes ReplicaSet self-heal; your job is RCA + verification.\n"
    "7. Structure final answers as: What happened → Evidence → Current status → "
    "Recovery validation."
)


class LLMClient:
    """Client for interacting with Language Models"""

    def __init__(self, provider: str, model_name: str, api_key: str):
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key
        self._tools: Optional[List[Any]] = None
        self.model = None

        if provider != "gemini":
            raise ValueError(f"Unsupported LLM provider: {provider}")
        # Defer Gemini client setup until first generate call
        # so MCP-only / fake-LLM tests can construct ReActAgent without a key.

    def _setup_gemini(self):
        if self.model is not None:
            return
        if not self.api_key:
            raise LLMError("GEMINI_API_KEY is not set")
        genai = _import_genai()
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": 0.2,
                "top_p": 0.95,
                "max_output_tokens": 8192,
            },
            system_instruction=SRE_SYSTEM_INSTRUCTION,
        )
        log_llm_debug(f"Initialized Gemini model: {self.model_name}")

    def _ensure_model_with_tools(self, tools: List[Dict[str, Any]]):
        """Recreate model with tool declarations when tool set changes."""
        self._setup_gemini()
        genai = _import_genai()
        gemini_tools = self._convert_tools_to_gemini(tools) if tools else None
        tool_key = tuple(sorted(t["function"]["name"] for t in tools)) if tools else ()
        if getattr(self, "_tool_key", None) == tool_key and self._tools is not None:
            return

        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": 0.2,
                "top_p": 0.95,
                "max_output_tokens": 8192,
            },
            tools=gemini_tools,
            system_instruction=SRE_SYSTEM_INSTRUCTION,
        )
        self._tools = gemini_tools
        self._tool_key = tool_key
        log_llm_debug(f"Gemini model configured with {len(tools)} tools")

    async def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate response with function calling.

        Returns:
            Dict with 'content' and optional 'tool_calls'
        """
        try:
            self._ensure_model_with_tools(tools)
            history, last_message = self._build_gemini_history(messages)

            chat = self.model.start_chat(history=history)
            response = await chat.send_message_async(last_message)
            return self._parse_gemini_response(response)

        except LLMError:
            raise
        except Exception as e:
            log_llm_error("LLM generation failed", error=e)
            raise LLMError(f"LLM generation failed: {e}", original_error=e)

    def _build_gemini_history(
        self, messages: List[Dict[str, Any]]
    ) -> tuple[List[Any], Any]:
        """
        Convert OpenAI-style messages into Gemini chat history + last turn.
        """
        genai = _import_genai()
        history: List[Any] = []
        i = 0
        n = len(messages)

        while i < n - 1:
            msg = messages[i]
            role = msg["role"]

            if role == "user":
                history.append({"role": "user", "parts": [msg.get("content") or ""]})
                i += 1

            elif role == "assistant":
                parts = []
                if msg.get("tool_calls"):
                    for tool_call in msg["tool_calls"]:
                        parts.append(
                            genai.protos.Part(
                                function_call=genai.protos.FunctionCall(
                                    name=tool_call["function"]["name"],
                                    args=tool_call["function"]["arguments"] or {},
                                )
                            )
                        )
                content = msg.get("content")
                if content:
                    parts.append(genai.protos.Part(text=content))
                if parts:
                    history.append({"role": "model", "parts": parts})
                i += 1

            elif role == "tool":
                fn_parts = []
                while i < n - 1 and messages[i]["role"] == "tool":
                    tool_msg = messages[i]
                    tool_name = self._tool_name_for_result(messages, tool_msg)
                    fn_parts.append(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=tool_name,
                                response={"result": tool_msg.get("content", "")},
                            )
                        )
                    )
                    i += 1
                history.append({"role": "user", "parts": fn_parts})

            else:
                i += 1

        last = messages[-1]
        if last["role"] == "user":
            last_message: Any = last.get("content") or ""
        elif last["role"] == "tool":
            tool_name = self._tool_name_for_result(messages, last)
            last_message = genai.protos.Part(
                function_response=genai.protos.FunctionResponse(
                    name=tool_name,
                    response={"result": last.get("content", "")},
                )
            )
        else:
            last_message = last.get("content") or "Continue."

        return history, last_message

    def _tool_name_for_result(
        self, messages: List[Dict[str, Any]], tool_msg: Dict[str, Any]
    ) -> str:
        """Find the tool name for a tool result via tool_call_id."""
        call_id = tool_msg.get("tool_call_id")
        if call_id:
            for msg in reversed(messages):
                if msg.get("role") != "assistant":
                    continue
                for tc in msg.get("tool_calls") or []:
                    if tc.get("id") == call_id:
                        return tc["function"]["name"]
        return "unknown_tool"

    def _convert_tools_to_gemini(self, tools: List[Dict[str, Any]]) -> Optional[List[Any]]:
        """Convert OpenAI-style tools to Gemini Tool declarations."""
        genai = _import_genai()
        declarations = []
        for tool in tools:
            if tool.get("type") != "function":
                continue
            func = tool["function"]
            parameters = self._to_gemini_schema(func.get("parameters") or {})
            declarations.append(
                genai.protos.FunctionDeclaration(
                    name=func["name"],
                    description=func.get("description") or "",
                    parameters=parameters,
                )
            )
        if not declarations:
            return None
        return [genai.protos.Tool(function_declarations=declarations)]

    def _to_gemini_schema(self, schema: Dict[str, Any]):
        """
        Convert JSON Schema dict to genai.protos.Schema.

        Gemini protobuf uses Type enum (OBJECT/STRING/...), not the string
        "object"/"string" from JSON Schema.
        """
        genai = _import_genai()
        type_map = {
            "string": genai.protos.Type.STRING,
            "integer": genai.protos.Type.INTEGER,
            "number": genai.protos.Type.NUMBER,
            "boolean": genai.protos.Type.BOOLEAN,
            "array": genai.protos.Type.ARRAY,
            "object": genai.protos.Type.OBJECT,
        }

        raw_type = schema.get("type", "object")
        if isinstance(raw_type, list):
            # JSON Schema union types e.g. ["string","null"] -> first non-null
            raw_type = next((t for t in raw_type if t != "null"), "string")

        kwargs: Dict[str, Any] = {
            "type": type_map.get(str(raw_type).lower(), genai.protos.Type.OBJECT)
        }

        if schema.get("description"):
            kwargs["description"] = schema["description"]

        if "properties" in schema and isinstance(schema["properties"], dict):
            kwargs["properties"] = {
                name: self._to_gemini_schema(prop if isinstance(prop, dict) else {"type": "string"})
                for name, prop in schema["properties"].items()
            }

        if "required" in schema and isinstance(schema["required"], list):
            kwargs["required"] = list(schema["required"])

        if "items" in schema and isinstance(schema["items"], dict):
            kwargs["items"] = self._to_gemini_schema(schema["items"])

        if "enum" in schema and isinstance(schema["enum"], list):
            kwargs["enum"] = [str(v) for v in schema["enum"]]

        return genai.protos.Schema(**kwargs)

    def _sanitize_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Deprecated helper kept for compatibility; use _to_gemini_schema."""
        return schema

    def _parse_gemini_response(self, response) -> Dict[str, Any]:
        """Parse Gemini response into OpenAI-style tool_calls format."""
        result: Dict[str, Any] = {"content": None, "tool_calls": []}

        try:
            parts = response.candidates[0].content.parts
        except (IndexError, AttributeError) as e:
            raise LLMError(f"Empty Gemini response: {e}", original_error=e)

        text_parts = []
        for part in parts:
            fc = getattr(part, "function_call", None)
            if fc and getattr(fc, "name", None):
                args = fc.args
                if hasattr(args, "items"):
                    arguments = dict(args)
                elif isinstance(args, dict):
                    arguments = args
                else:
                    arguments = json.loads(str(args)) if args else {}

                result["tool_calls"].append(
                    {
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "type": "function",
                        "function": {
                            "name": fc.name,
                            "arguments": arguments,
                        },
                    }
                )
                continue

            text = getattr(part, "text", None)
            if text:
                text_parts.append(text)

        if text_parts:
            result["content"] = "\n".join(text_parts)

        return result
