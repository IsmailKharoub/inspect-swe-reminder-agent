import importlib
import json
import shlex
import textwrap
from typing import Any

from inspect_ai.agent import Agent, agent
from inspect_swe import claude_code


def _hook_command(event: str, reminder: str) -> str:
    consultation_due = (
        "The required first consultant call is now due. Your next tool call must be "
        "Agent with subagent_type `general-purpose` and run_in_background `true`. Ask "
        "one narrow context-blind mechanical question grounded in a literal artifact "
        "you already observed. Launch it once, then continue useful local work; its "
        "answer, refusal, failure, or model label must never block the primary task."
    )
    script = textwrap.dedent(
        f"""
        import fcntl
        import json
        import os
        import sys

        hook_event = {event!r}
        event = json.load(sys.stdin)
        if hook_event != "SubagentStop" and event.get("agent_id"):
            raise SystemExit(0)

        state_path = "/tmp/inspect-swe-reminder-agent-state.json"
        lock_path = state_path + ".lock"
        with open(lock_path, "a+", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                with open(state_path, encoding="utf-8") as handle:
                    state = json.load(handle)
            except (FileNotFoundError, json.JSONDecodeError):
                state = {{"primary_tool_results": 0, "consultation_launched": False}}

            tool_name = str(event.get("tool_name", "")).lower()
            if hook_event == "SubagentStop":
                state["consultation_launched"] = True
                context = {reminder!r}
            elif tool_name in {{"agent", "task"}}:
                state["consultation_launched"] = True
                context = {reminder!r}
            else:
                state["primary_tool_results"] += 1
                if (
                    state["primary_tool_results"] >= 2
                    and not state["consultation_launched"]
                ):
                    context = {consultation_due!r}
                else:
                    context = {reminder!r}

            temporary = state_path + ".tmp"
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(state, handle, separators=(",", ":"))
            os.replace(temporary, state_path)

        payload = {{
            "hookSpecificOutput": {{
                "hookEventName": hook_event,
                "additionalContext": context,
            }}
        }}
        print(json.dumps(payload, separators=(",", ":")))
        """
    )
    return f"python3 -c {shlex.quote(script)}"


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
