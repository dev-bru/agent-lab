"""Check the MCP client lesson with local child servers."""

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LESSON = ROOT / "lessons" / "05_mcp_client.py"
HELPER = ROOT / "tests" / "mcp_with_resource.py"
TOOL_NAMES = {
    "add", "multiply", "convert_units", "write_note", "read_note",
    "list_notes", "now", "days_between", "search_docs",
}


def run_lesson(tmp_path: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """Run the lesson and pass local folders to its child server."""
    return subprocess.run(
        [sys.executable, "lessons/05_mcp_client.py", *args],
        cwd=ROOT,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
            "AGENT_LAB_NOTES_DIR": str(tmp_path / "notes"),
        },
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def test_default_server(tmp_path: Path) -> None:
    """List all nine tools and call multiply without a model."""
    result = run_lesson(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "server: agent-lab" in result.stdout
    assert "tools: 9" in result.stdout
    for name in TOOL_NAMES:
        assert f"- {name}:" in result.stdout
    assert "[tool: multiply] 17 x 23 = 391" in result.stdout
    assert "no resources offered" in result.stdout
    assert "Traceback" not in result.stdout + result.stderr
    assert "http://" not in result.stderr and "https://" not in result.stderr


def test_resource_server(tmp_path: Path) -> None:
    """Read a resource when a test server offers one."""
    result = run_lesson(tmp_path, "--server", "tests.mcp_with_resource")
    assert result.returncode == 0, result.stderr
    assert "resource docs://mcp-basics:" in result.stdout
    assert "# MCP basics" in result.stdout


def test_bad_server(tmp_path: Path) -> None:
    """Explain a missing server module without a traceback."""
    result = run_lesson(tmp_path, "--server", "agent_lab.no_such_module", timeout=60)
    assert result.returncode == 1
    assert any(line.startswith("error: ") and line.split(": ", 1)[1].strip()
               for line in result.stderr.splitlines())
    assert "Traceback" not in result.stderr


def test_sources_have_no_urls() -> None:
    """Keep network URLs out of the lesson and test server."""
    for path in (LESSON, HELPER):
        source = path.read_text(encoding="utf-8")
        assert "http://" not in source and "https://" not in source
