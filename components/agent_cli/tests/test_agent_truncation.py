"""
Head/tail truncation on tool results — this is what stops a 100k-line log
dump from blowing up the LLM's context window mid ReAct-loop.
"""
from agent_cli.agent import ReActAgent
from agent_cli.config import AgentConfig


def _make_agent(max_content_length: int = 4000) -> ReActAgent:
    # ReActAgent.__init__ only builds client objects, it never connects
    # to the network or the MCP server, so this is safe to construct in a test.
    config = AgentConfig(api_key="unit-test-key", max_content_length=max_content_length)
    return ReActAgent(config)


def test_short_content_passes_through_unchanged():
    agent = _make_agent(max_content_length=100)
    content = "pod frontend-abc123 is Running"
    assert agent._truncate_if_needed(content) == content


def test_long_content_is_truncated_with_marker():
    agent = _make_agent(max_content_length=100)
    content = "A" * 500
    result = agent._truncate_if_needed(content)
    assert len(result) < len(content)
    assert "TRUNCATED" in result


def test_truncation_keeps_head_and_tail_not_just_head():
    agent = _make_agent(max_content_length=100)
    content = "HEAD-MARKER" + ("x" * 1000) + "TAIL-MARKER"
    result = agent._truncate_if_needed(content)
    assert result.startswith("HEAD-MARKER")
    assert result.endswith("TAIL-MARKER")


def test_truncation_reports_correct_dropped_character_count():
    agent = _make_agent(max_content_length=1000)
    content = "B" * 5000
    result = agent._truncate_if_needed(content)
    dropped = len(content) - 1000
    assert f"TRUNCATED {dropped} characters" in result
