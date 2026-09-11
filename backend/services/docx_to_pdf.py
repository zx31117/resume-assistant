"""H8 §20.3：DOCX→PDF 本地转换编排器（父进程侧）。

产品链唯一 PDF 来源：最终 DOCX artifact（已持久化、不可变字节）→ MicrosoftWordComConverter
（Word COM，于**隔离子进程**执行）→ 校验 → 不可变 PDF artifact → PDF.js 预览/下载同字节。

父进程职责：
- 单 worker 互斥（进程内 threading.Lock：本应用单实例、并发请求共享同一锁）；
- 具名超时：子进程超时 → `taskkill /F /T` 只终止本次启动的子进程树（其自有 Word 随之退出），
  绝不触碰转换前已存在的用户 WINWORD；
- 正常/异常/超时/取消：清理子进程、临时目录与文件句柄；
- fail closed：任何失败抛 DocxToPdfError；调用方保留 DOCX、PDF 字段留空；
  禁止回退 ReportLab / LibreOffice / 旧 PDF / 空 PDF；
- 稳定 converter_id（H8 冻结，不再含 demo 命名）；
- startup capability check（Word 可创建 / 字体环境异常区分）。
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import platform
import subprocess
import sys
import threading
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)

CONVERTER_ID = "MicrosoftWordComConverter/1.0-h8"
_TIMEOUT_DEFAULT = 90.0

_lock = threading.Lock()


class DocxToPdfError(Exception):
    def __init__(self, message: str, *, code: str = "convert_failed", detail: dict | None = None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _worker_command() -> list[str]:
    if _is_frozen():
        # 冻结态：以本 exe 重新启动，launcher 顶部检测 H8_CONV_WORKER=1 后交权给 worker
        return [sys.executable]
    return [sys.executable, "-m", "services.docx_to_pdf_worker"]


def _kill_tree(pid: int) -> None:
    if os.name != "nt":
        return
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                   capture_output=True, timeout=15)


def _kill_owned_word(meta: dict) -> None:
    """超时/worker 崩溃后按 meta 记录清理由本次调用创建的 WINWORD（仅自有 PID）。"""
    pids = meta.get("word_pids") or []
    if not pids:
        return
    for pid in pids:
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=10)
        except Exception:  # noqa: BLE001
            pass


def _winword_pids() -> set[int]:
    """当前 WINWORD.EXE PID 集合。"""
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq WINWORD.EXE",
                            "/FO", "CSV"], capture_output=True, timeout=10)
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


def _cleanup_window_winword(before: set[int], *, wait_s: float = 5.0) -> None:
    """清理本转换窗口期内新出现的 WINWORD（spawn 前已存在的用户 Word 一律不动）。

    不依赖 worker meta：worker 在超时前可能尚未写 word_pids；只要 WINWORD 在
    before 快照之后出现且仍存活，即为本次调用创建，可安全按归属终止。
    """
    import time as _t
    deadline = _t.time() + wait_s
    while _t.time() < deadline:
        cur = _winword_pids()
        owned = cur - before
        if not owned:
            return
        for pid in owned:
            try:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True, timeout=10)
            except Exception:  # noqa: BLE001
                pass
        _t.sleep(0.4)
    cur = _winword_pids()
    still = cur - before
    if still:
        logger.warning("Word 清理后仍残留 %s（属本窗口自有，等其自然退出）", sorted(still))


def convert_docx_to_pdf_bytes(docx_abs: str, *, timeout_s: float = _TIMEOUT_DEFAULT) -> dict:
    """把确切 DOCX 字节转换为 PDF；返回 {pdf_bytes, fingerprint}。"""
    docx_path = Path(docx_abs)
    if not docx_path.is_file():
        raise DocxToPdfError("DOCX 不存在", code="docx_missing", detail={"path": docx_abs})
    docx_bytes = docx_path.read_bytes()
    docx_sha = hashlib.sha256(docx_bytes).hexdigest()

    acquired = _lock.acquire(timeout=timeout_s)
    if not acquired:
        raise DocxToPdfError("转换器忙（已有转换进行中）", code="busy")
    t0 = time.time()
    workdir = Path(tempfile.mkdtemp(prefix="h8_conv_"))
    out_pdf = workdir / "out.pdf"
    meta_file = workdir / "meta.json"
    env = dict(os.environ)
    env["H8_CONV_WORKER"] = "1"
    env["H8_CONV_DOCX"] = str(docx_path)
    env["H8_CONV_OUT"] = str(out_pdf)
    env["H8_CONV_META"] = str(meta_file)
    if not _is_frozen():
        # 源码态子进程需可 import services（父模块位于 backend/services/）
        _backend_dir = str(Path(__file__).resolve().parent.parent)
        env["PYTHONPATH"] = _backend_dir + (os.pathsep + env["PYTHONPATH"]
                                            if env.get("PYTHONPATH") else "")
    try:
        _before_wp = _winword_pids()  # spawn 前快照：窗口判定基准（用户已有 Word 永不触碰）
        try:
            proc = subprocess.Popen(
                _worker_command(), env=env, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as e:  # noqa: BLE001
            raise DocxToPdfError(f"无法启动转换子进程: {e}", code="spawn_failed",
                                 detail={"error": str(e)}) from e
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            meta = _read_meta(meta_file)
            _kill_tree(proc.pid)
            # 只清理由本次 worker 启动的 WINWORD：meta 优先，窗口兜底（防 meta 未及写入）
            _kill_owned_word(meta)
            _cleanup_window_winword(_before_wp)
            try:
                proc.wait(timeout=8)
            except Exception:  # noqa: BLE001
                pass
            raise DocxToPdfError(
                f"Word 转换超时（>{timeout_s}s）", code="timeout",
                detail={"docx_sha": docx_sha[:16], "owned_word_pids": meta.get("word_pids") or []})

        if proc.returncode != 0:
            meta = _read_meta(meta_file)
            # worker 异常/崩溃路径：残余自有 WINWORD 一并按归属清理
            if meta.get("word_pids"):
                _kill_owned_word(meta)
            _cleanup_window_winword(_before_wp)
            raise DocxToPdfError(
                f"Word 转换失败（worker exit={proc.returncode}）",
                code=meta.get("error") or "worker_failed",
                detail={"error": meta.get("detail"), "docx_sha": docx_sha[:16]},
            )

        meta = _read_meta(meta_file)
        if not meta.get("ok"):
            raise DocxToPdfError("Word 转换未成功",
                                 code=meta.get("error") or "convert_failed",
                                 detail={"error": meta.get("detail")})

        if not out_pdf.is_file():
            raise DocxToPdfError("输出 PDF 缺失", code="missing_output")
        pdf_bytes = out_pdf.read_bytes()
        if pdf_bytes[:5] != b"%PDF-":
            raise DocxToPdfError("PDF 文件头非法", code="bad_header")
        pages = _count_pages(pdf_bytes)
        if pages <= 0:
            raise DocxToPdfError("PDF 页数为 0", code="zero_pages")
        pdf_sha = hashlib.sha256(pdf_bytes).hexdigest()
        fingerprint = {
            "converter": CONVERTER_ID,
            "word": {"version": meta.get("word_version", ""),
                     "build": meta.get("word_build", "")},
            "os": meta.get("os", platform.platform()),
            "docx_sha256": docx_sha,
            "pdf_sha256": pdf_sha,
            "pages": pages,
            "size_bytes": len(pdf_bytes),
            "elapsed_s": round(time.time() - t0, 3),
        }
        return {"pdf_bytes": pdf_bytes, "fingerprint": fingerprint}
    finally:
        _lock.release()
        # 确定性清理：子进程已退出；仅删除本转换的临时目录
        try:
            subprocess.run(["cmd", "/c", "rd", "/s", "/q", str(workdir)],
                           capture_output=True, timeout=15)
        except Exception:  # noqa: BLE001
            pass
        try:
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)
        except Exception:  # noqa: BLE001
            pass


def _read_meta(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _count_pages(pdf_bytes: bytes) -> int:
    try:
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
        return len(doc)
    except Exception:  # noqa: BLE001
        return 0


def capability_probe(*, timeout_s: float = 60.0) -> dict:
    """启动/首次生成前转换能力检查（§20.3.7）。

    返回 {ok, word_version?, word_build?, error?, code?}；调用方据此把 PDF 能力标记不可用。
    code: word_com_unavailable / spawn_failed / com_failed / ok
    """
    out: dict = {"ok": False, "code": "unknown", "detail": {}}

    def _wpids() -> set[int]:
        try:
            r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq WINWORD.EXE",
                                "/FO", "CSV"], capture_output=True, timeout=10)
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

    try:
        import win32com.client
    except Exception as e:  # noqa: BLE001
        out.update({"code": "word_com_unavailable", "detail": {"error": str(e)}})
        return out
    before = _wpids()
    try:
        app = win32com.client.DispatchEx("Word.Application")
        try:
            app.Visible = False
            try:
                app.DisplayAlerts = 0
            except Exception:  # noqa: BLE001
                pass
            out["word_version"] = str(app.Version)
            out["word_build"] = str(app.Build)
        finally:
            try:
                app.Quit()
            except Exception:  # noqa: BLE001
                pass
        owned = _wpids() - before
        if owned:
            for pid in owned:
                try:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                   capture_output=True, timeout=10)
                except Exception:  # noqa: BLE001
                    pass
        out.update({"ok": True, "code": "ok", "converter": CONVERTER_ID})
    except Exception as e:  # noqa: BLE001
        out.update({"code": "com_failed", "detail": {"error": str(e)}})
    return out
