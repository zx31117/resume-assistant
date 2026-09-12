"""V2.1.0 R17a：第三方授权材料 + 确定性字体失败边界（开发侧断言，零 API Key）。

覆盖（RESULT §29.3 R17a 修正项 1–4 的正反向断言）：
  a) backend/templates/licenses/ 三文件存在且非空；NOTO-OFL.txt 为完整 OFL 文本
     （含 "OFL" 与 "SIL OPEN FONT LICENSE"）；PDFJS-APACHE2.txt 含 "Apache License"
     且与 frontend/node_modules/pdfjs-dist/LICENSE 字节一致（Apache 2.0 全文）；
     THIRD_PARTY_NOTICES.md 登记两第三方关键身份。
  b) 固定字体存在且 SHA-256 == d45f67f0…（与源码/包内同一份可再分发 Noto 字体）。
  c) 字体缺失/损坏（临时改名 / 写入错误字节）→ pdf_renderer 抛确定性 RuntimeError
     （fail closed），不产生 PDF、不伪造成功 —— 在独立子进程注入（进程级字体注册表
     不跨进程污染）。
  d) 产品源码（services/api/core/database/models/prompts/main.py + packaging spec）
     grep 无 simsun / 系统字体回退逻辑。
  e) docx 渲染不受字体影响：正常态与"字体缺失"态下 TemplateRenderer 均可产出真实
     docx；缺失态 PDF fail closed（模拟 generate 链 pdf_download_url=None）。

运行：python _v21_r17a_licensing.py
要求：exit 0 且末行 PASS=<N> FAIL=0。
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# ── 进程级临时数据根：必须在任何 backend import 之前设置 ──
_R17A_TMP = tempfile.mkdtemp(prefix="v21_r17a_")
os.environ["RESUME_DATA_DIR"] = _R17A_TMP

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
REPO_ROOT = BACKEND_ROOT.parent
FONT_PATH = BACKEND_ROOT / "templates" / "fonts" / "NotoSansSC-Regular.ttf"
FONT_SHA = "d45f67f0a7c0ca3f256950777ce6a61cc7ce5f9696d02900cbbaac25f8aa7d16"
LIC_DIR = BACKEND_ROOT / "templates" / "licenses"

PASS_COUNT = 0
FAILURES: list[str] = []


def _assert(cond: bool, label: str, detail: str = "") -> None:
    global PASS_COUNT
    if cond:
        PASS_COUNT += 1
        print(f"  [PASS] {label}")
    else:
        msg = f"  [FAIL] {label}" + (f" — {detail}" if detail else "")
        print(msg, file=sys.stderr)
        FAILURES.append(label)


def _section(title: str) -> None:
    print(f"\n[{title}]")


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _doc_snippet_body() -> str:
    """子进程内构造真实 fixture 文档（复用 R9 fixture：必填章节齐全，docx 可渲染）。

    注意：_v21_r9_preview_pdf 模块顶部会 mkdtemp 并重设 RESUME_DATA_DIR；只要在其后
    才 import core.config，settings 即指向该临时根，父子进程环境互不串扰。
    """
    return (
        "import _v21_r9_preview_pdf as _R9\n"
        "doc = _R9._make_resume_doc()\n"
    )


def _run_py(code: str) -> tuple[int, str]:
    """在全新子进程运行代码片段（隔离 reportlab 进程级字体注册表）。"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# ═══════════════════════════════════════════════════════════════════════════
