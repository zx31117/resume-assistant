"""H8 §20.3：Word COM 转换 worker（在隔离子进程中执行，可被父进程强超时终止）。

父进程 docx_to_pdf.convert_docx_to_pdf_bytes 以子进程方式启动本模块：
- 源码态：python -m services.docx_to_pdf_worker
- 冻结态：launcher 检测 H8_CONV_WORKER=1 后直接把控制权交给本模块 main()
协议（全部走环境变量，避免 windowed exe argv 丢失）：
  H8_CONV_DOCX  输入 DOCX 绝对路径（只读，绝不改写）
  H8_CONV_OUT   输出 PDF 临时文件（worker 先写临时文件校验后再原子落位）
  H8_CONV_META  输出 meta JSON：{ok, word_version, word_build, os, converter_id}
约定：worker 只触碰本次 DispatchEx 创建的 Word 实例；异常/成功路径都 Quit+释放 COM；
父进程超时以 taskkill /T 终止本进程树 → 该 Word 实例随进程结束，不伤用户 Word。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

CONVERTER_ID = "MicrosoftWordComConverter/1.0-h8"
WD_EXPORT_FORMAT_PDF = 17
MSO_AUTOMATION_SECURITY_FORCE_DISABLE = 3


def _winword_pids() -> set[int]:
    """当前系统里 WINWORD.EXE 的 PID 集合（用于识别本次 DispatchEx 自建的 Word）。"""
    import subprocess
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq WINWORD.EXE", "/FO", "CSV"],
                           capture_output=True, timeout=10)
        out = r.stdout.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return set()
    pids: set[int] = set()
    for ln in out.splitlines()[1:]:
        # CSV: "WINWORD.EXE","1234","Console","1",".."
        parts = ln.split('","')
        if len(parts) >= 2:
            try:
                pids.add(int(parts[1].strip('"')))
            except ValueError:
                continue
    return pids


def _kill_owned_winword(pids: list[int]) -> None:
    """只终止本次调用创建并确认归属的 WINWORD（仍以 WINWORD.EXE 存在才杀，防 PID 复用误伤）。"""
    import subprocess
    import time
    if not pids:
        return
    alive = _winword_pids()
    for pid in pids:
        if pid in alive:
            try:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True, timeout=10)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.2)


def _count_pages(pdf_bytes: bytes) -> int:
    import io
    import pypdfium2 as pdfium
    try:
        doc = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
        return len(doc)
    except Exception:  # noqa: BLE001
        return 0


def convert(docx_abs: str, out_pdf_abs: str, meta_abs: str = "") -> dict:
    import platform
    import time
    import uuid

    t0 = time.time()
    docx_path = Path(docx_abs)
    if not docx_path.is_file():
        return {"ok": False, "error": "docx_missing", "detail": docx_abs}
    tmp_out = Path(os.environ.get("TEMP", ".")) / f"h8_conv_{uuid.uuid4().hex}.pdf"
    result: dict = {"ok": False, "error": "", "detail": "", "word_version": "",
                    "word_build": "", "os": platform.platform(), "elapsed_s": 0.0,
                    "word_pids": []}
    _co = None

    def _partial_meta() -> None:
        if meta_abs:
            try:
                Path(meta_abs).write_text(json.dumps(result, ensure_ascii=False),
                                          encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass

    owned_pids: list[int] = []
    try:
        try:
            import pythoncom
            _co = pythoncom.CoInitialize()
        except Exception:  # noqa: BLE001
            _co = None
        import win32com.client
        before = _winword_pids()
        app = win32com.client.DispatchEx("Word.Application")
        # DispatchEx 返回后 Word 进程可能仍在拉起：轮询识别本次自建的 WINWORD PID，
        # 立刻写入 meta —— 父进程超时强杀时可据此只终止自有 Word（不伤用户 Word）。
        for _ in range(30):
            owned_pids = sorted(_winword_pids() - before)
            if owned_pids:
                break
            time.sleep(0.1)
        if not owned_pids:
            owned_pids = sorted(_winword_pids() - before)
        result["word_pids"] = owned_pids
        _partial_meta()
        try:
            app.Visible = False
            try:
                app.DisplayAlerts = 0
            except Exception:  # noqa: BLE001
                pass
            try:
                app.AutomationSecurity = MSO_AUTOMATION_SECURITY_FORCE_DISABLE
            except Exception:  # noqa: BLE001
                pass
            try:
                app.Options.UpdateLinksAtOpen = False
            except Exception:  # noqa: BLE001
                pass
            try:
                result["word_version"] = str(app.Version)
                result["word_build"] = str(app.Build)
            except Exception:  # noqa: BLE001
                pass
            doc = app.Documents.Open(str(docx_path), ReadOnly=True, AddToRecentFiles=False,
                                     Visible=False, ConfirmConversions=False)
            try:
                doc.ExportAsFixedFormat(str(tmp_out), WD_EXPORT_FORMAT_PDF)
            finally:
                try:
                    doc.Close(False)
                except Exception:  # noqa: BLE001
                    pass
        finally:
            try:
                app.Quit()
            except Exception:  # noqa: BLE001
                pass
        # Quit 后等待自有 WINWORD 退出；仍残留（Quit 异步/异常）则按归属清理
        for _ in range(40):
            if not (_winword_pids() & set(owned_pids)):
                break
            time.sleep(0.15)
        if _winword_pids() & set(owned_pids):
            _kill_owned_winword(owned_pids)
        result["word_pids"] = []
        if not tmp_out.is_file() or tmp_out.stat().st_size <= 0:
            result["error"] = "empty_output"
            return result
        pdf_bytes = tmp_out.read_bytes()
        if pdf_bytes[:5] != b"%PDF-":
            result["error"] = "bad_header"
            return result
        pages = _count_pages(pdf_bytes)
        if pages <= 0:
            result["error"] = "zero_pages"
            return result
        # 原子落位到父进程指定文件
        out_path = Path(out_pdf_abs)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_final = out_path.with_suffix(out_path.suffix + ".part")
        tmp_final.write_bytes(pdf_bytes)
        tmp_final.replace(out_path)
        result.update({"ok": True, "pages": pages,
                       "size_bytes": len(pdf_bytes),
                       "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
                       "elapsed_s": round(time.time() - t0, 3)})
        return result
    except Exception as e:  # noqa: BLE001
        result.update({"error": "com_failed", "detail": f"{type(e).__name__}: {e}"})
        return result
    finally:
        try:
            tmp_out.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
        if _co is not None:
            try:
                import pythoncom
                if _co == 0:
                    pythoncom.CoUninitialize()
            except Exception:  # noqa: BLE001
                pass


def main() -> int:
    docx = os.environ.get("H8_CONV_DOCX", "")
    out = os.environ.get("H8_CONV_OUT", "")
    meta = os.environ.get("H8_CONV_META", "")
    if not docx or not out or not meta:
        return 3
    result = convert(docx, out, meta_abs=meta)
    result["converter_id"] = CONVERTER_ID
    try:
        Path(meta).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
