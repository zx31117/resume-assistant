"""V2.1.0 R17：下载/artifact 失败态注入验证（后端可测部分）。

零 API Key：不调 LLM/Embedding/外发请求；所有写入落在进程级临时 RESUME_DATA_DIR。
用 mini FastAPI + TestClient 走真实 download 路由（api/routes/template.py），对
失败态与安全边界做断言；真实 PDF 字节由 reportlab canvas 生成（有效单页 PDF），
产物登记走服务层 write_pdf_artifact（resume_generation_service.py）。

覆盖（对应 PLAN §15.3/§15.4 R17 后端可测项）：
  1) 缺失 artifact 文件            → download 真实 404（绝不假装成功）；
  2) 非法 / 越界 path（空、仅目录、..、穿越、绝对越界外部文件、子目录）→ 400/404，
     且不泄漏 OUTPUT_DIR 外部文件字节；
  3) 非 PDF MIME：真实 txt 按 .txt 路径 → Content-Type != application/pdf；
     文本字节伪装 .pdf 名 → 后端无内容嗅探，按扩展名如实返回（已知边界，不伪造）；
  4) 截断/损坏 PDF（有效字节截半）→ download 200 且如实返回截断字节、SHA-256 一致；
     pdfplumber/pdfminer 解析抛异常（等价 pdfjs viewer 无法解析——属前端处理域）；
  5) hash 不符（登记 sha vs 磁盘实际，文件被替换）→ 服务层登记即内容 sha；
     替换后 download 如实返回磁盘真实字节；API 无登记比对 → 记录为已知边界，不伪造。

运行：python _v21_r17_failures.py
要求：exit 0 且末行 PASS=<N> FAIL=0。
"""
from __future__ import annotations

import hashlib
import io
import os
import sys
import tempfile
import uuid
from pathlib import Path

# ── 进程级临时数据根：必须在任何 backend import 之前设置 ──
_R17_TMP_ROOT = tempfile.mkdtemp(prefix="v21_r17_")
os.environ["RESUME_DATA_DIR"] = _R17_TMP_ROOT

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

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


