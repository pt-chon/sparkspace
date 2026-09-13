"""Open the local workspace or its compact capture window without a console."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener


PROJECT = Path(__file__).resolve().parent
DEFAULT_PORT = 18478


def python_windowless() -> str:
    candidate = Path(sys.executable).with_name("pythonw.exe")
    return str(candidate if candidate.is_file() else Path(sys.executable))


def healthy(port: int) -> bool:
    """Only a refused TCP connection means it is safe to start a new server."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=3):
            pass
    except ConnectionRefusedError:
        return False
    except OSError as error:
        if getattr(error, "winerror", None) == 10061 or error.errno in {61, 111}:
            return False
        raise RuntimeError("无法确认本机端口状态，请稍后重试。") from error
    try:
        with build_opener(ProxyHandler({})).open(f"http://127.0.0.1:{port}/api/health", timeout=1.5) as response:
            value = json.loads(response.read(4096))
        if isinstance(value, dict) and value.get("app") == "sparkspace" and value.get("ok") is True:
            return True
    except (HTTPError, URLError, OSError, ValueError):
        pass
    raise RuntimeError(f"端口 {port} 已被其他程序占用，或工作台未能正常响应。未启动第二个服务。")


@contextmanager
def startup_lock(port: int):
    if sys.platform != "win32":
        yield
        return
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateMutexW(None, False, f"Local\\SparkspaceStartup-{port}")
    if not handle:
        raise RuntimeError("无法取得工作台启动锁，请稍后重试。")
    acquired = False
    try:
        acquired = kernel.WaitForSingleObject(handle, 20000) in (0, 0x80)
        if not acquired:
            raise RuntimeError("另一个入口仍在启动工作台，请稍后重试。")
        yield
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


def ensure_service(port: int = DEFAULT_PORT, data_dir: Path | None = None) -> subprocess.Popen | None:
    if not 1 <= port <= 65535:
        raise ValueError("端口必须在 1 到 65535 之间。")
    with startup_lock(port):
        if healthy(port):
            return None
        data_dir = Path(data_dir or PROJECT / "user-data").resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        with (data_dir / "server.log").open("ab") as log:
            process = subprocess.Popen(
                [python_windowless(), str(PROJECT / "server.py"), "--host", "0.0.0.0", "--port", str(port), "--data-dir", str(data_dir)],
                cwd=PROJECT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            time.sleep(0.15)
            try:
                if healthy(port):
                    return process
            except RuntimeError:
                pass  # A bound listener can still be entering its HTTP serving loop.
            if process.poll() is not None:
                break
        raise RuntimeError(f"灵感屿服务未能启动，原有数据已保留。请查看 {data_dir / 'server.log'}。")


def open_workspace(port: int = DEFAULT_PORT) -> None:
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    chrome = next((str(path) for path in candidates if path.is_file()), None) or shutil.which("chrome")
    if not chrome:
        raise RuntimeError("没有找到 Google Chrome，请安装 Chrome 后重试。")
    subprocess.Popen(
        [chrome, f"--app=http://127.0.0.1:{port}", "--window-size=1440,960"],
        cwd=PROJECT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def open_quick(port: int = DEFAULT_PORT, data_dir: Path | None = None) -> None:
    subprocess.Popen(
        [python_windowless(), str(PROJECT / "quick_capture.pyw"), "--port", str(port), "--data-dir", str(Path(data_dir or PROJECT / "user-data").resolve())],
        cwd=PROJECT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def show_error(message: str) -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(None, message, "灵感屿", 0x10)
    else:
        print(message, file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="打开灵感屿桌面工作台")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--data-dir", type=Path, default=PROJECT / "user-data")
    parser.add_argument("--quick", action="store_true", help="只打开悬浮速记输入栏")
    args = parser.parse_args()
    try:
        ensure_service(args.port, args.data_dir)
        open_quick(args.port, args.data_dir) if args.quick else open_workspace(args.port)
    except (OSError, ValueError, RuntimeError) as error:
        show_error(str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
