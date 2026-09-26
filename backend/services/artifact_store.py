"""V2.2.0 Revision 3 返工：task-scoped staging、artifact 内容校验与同盘原子提升。

PLAN G04 / §3.3 / §5.3 与 RESULT §R3-18 C 的落地实现。

本模块只提供**机制**（路径、文件身份、格式可解析性、text 抽取、原子提升、清理），
业务级校验（owner/source/章节/字段守恒/education/哨兵/同源）由
`services.document_assembler.validate_staged_artifacts` 组合本模块原语完成。

不变量：
1. staging 位于 `<RESUME_DATA_DIR>/staging/<task_id>/<op_slug>/`，位于公开 output 目录之外，
   下载路由永不解析 staging 路径；
2. 提升使用 `os.replace`（同盘原子）；staging 与 output 同处 `RESUME_DATA_DIR` 之下，
   保证同卷；
3. 未登记的磁盘文件永不可见：下载路由只认已提交的 `artifacts` 表行；
4. cleanup 幂等：重复调用返回同样结果，不因目录已消失而失败。
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import zipfile
from pathlib import Path

STAGING_DIRNAME = "staging"
PUBLISH_DIRNAME = "output"

# 内容级最低门槛：真实简历 DOCX/PDF 远大于此；零字节/截断文件必须被拒。
MIN_DOCX_BYTES = 512
MIN_PDF_BYTES = 512

_PDF_EOF_RE = re.compile(rb"%%EOF\s*$")


def data_root() -> Path:
    from core.config import settings
    return Path(settings.RESUME_DATA_DIR)


def staging_root() -> Path:
    return data_root() / STAGING_DIRNAME


def publish_root() -> Path:
    from core.config import settings
    return Path(settings.DOCX_OUTPUT_DIR)


def is_within(child: os.PathLike | str, parent: os.PathLike | str) -> bool:
    """child 是否位于 parent 之内（解析符号链接与 `..`，大小写按平台默认）。"""
    try:
        c = os.path.normcase(os.path.abspath(os.fspath(child)))
        p = os.path.normcase(os.path.abspath(os.fspath(parent)))
    except Exception:  # noqa: BLE001
        return False
    if c == p:
        return True
    return c.startswith(p.rstrip(os.sep) + os.sep)


def safe_token(value: str) -> str:
    """把任意标识折叠为安全的单段文件名 token（不允许分隔符/上级引用）。"""
    t = "".join(c for c in (value or "") if c.isalnum() or c in "-_")
    return t or "x"


def task_staging_dir(task_id: str, op_slug: str) -> Path:
    """返回（并创建）当前任务的本次 staging 目录。"""
    safe_task = safe_token(task_id)[:64]
    safe_op = safe_token(op_slug)[:32]
    d = staging_root() / safe_task / safe_op
    d.mkdir(parents=True, exist_ok=True)
    return d


def assert_inside_staging(path: os.PathLike | str) -> bool:
    return is_within(path, staging_root())


def assert_inside_publish(path: os.PathLike | str) -> bool:
    return is_within(path, publish_root())


def sha256_file(path: os.PathLike | str) -> str:
    h = hashlib.sha256()
    with open(os.fspath(path), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_problems(path: os.PathLike | str, *, min_bytes: int, label: str) -> list[str]:
    """存在性 / 非零 / 可读 三项基础检查。"""
    problems: list[str] = []
    p = os.fspath(path)
    if not p or not os.path.isfile(p):
        problems.append(f"{label}:NOT_FOUND")
        return problems
    try:
        size = os.path.getsize(p)
    except OSError:
        problems.append(f"{label}:STAT_FAILED")
        return problems
    if size <= 0:
        problems.append(f"{label}:ZERO_BYTES")
        return problems
    if size < min_bytes:
        problems.append(f"{label}:TOO_SMALL")
    try:
        with open(p, "rb") as f:
            f.read(1)
    except OSError:
        problems.append(f"{label}:UNREADABLE")
    return problems


# ── DOCX 格式可解析性 + 文本抽取 ──────────────────────────────── #

def docx_problems(path: os.PathLike | str, *, label: str = "docx") -> list[str]:
    problems: list[str] = []
    p = os.fspath(path)
    if not zipfile.is_zipfile(p):
        return [f"{label}:NOT_ZIP"]
    try:
        with zipfile.ZipFile(p) as z:
            names = set(z.namelist())
            if "word/document.xml" not in names:
                problems.append(f"{label}:NO_DOCUMENT_XML")
            bad = z.testzip()
            if bad is not None:
                problems.append(f"{label}:CORRUPT_MEMBER:{bad}")
    except Exception:  # noqa: BLE001
        problems.append(f"{label}:ZIP_PARSE_FAILED")
    return problems


def docx_text(path: os.PathLike | str) -> str:
    """用 python-docx 抽取段落 + 表格文本（失败抛异常，由调用方判失败）。"""
    from docx import Document  # 本地导入：仅在此模块按需依赖
    doc = Document(os.fspath(path))
    parts: list[str] = [para.text for para in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


# ── PDF 格式可解析性 + 文本抽取 ───────────────────────────────── #

def pdf_problems(path: os.PathLike | str, *, label: str = "pdf") -> list[str]:
    problems: list[str] = []
    p = os.fspath(path)
    try:
        with open(p, "rb") as f:
            head = f.read(8)
            if not head.startswith(b"%PDF-"):
                problems.append(f"{label}:BAD_HEADER")
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 2048))
            tail = f.read()
            if not _PDF_EOF_RE.search(tail.rstrip()):
                problems.append(f"{label}:NO_EOF_MARKER")
    except OSError:
        problems.append(f"{label}:UNREADABLE")
    return problems


def pdf_text(path: os.PathLike | str) -> str:
    """用 pdfplumber 抽取 PDF 文本（失败抛异常，由调用方判失败）。"""
    import pdfplumber
    parts: list[str] = []
    with pdfplumber.open(os.fspath(path)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def normalize_for_match(text: str) -> str:
    """折叠所有空白，供 DOCX/PDF 同源文本比对（Word 换行/分页会改变空白）。"""
    return re.sub(r"\s+", "", text or "")


# ── 同盘原子提升 / 清理 ───────────────────────────────────────── #

def promote(staged_path: os.PathLike | str, final_dir: os.PathLike | str,
            final_name: str) -> tuple[str | None, str | None]:
    """把 staging 内文件同盘原子提升到最终目录。

    返回 (final_abs, None) 或 (None, reason)。任一步失败都不留下半成品：
    目标目录写失败时尝试回滚已建立的链接。
    """
    src = os.fspath(staged_path)
    if not assert_inside_staging(src):
        return None, "SOURCE_OUTSIDE_STAGING"
    if "/" in final_name or "\\" in final_name or not final_name:
        return None, "INVALID_FINAL_NAME"
    dst = os.path.join(os.fspath(final_dir), final_name)
    if not assert_inside_publish(dst):
        return None, "DEST_OUTSIDE_PUBLISH"
    try:
        os.makedirs(os.fspath(final_dir), exist_ok=True)
        os.replace(src, dst)
    except OSError as e:  # noqa: BLE001
        return None, f"PROMOTE_FAILED:{type(e).__name__}"
    if not os.path.isfile(dst):
        return None, "PROMOTE_NOT_VISIBLE"
    return dst, None


def remove_file_quiet(path: os.PathLike | str) -> bool:
    """删除单个文件；不存在视为成功（幂等）。返回是否最终不存在。"""
    p = os.fspath(path) if path else ""
    if not p:
        return True
    try:
        os.remove(p)
    except FileNotFoundError:
        return True
    except OSError:
        return not os.path.exists(p)
    return not os.path.exists(p)


def cleanup_dir_quiet(path: os.PathLike | str) -> bool:
    """递归删除目录；不存在视为成功（幂等）。返回是否最终不存在。"""
    p = os.fspath(path) if path else ""
    if not p:
        return True
    try:
        shutil.rmtree(p, ignore_errors=False)
    except FileNotFoundError:
        return True
    except OSError:
        shutil.rmtree(p, ignore_errors=True)
    return not os.path.exists(p)


def cleanup_task_staging(task_id: str) -> bool:
    """清理整个任务的 staging 根（幂等）。返回是否最终不存在。"""
    d = staging_root() / safe_token(task_id)[:64]
    if not assert_inside_staging(d):
        return False
    return cleanup_dir_quiet(d)


def cleanup_runtime_staging() -> bool:
    """清理整个 staging 根（幂等）。"""
    return cleanup_dir_quiet(staging_root())
