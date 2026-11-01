"""Check chat commands with local tools and scripted model replies."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from tests.procs import server_pids

from agent_lab import cli


ROOT = Path(__file__).resolve().parents[1]
QUESTION = "What is 17 times 23? Save the answer as a note called result.\n\nthanks\nexit\n"


def _chat(tmp_path, args, input_text, env=None):
    """Run the chat command with local folders and UTF-8 text."""
    command_env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1",
                   "AGENT_LAB_NOTES_DIR": str(tmp_path / "notes"),
                   "AGENT_LAB_RUNS_DIR": str(tmp_path / "runs"), **(env or {})}
    return subprocess.run([sys.executable, "-m", "agent_lab.cli", "chat", *args],
                          cwd=ROOT, env=command_env, input=input_text, capture_output=True,
                          text=True, encoding="utf-8", timeout=120)


@pytest.mark.parametrize("engine", ["hand", "graph"])
def test_fake_chat_and_traces(tmp_path, engine):
    """Answer two lines with tools and save one trace for each run."""
    result = _chat(tmp_path, ["--engine", engine, "--fake"], QUESTION)
    answers = [line for line in result.stdout.splitlines() if line.startswith("agent> ")]
    traces = [line for line in result.stdout.splitlines() if line.startswith("[trace] ")]
    assert result.returncode == 0, result.stderr
    assert len(answers) == 2 and "391" in answers[0]
    assert answers[1] == "agent> You are welcome."
    assert len(traces) == 2
    assert len(list((tmp_path / "runs").glob(f"*-{engine}.jsonl"))) == 2
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("engine", ["hand", "graph"])
def test_end_of_input(tmp_path, engine):
    """Leave chat cleanly when standard input ends."""
    script = tmp_path / "short.json"
    script.write_text('[{"text": "ok"}]\n', encoding="utf-8", newline="\n")
    result = _chat(tmp_path, ["--engine", engine, "--fake", str(script)], "thanks\n")
    assert result.returncode == 0, result.stderr
    assert "agent> ok" in result.stdout


def test_piped_bom_is_removed_from_trace(tmp_path):
    """Remove a piped UTF-8 mark before recording the user's text."""
    script = tmp_path / "short.json"
    script.write_text('[{"text": "ok"}]\n', encoding="utf-8", newline="\n")
    result = _chat(tmp_path, ["--fake", str(script)], "\ufeffhello\nexit\n")
    assert result.returncode == 0, result.stderr
    traces = list((tmp_path / "runs").glob("*-hand.jsonl"))
    assert len(traces) == 1
    records = [json.loads(line) for line in traces[0].read_text(encoding="utf-8").splitlines()]
    assert next(record for record in records if record["kind"] == "user")["text"] == "hello"


@pytest.mark.parametrize("engine", ["hand", "graph"])
def test_remote_host_rejected(tmp_path, engine):
    """Reject a remote model host before making a request."""
    result = _chat(tmp_path, ["--engine", engine], "hi\n", {"AGENT_LAB_HOST": "example.com"})
    assert result.returncode == 1
    assert "host must be 127.0.0.1 or localhost" in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_script(tmp_path):
    """Explain a fake script path that does not exist."""
    result = _chat(tmp_path, ["--fake", str(tmp_path / "missing.json")], "hi\n")
    assert result.returncode == 1
    assert "error: invalid script path" in result.stderr


def test_chat_help(tmp_path):
    """Explain that each line starts a new agent run."""
    result = _chat(tmp_path, ["--help"], "")
    assert result.returncode == 0
    assert "new agent run" in result.stdout


@pytest.mark.parametrize("engine", ["hand", "graph"])
def test_stopped_model_server(tmp_path, engine):
    """Name the local port and start command when the model is down."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    result = _chat(tmp_path, ["--engine", engine], "hi\n",
                   {"AGENT_LAB_HOST": "127.0.0.1", "AGENT_LAB_PORT": str(port)})
    assert result.returncode == 2, result.stderr
    assert f"cannot reach the model at 127.0.0.1:{port}" in result.stderr
    assert "agent-lab model start" in result.stderr
    assert "Traceback" not in result.stderr
    assert "Give Feedback" not in result.stdout + result.stderr
    assert "LiteLLM.Info" not in result.stdout + result.stderr


def test_stopped_model_server_does_not_start_tools(monkeypatch, capsys):
    """Report a stopped model before opening the local tools."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    monkeypatch.setenv("AGENT_LAB_HOST", "127.0.0.1")
    monkeypatch.setenv("AGENT_LAB_PORT", str(port))

    def fail_if_created(*args, **kwargs):
        """Fail if chat tries to open tools for a stopped model."""
        pytest.fail("McpTools was created")

    monkeypatch.setattr(cli.mcp_client, "McpTools", fail_if_created)
    assert cli.main(["chat"]) == 2
    error = capsys.readouterr().err
    assert "cannot reach the model at 127.0.0.1:" in error
    assert "agent-lab model start" in error


@pytest.mark.parametrize("engine", ["hand", "graph"])
def test_empty_script(tmp_path, engine):
    """Explain when the fake script has no reply."""
    script = tmp_path / "empty.json"
    script.write_text("[]\n", encoding="utf-8", newline="\n")
    result = _chat(tmp_path, ["--engine", engine, "--fake", str(script)], "hi\n")
    assert result.returncode == 1
    assert "error: the fake script has no more replies" in result.stderr


def test_interrupt_closes_tools_and_chat_leaves_no_child(tmp_path, monkeypatch):
    """Close the MCP thread on Ctrl+C and leave no new server child."""
    monkeypatch.setenv("AGENT_LAB_NOTES_DIR", str(tmp_path / "notes"))
    monkeypatch.setenv("AGENT_LAB_RUNS_DIR", str(tmp_path / "runs"))
    instances = []
    original = cli.mcp_client.McpTools

    class Recording(original):
        """Record each local tool session for the cleanup check."""

        def __init__(self, *args, **kwargs):
            """Save the session after its ordinary setup."""
            super().__init__(*args, **kwargs)
            instances.append(self)

    def interrupt(_prompt):
        """Stand in for Ctrl+C at the next prompt."""
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.mcp_client, "McpTools", Recording)
    monkeypatch.setattr("builtins.input", interrupt)
    assert cli.main(["chat", "--fake"]) == 0
    assert len(instances) == 1 and not instances[0]._thread.is_alive()

    before = server_pids()
    result = _chat(tmp_path, ["--engine", "hand", "--fake"], QUESTION)
    assert result.returncode == 0, result.stderr
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and server_pids() - before:
        time.sleep(0.1)
    assert not server_pids() - before