# a) 第三方授权目录三文件 + 内容断言
# ═══════════════════════════════════════════════════════════════════════════
def test_licenses() -> None:
    _section("a) backend/templates/licenses/ 第三方授权材料")
    for name in ("NOTO-OFL.txt", "PDFJS-APACHE2.txt", "THIRD_PARTY_NOTICES.md"):
        p = LIC_DIR / name
        _assert(
            p.is_file() and p.stat().st_size > 0,
            f"授权文件存在且非空: {name}",
            f"size={p.stat().st_size if p.is_file() else 'MISSING'}",
        )
    ofl = (LIC_DIR / "NOTO-OFL.txt").read_text(encoding="utf-8")
    _assert(
        "OFL" in ofl and "SIL OPEN FONT LICENSE" in ofl and "Version 1.1" in ofl,
        "NOTO-OFL.txt 为完整 OFL 文本（含 OFL / SIL OPEN FONT LICENSE / Version 1.1）",
    )
    _assert(
        "PERMISSION & CONDITIONS" in ofl and "TERMINATION" in ofl and "DISCLAIMER" in ofl,
        "NOTO-OFL.txt 含 OFL 1.1 全结构（条款/终止/免责）",
    )
    pdfjs = (LIC_DIR / "PDFJS-APACHE2.txt").read_text(encoding="utf-8")
    _assert(
        "Apache License" in pdfjs and "Version 2.0" in pdfjs,
        "PDFJS-APACHE2.txt 含 Apache License 2.0 全文标识",
    )
    node_lic = REPO_ROOT / "frontend" / "node_modules" / "pdfjs-dist" / "LICENSE"
    _assert(
        node_lic.is_file()
        and _sha256_file(LIC_DIR / "PDFJS-APACHE2.txt") == _sha256_file(node_lic),
        "PDFJS-APACHE2.txt 与 node_modules/pdfjs-dist/LICENSE 字节一致（原样复制）",
    )
    notices = (LIC_DIR / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    _assert(
        "Noto Sans SC" in notices and "@expo-google-fonts/noto-sans-sc@0.4.3" in notices
        and "SIL Open Font License" in notices,
        "THIRD_PARTY_NOTICES.md 登记 Noto Sans SC（上游包/许可证）",
    )
    _assert(
        "pdfjs-dist@4.10.38" in notices and "Apache License 2.0" in notices,
        "THIRD_PARTY_NOTICES.md 登记 pdfjs-dist@4.10.38（Apache 2.0）",
    )
    _assert(
        FONT_SHA in notices,
        "THIRD_PARTY_NOTICES.md 记录字体 SHA-256 d45f67f0…",
    )


# ═══════════════════════════════════════════════════════════════════════════
# b) 字体存在 + SHA-256 固定指纹
# ═══════════════════════════════════════════════════════════════════════════
def test_font_fingerprint() -> None:
    _section("b) 固定 Noto 字体存在且 SHA-256 匹配")
    _assert(
        FONT_PATH.is_file() and FONT_PATH.stat().st_size == 10559284,
        "字体存在且大小 == 10,559,284 字节",
        f"size={FONT_PATH.stat().st_size if FONT_PATH.is_file() else 'MISSING'}",
    )
    _assert(
        _sha256_file(FONT_PATH) == FONT_SHA,
        "字体 SHA-256 == d45f67f0a7c0ca3f…（与 RESULT/包内同一份可再分发版本）",
    )


# ═══════════════════════════════════════════════════════════════════════════
# c) 字体缺失 / 损坏 → fail closed（独立子进程注入）
# ═══════════════════════════════════════════════════════════════════════════
def test_fail_closed_corrupt() -> None:
    _section("c1) 字体损坏（写入错误字节到模板根）→ pdf_renderer 抛确定性错误")
    fake_root = Path(tempfile.mkdtemp(prefix="r17a_corrupt_"))
    (fake_root / "templates" / "fonts").mkdir(parents=True, exist_ok=True)
    (fake_root / "templates" / "fonts" / "NotoSansSC-Regular.ttf").write_bytes(
        b"\x00BAD-FONT-BYTES-" + os.urandom(256)
    )
    code = (
        "import sys, os, tempfile\n"
        f"BK = {str(BACKEND_ROOT)!r}\n"
        f"ROOT = {str(fake_root)!r}\n"
        "sys.path.insert(0, BK)\n"
        "os.environ['RESUME_DATA_DIR'] = tempfile.mkdtemp(prefix='r17a_c1_')\n"
        + _doc_snippet_body() +
        "from services import pdf_renderer\n"
        "try:\n"
        "    pdf_renderer.render(doc, 'pm_template', ROOT, artifact_id='c1')\n"
        "    print('RAISED=False'); sys.exit(2)\n"
        "except RuntimeError as e:\n"
        "    print('RAISED=True')\n"
        "    print('HASH_MISMATCH=%s' % ('SHA-256 \u4e0d\u7b26' in str(e)))\n"
        "    sys.exit(0 if 'SHA-256 \u4e0d\u7b26' in str(e) else 3)\n"
    )
    rc, out = _run_py(code)
    _assert(
        rc == 0 and "RAISED=True" in out and "HASH_MISMATCH=True" in out,
        "损坏字体 → RuntimeError 且错误含「SHA-256 不符」（未回退、未伪造 PDF）",
        f"rc={rc} tail={out[-300:]}",
    )


def test_fail_closed_missing() -> None:
    _section("c2) 字体缺失（临时改名）+ docx 不受影响（子进程注入）")
    backup = FONT_PATH.with_name(FONT_PATH.name + ".r17abak")
    renamed = False
    try:
        os.replace(FONT_PATH, backup)
        renamed = True
        out_dir = Path(tempfile.mkdtemp(prefix="r17a_c2_"))
        code = (
            "import sys, os, tempfile\n"
            f"BK = {str(BACKEND_ROOT)!r}\n"
            f"OUT = {str(out_dir)!r}\n"
            "sys.path.insert(0, BK)\n"
            "os.environ['RESUME_DATA_DIR'] = tempfile.mkdtemp(prefix='r17a_c2_')\n"
            "from core.config import settings\n"
            + _doc_snippet_body() +
            "from services.template_renderer import TemplateRenderer\n"
            "from services import pdf_renderer\n"
            "os.makedirs(settings.DOCX_OUTPUT_DIR, exist_ok=True)\n"
            "os.makedirs(OUT, exist_ok=True)\n"
            "r = TemplateRenderer('pm_template', backend_root=BK)\n"
            "dd, _w, _s = r.render(doc)\n"
            "docx_p = os.path.join(OUT, 'e2.docx')\n"
            "dd.save(docx_p)\n"
            "docx_ok = os.path.isfile(docx_p) and os.path.getsize(docx_p) > 0\n"
            "try:\n"
            "    pdf_renderer.render(doc, 'pm_template', BK, artifact_id='c2')\n"
            "    pdf_none = False; msg = '(no exception)'\n"
            "except RuntimeError as e:\n"
            "    pdf_none = True; msg = str(e)\n"
            "print('DOCX_OK=%s' % docx_ok)\n"
            "print('PDF_FAIL_CLOSED=%s' % pdf_none)\n"
            "print('ERR_HAS_MISSING=%s' % ('\u4e0d\u5b58\u5728' in msg))\n"
            "sys.exit(0 if (docx_ok and pdf_none and '\u4e0d\u5b58\u5728' in msg) else 1)\n"
        )
        rc, out = _run_py(code)
        _assert(
            rc == 0 and "DOCX_OK=True" in out and "PDF_FAIL_CLOSED=True" in out
            and "ERR_HAS_MISSING=True" in out,
            "字体缺失 → PDF fail closed（RuntimeError 含「不存在」）且 docx 仍正常产出",
            f"rc={rc} tail={out[-300:]}",
        )
    finally:
        if renamed and backup.is_file():
            os.replace(backup, FONT_PATH)
    _assert(
        FONT_PATH.is_file() and _sha256_file(FONT_PATH) == FONT_SHA,
        "失败注入后字体已恢复原状（SHA-256 复原）",
    )


# ═══════════════════════════════════════════════════════════════════════════
# d) 源码无 simsun / 系统字体回退逻辑
# ═══════════════════════════════════════════════════════════════════════════
def test_no_system_font_fallback() -> None:
    _section("d) 产品源码无 simsun / 系统字体回退")
    product_dirs = ("services", "api", "core", "database", "models", "prompts")
    targets: list[Path] = [BACKEND_ROOT / "main.py"]
    for d in product_dirs:
        targets.extend((BACKEND_ROOT / d).rglob("*.py"))
    targets.extend(list((REPO_ROOT / "packaging").glob("*.spec")))
    pattern = re.compile(r"simsun|FONT_FALLBACK|C:/Windows/Fonts|system[_ ]font[_ ]fallback",
                         re.IGNORECASE)
    hits: list[str] = []
    for p in targets:
        if not p.is_file():
            continue
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(ln):
                hits.append(f"{p.relative_to(REPO_ROOT)}:{i}")
    _assert(not hits, "产品源码 grep 无 simsun / 系统字体回退引用", "; ".join(hits[:10]))


# ═══════════════════════════════════════════════════════════════════════════
# e) docx 渲染不受字体影响（正常态正向）
# ═══════════════════════════════════════════════════════════════════════════
def test_docx_positive() -> None:
    _section("e) docx 渲染不受字体影响（正常态正向）")
    import _v21_r9_preview_pdf as _R9
    from core.config import settings
    from services.template_renderer import TemplateRenderer
    doc = _R9._make_resume_doc()
    out = Path(settings.DOCX_OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    r = TemplateRenderer("pm_template", backend_root=str(BACKEND_ROOT))
    dd, _w, _s = r.render(doc)
    p = out / "r17a_docx_positive.docx"
    dd.save(str(p))
    _assert(p.is_file() and p.stat().st_size > 0, "正常态 docx 渲染并保存成功", str(p))


def main() -> int:
    test_licenses()
    test_font_fingerprint()
    test_fail_closed_corrupt()
    test_fail_closed_missing()
    test_no_system_font_fallback()
    test_docx_positive()

    import py_compile
    _ok = True
    try:
        py_compile.compile(str(Path(__file__).resolve()), doraise=True)
        py_compile.compile(str(BACKEND_ROOT / "services" / "pdf_renderer.py"), doraise=True)
    except py_compile.PyCompileError as e:
        _ok = False
        print(f"  py_compile 失败：{e}", file=sys.stderr)
    _assert(_ok, "r17a 脚本 + pdf_renderer py_compile 通过")

    print()
    print("=" * 64)
    print(f"V2.1.0 R17a 授权与字体失败边界：PASS={PASS_COUNT} FAIL={len(FAILURES)}")
    print("=" * 64)
    if FAILURES:
        for f in FAILURES:
            print(f"  - {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    code = main()
    print(f"PASS={PASS_COUNT} FAIL={len(FAILURES)}")
    sys.exit(code)
