import json
import subprocess
from pathlib import Path

from inspect_swe_reminder_agent.agent import _hook_command, _settings


def _run_hook(command: str, hook_input: dict[str, str]) -> str:
    result = subprocess.run(
        command,
        check=True,
        input=json.dumps(hook_input),
        capture_output=True,
        shell=True,
        text=True,
    )
    return result.stdout.strip()


def _reset_state() -> None:
    for suffix in ("", ".lock", ".tmp"):
        Path(f"/tmp/inspect-swe-reminder-agent-state.json{suffix}").unlink(
            missing_ok=True
        )


def test_hook_injects_exact_additional_context() -> None:
    _reset_state()
    reminder = "repeat"
    command = _hook_command("PostToolUse", reminder)
    payload = _run_hook(command, {"hook_event_name": "PostToolUse"})

    assert json.loads(payload) == {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": reminder,
        }
    }


def test_tool_hook_skips_subagent_tools() -> None:
    _reset_state()
    command = _hook_command("PostToolUse", "repeat")

    assert (
        _run_hook(
            command,
            {"hook_event_name": "PostToolUse", "agent_id": "subagent-1"},
        )
        == ""
    )


def test_all_cycle_events_receive_the_reminder() -> None:
    _reset_state()
    hooks = _settings("repeat")["hooks"]

    assert set(hooks) == {"PostToolUse", "PostToolUseFailure", "SubagentStop"}
    assert all(entries[0]["matcher"] == "*" for entries in hooks.values())
    for event, entries in hooks.items():
        command = entries[0]["hooks"][0]["command"]
        payload = json.loads(_run_hook(command, {"hook_event_name": event}))
        assert payload["hookSpecificOutput"]["hookEventName"] == event
        assert payload["hookSpecificOutput"]["additionalContext"]


def test_second_primary_result_requires_one_consultation_then_relaxes() -> None:
    _reset_state()
    command = _hook_command("PostToolUse", "keep going")

    first = json.loads(
        _run_hook(command, {"hook_event_name": "PostToolUse", "tool_name": "Bash"})
    )
    second = json.loads(
        _run_hook(command, {"hook_event_name": "PostToolUse", "tool_name": "Read"})
    )
    launched = json.loads(
        _run_hook(command, {"hook_event_name": "PostToolUse", "tool_name": "Agent"})
    )
    later = json.loads(
        _run_hook(command, {"hook_event_name": "PostToolUse", "tool_name": "Bash"})
    )

    assert first["hookSpecificOutput"]["additionalContext"] == "keep going"
    assert (
        "next tool call must be Agent"
        in second["hookSpecificOutput"]["additionalContext"]
    )
    assert launched["hookSpecificOutput"]["additionalContext"] == "keep going"
    assert later["hookSpecificOutput"]["additionalContext"] == "keep going"
