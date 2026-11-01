"""Block network calls outside this computer during every test."""

import socket

REAL_CONNECT = socket.socket.connect
REAL_CONNECT_EX = socket.socket.connect_ex
REAL_GETADDRINFO = socket.getaddrinfo


def _allowed(host):
    """Accept only names that point to this computer."""
    return str(host).lower() in {"127.0.0.1", "::1", "localhost"}


def _connect(self, address):
    """Stop a remote connection before it opens."""
    if self.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple) and not _allowed(address[0]):
        raise RuntimeError(f"network blocked by test guard: {address[0]}")
    return REAL_CONNECT(self, address)


def _connect_ex(self, address):
    """Stop a remote connection before it opens."""
    if self.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple) and not _allowed(address[0]):
        raise RuntimeError(f"network blocked by test guard: {address[0]}")
    return REAL_CONNECT_EX(self, address)


def _getaddrinfo(host, *args, **kwargs):
    """Stop a remote name lookup before it starts."""
    if host not in (None, "") and not _allowed(host):
        raise RuntimeError(f"network blocked by test guard: {host}")
    return REAL_GETADDRINFO(host, *args, **kwargs)


for _wrapper in (_connect, _connect_ex, _getaddrinfo):
    _wrapper._agent_lab_guard = True
if not getattr(socket.socket.connect, "_agent_lab_guard", False):
    socket.socket.connect = _connect
if not getattr(socket.socket.connect_ex, "_agent_lab_guard", False):
    socket.socket.connect_ex = _connect_ex
if not getattr(socket.getaddrinfo, "_agent_lab_guard", False):
    socket.getaddrinfo = _getaddrinfo
