"""Check that tests cannot open remote network connections."""

import os
import socket
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

@pytest.mark.parametrize("family,address", [
    (socket.AF_INET, ("93.184.216.34", 80)),
    (socket.AF_INET6, ("2001:db8::1", 80, 0, 0)),
])
def test_remote_connections_blocked(monkeypatch, family, address):
    calls = []
    monkeypatch.setitem(socket.socket.connect.__globals__, "REAL_CONNECT", lambda *args: calls.append(args))
    monkeypatch.setitem(socket.socket.connect_ex.__globals__, "REAL_CONNECT_EX", lambda *args: calls.append(args))
    with socket.socket(family) as client:
        with pytest.raises(RuntimeError, match="network blocked by test guard"):
            client.connect(address)
        with pytest.raises(RuntimeError, match="network blocked by test guard"):
            client.connect_ex(address)
    assert calls == []


def test_loopback_and_dns():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with socket.socket() as client:
            client.connect(listener.getsockname())
            peer, _ = listener.accept()
            peer.close()
    assert socket.getaddrinfo("localhost", 80)
    assert socket.getaddrinfo("::1", 80)
    with pytest.raises(RuntimeError, match="example.com"):
        socket.getaddrinfo("example.com", 80)


@pytest.mark.parametrize("start,expected", [
    ("example.internal", "example.internal,127.0.0.1,localhost"),
    ("127.0.0.1", "127.0.0.1,localhost"),
])
def test_import_sets_local_environment(start, expected):
    root = Path(__file__).resolve().parents[1]
    code = ("import os, sys; sys.path.insert(0, os.environ['PYTHONPATH']); "
            "import agent_lab.model; "
            "print(os.environ['LITELLM_LOCAL_MODEL_COST_MAP']); print(os.environ['NO_PROXY'])")
    env = dict(os.environ, PYTHONPATH=str(root / "src"), NO_PROXY=start)
    env.pop("LITELLM_LOCAL_MODEL_COST_MAP", None)
    result = subprocess.run([sys.executable, "-I", "-c", code], env=env,
                            capture_output=True, text=True, check=True)
    assert result.stdout.splitlines() == ["True", expected]


def test_live_tests_are_opt_in():
    root = Path(__file__).resolve().parents[1]
    with (root / "pyproject.toml").open("rb") as file:
        options = tomllib.load(file)["tool"]["pytest"]["ini_options"]
    assert "-m 'not live'" in options["addopts"]
    assert any(marker.startswith("live:") for marker in options["markers"])
