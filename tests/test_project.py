"""Check the package command, paths, and dependency record."""

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def project_data() -> dict:
    """Read the project file for its dependency lists."""

    with (ROOT / "pyproject.toml").open("rb") as file:
        return tomllib.load(file)


def test_runtime_dependencies_are_pinned() -> None:
    """Check exact runtime pins and Windows time-zone data."""

    dependencies = project_data()["project"]["dependencies"]
    assert all("==" in item for item in dependencies)
    assert "tzdata" in {item.split("==", 1)[0].lower().replace("_", "-") for item in dependencies}


def test_cli_help() -> None:
    """Run the command line module in a child process."""

    result = subprocess.run(
        [sys.executable, "-m", "agent_lab.cli", "--help"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    assert "chat" in result.stdout
    assert "model" in result.stdout


def test_source_has_no_user_paths() -> None:
    """Find machine-specific paths in source, lessons, and tests."""

    drive_path = re.compile(r"(?<![A-Za-z0-9/])[A-Za-z]" + r":[\\/]" + r"(?!/)")
    user_folder = re.compile(r"[\\/]users[\\/]", re.IGNORECASE)
    for folder in ("src", "lessons", "tests"):
        base = ROOT / folder
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if "__pycache__" in path.parts or path.suffix not in {".py", ".md", ".toml"}:
                continue
            content = path.read_text(encoding="utf-8")
            assert not drive_path.search(content), path
            assert not user_folder.search(content), path


def test_dependency_record_is_complete() -> None:
    """Check each direct dependency and the local model record."""

    data = project_data()
    dependencies = data["project"]["dependencies"] + data["dependency-groups"]["dev"]
    record = (ROOT / "docs" / "DEPENDENCIES.md").read_text(encoding="utf-8")
    recorded_names = {
        match.group(1).lower().replace("_", "-")
        for match in re.finditer(r"^\|\s*([\w-]+)(?:\s+\(dev\))?\s*\|", record, re.MULTILINE)
    }
    for item in dependencies:
        name = item.split("==", 1)[0].lower().replace("_", "-")
        assert name in recorded_names, name
    assert "llama.cpp" in record
    assert re.search(r"\b[0-9a-f]{64}\b", record)
