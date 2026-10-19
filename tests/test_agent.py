import json
import shlex

from inspect_swe_reminder_agent.agent import _hook_command, _settings


def test_hook_injects_exact_additional_context() -> None:
    reminder = "repeat"
    command = _hook_command("PostToolUse", reminder)
    payload = shlex.split(command)[-1]

    assert json.loads(payload) == {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": reminder,
        }
    }


def test_all_cycle_events_receive_the_reminder() -> None:
    hooks = _settings("repeat")["hooks"]

    assert set(hooks) == {"PostToolUse", "PostToolUseFailure", "SubagentStop"}
    assert all(entries[0]["matcher"] == "*" for entries in hooks.values())
    for event, entries in hooks.items():
        command = entries[0]["hooks"][0]["command"]
        payload = json.loads(shlex.split(command)[-1])
        assert payload["hookSpecificOutput"] == {
            "hookEventName": event,
            "additionalContext": "repeat",
        }
