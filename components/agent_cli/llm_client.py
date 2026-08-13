"""
LLM client (DeepSeek via the OpenAI-compatible Chat Completions API).

Agent messages stay in OpenAI shape. This module only talks to the HTTP API
and normalizes tool-call arguments to dicts for mcp_client.call_tool.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .exceptions import LLMError
from .logging_utils import log_llm_debug, log_llm_error

DEFAULT_BASE_URL = "https://api.deepseek.com"


def _import_openai():
    from openai import AsyncOpenAI
    return AsyncOpenAI


def arguments_as_dict(raw: Any) -> Dict[str, Any]:
    """OpenAI returns arguments as a JSON string; the agent needs a dict."""
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def arguments_as_json(raw: Any) -> str:
    """The API expects tool-call arguments as a JSON object string."""
    if isinstance(raw, str):
        return raw if raw else "{}"
    if raw is None:
        return "{}"
    return json.dumps(raw)


def messages_for_api(
    messages: List[Dict[str, Any]],
    system_instruction: str = "",
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if system_instruction:
        out.append({"role": "system", "content": system_instruction})

    for msg in messages:
        role = msg["role"]
        if role == "assistant" and msg.get("tool_calls"):
            tool_calls = []
            for tc in msg["tool_calls"]:
                tool_calls.append(
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": arguments_as_json(tc["function"].get("arguments")),
                        },
                    }
                )
            out.append(
                {
                    "role": "assistant",
                    "content": msg.get("content") or None,
                    "tool_calls": tool_calls,
                }
            )
        elif role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id") or "",
                    "content": msg.get("content") or "",
                }
            )
        else:
            out.append({"role": role, "content": msg.get("content") or ""})
    return out


class LLMClient:
    def __init__(
        self,
        provider: str,
        model_name: str,
        api_key: str,
        system_instruction: str = "",
        base_url: str = DEFAULT_BASE_URL,
    ):
        if provider not in ("deepseek", "openai"):
            raise ValueError(f"Unsupported LLM provider: {provider}")
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key
        self.system_instruction = system_instruction
        self.base_url = base_url.rstrip("/")
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return
        if not self.api_key:
            raise LLMError("DEEPSEEK_API_KEY is not set")
        AsyncOpenAI = _import_openai()
        self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        log_llm_debug(f"DeepSeek client ready: {self.model_name} @ {self.base_url}")

    async def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        try:
            self._ensure_client()
            kwargs: Dict[str, Any] = {
                "model": self.model_name,
                "messages": messages_for_api(messages, self.system_instruction),
                "temperature": 0.2,
                "max_tokens": 8192,
                # Non-thinking: cheaper, and ReAct already does the reasoning loop.
                "extra_body": {"thinking": {"type": "disabled"}},
            }
            if tools:
                kwargs["tools"] = tools
            response = await self._client.chat.completions.create(**kwargs)
            return self._parse_response(response)
        except LLMError:
            raise
        except Exception as e:
            log_llm_error("LLM generation failed", error=e)
            raise LLMError(f"LLM generation failed: {e}", original_error=e)

    def _parse_response(self, response) -> Dict[str, Any]:
        try:
            message = response.choices[0].message
        except (IndexError, AttributeError) as e:
            raise LLMError(f"Empty LLM response: {e}", original_error=e)

        result: Dict[str, Any] = {"content": message.content, "tool_calls": []}
        for tc in message.tool_calls or []:
            result["tool_calls"].append(
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": arguments_as_dict(tc.function.arguments),
                    },
                }
            )
        return result
