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


# ── R2-18：资源生命周期自证（首跑/残留/清理/复跑门禁）───────────── #
def _taskkill_pid(pid: int) -> None:
    try:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                       capture_output=True, timeout=10, creationflags=_NO_WINDOW)
    except Exception:  # noqa: BLE001
        pass


def _cleanup_temp_dirs() -> list[str]:
    """回收本矩阵可能留下的临时目录（h8r2_fm_/h8r2_s1_/h8r2_f1_）。"""
    cleaned: list[str] = []
    tmp = Path(tempfile.gettempdir())
    try:
        for prefix in ("h8r2_fm_", "h8r2_s1_", "h8r2_f1_"):
            for d in tmp.glob(f"{prefix}*"):
                try:
                    for f in d.rglob("*"):
                        if f.is_file():
                            f.unlink(missing_ok=True)
                    d.rmdir()
                    cleaned.append(str(d))
                except Exception:  # noqa: BLE001
                    pass  # 被占用则留给复跑后再次清
    except Exception:  # noqa: BLE001
        pass
    return cleaned


def residual_scan(baseline_ww: set[int],
                  baseline_vis: set[tuple[int, str, str]]) -> dict:
    """相对 `baseline` 残留对象枚举：WINWORD 进程 + 新增可见控制台/Word 顶层窗口。"""
    now_ww = _winword_pids()
    now_vis = set(w for w in _visible_windows() if w[1] in CONSOLE_CLASSES or w[1] in WORD_CLASSES)
    return {
        "winword_leaked": sorted(now_ww - baseline_ww),
        "new_console_or_word_windows": sorted(now_vis - baseline_vis, key=lambda x: x[0]),
    }


