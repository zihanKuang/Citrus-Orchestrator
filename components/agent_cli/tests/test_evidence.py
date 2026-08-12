"""Hard evidence check — no LLM, no cluster."""
from agent_cli.evidence import assess, attach_footer


def test_no_tools_is_low():
    check = assess(
        query="What happened to frontend?",
        answer="The frontend was killed by chaos.",
        stats={"tool_calls": {}, "errors": 0},
    )
    assert check.level == "LOW"
    assert "0 live tool calls" in check.reasons[0]


def test_empty_answer_is_low():
    check = assess(
        query="status",
        answer="   ",
        stats={"tool_calls": {"list_pods": 1}, "errors": 0},
    )
    assert check.level == "LOW"
    assert "empty" in check.reasons[0]


def test_healthy_rca_run_is_high():
    check = assess(
        query="What just happened to the frontend pods? RCA + validate recovery.",
        answer="Pod frontend-abc was killed; ReplicaSet recreated it. validate_recovery=PASS.",
        stats={
            "tool_calls": {
                "list_pods": 1,
                "get_recent_events": 1,
                "validate_recovery": 1,
            },
            "errors": 0,
        },
    )
    assert check.level == "HIGH"


def test_rca_without_validate_recovery_caps_at_medium():
    check = assess(
        query="What happened to frontend? RCA please.",
        answer="A pod was killed and came back.",
        stats={
            "tool_calls": {"list_pods": 1, "get_recent_events": 1},
            "errors": 0,
        },
    )
    assert check.level == "MEDIUM"
    assert any("validate_recovery" in r for r in check.reasons)


def test_half_the_calls_failing_is_low():
    check = assess(
        query="list pods",
        answer="I could not reach the cluster.",
        stats={"tool_calls": {"list_pods": 2}, "errors": 1},
    )
    assert check.level == "LOW"


def test_footer_is_appended_and_not_inside_the_answer():
    check = assess(
        query="list pods",
        answer="All pods Running.",
        stats={"tool_calls": {"list_pods": 1}, "errors": 0},
    )
    text = attach_footer("All pods Running.", check)
    assert text.startswith("All pods Running.")
    assert "Evidence check:" in text
    assert "---" in text
