import importlib
import json
import shlex
from typing import Any

from inspect_ai.agent import Agent, agent
from inspect_swe import claude_code


def _hook_command(event: str, reminder: str) -> str:
    payload = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": reminder,
            }
        },
        separators=(",", ":"),
    )
    return f"printf '%s\\n' {shlex.quote(payload)}"


def _settings(reminder: str) -> dict[str, Any]:
    def hook(event: str) -> dict[str, str]:
        return {"type": "command", "command": _hook_command(event, reminder)}

    return {
        "hooks": {
            "PostToolUse": [{"matcher": "*", "hooks": [hook("PostToolUse")]}],
            "PostToolUseFailure": [
                {"matcher": "*", "hooks": [hook("PostToolUseFailure")]}
            ],
            "SubagentStop": [{"matcher": "*", "hooks": [hook("SubagentStop")]}],
        }
    }


@agent
def claude_code_with_reminders(
    reminder: str,
    **kwargs: Any,
) -> Agent:
    module = importlib.import_module("inspect_swe._claude_code.claude_code")
    settings = _settings(reminder)

    async def seed_config(
        sbox: Any,
        api_key: str,
        user: str | None,
        cwd: str,
    ) -> None:
        config = dict(settings)
        config["apiKeyHelper"] = f"echo {api_key}"
        config_json = json.dumps(config, separators=(",", ":"))
        await sbox.exec(
            cmd=[
                "bash",
                "-c",
                (
                    'mkdir -p "$HOME/.claude"'
                    f" && printf %s {shlex.quote(config_json)}"
                    ' > "$HOME/.claude/settings.json"'
                ),
            ],
            user=user,
            cwd=cwd,
        )

    module._seed_claude_config = seed_config
    return claude_code(**kwargs)