def _make_valid_pdf_bytes() -> bytes:
    """reportlab 生成的真实有效单页 PDF 字节。"""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.setFont("Helvetica", 12)
    c.drawString(72, 720, "V2.1.0 R17 failure injection fixture")
    c.drawString(72, 700, "line 2 for content marker")
    c.showPage()
    c.save()
    return buf.getvalue()


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.routes import template as template_route
    app = FastAPI()
    app.include_router(template_route.router, prefix="/api/template")
    return TestClient(app)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    from core.config import settings

    out_dir = settings.DOCX_OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    user_id, template_id = "r17user", "pm_template"
    pdf_bytes = _make_valid_pdf_bytes()

    _section("0) 正向控制：真实 PDF artifact 登记落盘")
    from services.resume_generation_service import write_pdf_artifact
    art_id = str(uuid.uuid4())
    meta = write_pdf_artifact(pdf_bytes, user_id, template_id, art_id)
    _assert(
        os.path.isfile(os.path.join(out_dir, meta["file_name"]))
        and meta["sha256"] == _sha(pdf_bytes)
        and meta["size_bytes"] == len(pdf_bytes),
        "write_pdf_artifact 登记落盘：文件名/SHA-256/size_bytes 如实",
    )

    _section("1) 缺失 artifact 文件 → download 真实 404")
    client = _client()
    # 从未存在的 artifact：按真实命名规则给出不存在的文件名
    r = client.get("/api/template/download", params={"path": f"output/resume_r17user_pm_template_{uuid.uuid4()}.pdf"})
    _assert(r.status_code == 404, "缺失 artifact 文件 → 404（不假装成功）", f"status={r.status_code}")
    # 已登记但磁盘文件被删除（runtime 丢文件）：同样真实 404
    del_art = str(uuid.uuid4())
    del_meta = write_pdf_artifact(pdf_bytes, user_id, template_id, del_art)
    del_path = os.path.join(out_dir, del_meta["file_name"])
    os.remove(del_path)
    r2 = client.get("/api/template/download", params={"path": f"output/{del_meta['file_name']}"})
    _assert(r2.status_code == 404, "登记后磁盘被删 → 404（文件真实缺失如实暴露）", f"status={r2.status_code}")

    _section("2) 非法 / 越界 path → 400/404（不泄漏外部文件）")
    r3 = client.get("/api/template/download", params={"path": ""})
    _assert(r3.status_code == 400, "path 为空 → 400", f"status={r3.status_code}")
    r4 = client.get("/api/template/download", params={"path": "output/"})
    _assert(r4.status_code == 400, "path 仅目录名（空文件名）→ 400", f"status={r4.status_code}")
    r5 = client.get("/api/template/download", params={"path": ".."})
    _assert(r5.status_code == 400, "path 为 '..' → 400", f"status={r5.status_code}")
    r6 = client.get("/api/template/download", params={"path": "../secret"})
    _assert(
        400 <= r6.status_code < 500,
        "穿越 path ../secret → 4xx（文件名被收敛到 OUTPUT_DIR 内 → 404）",
        f"status={r6.status_code}",
    )
    # 绝对越界：OUTPUT_DIR 外真实存在的文件（含唯一 marker），必须既非 200 也不泄漏其字节
    outside = Path(_R17_TMP_ROOT) / f"outside_secret_{uuid.uuid4().hex}.txt"
    marker = f"R17-OUTSIDE-MARKER-{uuid.uuid4().hex}"
    outside.write_text(marker, encoding="utf-8")
    r7 = client.get("/api/template/download", params={"path": str(outside).replace("\\", "/")})
    leaked = r7.status_code == 200 and marker in r7.content.decode("utf-8", "replace")
    _assert(
        not leaked and r7.status_code != 200,
        "绝对越界外部文件 → 拒绝且不泄漏字节",
        f"status={r7.status_code} leaked={leaked}",
    )
    # 子目录路径：OUTPUT_DIR 下 sub/inner 真实文件，路径带子目录 → 拒绝（单层策略）
    sub = Path(out_dir) / "sub"
    sub.mkdir(parents=True, exist_ok=True)
    inner_bytes = _make_valid_pdf_bytes()
    (sub / "inner.pdf").write_bytes(inner_bytes)
    r8 = client.get("/api/template/download", params={"path": "output/sub/inner.pdf"})
    _assert(
        r8.status_code == 404 and r8.content != inner_bytes,
        "OUTPUT_DIR 子目录文件不可经路径穿透下载 → 404（单层暴露策略）",
        f"status={r8.status_code}",
    )

    _section("3) 非 PDF MIME：txt 按 .txt 路径 → 非 application/pdf")
    txt_name = f"report_{uuid.uuid4().hex}.txt"
    txt_bytes = ("纯文本内容 R17-非PDF-MIME\n" + "x" * 64).encode("utf-8")
    (Path(out_dir) / txt_name).write_bytes(txt_bytes)
    r9 = client.get("/api/template/download", params={"path": f"output/{txt_name}"})
    ct9 = r9.headers.get("content-type", "").lower()
    _assert(
        r9.status_code == 200 and ct9 != "application/pdf" and r9.content == txt_bytes,
        "真实 txt 路径 → 非 application/pdf 且字节如实",
        f"status={r9.status_code} ct={ct9}",
    )
    # 已知边界：文本字节伪装 .pdf 名。后端无内容嗅探（按扩展名路由 MIME），
    # 如实返回字节与 application/pdf；viewer 解析失败属前端，后端不伪造校验。
    fake_pdf_name = f"fake_{uuid.uuid4().hex}.pdf"
    fake_bytes = b"%PDF-1.4 not really a pdf " + b"TEXT" * 32
    (Path(out_dir) / fake_pdf_name).write_bytes(fake_bytes)
    r10 = client.get("/api/template/download", params={"path": f"output/{fake_pdf_name}"})
    ct10 = r10.headers.get("content-type", "").lower()
    _assert(
        r10.status_code == 200 and r10.content == fake_bytes and ct10 == "application/pdf",
        "txt 字节伪装 .pdf → 后端无嗅探、按扩展名如实返回（已知边界：MIME 由 ext 判定）",
        f"status={r10.status_code} ct={ct10}",
    )

    _section("4) 截断/损坏 PDF → 下载如实返回字节；解析失败属前端 viewer")
    assert pdf_bytes.startswith(b"%PDF-"), "控制：真实 PDF 以 %PDF 头开始"
    truncated = pdf_bytes[: len(pdf_bytes) // 2]
    _assert(truncated.startswith(b"%PDF-") and len(truncated) < len(pdf_bytes),
            "控制：截断样本保留 %PDF 头但字节数减半",
            f"len={len(pdf_bytes)} -> {len(truncated)}")
    trunc_name = f"resume_r17user_pm_template_{uuid.uuid4().hex}.pdf"
    (Path(out_dir) / trunc_name).write_bytes(truncated)
    r11 = client.get("/api/template/download", params={"path": f"output/{trunc_name}"})
    _assert(
        r11.status_code == 200 and r11.content == truncated and _sha(r11.content) == _sha(truncated),
        "截断 PDF 下载 200 且字节/SHA-256 与磁盘文件一致（后端如实返回）",
        f"status={r11.status_code} len={len(r11.content)}",
    )
    # viewer 无法解析：pdfplumber/pdfminer 对该损坏字节确定性抛异常（等价 pdfjs 解析失败）。
    # 后端无完整性/登记校验，不伪造；前端 viewer 需自行处理坏文件态。
    parse_raises = False
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(truncated)) as pdf:
            _ = len(pdf.pages)
    except Exception:
        parse_raises = True
    _assert(
        parse_raises,
        "截断 PDF pdfplumber 解析抛异常（viewer 解析失败属前端，后端已如实交付字节）",
    )

    _section("5) hash 不符：登记 sha vs 磁盘实际（文件被替换）→ 已知边界")
    art_b = str(uuid.uuid4())
    bytes_a = _make_valid_pdf_bytes()
    meta_b = write_pdf_artifact(bytes_a, user_id, template_id, art_b)
    sha_registered = meta_b["sha256"]
    # 文件被替换为不同内容（模拟 artifact 磁盘被篡改/覆盖）
    bytes_replaced = b"%PDF-1.4\nreplaced-content-" + os.urandom(512)
    replaced_path = os.path.join(out_dir, meta_b["file_name"])
    with open(replaced_path, "wb") as f:
        f.write(bytes_replaced)
    r12 = client.get("/api/template/download", params={"path": f"output/{meta_b['file_name']}"})
    sha_disk = _sha(r12.content)
    _assert(
        r12.status_code == 200 and r12.content == bytes_replaced
        and sha_disk == _sha(bytes_replaced) and sha_disk != sha_registered,
        "文件被替换后 download 如实返回磁盘真实字节（API 无登记比对 → 已知边界，不伪造）",
        f"reg={sha_registered[:12]}.. disk={sha_disk[:12]}..",
    )

    _section("6) 正向控制 + 模块可 import 回归")
    r13 = client.get("/api/template/download", params={"path": f"output/{meta['file_name']}"})
    ct13 = r13.headers.get("content-type", "").lower()
    _assert(
        r13.status_code == 200 and ct13 == "application/pdf" and r13.content == pdf_bytes
        and _sha(r13.content) == meta["sha256"],
        "真实 PDF artifact 正向 download 200 + application/pdf + 字节/SHA 与登记一致",
        f"status={r13.status_code} ct={ct13}",
    )
    import py_compile
    ok = True
    try:
        py_compile.compile(str(Path(__file__).resolve()), doraise=True)
        from api.routes import template as _tr
        from services.resume_generation_service import write_pdf_artifact as _wpa
        if _tr.router is None or _wpa is None:
            raise RuntimeError("import 返回 None")
    except Exception as e:
        ok = False
        print(f"  compile/import 异常：{e!r}", file=sys.stderr)
    _assert(ok, "本脚本 py_compile + template/write_pdf_artifact import 成功")

    print()
    print("=" * 64)
    print(f"V2.1.0 R17 失败态注入：PASS={PASS_COUNT} FAIL={len(FAILURES)}")
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
