"""Check the real local model, lessons, agents, and server controls."""

import dataclasses
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from agent_lab import model, model_server, settings
from agent_lab.agent import graph, hand
from agent_lab.mcp_client import McpTools
from agent_lab.trace import Trace


ROOT = Path(__file__).resolve().parents[1]
QUESTION = "What is 17 times 23? Save the answer as a note called result."


class AttemptError(Exception):
    """Keep the reply and trace from a failed live attempt."""

    def __init__(self, message, reply=None, trace_path=None):
        """Save details that make a model failure easier to inspect."""
        super().__init__(message)
        self.reply = reply
        self.trace_path = trace_path


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    """Start one local server if needed and stop only a server we own."""
    with pytest.MonkeyPatch().context() as monkeypatch:
        monkeypatch.chdir(ROOT)
        config_path = ROOT / "agent-lab.toml"
        if not config_path.exists():
            pytest.fail(f"local settings file is missing: {config_path}")
        config = settings.load(config_path)
        owned = False
        home = ROOT / ".agent-lab"
        try:
            if model_server.port_in_use(config):
                if not (home / "model.pid").exists():
                    pytest.fail(
                        f"server on port {config.port} was not started by 'agent-lab model start' "
                        "from the repo root (no .agent-lab/model.pid)"
                    )
            else:
                home = tmp_path_factory.mktemp("live-server")
                assert model_server.start(config, home) == 0
                owned = True
            model.chat([{"role": "user", "content": "Say ready."}], settings=config)
            yield config, home, owned
        finally:
            if owned:
                assert model_server.stop(config, home) == 0


def attempts(fn, n=3):
    """Try a live check again and report every failed attempt."""
    errors = []
    for number in range(1, n + 1):
        try:
            fn()
        except AttemptError as error:
            errors.append(error)
        else:
            print(f"passed on attempt {number} of {n}")
            return number
    last = errors[-1]
    pytest.fail("\n".join(
        [f"attempt {index}: {error}" for index, error in enumerate(errors, 1)]
        + [f"last model reply: {last.reply if last.reply is not None else 'none'}",
           f"trace: {last.trace_path if last.trace_path is not None else 'none'}"]
    ))


def test_attempts_helper():
    """Show the first success and the last trace after three failures."""
    calls = 0

    def once():
        """Fail once before reporting success."""
        nonlocal calls
        calls += 1
        if calls == 1:
            raise AttemptError("first failure")

    def always():
        """Keep failing with a trace for the report."""
        raise AttemptError("still failing", trace_path="t.jsonl")

    assert attempts(once) == 2
    with pytest.raises(pytest.fail.Exception, match="attempt 3:.*") as error:
        attempts(always)
    assert "trace: t.jsonl" in str(error.value)


