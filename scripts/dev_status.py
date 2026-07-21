from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = REPO_ROOT / "frontend"
BACKEND_RUNNER = REPO_ROOT / "scripts" / "dev_backend.py"
PYTHON_EXE = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
FRONTEND_LOG = REPO_ROOT / "frontend-dev-local.log"
FRONTEND_ERR_LOG = REPO_ROOT / "frontend-dev-local.err.log"
BACKEND_LOG = REPO_ROOT / "backend-dev-local.log"


@dataclass
class Listener:
    port: int
    pid: int
    command_line: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check and manage local AI Radar dev servers.")
    parser.add_argument("--frontend-port", type=int, default=3000)
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--data-mode", choices=("live", "local"), default="live")
    parser.add_argument("--start", action="store_true", help="Start missing frontend/backend servers.")
    parser.add_argument("--restart", action="store_true", help="Safely restart repo-owned servers on the configured ports.")
    parser.add_argument("--wait", type=int, default=25, help="Seconds to wait for health checks after start/restart.")
    return parser.parse_args()


def run_command(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def ps_single_quote(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def get_listeners(port: int) -> list[Listener]:
    result = run_command(["netstat", "-ano"])
    listeners: list[Listener] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if "LISTENING" not in line or f":{port}" not in line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local_address = parts[1]
        state = parts[-2]
        pid_text = parts[-1]
        if state != "LISTENING" or not local_address.endswith(f":{port}") or not pid_text.isdigit():
            continue
        listeners.append(Listener(port=port, pid=int(pid_text)))
    attach_command_lines(listeners)
    return listeners


def attach_command_lines(listeners: list[Listener]) -> None:
    for listener in listeners:
        command = (
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            "$OutputEncoding=[System.Text.Encoding]::UTF8; "
            f"Get-CimInstance Win32_Process -Filter \"ProcessId = {listener.pid}\" | "
            "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
        )
        result = run_command(["powershell.exe", "-NoProfile", "-Command", command])
        if result.returncode != 0 or not result.stdout.strip():
            continue
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            listener.command_line = str(payload.get("CommandLine") or "")
        if listener.command_line:
            continue
        path_command = (
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            f"(Get-Process -Id {listener.pid} -ErrorAction SilentlyContinue).Path"
        )
        path_result = run_command(["powershell.exe", "-NoProfile", "-Command", path_command])
        if path_result.returncode == 0 and path_result.stdout.strip():
            listener.command_line = path_result.stdout.strip()


def http_status(url: str, *, timeout: int = 4) -> tuple[bool, str]:
    try:
        with request.urlopen(url, timeout=timeout) as response:
            status = int(response.status)
            return 200 <= status < 500, str(status)
    except error.HTTPError as exc:
        return 200 <= int(exc.code) < 500, str(exc.code)
    except Exception as exc:
        return False, type(exc).__name__


def is_repo_owned(listener: Listener) -> bool:
    command = listener.command_line.lower()
    if not command and listener.port in {3000, 8000}:
        return True
    repo_markers = {str(REPO_ROOT).lower(), REPO_ROOT.name.lower()}
    if "dev_backend.py" in command:
        return True
    if listener.port == 8000 and command.endswith("python.exe"):
        return True
    if listener.port == 3000 and "node_modules" in command and "next" in command:
        return True
    if listener.port == 3000 and command.endswith("node.exe"):
        return True
    return any(marker and marker in command for marker in repo_markers) and ("npm" in command or "next" in command)


def stop_listener(listener: Listener) -> bool:
    if not is_repo_owned(listener):
        print(f"Refusing to stop PID {listener.pid} on {listener.port}; command line does not look repo-owned.")
        print(f"  {listener.command_line or '(no command line available)'}")
        return False
    result = run_command(["powershell.exe", "-NoProfile", "-Command", f"Stop-Process -Id {listener.pid} -Force"])
    if result.returncode == 0:
        print(f"Stopped PID {listener.pid} on port {listener.port}")
        return True
    print(f"Failed to stop PID {listener.pid} on port {listener.port}: {result.stderr.strip()}")
    return False


def start_backend(port: int, data_mode: str) -> None:
    if not PYTHON_EXE.exists():
        raise RuntimeError(f"Python virtualenv not found: {PYTHON_EXE}")
    args = [
        str(PYTHON_EXE),
        str(BACKEND_RUNNER),
        "--data-mode",
        data_mode,
        "--port",
        str(port),
    ]
    subprocess.Popen(
        args,
        cwd=str(REPO_ROOT),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
    )
    print(f"Started backend on http://127.0.0.1:{port} (log: {BACKEND_LOG})")


def start_frontend(port: int) -> None:
    cmd_command = (
        f'npm.cmd run dev -- --hostname 127.0.0.1 --port {port} '
        f'> "{FRONTEND_LOG}" 2> "{FRONTEND_ERR_LOG}"'
    )
    command = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue; "
        "Start-Process -FilePath 'cmd.exe' "
        f"-ArgumentList @('/d','/s','/c',{ps_single_quote(cmd_command)}) "
        f"-WorkingDirectory {ps_single_quote(FRONTEND_DIR)} "
        "-WindowStyle Hidden"
    )
    result = run_command(["powershell.exe", "-NoProfile", "-Command", command])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Failed to start frontend dev server.")
    print(f"Started frontend on http://127.0.0.1:{port} (log: {FRONTEND_LOG}; errors: {FRONTEND_ERR_LOG})")


def wait_for(url: str, seconds: int) -> tuple[bool, str]:
    deadline = time.time() + seconds
    last_detail = "not checked"
    while time.time() < deadline:
        ok, detail = http_status(url)
        if ok:
            return True, detail
        last_detail = detail
        time.sleep(1)
    return False, last_detail


def print_status(frontend_port: int, backend_port: int) -> tuple[bool, bool]:
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    backend_url = f"http://127.0.0.1:{backend_port}/health"
    frontend_listeners = get_listeners(frontend_port)
    backend_listeners = get_listeners(backend_port)
    frontend_ok, frontend_detail = http_status(frontend_url)
    backend_ok, backend_detail = http_status(backend_url)

    print("AI Radar local dev status")
    print(f"  Frontend: {frontend_url} -> {'OK' if frontend_ok else 'DOWN'} ({frontend_detail})")
    for listener in frontend_listeners:
        owner = "repo-owned" if is_repo_owned(listener) else "external/unknown"
        print(f"    listener pid={listener.pid} {owner}")
        if owner == "external/unknown" and listener.command_line:
            print(f"      command: {listener.command_line}")
    if not frontend_listeners:
        print("    no listener")

    print(f"  Backend:  {backend_url} -> {'OK' if backend_ok else 'DOWN'} ({backend_detail})")
    for listener in backend_listeners:
        owner = "repo-owned" if is_repo_owned(listener) else "external/unknown"
        print(f"    listener pid={listener.pid} {owner}")
        if owner == "external/unknown" and listener.command_line:
            print(f"      command: {listener.command_line}")
    if not backend_listeners:
        print("    no listener")

    return frontend_ok, backend_ok


def main() -> int:
    args = parse_args()

    if args.restart:
        for listener in get_listeners(args.frontend_port) + get_listeners(args.backend_port):
            stop_listener(listener)
        time.sleep(2)
        args.start = True

    if args.start:
        if not get_listeners(args.backend_port):
            start_backend(args.backend_port, args.data_mode)
        if not get_listeners(args.frontend_port):
            start_frontend(args.frontend_port)
        frontend_ok, frontend_detail = wait_for(f"http://127.0.0.1:{args.frontend_port}", args.wait)
        backend_ok, backend_detail = wait_for(f"http://127.0.0.1:{args.backend_port}/health", args.wait)
        print(f"Startup check frontend: {'OK' if frontend_ok else 'DOWN'} ({frontend_detail})")
        print(f"Startup check backend:  {'OK' if backend_ok else 'DOWN'} ({backend_detail})")

    frontend_ok, backend_ok = print_status(args.frontend_port, args.backend_port)
    return 0 if frontend_ok and backend_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
