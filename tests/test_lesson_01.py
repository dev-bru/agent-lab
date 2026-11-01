"""Check the first lesson with scripted model replies."""

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LESSON = ROOT / "lessons" / "01_model_call.py"


def run_lesson(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the lesson in a child process without a model server."""
    return subprocess.run(
        [sys.executable, "lessons/01_model_call.py", "--fake", *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_builtin_reply() -> None:
    """Show the request, reply, and fake token counts."""
    result = run_lesson()
    assert result.returncode == 0, result.stderr
    assert "system> You are a patient teacher." in result.stdout
    assert "you> What is a large language model?" in result.stdout
    assert "agent> A large language model is a program that predicts the next words of a text." in result.stdout
    assert "[tokens] prompt=0 completion=0 total=0" in result.stdout


def test_custom_reply(tmp_path: Path) -> None:
    """Read a script given after the fake option."""
    script = tmp_path / "custom.json"
    script.write_text('[{"text": "custom reply"}]', encoding="utf-8")
    result = run_lesson(str(script))
    assert result.returncode == 0, result.stderr
    assert "agent> custom reply" in result.stdout


def test_empty_script(tmp_path: Path) -> None:
    """Explain when a script has no reply."""
    script = tmp_path / "empty.json"
    script.write_text("[]", encoding="utf-8")
    result = run_lesson(str(script))
    assert result.returncode == 1
    assert "error: the fake script has no more replies" in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_script(tmp_path: Path) -> None:
    """Explain when the requested script does not exist."""
    result = run_lesson(str(tmp_path / "missing.json"))
    assert result.returncode == 1
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_lesson_has_no_url() -> None:
    """Keep the lesson limited to local model access."""
    source = LESSON.read_text(encoding="utf-8")
    assert "http://" not in source
    assert "https://" not in source
