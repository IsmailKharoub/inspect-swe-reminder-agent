import json
import subprocess

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


def test_hook_injects_exact_additional_context() -> None:
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
    command = _hook_command("PostToolUse", "repeat")

    assert (
        _run_hook(
            command,
            {"hook_event_name": "PostToolUse", "agent_id": "subagent-1"},
        )
        == ""
    )


def test_all_cycle_events_receive_the_reminder() -> None:
    hooks = _settings("repeat")["hooks"]

    assert set(hooks) == {"PostToolUse", "PostToolUseFailure", "SubagentStop"}
    assert all(entries[0]["matcher"] == "*" for entries in hooks.values())
    for event, entries in hooks.items():
        command = entries[0]["hooks"][0]["command"]
        payload = json.loads(_run_hook(command, {"hook_event_name": event}))
        assert payload["hookSpecificOutput"] == {
            "hookEventName": event,
            "additionalContext": "repeat",
        }
