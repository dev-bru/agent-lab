"""Check the agent loop lesson with scripted model replies."""

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LESSON = ROOT / "lessons" / "04_agent_loop.py"


def run_lesson(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the lesson without a model server or repo output files."""
    return subprocess.run(
        [sys.executable, str(LESSON), "--fake", *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"),
             "AGENT_LAB_NOTES_DIR": str(tmp_path / "notes"),
             "AGENT_LAB_RUNS_DIR": str(tmp_path / "runs")},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def test_builtin_script_saves_note_and_trace(tmp_path: Path) -> None:
    """Show both tool results, the final answer, and its saved trace."""
    result = run_lesson(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "[step 1/6]" in result.stdout
    assert "[tool: multiply] 391" in result.stdout
    assert "[tool: write_note] saved note 'result'" in result.stdout
    assert any(line.startswith("agent> ") and "391" in line for line in result.stdout.splitlines())
    assert any(line.startswith("[trace] ") for line in result.stdout.splitlines())
    assert (tmp_path / "notes" / "result.md").exists()
    traces = list((tmp_path / "runs").glob("*-hand.jsonl"))
    assert len(traces) == 1
    assert json.loads(traces[0].read_text(encoding="utf-8").splitlines()[-1])["kind"] == "final"


def test_step_limit(tmp_path: Path) -> None:
    """Stop after six model calls when each reply asks for a tool."""
    script = tmp_path / "limit.json"
    script.write_text(json.dumps([{"tool_calls": [{"name": "multiply",
        "arguments": '{"a": 2, "b": 3}'}]}] * 6), encoding="utf-8")
    result = run_lesson(tmp_path, str(script))
    assert result.returncode == 1
    assert "Stopped: reached the step limit (6 model calls)." in result.stdout


def test_empty_script(tmp_path: Path) -> None:
    """Show a short error when the fake runs out of replies."""
    script = tmp_path / "empty.json"
    script.write_text("[]", encoding="utf-8")
    result = run_lesson(tmp_path, str(script))
    assert result.returncode == 1
    assert "error: the fake script has no more replies" in result.stderr
    assert "Traceback" not in result.stderr


def test_lesson_has_no_url() -> None:
    """Keep the lesson limited to local model access."""
    source = LESSON.read_text(encoding="utf-8")
    assert "http://" not in source
    assert "https://" not in source
