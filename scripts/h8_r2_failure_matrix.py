#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""H8-R2 §21.4 失败矩阵（PLAN §21.4 第三条）。

五类生产失败路径在**无控制台父进程**（pythonw，与冻结 onedir GUI 子系统同构）下执行，
验证：零可见控制台/Word 窗口、错误可诊断、PDF fail closed（失败抛错不产出伪 PDF）、
DOCX 输入字节不被改写（Word 可按原合同下载）、无 worker/WINWORD 泄漏。

场景：
  S1 com_missing   ：win32com.client 导入失败（Word/COM 缺失模拟）→ worker com_failed
  S2 corrupt_docx  ：损坏 DOCX → 父进程 DocxToPdfError，DOCX 字节不变
  S3 timeout       ：有效 DOCX + 极短超时 → DocxToPdfError(timeout)，taskkill /T 清理树
  S4 busy          ：并发转换 → 第二路 busy 错误；第一路正常完成
  S5 recovery      ：S2 失败后再次转换有效 DOCX → 成功产出 %PDF- 字节
  F1 frozen_worker ：冻结 exe worker 模式 + 损坏 DOCX → meta 错误（冻结路径零窗口）

窗口自证：矩阵自身为 pythonw（无控制台）。任何遗漏隐藏窗口参数的子进程都会因
无控制台父进程而分配**新可见控制台窗口**，由脚本前后枚举可见顶层窗口捕获并记为失败。
外部 winmon（--app-exe 置空）另行旁证零新增控制台/Word 窗口。

用法（无控制台执行，须用 pythonw.exe）：
  pythonw.exe scripts/h8_r2_failure_matrix.py --exe <ResumeAssistant.exe> --out <evid.json>
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from ctypes import wintypes

HERE = Path(__file__).resolve().parent          # scripts/
ROOT = HERE.parent                               # repo root
BACKEND = ROOT / "backend"

# ── 目标窗口类别（可见控制台 / conhost / Word 顶层/对话框）──
CONSOLE_CLASSES = {"ConsoleWindowClass", "PseudoConsoleWindow",
                   "CASCADIA_HOSTING_WINDOW_CLASS"}
WORD_CLASSES = {"OpusApp", "#32770"}  # #32770 为 Word/Windows 对话框类
BAD_IMAGES = {"conhost.exe", "cmd.exe", "powershell.exe", "winword.exe", "dwwin.exe"}

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# ── 可见窗口枚举（本进程自证）────────────────────────────────── #
def _visible_windows() -> list[tuple[int, str, str]]:
    user32 = ctypes.windll.user32
    buf: list[int] = []

    def _cb(hwnd, lparam):
        buf.append(int(hwnd))
        return True

    CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    cb = CB(_cb)
    user32.EnumWindows(cb, 0)
    out = []
    for hwnd in buf:
        if not user32.IsWindowVisible(hwnd):
            continue
        cls = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(hwnd, cls, 128)
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        out.append((int(hwnd), cls.value, int(pid.value)))
    return out


def _winword_pids() -> set[int]:
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq WINWORD.EXE", "/FO", "CSV"],
                           capture_output=True, timeout=10, creationflags=_NO_WINDOW)
        text = r.stdout.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return set()
    pids: set[int] = set()
    for ln in text.splitlines()[1:]:
        parts = ln.split('","')
        if len(parts) >= 2:
            try:
                pids.add(int(parts[1].strip('"')))
            except ValueError:
                continue
    return pids


def _proc_image(pid: int) -> str:
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not h:
            return ""
        try:
            b = ctypes.create_unicode_buffer(512)
            n = ctypes.windll.psapi.GetModuleFileNameExW(h, None, b, len(b))
            return os.path.basename(b.value) if n else ""
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    except Exception:  # noqa: BLE001
        return ""


def classify(wins: list[tuple[int, str, str]]) -> list[tuple[int, str, str]]:
    """仅保留可见的控制台类/Word 类窗口。"""
    out = []
    for hwnd, cls, pid in wins:
        if cls in CONSOLE_CLASSES or cls in WORD_CLASSES:
            img = _proc_image(pid)
            if cls in CONSOLE_CLASSES or img.lower() in BAD_IMAGES:
                out.append((hwnd, cls, img))
    return out


