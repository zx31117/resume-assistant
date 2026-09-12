#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""H8-R2 窗口事件监测器（PLAN §21.2 / §21.4 机器证据）。

在独立进程中运行，用 WinEventHook（EVENT_OBJECT_CREATE / EVENT_OBJECT_SHOW /
EVENT_OBJECT_DESTROY）捕获短寿命顶层窗口，并辅以高频 EnumWindows 可见窗口轮询兜底，
同时维护进程树（pid -> image/ppid），输出 JSONL 事件流到指定文件。

关键设计：
- 每条窗口事件处理时**同步刷新进程表**（CreateToolhelp32Snapshot），保证短寿命窗口的
  pid/ppid/映像名/ancestor_is_app 判定不依赖定时刷新的滞后；
- poll 通道每 10ms 扫描可见顶层窗口，捕获存活几十毫秒以上的闪窗；
- hook 通道捕获 create/show/destroy 事件，覆盖 poll 可能错过的超短窗口；
- 输出字段（脱敏，不含 Key / JD / 履历正文）：
  ts_epoch_ms, event(create/show/destroy/poll_visible), hwnd,
  pid, ppid, image(可执行映像名), class_name, title(截断), title_len,
  visible(处理时刻快照), ancestor_is_app(父链是否含被测 exe)

用法：
  python scripts/h8_r2_winmon.py --out <events.jsonl> [--app-exe <ResumeAssistant.exe>]
                                 [--poll-ms 10] [--dump <snapshot.json>]
                                 [--tail N]  # 只打印最后 N 条事件后退出
                                 [--timeout S]  # 主动退出秒数（默认无限）
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import queue
import sys
import threading
import time
from ctypes import wintypes

# ── Win32 常量 ────────────────────────────────────────────────
EVENT_OBJECT_CREATE = 0x8000
EVENT_OBJECT_SHOW = 0x8002
EVENT_OBJECT_DESTROY = 0x8001
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0001

HWND = wintypes.HWND
DWORD = wintypes.DWORD
LONG = ctypes.c_long
BOOL = wintypes.BOOL
WINEVENTPROC = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, DWORD, HWND, LONG, LONG, DWORD, DWORD)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.SetWinEventHook.restype = wintypes.HANDLE
user32.SetWinEventHook.argtypes = [DWORD, DWORD, wintypes.HMODULE, WINEVENTPROC,
                                   DWORD, DWORD, DWORD]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [HWND]
user32.GetWindowThreadProcessId.restype = DWORD
user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(DWORD)]
user32.IsWindowVisible.restype = BOOL
user32.IsWindowVisible.argtypes = [HWND]
user32.EnumWindows.restype = BOOL
user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(BOOL, HWND, wintypes.LPARAM),
                               wintypes.LPARAM]
user32.GetMessageW.restype = BOOL
user32.GetMessageW.argtypes = [ctypes.c_void_p, HWND, ctypes.c_uint, ctypes.c_uint]
user32.TranslateMessage.restype = BOOL
user32.TranslateMessage.argtypes = [ctypes.c_void_p]
user32.DispatchMessageW.argtypes = [ctypes.c_void_p]

psapi = ctypes.windll.psapi
psapi.GetModuleFileNameExW.restype = DWORD
psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE,
                                       wintypes.LPWSTR, DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [DWORD, BOOL, DWORD]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

PROCESSENTRY32 = None
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

_TITLE_MAX = 160


