"""OpenAI-shaped message conversion — no network."""
from agent_cli.llm_client import arguments_as_dict, arguments_as_json, messages_for_api


def test_json_string_arguments_become_a_dict():
    assert arguments_as_dict('{"pod_selector": "app=frontend"}') == {
        "pod_selector": "app=frontend"
    }


def test_dict_arguments_pass_through():
    assert arguments_as_dict({"minutes": 10}) == {"minutes": 10}


def test_empty_or_invalid_arguments_become_empty_dict():
    assert arguments_as_dict("") == {}
    assert arguments_as_dict(None) == {}
    assert arguments_as_dict("not-json") == {}


def test_dict_arguments_are_serialized_for_the_api():
    assert arguments_as_json({"a": 1}) == '{"a": 1}'


def test_messages_for_api_prepends_system_and_stringifies_tool_args():
    messages = [
        {"role": "user", "content": "status?"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "list_pods", "arguments": {}},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "ok"},
    ]
    out = messages_for_api(messages, system_instruction="You are SRE.")
    assert out[0] == {"role": "system", "content": "You are SRE."}
    assert out[1]["role"] == "user"
    assert out[2]["tool_calls"][0]["function"]["arguments"] == "{}"
    assert out[3]["role"] == "tool"