def _valid_docx() -> Path:
    p = BACKEND / "templates" / "pm_template.docx"
    if not p.is_file():
        raise SystemExit(f"模板 DOCX 缺失：{p}")
    return p


def _corrupt_docx() -> Path:
    d = Path(tempfile.mkdtemp(prefix="h8r2_fm_"))
    p = d / "corrupt.docx"
    p.write_bytes(b"this is not a real docx file " * 200)
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True, help="冻结 onedir 的 ResumeAssistant.exe（F1 用）")
    ap.add_argument("--out", required=True, help="证据 JSON 输出")
    args = ap.parse_args()

    sys.path.insert(0, str(BACKEND))
    from services import docx_to_pdf  # noqa: E402  生产父模块（含 CREATE_NO_WINDOW 修复）

    evid: dict = {"scenarios": [], "win_snapshot": {}}
    ww_before = _winword_pids()
    vis_before = set(win for win in _visible_windows() if win[1] in CONSOLE_CLASSES or win[1] in WORD_CLASSES)
    t0 = time.time()

    def record(name: str, ok: bool, **kw) -> None:
        rec = {"scenario": name, "ok": ok, "elapsed_s": round(time.time() - t0, 2), **kw}
        evid["scenarios"].append(rec)
        try:
            print(f"[{name}] ok={ok} " + json.dumps(kw, ensure_ascii=False)[:400], flush=True)
        except Exception:
            pass

    # ── S1 Word/COM 缺失（worker 级：win32com 导入失败）───────────── #
    try:
        docx = _valid_docx()
        wd = Path(tempfile.mkdtemp(prefix="h8r2_s1_"))
        out_pdf, meta = wd / "out.pdf", wd / "meta.json"
        patch = (
            "import sys\n"
            "sys.modules['win32com'] = None\n"
            "sys.modules['win32com.client'] = None\n"
            "from services.docx_to_pdf_worker import convert\n"
            "import json\n"
            f"r = convert({str(docx)!r}, {str(out_pdf)!r}, {str(meta)!r})\n"
            "json.dump(r, open(" + repr(str(meta)) + ",'w',encoding='utf-8'))\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(BACKEND)
        p = subprocess.run([sys.executable, "-c", patch], capture_output=True,
                           timeout=60, creationflags=_NO_WINDOW, env=env)
        m = {}
        if meta.is_file():
            m = json.loads(meta.read_text(encoding="utf-8"))
        ok = (m.get("error") == "com_failed" and not out_pdf.exists())
        record("S1_com_missing", ok, meta=m, worker_rc=p.returncode)
    except Exception as e:  # noqa: BLE001
        record("S1_com_missing", False, error=str(e))

    # ── S2 损坏 DOCX（父进程全链）────────────────────────────────── #
    try:
        corrupt = _corrupt_docx()
        corrupt_sha = sha256_file(corrupt)
        err = None
        try:
            docx_to_pdf.convert_docx_to_pdf_bytes(str(corrupt), timeout_s=30.0)
        except docx_to_pdf.DocxToPdfError as e:
            err = {"code": e.code, "msg": str(e)[:200]}
        unchanged = sha256_file(corrupt) == corrupt_sha
        ok = (err is not None and err["code"] in ("com_failed", "worker_failed") and unchanged)
        record("S2_corrupt_docx", ok, error=err, docx_unchanged=unchanged)
    except Exception as e:  # noqa: BLE001
        record("S2_corrupt_docx", False, error=str(e))

    # ── S3 超时（有效 DOCX + 极短超时）────────────────────────────── #
    try:
        docx = _valid_docx()
        wb = _winword_pids()
        err = None
        try:
            docx_to_pdf.convert_docx_to_pdf_bytes(str(docx), timeout_s=0.6)
        except docx_to_pdf.DocxToPdfError as e:
            err = {"code": e.code, "msg": str(e)[:200]}
        time.sleep(1.0)  # 等 taskkill 清理尘埃落定
        wa = _winword_pids()
        leak = sorted(wa - wb)
        ok = (err is not None and err["code"] == "timeout" and not leak)
        record("S3_timeout", ok, error=err, winword_leaked=leak)
    except Exception as e:  # noqa: BLE001
        record("S3_timeout", False, error=str(e))

    # ── S4 并发 busy ──────────────────────────────────────────────── #
    try:
        docx = _valid_docx()
        res: dict = {}

        def _slow():
            try:
                r = docx_to_pdf.convert_docx_to_pdf_bytes(str(docx), timeout_s=60.0)
                res["a"] = {"ok": True, "pdf_header": r["pdf_bytes"][:5].decode("latin1")}
            except Exception as e:  # noqa: BLE001
                res["a"] = {"ok": False, "error": str(e)[:120]}

        th = threading.Thread(target=_slow, daemon=True)
        th.start()
        time.sleep(0.2)  # 确保 A 已持锁（worker 已 spawn，转换进行中）
        err = None
        try:
            docx_to_pdf.convert_docx_to_pdf_bytes(str(docx), timeout_s=0.05)
        except docx_to_pdf.DocxToPdfError as e:
            err = {"code": e.code, "msg": str(e)[:200]}
        th.join(timeout=90)
        ok = (err is not None and err["code"] == "busy"
              and res.get("a", {}).get("pdf_header") == "%PDF-")
        record("S4_busy", ok, second_error=err, first_result=res.get("a"))
    except Exception as e:  # noqa: BLE001
        record("S4_busy", False, error=str(e))

    # ── S5 恢复后再生成（S2 失败后立即成功）────────────────────────── #
    try:
        docx = _valid_docx()
        r = docx_to_pdf.convert_docx_to_pdf_bytes(str(docx), timeout_s=90.0)
        pdf_sha = r["fingerprint"]["pdf_sha256"]
        ok = (r["pdf_bytes"][:5] == b"%PDF-" and r["fingerprint"]["pages"] > 0)
        record("S5_recovery", ok, pdf_sha=pdf_sha[:16], pages=r["fingerprint"]["pages"])
    except Exception as e:  # noqa: BLE001
        record("S5_recovery", False, error=str(e))

    # ── F1 冻结 worker + 损坏 DOCX（冻结 exe 路径）────────────────── #
    try:
        corrupt = _corrupt_docx()
        wd = Path(tempfile.mkdtemp(prefix="h8r2_f1_"))
        out_pdf, meta = wd / "out.pdf", wd / "meta.json"
        env = dict(os.environ)
        env["H8_CONV_WORKER"] = "1"
        env["H8_CONV_DOCX"] = str(corrupt)
        env["H8_CONV_OUT"] = str(out_pdf)
        env["H8_CONV_META"] = str(meta)
        p = subprocess.run([str(args.exe)], capture_output=True, timeout=60,
                           creationflags=_NO_WINDOW, env=env)
        m = {}
        if meta.is_file():
            m = json.loads(meta.read_text(encoding="utf-8"))
        ok = (not m.get("ok") and bool(m.get("error")) and not out_pdf.exists())
        record("F1_frozen_worker_corrupt", ok, meta_error=m.get("error"),
               worker_rc=p.returncode)
    except Exception as e:  # noqa: BLE001
        record("F1_frozen_worker_corrupt", False, error=str(e))

    # ── 窗口自证 ──────────────────────────────────────────────────── #
    time.sleep(0.5)
    ww_after = _winword_pids()
    vis_after = set(win for win in _visible_windows() if win[1] in CONSOLE_CLASSES or win[1] in WORD_CLASSES)
    new_win = sorted(vis_after - vis_before, key=lambda x: x[0])
    winword_leak = sorted(ww_after - ww_before)
    evid["win_snapshot"] = {
        "visible_console_or_word_before": sorted(vis_before),
        "visible_console_or_word_after": sorted(vis_after),
        "new_console_or_word_windows": new_win,
        "winword_before": sorted(ww_before),
        "winword_after": sorted(ww_after),
        "winword_leaked": winword_leak,
    }
    all_ok = all(s["ok"] for s in evid["scenarios"]) and not new_win and not winword_leak
    evid["all_ok"] = all_ok
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(evid, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        print(f"[matrix] all_ok={all_ok} scenarios={len(evid['scenarios'])} "
              f"new_console_or_word={len(new_win)} winword_leaked={len(winword_leak)}", flush=True)
    except Exception:
        pass
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
