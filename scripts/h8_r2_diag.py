#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""诊断：无控制台父进程派生 cmd/tasklist 是否产生可见 ConsoleWindowClass 窗口。"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.EnumWindows.restype = wintypes.BOOL
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

_INNER = r"""
import subprocess, time
subprocess.run(["cmd", "/c", "ping -n 3 127.0.0.1 >nul"], capture_output=True)
subprocess.run(["tasklist", "/FI", "IMAGENAME eq WINWORD.EXE", "/FO", "CSV"], capture_output=True)
time.sleep(0.5)
print("inner_done", flush=True)
"""


def scan() -> list[tuple[int, int, str]]:
    buf: list[int] = []
    def _cb(hwnd, lparam):
        buf.append(int(hwnd))
        return True
    cb = WNDENUMPROC(_cb)
    user32.EnumWindows(cb, 0)
    out = []
    for hwnd in buf:
        if user32.IsWindowVisible(hwnd):
            cls = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, cls, 128)
            pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            out.append((hwnd, int(pid.value), cls.value))
    return out


def main() -> int:
    # 用 pythonw.exe（GUI 子系统、无控制台）模拟冻结 onedir 服务进程：
    # 无控制台的父进程派生控制台子进程 → 分配新控制台 → 可见控制台窗口。
    exe_dir = os.path.dirname(sys.executable)
    pyw = os.path.join(exe_dir, "pythonw.exe")
    if not os.path.exists(pyw):
        print("pythonw.exe 不存在", flush=True)
        return 2
    p = subprocess.Popen([pyw, "-c", _INNER],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    seen: set[int] = set()
    t0 = time.time()
    while time.time() - t0 < 20:
        for hwnd, pid, cls in scan():
            if cls in ("ConsoleWindowClass", "PseudoConsoleWindow"):
                key = (hwnd, pid)
                if key not in seen:
                    seen.add(key)
                    print(f"CONSOLE hwnd={hwnd} pid={pid} cls={cls} t={time.time()-t0:.2f}s", flush=True)
        if p.poll() is not None:
            print(f"inner rc={p.returncode}", flush=True)
        time.sleep(0.005)
    print("total_console_windows_seen=", len(seen), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
