"""V2.0.0 便携图形启动器（Windows x64，PLAN §3.4 / §6 T7）。

职责：
- 以 loopback 启动 FastAPI 服务（复用 ``main.app``，不复制业务逻辑）。
- 单实例：Windows 命名互斥量；重复启动只重新打开浏览器，不重复起服务。
- 端口：优先 ``APP_PORT``（默认 8000），被占用时向后扫描安全可用端口。
- 等待 ``/api/health`` 就绪后打开默认浏览器。
- 图形窗口提供「重新打开界面」与「退出」；退出释放 server / DB 引擎 / 互斥量。
- 会话令牌走 HttpOnly Cookie，不通过可复制 Token URL 暴露（PLAN §3.4）。
"""
from __future__ import annotations

import ctypes
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# 使用 Local\（会话命名空间）而非 Global\：Windows 10/11 默认禁止普通（非管理员）
# 用户创建 Global\ 命名对象（需 SeCreateGlobalPrivilege），会导致首次启动被误判为
# "已在运行"而只打开指向不存在服务的浏览器。桌面单实例只需会话级，Local\ 无需特权。
MUTEX_NAME = "Local\\ResumeAssistant.V2.0.0"
ERROR_ALREADY_EXISTS = 183
HOST = "127.0.0.1"

# 冻结 windowed 模式（console=False）下 sys.stdout/stderr 为 None；重定向到
# runtime 日志文件，既不发控制台窗口，又避免 uvicorn/logging 写 None 句柄崩溃。
_LOG_STREAM = None


def _backend_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent / "backend"


if not getattr(sys, "frozen", False):
    _bd = str(_backend_dir())
    if _bd not in sys.path:
        sys.path.insert(0, _bd)


def _acquire_mutex(name: str) -> int:
    """返回互斥量句柄（进程内持有即单实例）；已存在返回 0。"""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    handle = kernel32.CreateMutexW(None, False, name)
    if not handle:
        return 0
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        return 0
    return int(handle)


def _release_mutex(handle: int) -> None:
    if not handle:
        return
    try:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(ctypes.c_void_p(handle))
    except Exception:  # noqa: BLE001
        pass


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((HOST, port))
            return True
        except OSError:
            return False


def _find_free_port(preferred: int, max_scan: int = 50) -> int:
    for p in range(preferred, preferred + max_scan):
        if _port_available(p):
            return p
    return preferred  # 兜底：交给 uvicorn 显式报错并给出可操作错误


def _open_browser(port: int) -> None:
    webbrowser.open(f"http://{HOST}:{port}/")


def _wait_health(port: int, timeout: float = 30.0) -> bool:
    import urllib.request

    deadline = time.time() + timeout
    url = f"http://{HOST}:{port}/api/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.25)
    return False


def _run_server_thread(port: int):
    """在后台线程启动 uvicorn，返回 (server, thread)。"""
    import uvicorn

    import main as app_module  # noqa: F401 (触发路由注册与 lifespan)

    config = uvicorn.Config(app_module.app, host=HOST, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="uvicorn")
    thread.start()
    return server, thread


def _already_running(port: int) -> None:
    from tkinter import messagebox

    _open_browser(port)
    try:
        messagebox.showinfo("简历助手", "应用已在运行，已为你重新打开浏览器界面。")
    except Exception:  # noqa: BLE001
        pass


def _ensure_stdio(settings) -> None:
    """windowed 冻结模式下保证有可写 stdout/stderr（重定向到 runtime 日志）。"""
    global _LOG_STREAM
    if sys.stdout is not None and sys.stderr is not None:
        return
    logs_dir = Path(settings.LOGS_DIR)
    logs_dir.mkdir(parents=True, exist_ok=True)
    _LOG_STREAM = open(logs_dir / "app.log", "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = _LOG_STREAM
    if sys.stderr is None:
        sys.stderr = _LOG_STREAM


def main() -> None:
    from core.config import settings  # noqa: E402 (延迟 import，取得统一 runtime root)

    _ensure_stdio(settings)

    instance_dir = settings.RESUME_DATA_DIR / ".instance"
    instance_dir.mkdir(parents=True, exist_ok=True)
    port_file = instance_dir / "port.txt"

    handle = _acquire_mutex(MUTEX_NAME)
    if not handle:
        port = 8000
        try:
            port = int(port_file.read_text(encoding="utf-8").strip())
        except Exception:  # noqa: BLE001
            pass
        _already_running(port)
        return

    preferred = int(os.environ.get("APP_PORT", settings.APP_PORT))
    port = _find_free_port(preferred)
    try:
        port_file.write_text(str(port), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

    server, server_thread = _run_server_thread(port)

    if not _wait_health(port):
        # 服务未能就绪：释放资源并给出可操作错误
        _stop(server, server_thread, port_file, handle)
        _show_start_failed(preferred, port)
        return

    _open_browser(port)
    _run_gui(server, server_thread, port_file, handle, port)


def _stop(server, thread, port_file: Path, handle: int) -> None:
    try:
        server.should_exit = True
        thread.join(timeout=5)
    except Exception:  # noqa: BLE001
        pass
    try:
        from database.session import engine

        engine.dispose()
    except Exception:  # noqa: BLE001
        pass
    try:
        port_file.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass
    global _LOG_STREAM
    if _LOG_STREAM is not None:
        try:
            _LOG_STREAM.close()
        except Exception:  # noqa: BLE001
            pass
        _LOG_STREAM = None
    _release_mutex(handle)


def _show_start_failed(preferred: int, actual: int) -> None:
    import tkinter as tk
    from tkinter import messagebox

    try:
        messagebox.showerror(
            "简历助手",
            f"服务未能启动。\n优先端口 {preferred}，实际尝试端口 {actual}。\n"
            "请确认端口未被占用、依赖完整，或查看日志目录。",
        )
    except Exception:  # noqa: BLE001
        pass
    del tk


def _run_gui(server, thread, port_file: Path, handle: int, port: int) -> None:
    import tkinter as tk

    root = tk.Tk()
    root.title("简历助手")
    root.geometry("380x160")
    root.resizable(False, False)

    frame = tk.Frame(root, padx=20, pady=16)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="简历助手已就绪", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w")
    tk.Label(
        frame,
        text=f"服务地址 http://{HOST}:{port}\n浏览器已打开，可随时重新打开或退出应用。",
        justify="left",
        fg="#666666",
    ).pack(anchor="w", pady=(6, 12))

    def on_close():
        _stop(server, thread, port_file, handle)
        root.destroy()

    btn_row = tk.Frame(frame)
    btn_row.pack(anchor="w")
    tk.Button(btn_row, text="重新打开界面", width=14, command=lambda: _open_browser(port)).pack(
        side="left", padx=(0, 8)
    )
    tk.Button(btn_row, text="退出", width=14, command=on_close).pack(side="left")

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()