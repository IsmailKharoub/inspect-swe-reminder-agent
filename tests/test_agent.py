import json
import shlex

from inspect_swe_reminder_agent.agent import _hook_command, _settings


def test_hook_emits_exact_system_reminder() -> None:
    reminder = "<system-reminder>repeat</system-reminder>"
    command = _hook_command(reminder)
    payload = shlex.split(command)[-1]

    assert json.loads(payload) == {"systemMessage": reminder}


def test_all_cycle_events_receive_the_reminder() -> None:
    hooks = _settings("repeat")["hooks"]

    assert set(hooks) == {"PostToolUse", "PostToolUseFailure", "SubagentStop"}
    assert all(entries[0]["matcher"] == "*" for entries in hooks.values())
