"""Check local model server control without starting a real server."""

import ast
import os
import socket
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from agent_lab import model_server as server
from agent_lab.cli import main
from agent_lab.settings import Settings, load


ROOT = Path(__file__).resolve().parents[1]
REAL_POPEN = subprocess.Popen
REAL_KILL = server._kill


@pytest.fixture(autouse=True)
def block_processes(monkeypatch, request) -> None:
    """Fail if an offline test starts, stops, or calls a server."""
    if request.node.get_closest_marker("live"):
        return

    def blocked(*args, **kwargs):
        """Stop an unexpected call to a real process or server."""
        pytest.fail("unexpected process or health call")

    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(server, "_kill", blocked)
    monkeypatch.setattr(server, "healthy", blocked)


@pytest.fixture
def local_settings(tmp_path: Path) -> Settings:
    """Make files that pass the start checks."""
    executable = tmp_path / "llama-server.exe"
    model = tmp_path / "model.gguf"
    executable.touch()
    model.touch()
    return Settings(llama_server=str(executable), model=str(model))


@pytest.fixture
def fast_start(monkeypatch) -> None:
    """Keep start tests away from real ports and real waits."""
    monkeypatch.setattr(server, "port_in_use", lambda settings: False)
    monkeypatch.setattr(server.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(server.time, "monotonic", lambda: 0)


def test_command_from_example() -> None:
    """Pass the exact model arguments in the required order."""
    settings = load(ROOT / "agent-lab.example.toml", {})
    assert server.command(settings) == [
        settings.llama_server, "-m", settings.model, "--jinja", "-ngl", "99",
        "-c", "8192", "--host", settings.host, "--port", str(settings.port),
    ]


@pytest.mark.parametrize("function", [server.check, server.status, server.healthy])
def test_nonlocal_host_is_rejected(function, tmp_path: Path) -> None:
    """Name the unsafe host before any server connection."""
    with pytest.raises(server.ModelServerError, match="example.com"):
        if function is server.status:
            function(Settings(host="example.com"), tmp_path)
        else:
            function(Settings(host="example.com"))


def test_missing_files_name_setting_and_value(tmp_path: Path) -> None:
    """Show which required file is missing."""
    missing_server = str(tmp_path / "missing.exe")
    with pytest.raises(server.ModelServerError, match="llama_server not found: .*missing.exe"):
        server.check(Settings(llama_server=missing_server))
    existing = tmp_path / "server.exe"
    existing.touch()
    with pytest.raises(server.ModelServerError, match="model not found: .*missing.gguf"):
        server.check(Settings(llama_server=str(existing), model=str(tmp_path / "missing.gguf")))


def test_bare_server_name_on_path(monkeypatch, tmp_path: Path) -> None:
    """Allow a server name found on PATH."""
    model = tmp_path / "model.gguf"
    model.touch()
    monkeypatch.setattr(server.shutil, "which", lambda name: "found" if name == "server.exe" else None)
    server.check(Settings(llama_server="server.exe", model=str(model)))


def test_already_running(local_settings, tmp_path: Path, monkeypatch, fast_start, capsys) -> None:
    """Reuse a ready process and keep its pid."""
    home = tmp_path / "state"
    home.mkdir()
    (home / "model.pid").write_text("4242\n", encoding="ascii")
    monkeypatch.setattr(server, "pid_alive", lambda pid: True)
    monkeypatch.setattr(server, "healthy", lambda settings: True)
    assert server.start(local_settings, home) == 0
    assert capsys.readouterr().out.strip() == "already running"


def test_port_in_use(local_settings, tmp_path: Path, monkeypatch, capsys) -> None:
    """Refuse a port held by another local process."""
    monkeypatch.setattr(server.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(server.time, "monotonic", lambda: 0)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        settings = replace(local_settings, port=listener.getsockname()[1])
        assert server.start(settings, tmp_path / "state") == 1
        assert f"port {settings.port}" in capsys.readouterr().out


def test_dead_pid_is_removed(tmp_path: Path, capsys) -> None:
    """Clear a pid after its process exits."""
    result = REAL_POPEN([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL)
    assert result.wait() == 0
    pid_path = tmp_path / "model.pid"
    pid_path.write_text(f"{result.pid}\n", encoding="ascii")
    assert server.status(Settings(), tmp_path) == 0
    assert capsys.readouterr().out.strip() == "stopped"
    assert not pid_path.exists()
    pid_path.write_text(f"{result.pid}\n", encoding="ascii")
    assert server.stop(Settings(), tmp_path) == 0
    assert capsys.readouterr().out.strip() == "already stopped"
    assert not pid_path.exists()


def test_corrupt_pid_is_removed(tmp_path: Path, capsys) -> None:
    """Treat text in the pid file as stopped."""
    path = tmp_path / "model.pid"
    path.write_text("abc", encoding="ascii")
    assert server.status(Settings(), tmp_path) == 0
    assert capsys.readouterr().out.strip() == "stopped"
    assert not path.exists()


def test_pid_alive() -> None:
    """Find this process and reject pid zero."""
    assert server.pid_alive(os.getpid())
    assert not server.pid_alive(0)


def test_start_success(local_settings, tmp_path: Path, monkeypatch, fast_start, capsys) -> None:
    """Save the launched pid and report a healthy server."""
    calls = []

    class Process:
        """Act like a process that keeps running."""
        pid = 4242

        def poll(self):
            """Report that the process is still active."""
            return None

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)) or Process())
    monkeypatch.setattr(server, "healthy", lambda settings: True)
    home = tmp_path / "state"
    assert server.start(local_settings, home) == 0
    assert capsys.readouterr().out.strip() == "running (pid 4242)"
    assert (home / "model.pid").read_text(encoding="ascii") == "4242\n"
    assert calls[0][0][0] == server.command(local_settings)
    assert calls[0][1]["creationflags"] == subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP


