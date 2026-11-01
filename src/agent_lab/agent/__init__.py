"""Share the small result and prompt used by agent loops."""

from dataclasses import dataclass


LIMIT_MESSAGE = "Stopped: reached the step limit ({} model calls)."
SYSTEM_PROMPT = "You are a helpful assistant. Use the tools when they help. Answer briefly."


@dataclass(frozen=True)
class RunResult:
    """Store the final answer and why the loop stopped."""

    text: str
    steps: int
    stopped_by: str
