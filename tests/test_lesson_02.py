"""Check the second lesson with scripted model replies."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from agent_lab import fakes


ROOT = Path(__file__).resolve().parents[1]
LESSON = ROOT / "lessons" / "02_tool_call.py"
BRIDGE = ROOT / "src" / "agent_lab" / "tools_schema.py"


def run_lesson(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the lesson in a child process without a model server."""
    return subprocess.run(
        [sys.executable, "lessons/02_tool_call.py", "--fake", *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def test_builtin_tool_call() -> None:
    """Show the request, tool result, and final answer."""
    result = run_lesson()
    assert result.returncode == 0, result.stderr
    assert "agent> tool call multiply" in result.stdout
    assert "[tool: multiply] 391" in result.stdout
    assert "agent> 17 times 23 is 391." in result.stdout


def test_tool_result_uses_the_matching_id() -> None:
    """Send the tool result back with the id from the model's request."""
    spec = importlib.util.spec_from_file_location("lesson_02", LESSON)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fake = fakes.FakeModel(fakes.builtin("02_tool_call"))
    assert module.run(fake.chat) == 0
    assert len(fake.requests) == 2
    messages = fake.requests[1]["messages"]
    assert messages[-1]["role"] == "tool"
    assert messages[-1]["tool_call_id"] == "call_1"
    assert messages[-2]["tool_calls"][0]["id"] == "call_1"


def test_bad_argument_returns_tool_error(tmp_path: Path) -> None:
    """Tell the model why a tool argument is wrong."""
    script = tmp_path / "bad_arg.json"
    script.write_text(json.dumps([{"tool_calls": [{"name": "multiply",
                        "arguments": '{"a": "x", "b": 2}'}]}, {"text": "ok"}]), encoding="utf-8")
    result = run_lesson(str(script))
    assert result.returncode == 0, result.stderr
    assert "[tool: multiply] error: argument 'a' must be number, got str" in result.stdout


def test_answer_without_tool(tmp_path: Path) -> None:
    """Explain when the model skips the offered tool."""
    script = tmp_path / "text.json"
    script.write_text('[{"text": "ok"}]', encoding="utf-8")
    result = run_lesson(str(script))
    assert result.returncode == 0, result.stderr
    assert "the model answered without a tool" in result.stdout


def test_empty_script(tmp_path: Path) -> None:
    """Explain when a fake script has no replies."""
    script = tmp_path / "empty.json"
    script.write_text("[]", encoding="utf-8")
    result = run_lesson(str(script))
    assert result.returncode == 1
    assert "error: the fake script has no more replies" in result.stderr
    assert "Traceback" not in result.stderr


def test_sources_have_no_url() -> None:
    """Keep both files limited to local model access."""
    for path in (LESSON, BRIDGE):
        source = path.read_text(encoding="utf-8")
        assert "http://" not in source
        assert "https://" not in source
