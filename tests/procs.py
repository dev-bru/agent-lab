"""Find MCP server processes for cleanup checks."""

import json
import os
import subprocess


def server_pids():
    """Find this test's MCP servers and servers whose parent has exited."""
    command = ("Get-CimInstance Win32_Process | "
               "Select-Object ProcessId, ParentProcessId, CommandLine | "
               "ConvertTo-Json -Compress")
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                            capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        # ponytail: The sandbox denies CIM; compare all Python PIDs until command lines are available.
        command = "Get-Process -Name python -ErrorAction SilentlyContinue | ForEach-Object { $_.Id }"
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                                capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        return {int(line) for line in result.stdout.splitlines() if line.strip().isdigit()}
    processes = json.loads(result.stdout) if result.stdout.strip() else []
    if isinstance(processes, dict):
        processes = [processes]
    by_pid = {int(process["ProcessId"]): process for process in processes}
    servers = set()
    for pid, process in by_pid.items():
        if "agent_lab.mcp_server" not in (process["CommandLine"] or ""):
            continue
        parent = int(process["ParentProcessId"] or 0)
        # Other workers' servers have a live parent outside this test's tree.
        if parent not in by_pid:
            servers.add(pid)
            continue
        seen = set()
        while parent in by_pid and parent != os.getpid() and parent not in seen:
            seen.add(parent)
            parent = int(by_pid[parent]["ParentProcessId"] or 0)
        if parent == os.getpid():
            servers.add(pid)
    return servers