def test_start_failure(local_settings, tmp_path: Path, monkeypatch, fast_start, capsys) -> None:
    """Remove the pid when the process exits before health."""
    class Process:
        """Act like a process that exits at once."""
        pid = 4242

        def poll(self):
            """Report a failed process."""
            return 1

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: Process())
    home = tmp_path / "state"
    assert server.start(local_settings, home) == 1
    output = capsys.readouterr().out
    assert str(home / "model.log") in output
    assert "stopped" not in output
    assert not (home / "model.pid").exists()


def test_start_timeout(local_settings, tmp_path: Path, monkeypatch, fast_start) -> None:
    """Stop one failed start after the time limit."""
    class Process:
        """Act like a process that never becomes ready."""
        pid = 4242

        def poll(self):
            """Report that the process still runs."""
            return None

    calls = []
    clock = iter([0, 0, 121])
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: Process())
    monkeypatch.setattr(server, "healthy", lambda settings: False)
    monkeypatch.setattr(server, "_kill", lambda pid: calls.append(pid))
    monkeypatch.setattr(server.time, "monotonic", lambda: next(clock))
    home = tmp_path / "state"
    assert server.start(local_settings, home) == 1
    assert calls == [4242]
    assert not (home / "model.pid").exists()


def test_stop_success(tmp_path: Path, monkeypatch, capsys) -> None:
    """Wait for the port before removing the pid after taskkill."""
    path = tmp_path / "model.pid"
    path.write_text("4242\n", encoding="ascii")
    checks = []
    sleeps = []
    monkeypatch.setattr(server, "pid_alive", lambda pid: True)
    monkeypatch.setattr(server, "_kill", lambda pid: subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(server, "port_in_use", lambda settings: checks.append(1) or len(checks) < 3)
    monkeypatch.setattr(server.time, "sleep", lambda seconds: sleeps.append(seconds))
    assert server.stop(Settings(), tmp_path) == 0
    assert capsys.readouterr().out.strip() == "stopped"
    assert len(checks) == 3
    assert sleeps == [0.25, 0.25]
    assert not path.exists()


def test_stop_port_stays_in_use(tmp_path: Path, monkeypatch, capsys) -> None:
    """Report a busy port after ten seconds without waiting in the test."""
    path = tmp_path / "model.pid"
    path.write_text("4242\n", encoding="ascii")
    sleeps = []
    monkeypatch.setattr(server, "pid_alive", lambda pid: True)
    monkeypatch.setattr(server, "_kill", lambda pid: subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(server, "port_in_use", lambda settings: True)
    monkeypatch.setattr(server.time, "sleep", lambda seconds: sleeps.append(seconds))
    assert server.stop(Settings(), tmp_path) == 0
    assert capsys.readouterr().out.strip() == "stopped, but port 8090 is still in use"
    assert sleeps == [0.25] * 40
    assert not path.exists()


def test_kill_command(monkeypatch) -> None:
    """Pass the exact taskkill arguments without a shell."""
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    REAL_KILL(4242)
    assert calls == [((["taskkill", "/PID", "4242", "/T", "/F"],),
                      {"capture_output": True, "text": True})]


def test_stop_failure_keeps_pid(tmp_path: Path, monkeypatch, capsys) -> None:
    """Keep the pid so a failed stop can be retried."""
    path = tmp_path / "model.pid"
    path.write_text("4242\n", encoding="ascii")
    monkeypatch.setattr(server, "pid_alive", lambda pid: True)
    monkeypatch.setattr(server, "_kill", lambda pid: subprocess.CompletedProcess([], 1, "error", ""))
    assert server.stop(Settings(), tmp_path) == 1
    assert "could not stop pid 4242:" in capsys.readouterr().out
    assert path.exists()


def test_cli_status(tmp_path: Path, monkeypatch, capsys) -> None:
    """Show stopped from the command line with no pid."""
    monkeypatch.chdir(tmp_path)
    assert main(["model", "status"]) == 0
    assert capsys.readouterr().out.strip() == "stopped"


@pytest.mark.parametrize("key,value,expected", [
    ("AGENT_LAB_PORT", "abc", "port"),
    ("AGENT_LAB_HOST", "example.com", "example.com"),
    ("AGENT_LAB_MODEL", "missing.gguf", "missing.gguf"),
])
def test_cli_errors(tmp_path: Path, monkeypatch, capsys, fast_start, key, value, expected) -> None:
    """Show settings and start errors on stderr."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(key, value)
    if key == "AGENT_LAB_MODEL":
        executable = tmp_path / "server.exe"
        executable.touch()
        monkeypatch.setenv("AGENT_LAB_LLAMA_SERVER", str(executable))
    assert main(["model", "start"]) == 1
    assert expected in capsys.readouterr().err


def test_cli_requires_action() -> None:
    """Reject a model command with no action."""
    with pytest.raises(SystemExit) as error:
        main(["model"])
    assert error.value.code == 2


def test_module_docstrings_and_local_urls() -> None:
    """Keep help text short and avoid written network URLs."""
    for path in (ROOT / "src/agent_lab/model_server.py", ROOT / "src/agent_lab/cli.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert ast.get_docstring(tree)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node)
                assert doc, node.name
                assert all(len(sentence.split()) <= 20 for sentence in doc.split("."))
        if path.name == "model_server.py":
            assert "http://" not in source
            assert "https://" not in source


@pytest.mark.live
def test_live_model_server(tmp_path: Path, capsys) -> None:
    """Start, inspect, and stop the real local model server."""
    config = ROOT / "agent-lab.toml"
    if not config.exists():
        pytest.fail(f"local settings file is missing: {config}")
    settings = load(config)
    if server.port_in_use(settings):
        home = ROOT / ".agent-lab"
        if not (home / "model.pid").exists():
            pytest.fail(
                f"server on port {settings.port} was not started by 'agent-lab model start' "
                "from the repo root (no .agent-lab/model.pid)"
            )
        assert server.status(settings, home) == 0
        assert capsys.readouterr().out.strip().splitlines()[-1] == "running"
        return
    assert server.start(settings, tmp_path) == 0
    assert server.status(settings, tmp_path) == 0
    assert "running" in capsys.readouterr().out
    assert server.stop(settings, tmp_path) == 0
    assert server.status(settings, tmp_path) == 0
    assert capsys.readouterr().out.endswith("stopped\n")