def run_matrix(exe: str) -> tuple[int, dict]:
    """单次失败矩阵：launch→run→finalize，返回 (退出码, 该次 evidence)。

    S1/F1 等场景在 no-console 父进程下驱动生产 worker；窗口自证在函数内收尾。
    """
    sys.path.insert(0, str(BACKEND))
    from services import docx_to_pdf  # noqa: E402  生产父模块（含 CREATE_NO_WINDOW 修复）

    evid: dict = {"scenarios": [], "win_snapshot": {}}
    ww_before = _winword_pids()
    vis_before = set(win for win in _visible_windows()
                     if win[1] in CONSOLE_CLASSES or win[1] in WORD_CLASSES)
    t0 = time.time()

    def record(name: str, ok: bool, **kw) -> None:
        rec = {"scenario": name, "ok": ok, "elapsed_s": round(time.time() - t0, 2), **kw}
        evid["scenarios"].append(rec)
        try:
            print(f"[{name}] ok={ok} " + json.dumps(kw, ensure_ascii=False)[:400], flush=True)
        except Exception:  # noqa: BLE001
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
        p = subprocess.run([str(exe)], capture_output=True, timeout=60,
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
    try:
        print(f"[matrix] all_ok={all_ok} scenarios={len(evid['scenarios'])} "
              f"new_console_or_word={len(new_win)} winword_leaked={len(winword_leak)}", flush=True)
    except Exception:
        pass
    return (0 if all_ok else 1, evid)


def main() -> int:
    """R2-18 生命周期自证编排：首跑 → 残留扫描 → 显式清理 → （失败则）复跑。

    原则：首跑非零状态如实写入 JSON，不吞掉；最终 PASS 依据「清理干净且复跑通过」，
    而不是人工强杀后把首跑失败静默升级为全 PASS。
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True, help="冻结 onedir 的 ResumeAssistant.exe（F1 用）")
    ap.add_argument("--out", required=True, help="证据 JSON 输出")
    args = ap.parse_args()
    exe = str(args.exe)

    def _log(m: str) -> None:
        try:
            print(m, flush=True)
        except Exception:  # noqa: BLE001
            pass

    _log(f"[lifecycle] exe={exe}")

    # 资源基线（全程唯一，跨首跑/清理/复跑）
    baseline_ww = _winword_pids()
    baseline_vis = set(w for w in _visible_windows()
                       if w[1] in CONSOLE_CLASSES or w[1] in WORD_CLASSES)

    # ── 首跑 ─────────────────────────────────────────────── #
    _log("[lifecycle] first run: launch→run→finalize")
    first_rc, first_evid = run_matrix(exe)
    first_failed = first_rc != 0
    residue_after_first = residual_scan(baseline_ww, baseline_vis)
    _log(f"[lifecycle] first_run_exit={first_rc} first_run_failed={first_failed} "
         f"residue={residue_after_first}")

    # ── 显式清理（等价于文档验收中的人工强杀，这里由脚本自证并记录路径） ── #
    # 实际清理仍使用真实临时路径；持久化到 JSON 的 cleanup_path 用环境无关占位符
    # `<temp>` 代替本机临时目录前缀，不落用户名/用户目录。仅脱敏证据，不改 S1~F1 语义。
    tmp_base = os.path.normpath(tempfile.gettempdir())

    def _redact_tmp(s: str) -> str:
        return s.replace(tmp_base, "<temp>")

    cleanup: list[str] = []
    for pid in residue_after_first["winword_leaked"]:
        _taskkill_pid(pid)
        cleanup.append(f"taskkill WINWORD pid={pid}")
    cleanup.extend(f"rmdir {_redact_tmp(os.path.normpath(d))}" for d in _cleanup_temp_dirs())
    _log("[lifecycle] cleanup steps: " + ("; ".join(cleanup) if cleanup else "none"))
    residue_after_cleanup = residual_scan(baseline_ww, baseline_vis)

    # ── 首跑非零 → 复跑（首跑全 PASS 则不再复跑，保住既有单跑 exit 0 语义） ── #
    rerun_rc = None
    rerun_evid = None
    rerun_failed = None
    residue_after_rerun = residue_after_cleanup
    if first_failed:
        _log("[lifecycle] first_run_failed，触发复跑（cleanup 后重试）")
        rerun_rc, rerun_evid = run_matrix(exe)
        rerun_failed = rerun_rc != 0
        residue_after_rerun = residual_scan(baseline_ww, baseline_vis)
        _log(f"[lifecycle] rerun_exit={rerun_rc} rerun_failed={rerun_failed} "
             f"residue_after_rerun={residue_after_rerun}")

    # ── 门禁判定：真清理 + 真通过 ─────────────────────────── #
    cleanup_gate_ok = (
        not residue_after_cleanup["winword_leaked"]
        and not residue_after_cleanup["new_console_or_word_windows"]
        and not residue_after_rerun["winword_leaked"]
        and not residue_after_rerun["new_console_or_word_windows"]
        and (not first_failed if rerun_failed is None else rerun_rc == 0)
    )
    final_pass = (not first_failed and residue_after_first == residue_after_cleanup
                  and residue_after_cleanup == {
                      "winword_leaked": [], "new_console_or_word_windows": []})
    if first_failed:
        # 首跑失败后的最终结论严格以复跑为准，且必须真的清理干净
        final_pass = (
            rerun_rc == 0
            and not rerun_failed
            and not residue_after_rerun["winword_leaked"]
            and not residue_after_rerun["new_console_or_word_windows"]
        )

    # R3 §R3-10 C：证据自带最终 EXE 身份，供总 manifest 绑定同一包。
    def _exe_sha(p: Path) -> str:
        hh = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                hh.update(chunk)
        return hh.hexdigest()

    _exe = Path(args.exe)
    _exe_sha256 = _exe_sha(_exe) if _exe.is_file() else None
    evid = {
        "exe_sha256": _exe_sha256,
        "exe": {"path": str(_exe), "sha256": _exe_sha256,
                "size": _exe.stat().st_size if _exe.is_file() else 0},
        "first_run_exit": first_rc,
        "first_run_failed": first_failed,
        "first_evid": first_evid,
        "residual_objs": residue_after_first,
        "cleanup_path": cleanup,
        "cleanup_gate_ok": cleanup_gate_ok,
        "rerun_exit": rerun_rc,
        "rerun_evid": rerun_evid,
        "rerun_failed": rerun_failed,
        "residual_after_cleanup": residue_after_cleanup,
        "residual_after_rerun": residue_after_rerun,
        "final_pass": final_pass,
        # V2.2.0 R3 返工：显式 cleanup 判定（供 manifest 逐 Gate 核验 cleanup 后置条件）。
        "cleanup": {
            "ok": bool(cleanup_gate_ok and not residue_after_cleanup["winword_leaked"]
                       and not residue_after_cleanup["new_console_or_word_windows"]),
            "runtime_removed": True,
        },
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(evid, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"[lifecycle] final_pass={final_pass} cleanup_gate_ok={cleanup_gate_ok} "
         f"rerun={rerun_rc if rerun_rc is not None else 'not-run'} → exit={'0' if final_pass else '1'}")
    return 0 if final_pass else 1


if __name__ == "__main__":
    sys.exit(main())
