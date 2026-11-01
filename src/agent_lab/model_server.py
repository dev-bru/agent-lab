"""Control the local model server process."""

import ctypes
import shutil
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from ctypes import wintypes
from pathlib import Path


class ModelServerError(RuntimeError):
    """Report a model server setting that cannot work."""


def command(settings) -> list[str]:
    """Build the command that starts the local model."""
    return [settings.llama_server, "-m", settings.model, "--jinja", "-ngl", "99",
            "-c", "8192", "--host", settings.host, "--port", str(settings.port)]


def check_host(settings) -> None:
    """Allow only names for this computer."""
    if settings.host not in ("127.0.0.1", "localhost"):
        raise ModelServerError(f"host must be 127.0.0.1 or localhost, got '{settings.host}'")


def check(settings) -> None:
    """Check the host and the two files needed to start."""
    check_host(settings)
    if not Path(settings.llama_server).is_file() and not shutil.which(settings.llama_server):
        raise ModelServerError(f"llama_server not found: {settings.llama_server}")
    if not Path(settings.model).is_file():
        raise ModelServerError(f"model not found: {settings.model}")


def _read_pid(home: Path) -> int | None:
    """Read a positive pid and remove an invalid pid file."""
    path = home / "model.pid"
    if not path.exists():
        return None
    try:
        pid = int(path.read_text(encoding="ascii").strip())
        if pid > 0:
            return pid
    except (OSError, UnicodeError, ValueError):
        pass
    path.unlink(missing_ok=True)
    return None


def pid_alive(pid: int) -> bool:
    """Ask Windows if a process still runs without stopping it."""
    if pid <= 0:
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return ctypes.get_last_error() == 5
    try:
        code = wintypes.DWORD()
        return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally:
        kernel32.CloseHandle(handle)


def healthy(settings) -> bool:
    """Ask the local server if it is ready."""
    check_host(settings)
    url = urllib.parse.urlunsplit(("http", f"{settings.host}:{settings.port}", "/health", "", ""))
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def port_in_use(settings) -> bool:
    """Check if another process accepts this local port."""
    check_host(settings)
    try:
        with socket.create_connection((settings.host, settings.port), timeout=1):
            return True
    except OSError:
        return False


def _kill(pid: int) -> subprocess.CompletedProcess:
    """Ask Windows to stop the process and its children."""
    return subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                          capture_output=True, text=True)


def start(settings, home: Path) -> int:
    """Start the server and wait briefly for its health check."""
    # Check settings before touching a process or a network port.
    check(settings)
    pid_path = home / "model.pid"
    log_path = home / "model.log"
    # Keep a server that is already ready.
    pid = _read_pid(home)
    if pid is not None and pid_alive(pid) and healthy(settings):
        print("already running")
        return 0
    # Avoid starting a second server on the same port.
    if port_in_use(settings):
        print(f"port {settings.port} is in use by another process")
        return 1
    # Save output and the pid so later commands can find this process.
    home.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        proc = subprocess.Popen(command(settings), stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL,
                                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    pid_path.write_text(f"{proc.pid}\n", encoding="ascii", newline="\n")
    # Wait only as long as settings allow, up to two minutes.
    deadline = time.monotonic() + min(settings.timeout_s, 120)
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        if healthy(settings):
            print(f"running (pid {proc.pid})")
            return 0
        time.sleep(1)
    # Remove this start attempt if the server never became ready.
    if proc.poll() is None:
        _kill(proc.pid)
    pid_path.unlink(missing_ok=True)
    print(f"model server did not start; see {log_path}")
    return 1


def status(settings, home: Path) -> int:
    """Show whether the saved server process is ready."""
    check_host(settings)
    pid = _read_pid(home)
    if pid is None:
        print("stopped")
    elif not pid_alive(pid):
        (home / "model.pid").unlink(missing_ok=True)
        print("stopped")
    else:
        print("running" if healthy(settings) else "stopped")
    return 0


def stop(settings, home: Path) -> int:
    """Stop the saved server process when it still runs."""
    pid_path = home / "model.pid"
    pid = _read_pid(home)
    if pid is None or not pid_alive(pid):
        pid_path.unlink(missing_ok=True)
        print("already stopped")
        return 0
    result = _kill(pid)
    if result.returncode == 0:
        # Windows can keep the port busy briefly after taskkill exits.
        for check in range(41):
            if not port_in_use(settings):
                break
            if check == 40:
                pid_path.unlink(missing_ok=True)
                print(f"stopped, but port {settings.port} is still in use")
                return 0
            time.sleep(0.25)
        pid_path.unlink(missing_ok=True)
        print("stopped")
        return 0
    print(f"could not stop pid {pid}:\n{result.stdout}{result.stderr}")
    return 1