@pytest.mark.live
@pytest.mark.parametrize("name", [
    "01_model_call", "02_tool_call", "03_structured_output", "04_agent_loop",
    "05_mcp_client", "06_langgraph_agent",
])
def test_live_lesson(name, live_server, tmp_path):
    """Run one lesson with a fresh note and trace folder each time."""
    number = 0

    def run_once():
        """Run one lesson and keep its output when it fails."""
        nonlocal number
        number += 1
        folder = tmp_path / str(number)
        folder.mkdir()
        runs = folder / "runs"
        try:
            result = subprocess.run(
                [sys.executable, f"lessons/{name}.py"], cwd=ROOT,
                env={**os.environ, "PYTHONPATH": "src", "PYTHONUTF8": "1",
                     "AGENT_LAB_NOTES_DIR": str(folder / "notes"),
                     "AGENT_LAB_RUNS_DIR": str(runs)},
                capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
            if result.returncode == 0:
                return
            message = f"exit code {result.returncode}"
            stdout, stderr = result.stdout, result.stderr
        except subprocess.TimeoutExpired as error:
            message = "timed out after 30 s"
            stdout, stderr = error.stdout or "", error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        traces = list(runs.glob("*")) if runs.exists() else []
        newest = max(traces, key=lambda path: path.stat().st_mtime) if traces else None
        raise AttemptError(f"{message}; stderr: {stderr[-500:]}", stdout[-500:], newest)

    attempts(run_once)


@pytest.mark.live
@pytest.mark.parametrize("engine", ["hand", "graph"])
def test_live_agent(engine, live_server, tmp_path):
    """Check the two required tools and the final answer in a fresh run."""
    config, _, _ = live_server
    number = 0

    def run_once():
        """Run an agent once and inspect the closed trace."""
        nonlocal number
        number += 1
        folder = tmp_path / str(number)
        folder.mkdir()
        path = None
        result = None
        failure = None
        started = time.monotonic()
        try:
            with McpTools(settings=dataclasses.replace(config, notes_dir=str(folder / "notes"))) as tools, \
                    Trace.new(folder / "runs", engine) as log:
                path = log.path
                runner = hand if engine == "hand" else graph
                agent_model = model if engine == "hand" else graph.chat_model(config)
                result = runner.run(QUESTION, model=agent_model, tools=tools, trace=log)
        except Exception as error:
            failure = str(error)
        elapsed = time.monotonic() - started
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path else []
        reply = next((row.get("text") for row in reversed(records)
                      if row.get("kind") == "model_reply"), None)
        calls = [row for row in records if row.get("kind") == "tool_call"]
        if failure:
            raise AttemptError(failure, reply, path)
        try:
            assert elapsed <= 30, f"took {elapsed:.1f} s (limit 30 s)"
            assert result.stopped_by == "answer" and "391" in result.text, f"final answer: {result}"
            assert calls and calls[0]["name"] == "multiply", f"first tool call: {calls[:1]}"
            assert json.loads(calls[0]["arguments"]) == {"a": 17, "b": 23}
            assert any(row["name"] == "write_note"
                       and (args := json.loads(row["arguments"])).get("name") == "result"
                       and "391" in args.get("text", "") for row in calls[1:]), \
                f"write_note after multiply: {calls[1:]}"
        except (AssertionError, KeyError, ValueError, TypeError) as error:
            raise AttemptError(str(error), reply, path) from error

    attempts(run_once)


@pytest.mark.live
def test_live_model_hash(live_server):
    """Match the model file to its recorded SHA-256 value."""
    config, _, _ = live_server
    name = Path(config.model).name
    lines = (ROOT / "docs/DEPENDENCIES.md").read_text(encoding="utf-8").splitlines()
    rows = [cells for line in lines if line.startswith("|")
            if (cells := [cell.strip() for cell in line.strip().strip("|").split("|")])[0] == name]
    assert len(rows) == 1, f"expected one dependency row for {name}, found {len(rows)}"
    expected = rows[0][-1]
    assert re.fullmatch(r"[0-9a-f]{64}", expected), f"invalid SHA-256 for {name}: {expected}"
    digest = hashlib.sha256()
    with Path(config.model).open("rb") as file:
        while block := file.read(1024 * 1024):
            digest.update(block)
    assert digest.hexdigest() == expected, f"SHA-256 mismatch for {name}"


@pytest.mark.live
def test_live_server_restart(live_server, capsys):
    """Stop and restart the same server, then check it answers."""
    config, home, _ = live_server
    try:
        assert model_server.stop(config, home) == 0
        assert model_server.status(config, home) == 0
        assert capsys.readouterr().out.strip().splitlines()[-1] == "stopped"
        assert model_server.start(config, home) == 0
        assert model_server.status(config, home) == 0
        assert capsys.readouterr().out.strip().splitlines()[-1] == "running"
        model.chat([{"role": "user", "content": "Say ready."}], settings=config)
    finally:
        if not model_server.port_in_use(config):
            assert model_server.start(config, home) == 0
