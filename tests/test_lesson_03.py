"""Check study card validation and its one retry without a model server."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from agent_lab import fakes


ROOT = Path(__file__).resolve().parents[1]
LESSON = ROOT / "lessons" / "03_structured_output.py"
BAD = {"text": '{"term": "tool calling", "definition": "Using a tool."}'}
GOOD = {"text": '{"term": "tool calling", "meaning": "The model asks the program to run a tool.", '
                '"example": "The model asks for multiply with 17 and 23."}'}


def run_lesson(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the lesson with a fake script in a child process."""
    return subprocess.run(
        [sys.executable, "lessons/03_structured_output.py", "--fake", *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def load_lesson():
    """Load the lesson to inspect requests sent to the fake model."""
    spec = importlib.util.spec_from_file_location("lesson_03", LESSON)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_script(tmp_path: Path, replies: list[dict]) -> Path:
    """Write model replies for one test."""
    script = tmp_path / "replies.json"
    script.write_text(json.dumps(replies), encoding="utf-8")
    return script


def test_builtin_retries_and_succeeds() -> None:
    """Check the built-in reply, correction, and schema request."""
    result = run_lesson()
    assert result.returncode == 0, result.stderr
    assert "[check] not valid: meaning: Field required; example: Field required" in result.stdout
    assert "[check] valid study card" in result.stdout
    assert "term: tool calling" in result.stdout

    lesson = load_lesson()
    fake = fakes.FakeModel(fakes.builtin("03_structured_output"))
    assert lesson.run(fake.chat) == 0
    assert len(fake.requests) == 2
    assert all(request["response_format"] == lesson.RESPONSE_FORMAT for request in fake.requests)
    correction = fake.requests[1]["messages"][-1]
    assert correction["role"] == "user"
    assert correction["content"].startswith("That reply was not a valid study card.")
    assert "meaning" in correction["content"]


def test_two_bad_replies_fail(tmp_path: Path) -> None:
    """Stop after two invalid replies."""
    result = run_lesson(str(write_script(tmp_path, [BAD, BAD])))
    assert result.returncode == 1
    assert "error: the reply was not a valid study card after 2 tries:" in result.stderr

    lesson = load_lesson()
    fake = fakes.FakeModel([BAD, BAD])
    assert lesson.run(fake.chat) == 1
    assert len(fake.requests) == 2


def test_long_meaning_can_be_fixed(tmp_path: Path) -> None:
    """Report a meaning that exceeds the schema limit."""
    long = {"text": json.dumps({"term": "tool calling", "meaning": "x" * 201, "example": "example"})}
    result = run_lesson(str(write_script(tmp_path, [long, GOOD])))
    assert result.returncode == 0, result.stderr
    assert "[check] not valid: meaning: String should have at most 200 characters" in result.stdout


def test_plain_text_can_be_fixed(tmp_path: Path) -> None:
    """Report plain text as invalid JSON."""
    result = run_lesson(str(write_script(tmp_path, [{"text": "hello"}, GOOD])))
    assert result.returncode == 0, result.stderr
    assert "[check] not valid: reply: Invalid JSON" in result.stdout


def test_empty_text_can_be_fixed(tmp_path: Path) -> None:
    """Report an empty reply as invalid JSON."""
    result = run_lesson(str(write_script(tmp_path, [{"text": ""}, GOOD])))
    assert result.returncode == 0, result.stderr
    assert "[check] not valid: reply: Invalid JSON" in result.stdout


def test_empty_script(tmp_path: Path) -> None:
    """Explain when a fake script has no replies."""
    result = run_lesson(str(write_script(tmp_path, [])))
    assert result.returncode == 1
    assert "error: the fake script has no more replies" in result.stderr
    assert "Traceback" not in result.stderr


def test_source_has_no_url() -> None:
    """Keep model access local in the lesson source."""
    source = LESSON.read_text(encoding="utf-8")
    assert "http://" not in source
    assert "https://" not in source