def _load_pe32():
    global PROCESSENTRY32
    if PROCESSENTRY32 is not None:
        return
    class PE32(ctypes.Structure):
        _fields_ = [("dwSize", DWORD),
                    ("cntUsage", DWORD),
                    ("th32ProcessID", DWORD),
                    ("th32DefaultHeapID", ctypes.c_void_p),
                    ("th32ModuleID", DWORD),
                    ("cntThreads", DWORD),
                    ("th32ParentProcessID", DWORD),
                    ("pcPriClassBase", LONG),
                    ("dwFlags", DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]
    PROCESSENTRY32 = PE32


def _snapshot_procs() -> dict[int, tuple[str, int]]:
    """进程表 pid -> (image, ppid)。"""
    _load_pe32()
    out: dict[int, tuple[str, int]] = {}
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = [DWORD, DWORD]
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
    h = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if h == INVALID_HANDLE_VALUE:
        return out
    try:
        e = PROCESSENTRY32()
        e.dwSize = ctypes.sizeof(PROCESSENTRY32)
        ok = kernel32.Process32FirstW(h, ctypes.byref(e))
        while ok:
            out[int(e.th32ProcessID)] = (str(e.szExeFile), int(e.th32ParentProcessID))
            ok = kernel32.Process32NextW(h, ctypes.byref(e))
    finally:
        kernel32.CloseHandle(h)
    return out


def _image_of(pid: int) -> str:
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(512)
        n = psapi.GetModuleFileNameExW(h, None, buf, len(buf))
        if n:
            return os.path.basename(buf.value)
        return ""
    finally:
        kernel32.CloseHandle(h)


def _hwnd_info(hwnd: int) -> tuple[int, str, str, int, bool]:
    """返回 (pid, class_name, title, title_len, visible)。"""
    pid = DWORD(0)
    user32.GetWindowThreadProcessId(HWND(hwnd), ctypes.byref(pid))
    cls = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(HWND(hwnd), cls, 128)
    tl = user32.GetWindowTextLengthW(HWND(hwnd))
    title = ""
    if tl > 0:
        tb = ctypes.create_unicode_buffer(min(tl + 1, _TITLE_MAX + 1))
        n = user32.GetWindowTextW(HWND(hwnd), tb, len(tb))
        title = tb.value[: _TITLE_MAX]
    visible = bool(user32.IsWindowVisible(HWND(hwnd)))
    return int(pid.value) or None, cls.value, title, int(tl) if tl > 0 else 0, visible


class WindowMonitor:
    def __init__(self, out_path: str, app_exe: str | None = None, poll_ms: int = 10):
        self.out_path = out_path
        self.app_exe = (os.path.basename(app_exe).lower() if app_exe else None)
        self.poll_ms = max(5, int(poll_ms))
        self.events: list[dict] = []
        self._q: queue.Queue = queue.Queue()
        self._seen_hwnds: set[int] = set()
        self._procs: dict[int, tuple[str, int]] = {}
        self._lock = threading.Lock()
        self._hook = None
        self._msg_pump_done = threading.Event()

    # ── 事件回调（WinEventHook 线程）──────────────────────────
    def _proc(self, hhook, event, hwnd, idObject, idChild, idThread, dwms):
        if not hwnd:
            return
        if idObject != 0:  # 只关心顶层窗口对象 OBJID_WINDOW
            return
        try:
            self._q.put_nowait({"event": {EVENT_OBJECT_CREATE: "create",
                                          EVENT_OBJECT_SHOW: "show",
                                          EVENT_OBJECT_DESTROY: "destroy"}.get(event, "event"),
                                "hwnd": int(hwnd),
                                "ts": time.time()})
        except Exception:
            pass
        return

    def start(self):
        self._cb = WINEVENTPROC(self._proc)
        self._hook = user32.SetWinEventHook(EVENT_OBJECT_CREATE, EVENT_OBJECT_DESTROY,
                                            None, self._cb, 0, 0,
                                            WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS)
        self._procs = _snapshot_procs()
        threading.Thread(target=self._msg_loop, daemon=True).start()
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def _msg_loop(self):
        MSG = ctypes.c_void_p
        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    # ── 高频可见窗口轮询兜底 ─────────────────────────────────
    def _poll_loop(self):
        WNDENUMPROC = ctypes.WINFUNCTYPE(BOOL, HWND, wintypes.LPARAM)
        buf: list[int] = []

        def _cb(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                buf.append(int(hwnd))
            return True

        _cb_ref = WNDENUMPROC(_cb)
        while True:
            buf.clear()
            user32.EnumWindows(_cb_ref, 0)
            now = set(buf)
            new_visible = now - self._seen_hwnds
            if new_visible:
                for hwnd in sorted(new_visible):
                    self._record(hwnd, "poll_visible")
            self._seen_hwnds = now
            time.sleep(self.poll_ms / 1000.0)

    def _refresh_procs(self) -> None:
        try:
            self._procs = _snapshot_procs()
        except Exception:
            pass

    def _record(self, hwnd: int, event: str) -> None:
        # 同步刷新进程表：短寿命窗口的父子链判定不依赖定时刷新滞后
        self._refresh_procs()
        pid, cls, title, tlen, visible = _hwnd_info(hwnd)
        rec = {"ts_epoch_ms": int(time.time() * 1000), "event": event, "hwnd": int(hwnd),
               "pid": pid, "ppid": None, "image": "", "class_name": cls,
               "title": title, "title_len": tlen, "visible": visible,
               "ancestor_is_app": None}
        if pid:
            rec["image"] = _image_of(pid)
            rec["ppid"] = self._procs.get(pid, (None, None))[1]
            rec["ancestor_is_app"] = self._app_ancestor(pid)
        with self._lock:
            self.events.append(rec)
        self._flush_rec(rec)

    def _app_ancestor(self, pid: int) -> bool:
        if not self.app_exe:
            return None
        seen = set()
        cur = pid
        for _ in range(16):
            if cur in seen or not cur:
                return False
            seen.add(cur)
            info = self._procs.get(cur)
            if not info:
                img = _image_of(cur)
                info = (img, None)
                self._procs[cur] = info
            if info[0].lower() == self.app_exe:
                return True
            cur = info[1]
        return False

    def _flush_rec(self, rec: dict):
        try:
            with open(self.out_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def snapshot(self) -> dict:
        with self._lock:
            return {"total_events": len(self.events),
                    "events": list(self.events),
                    "app_exe": self.app_exe,
                    "poll_ms": self.poll_ms,
                    "ended": time.strftime("%Y-%m-%dT%H:%M:%S")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--app-exe", default=None)
    ap.add_argument("--poll-ms", type=int, default=10)
    ap.add_argument("--dump", default=None)
    ap.add_argument("--tail", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=0)
    args = ap.parse_args()

    open(args.out, "w", encoding="utf-8").close()
    mon = WindowMonitor(args.out, args.app_exe, args.poll_ms)
    mon.start()
    print(f"[winmon] started out={args.out} app_exe={args.app_exe} poll_ms={args.poll_ms}",
          flush=True)
    t0 = time.time()
    last_proc = 0.0
    try:
        while True:
            # 消费事件队列（hook 通道）
            try:
                ev = mon._q.get_nowait()
                mon._record(ev["hwnd"], ev["event"])
            except queue.Empty:
                pass
            # 周期刷新进程表兜底（250ms）
            if time.time() - last_proc > 0.25:
                mon._refresh_procs()
                last_proc = time.time()
            if args.timeout and time.time() - t0 > args.timeout:
                break
            if args.tail:
                with mon._lock:
                    if len(mon.events) >= args.tail:
                        break
            time.sleep(0.005)
    except KeyboardInterrupt:
        pass
    snap = mon.snapshot()
    if args.dump:
        with open(args.dump, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)
    print(f"[winmon] done total={snap['total_events']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
