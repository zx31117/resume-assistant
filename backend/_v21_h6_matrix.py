"""V2.1.0 H6（PLAN §18.2.5 / T12-R28）：确定性专项矩阵统一入口（零 Key、不依赖 GUI）。

干净 checkout 下：  python backend/_v21_h6_matrix.py
要求：exit 0 且末行 PASS=<N> FAIL=0（precheck 的 H6 阻断步骤以精确计数正则校验）。

覆盖（全部为无需浏览器人工判断的确定性断言，浏览器半自动矩阵由 R29 单独执行）：
  1) fixture 生成：PDF（reportlab invariant，两页）与 DOCX（确定性重打包）两次生成
     SHA-256 稳定，且与 backend/h6_fixtures/fixture_hashes.json 冻结值一致（跨进程可复现）；
     PDF/DOCX 文本含虚构姓名/经历；PDF 恰好 2 页、页面内可解析。
  2) PreviewAnchor 与冻结 fixture 一致：坐标/页码/文本/空非空 fact_refs 与
     preview_anchors.json 全等（结构 + 几何容差 0.02pt）；越界/不编造等语义断言。
  3) artifact 身份不可变/更换：同 run_no 两次 POST → 新 pdf_artifact_id/operation_id，
     但成品字节 SHA-256 稳定、下载一致；run_no 递增 → 新 file_name/pdf_artifact_id
     （旧 artifact 保持可下载、内容不漂移）。
  4) 失败路径诚实：pdf broken/html/missing、未知文件/路径穿越 4xx、fail_generate=500
     域错误、pdf_gen=none 不带 pdf_* 字段、anchors=empty/mismatch 语义。
  5) POST 幂等计数：仅 generate-docx 计数；GET 状态/模板/轮询/下载/计数本身都不计数；
     直接调用 stub 逻辑层 record_generate_post 与 HTTP POST 共用同一计数存储。

安全审计：扫描本次 H6 新增资产的文本（fixture JSON/TXT + gen/stub/matrix），断言不含
真实用户 PII、真实路径、Key 形态或本机绝对路径。

隔离：进程级临时 RESUME_DATA_DIR + H6_STUB_RUNTIME_DIR（默认 runtime 零改动，F3 哨兵兼容）。
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

# ── 进程级隔离：必须在任何 backend import 之前设置 ──
_H6_TMP = tempfile.mkdtemp(prefix="v21_h6_")
os.environ["RESUME_DATA_DIR"] = _H6_TMP
os.environ["H6_STUB_RUNTIME_DIR"] = os.path.join(_H6_TMP, "stub_runtime")

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
H6_FIXTURES = BACKEND_ROOT / "h6_fixtures"

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


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _norm(s: str) -> str:
    return "".join(s.split())


# 惰性引用（stub 需在环境变量设好后 import）
_STUB = None


def _stub():
    global _STUB
    if _STUB is None:
        import _v21_h6_stub as s
        _STUB = s
    return _STUB


_GEN = None


def _gen():
    global _GEN
    if _GEN is None:
        from h6_fixtures import gen_fixtures as g
        _GEN = g
    return _GEN


def _frozen(name: str) -> dict:
    return json.loads((H6_FIXTURES / name).read_text(encoding="utf-8"))


def _pdf_pages(pdf_bytes: bytes) -> int:
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return len(pdf.pages)


def _pdf_text(pdf_bytes: bytes) -> str:
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join((pg.extract_text() or "") for pg in pdf.pages)


def _docx_paragraphs(docx_bytes: bytes) -> list[str]:
    import docx as docx_mod
    doc = docx_mod.Document(io.BytesIO(docx_bytes))
    return [p.text for p in doc.paragraphs if (p.text or "").strip()]


# ═══════════════════════════════════════════════════════════════════════════
def test_fixture_determinism() -> None:
    _section("1) fixture 生成确定性：PDF 两页/DOCX 与冻结 hash 一致")
    g = _gen()
    doc = g.load_resume_doc()
    hashes = _frozen("fixture_hashes.json")
    refs = doc.get("bullet_fact_refs") or {}

    pdf1, anchors1 = g.build_fixture_pdf(artifact_id="ARTIFACT_ID_H6", bullet_fact_refs=refs)
    pdf2, anchors2 = g.build_fixture_pdf(artifact_id="ARTIFACT_ID_H6", bullet_fact_refs=refs)
    _assert(_sha(pdf1) == _sha(pdf2), "PDF 两次独立生成 SHA-256 一致（reportlab invariant）")
    _assert(
        _sha(pdf1) == hashes["pdf"]["sha256"] and len(pdf1) == hashes["pdf"]["size_bytes"],
        "PDF 与 fixture_hashes.json 冻结 SHA-256/size 一致（跨进程可复现）",
        f"{_sha(pdf1)[:16]}…",
    )
    _assert(_pdf_pages(pdf1) == 2, "fixture PDF 恰好 2 页（page_index 0/1 均有锚点）")
    _assert(pdf1.startswith(b"%PDF-"), "fixture PDF 以 %PDF 头开始")

    docx1 = g.build_fixture_docx()
    docx2 = g.build_fixture_docx()
    _assert(_sha(docx1) == _sha(docx2), "DOCX 两次独立生成 SHA-256 一致（确定性重打包）")
    _assert(
        _sha(docx1) == hashes["docx"]["sha256"] and len(docx1) == hashes["docx"]["size_bytes"],
        "DOCX 与 fixture_hashes.json 冻结 SHA-256/size 一致（跨进程可复现）",
        f"{_sha(docx1)[:16]}…",
    )

    prof = doc.get("profile") or {}
    pdf_n = _norm(_pdf_text(pdf1))
    _assert(_norm(prof.get("name") or "") in pdf_n, "PDF 文本含虚构姓名（内容可解析）")
    docx_paras = _docx_paragraphs(docx1)
    docx_n = _norm(" ".join(docx_paras))
    _assert(_norm(prof.get("name") or "") in docx_n, "DOCX 段落含虚构姓名")
    # 每一条 work/project bullet 必须同时出现在 docx 与 PDF（内容一致性，锚点文本即源）
    all_bullets = []
    for key in ("work", "projects"):
        for it in doc.get(key) or []:
            all_bullets.extend(b.strip() for b in (it.get("bullets") or []) if b.strip())
    _assert(
        all(_norm(b) in docx_n for b in all_bullets)
        and all(_norm(b) in pdf_n for b in all_bullets),
        "全部 work/project bullet 文本在 DOCX 与 PDF 中逐条可提取",
    )


# ═══════════════════════════════════════════════════════════════════════════
def test_anchors_consistency() -> None:
    _section("2) PreviewAnchor 与冻结 fixture 一致（含空/非空 fact_refs、越界、不编造）")
    g = _gen()
    doc = g.load_resume_doc()
    frozen = _frozen("preview_anchors.json")
    frozen_anchors = frozen["anchors"]
    pdf_bytes, anchors = g.build_fixture_pdf(
        artifact_id="ARTIFACT_ID_H6", bullet_fact_refs=doc.get("bullet_fact_refs") or {},
    )

    _assert(len(anchors) == len(frozen_anchors) == 12,
            "锚点数量与冻结数据集一致（12 条）", f"got={len(anchors)} frozen={len(frozen_anchors)}")

    pdf_text_n = _norm(_pdf_text(pdf_bytes))
    structural_ok = True
    geo_ok = True
    detail = ""
    for i, (a, fa) in enumerate(zip(anchors, frozen_anchors)):
        # 结构：除坐标外的所有字段逐一相等
        for k in ("artifact_id", "page_index", "content_item_id", "bullet_index", "text", "fact_refs"):
            if a.get(k) != fa.get(k):
                structural_ok = False
                detail = f"anchor[{i}] 字段 {k} 不符：{a.get(k)!r} vs {fa.get(k)!r}"
                break
        if not structural_ok:
            break
        # 几何：冻结坐标与再生成坐标一致（确定性容差 0.02pt）
        if abs(a["x0"] - fa["x0"]) > 0.02 or abs(a["y0"] - fa["y0"]) > 0.02 \
                or abs(a["x1"] - fa["x1"]) > 0.02 or abs(a["y1"] - fa["y1"]) > 0.02:
            geo_ok = False
            detail = f"anchor[{i}] 几何漂移：{a} vs {fa}"
            break
        # 页内：A4 范围、x0<x1、y0<y1（越界即前端 fail closed，断言数据集本身不越界）
        if not (0.0 <= a["x0"] < a["x1"] <= 595.28 and 0.0 <= a["y0"] < a["y1"] <= 842.0):
            geo_ok = False
            detail = f"anchor[{i}] 越出 A4 页内：{a}"
            break
        # 锚点文本在 PDF 文本中可提取（不编造不可见内容）
        if not (_norm(a["text"]) in pdf_text_n):
            structural_ok = False
            detail = f"anchor[{i}] text 不在 PDF 文本中"
            break
    _assert(structural_ok, "锚点结构（身份/页码/内容项/bullet 序/文本/refs）与冻结数据一致", detail)
    _assert(geo_ok, "锚点坐标与冻结数据一致且在 A4 页内（x/y 顺序合法）", detail)

    # 多 section 覆盖：education/work/project/skills 的 content_item_id 都出现
    seen_cids = {a["content_item_id"] for a in anchors}
    _assert(
        {"h6-edu-1", "h6-work-1", "h6-work-2", "h6-proj-1", "h6-proj-2", "skills:0", "skills:1"}
        <= seen_cids,
        "锚点覆盖多 section（education/work/project/skills 各条目均有可点内容行）",
        f"{sorted(seen_cids)}",
    )
    pages = {a["page_index"] for a in anchors}
    _assert(pages == {0, 1}, "锚点分布在两页（page_index ∈ {0,1}）", f"{pages}")

    # 空/非空 fact_refs 语义：与 resume_doc.bullet_fact_refs 逐条对应（无映射/空不编造）
    ref_map = doc.get("bullet_fact_refs") or {}
    ref_ok = True
    ref_detail = ""
    for a in anchors:
        cid = a["content_item_id"]
        if cid not in ref_map:
            # 教育 description/gpa、skills、无映射 → 恒空
            if a["fact_refs"] != []:
                ref_ok = False
                ref_detail = f"{cid} 无映射却有 refs: {a['fact_refs']}"
                break
            continue
        expect = ref_map[cid][a["bullet_index"]] if a["bullet_index"] < len(ref_map[cid]) else []
        if list(a["fact_refs"]) != list(expect):
            ref_ok = False
            ref_detail = f"{cid}[{a['bullet_index']}] refs {a['fact_refs']} != {expect}"
            break
    _assert(ref_ok, "fact_refs 逐条与 fixture bullet_fact_refs 对应（无映射一律空，不编造）", ref_detail)
    _assert(
        any(a["fact_refs"] for a in anchors) and any(not a["fact_refs"] for a in anchors),
        "数据集同时含非空与空的 fact_refs（多状态覆盖）",
    )


# ═══════════════════════════════════════════════════════════════════════════
def test_stub_logic_layer() -> None:
    _section("3) stub 逻辑层：PDF/DOCX 下载正反向 + artifact 身份 + PDF 元数据如实")
    s = _stub()
    s.reset_mode_override()
    s.set_mode_override({"delay_ms": 0, "pdf_mode": "good", "anchors": "full", "run_no": 1})

    # 纯逻辑层：生成 PDF 字节与下载字节一致（fixture PDF）
    pdf_fix = s.fixture_pdf()
    docx_fix = s.fixture_docx()
    _assert(pdf_fix.startswith(b"%PDF-") and _pdf_pages(pdf_fix) == 2,
            "stub fixture PDF 有效且两页")
    _assert(s.fixture_anchor_template()[0]["artifact_id"] == "ARTIFACT_ID_H6",
            "fixture 锚点模板使用可替换 token")

    # generate 响应元数据如实（hash/size 不再用占位假值）
    op1 = "op-00000000000000000001"
    resp = s._build_generate_response(op1)
    _assert(resp["pdf_sha256"] == _sha(pdf_fix), "响应 pdf_sha256 与成品字节 SHA-256 一致（如实）")
    _assert(resp["pdf_size_bytes"] == len(pdf_fix), "响应 pdf_size_bytes == 成品字节数")
    _assert(resp["pdf_artifact_id"] == f"artifact_1_{op1[:8]}", "artifact id 由 run_no+op 构成")
    _assert(resp["pdf_file_name"] == "resume_1.pdf", "file_name 绑定 run_no")
    _assert(all(a["artifact_id"] == resp["pdf_artifact_id"] for a in resp["pdf_anchors"]),
            "full 模式 anchors.artifact_id == pdf_artifact_id（身份绑定）")
    _assert(resp["ok"] is True and resp["operation_id"] == op1, "成功响应结构正确")

    # artifact 更换：run_no 2 → 新 file_name/artifact，旧 artifact 内容仍稳定可下载
    s.set_mode_override({"delay_ms": 0, "pdf_mode": "good", "anchors": "full", "run_no": 2})
    resp2 = s._build_generate_response("op-00000000000000000002")
    _assert(resp2["pdf_file_name"] == "resume_2.pdf"
            and resp2["pdf_artifact_id"].startswith("artifact_2_")
            and resp2["pdf_artifact_id"] != resp["pdf_artifact_id"],
            "run_no 递增 → 新 file_name/pdf_artifact_id（artifact 更换）",
            f"{resp['pdf_artifact_id']} -> {resp2['pdf_artifact_id']}")
    _assert(resp2["pdf_sha256"] == resp["pdf_sha256"] == _sha(pdf_fix),
            "更换 artifact 后成品内容 SHA-256 稳定（确定性）")

    # 幂等身份：同 run_no 两次生成 → 不同 artifact/op（每次 POST 独立身份），文件名语义不变
    r_a = s._build_generate_response("op-aaaaaaaaaaaaaaaaaaaa")
    r_b = s._build_generate_response("op-bbbbbbbbbbbbbbbbbbbb")
    _assert(r_a["pdf_artifact_id"] != r_b["pdf_artifact_id"]
            and r_a["pdf_file_name"] == r_b["pdf_file_name"],
            "同 run_no 两次生成：artifact/op 独立、文件名规则稳定")


# ═══════════════════════════════════════════════════════════════════════════
def test_http_matrix() -> None:
    _section("4) stub ASGI：生成/下载/失败路径诚实 + POST 计数语义")
    s = _stub()
    from fastapi.testclient import TestClient
    client = TestClient(s.app)

    # 4.1 计数：干净起点（本进程首次 POST 前）
    def cnt() -> int:
        return client.get("/__stub/count").json()["count"]

    base = cnt()
    _assert(base >= 0, "计数接口可读（当前运行态累计基数非负）")
    for _path in ("/api/system/status", "/api/template/list",
                  f"/api/system/operations/{uuid.uuid4().hex}"):
        r = client.get(_path)
        _assert(r.status_code == 200, f"GET {_path.split('?')[0]} 200（不计数）")
    _assert(cnt() == base, "GET 状态/模板/轮询均不产生 POST 计数", f"base={base} now={cnt()}")

    # 4.2 正向生成 + 下载 + 幂等成功
    s.set_mode_override({"delay_ms": 0, "pdf_mode": "good", "anchors": "full", "run_no": 1})
    r = client.post("/api/resume/generate-docx", json={"profile": {"name": "何小北"}})
    _assert(r.status_code == 200 and r.json()["ok"] is True, "generate-docx 正向 200 ok")
    gen = r.json()
    dl = client.get("/api/template/download", params={"path": f"output/{gen['pdf_file_name']}"})
    ct = dl.headers.get("content-type", "").lower()
    _assert(dl.status_code == 200 and ct == "application/pdf"
            and dl.content == s.fixture_pdf(),
            "PDF 下载 200 + application/pdf + 字节与 fixture 一致")
    _assert(_sha(dl.content) == gen["pdf_sha256"], "下载字节 SHA-256 与响应记录一致")
    dlw = client.get("/api/template/download", params={"path": f"output/{gen['file_name']}"})
    _assert(dlw.status_code == 200
            and "wordprocessingml" in dlw.headers.get("content-type", "").lower()
            and dlw.content == s.fixture_docx(),
            "DOCX 下载 200 + wordprocessingml MIME + 字节一致")
    _assert(cnt() == base + 1, "正向 generate POST 恰好 +1 计数")

    # 4.3 同 run_no 再生成：仅计 +1；下载字节稳定
    r2 = client.post("/api/resume/generate-docx", json={})
    gen2 = r2.json()
    _assert(r2.status_code == 200 and gen2["pdf_artifact_id"] != gen["pdf_artifact_id"]
            and gen2["pdf_file_name"] == gen["pdf_file_name"],
            "再次生成 → 新 artifact 身份、同文件名规则（服务端不因轮询/下载重复生成）")
    _assert(cnt() == base + 2, "再次 POST 恰好 +1 计数")

    # 4.4 fail_generate：500 域错误，且尝试如实计数
    s.set_mode_override({"delay_ms": 0, "fail_generate": True})
    rf = client.post("/api/resume/generate-docx", json={})
    body = rf.json()
    _assert(rf.status_code == 500 and body.get("ok") is False
            and body.get("error_code") == "RESUME_GENERATION_FAILED"
            and body.get("retryable") is True,
            "fail_generate → 真实 500 域错误（不假装成功）")
    _assert(cnt() == base + 3, "失败 POST 尝试也如实计入（诚实计数）")

    # 4.5 pdf_gen=none：不带任何 pdf_* 字段（PDF URL 空场景诚实）
    s.set_mode_override({"delay_ms": 0, "fail_generate": False, "pdf_gen": "none", "run_no": 3})
    rn = client.post("/api/resume/generate-docx", json={}).json()
    _assert(all(k not in rn for k in (
        "pdf_file_name", "pdf_download_url", "pdf_artifact_id",
        "pdf_sha256", "pdf_size_bytes", "pdf_anchors")),
        "pdf_gen=none → 成功响应不带任何 pdf_* 字段（前端显示 PDF 未生成，无假字段）")

    # 4.6 anchors=empty / mismatch
    s.set_mode_override({"delay_ms": 0, "anchors": "empty", "run_no": 3})
    rem = client.post("/api/resume/generate-docx", json={}).json()
    _assert(rem["pdf_anchors"] == [], "anchors=empty → pdf_anchors == []（无命中层可点区）")
    s.set_mode_override({"delay_ms": 0, "anchors": "mismatch", "run_no": 3})
    rmm = client.post("/api/resume/generate-docx", json={}).json()
    _assert(
        all(a["artifact_id"] != rmm["pdf_artifact_id"] for a in rmm["pdf_anchors"]),
        "anchors=mismatch → anchors.artifact_id != pdf_artifact_id（前端 fail closed 丢弃）",
    )

    # 4.7 PDF 失败路径：broken / html / missing
    pdf_name = "resume_3.pdf"
    s.set_mode_override({"delay_ms": 0, "pdf_mode": "broken"})
    rb = client.get("/api/template/download", params={"path": f"output/{pdf_name}"})
    _assert(rb.status_code == 200 and rb.content.startswith(b"%PDF-")
            and _sha(rb.content) != _sha(s.fixture_pdf()),
            "pdf_mode=broken → 200 且字节损坏（与 fixture 哈希不同，viewer 解析失败属前端）")
    parse_raises = False
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(rb.content)) as pdf:
            _ = len(pdf.pages)
    except Exception:
        parse_raises = True
    _assert(parse_raises, "broken PDF 字节确定性不可解析（等价 pdfjs 解析失败输入）")
    s.set_mode_override({"delay_ms": 0, "pdf_mode": "html"})
    rh = client.get("/api/template/download", params={"path": f"output/{pdf_name}"})
    _assert(rh.status_code == 200
            and rh.headers.get("content-type", "").lower().startswith("text/html"),
            "pdf_mode=html → 200 且 Content-Type 为 text/html（非 application/pdf，诚实暴露）")
    s.set_mode_override({"delay_ms": 0, "pdf_mode": "missing"})
    rm = client.get("/api/template/download", params={"path": f"output/{pdf_name}"})
    _assert(rm.status_code == 404, "pdf_mode=missing → 真实 404（绝不假装成功）")

    # 4.8 未知文件 / 路径穿越 / 绝对路径越界 → 4xx（不泄漏 fixture 之外的字节）
    s.set_mode_override({"delay_ms": 0, "pdf_mode": "good"})
    for bad in ("output/not_exist_resume.pdf", "not_resume_1.pdf", "../secret",
                "C:/Windows/win.ini", "/etc/passwd", "output/../mode.json"):
        rb_ = client.get("/api/template/download", params={"path": bad})
        _assert(400 <= rb_.status_code < 500,
                f"非法/越界 path → 4xx（{bad!r}）", f"status={rb_.status_code}")
    _assert(cnt() == base + 6, "全部下载/失败路径均不产生 POST 计数（最终校验）")


def test_logic_layer_count() -> None:
    _section("5) POST 幂等计数：逻辑层与 HTTP 共用同一计数存储")
    s = _stub()
    from fastapi.testclient import TestClient
    client = TestClient(s.app)

    before = client.get("/__stub/count").json()["count"]
    op = str(uuid.uuid4())
    n = s.record_generate_post(op, {"mode": "direct-logic"})
    _assert(n == before + 1, "逻辑层 record_generate_post 返回递增计数", f"{before} -> {n}")
    after = client.get("/__stub/count").json()["count"]
    _assert(after == before + 1, "GET /__stub/count 读到逻辑层写入（同存储、幂等语义一致）")
    _assert(client.get("/__stub/count").json()["count"] == after,
            "重复 GET 计数接口不递增（读操作无副作用）")


def test_safety_audit() -> None:
    _section("6) 安全审计：新增资产无真实 PII / Key / 本机绝对路径")
    # 审计对象为「入库内容资产/服务端资产」；_v21_h6_matrix.py 自身含故意构造的越界
    # 样本串（如 C:/Windows/win.ini、/etc/passwd），不作为泄漏样本自证。
    assets = [
        H6_FIXTURES / "README.md",
        H6_FIXTURES / "gen_fixtures.py",
        H6_FIXTURES / "resume_doc.json",
        H6_FIXTURES / "jd.txt",
        H6_FIXTURES / "preview_anchors.json",
        H6_FIXTURES / "identity_samples.json",
        H6_FIXTURES / "fixture_hashes.json",
        BACKEND_ROOT / "_v21_h6_stub.py",
    ]
    banned = [
        re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]"),      # Windows 盘符绝对路径（排除 http 等 scheme）
        re.compile(r"/Users/|/home/"),                       # POSIX 用户主目录
        re.compile(r"sk-[A-Za-z0-9]{12,}"),                  # OpenAI 风格 Key
        re.compile(r"(?i)api\s*key\s*[:=]\s*['\"][^'\"]+"),  # Key 赋值形态
        re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}"),
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        re.compile(r"(?i)ark\s*api"),                        # 本产品真实 Key 前缀
    ]
    clean = True
    detail = ""
    for p in assets:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            clean = False
            detail = f"{p}: 读取失败 {e}"
            break
        for rx in banned:
            m = rx.search(text)
            if m:
                clean = False
                detail = f"{p.name}: 命中 {rx.pattern!r} → {m.group(0)!r}"
                break
        if not clean:
            break
    _assert(clean, "H6 新增资产无本机绝对路径 / API Key / 私钥形态文本", detail)

    doc = _frozen("resume_doc.json")
    text_all = json.dumps(doc, ensure_ascii=False)
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", text_all)
    _assert(emails and all(e.endswith("example.invalid") for e in emails),
            "fixture 内邮箱（若有）仅使用 example.invalid 保留域", f"{emails}")


# ═══════════════════════════════════════════════════════════════════════════
def main() -> int:
    test_fixture_determinism()
    test_anchors_consistency()
    test_stub_logic_layer()
    test_http_matrix()
    test_logic_layer_count()
    test_safety_audit()

    # 汇编与 import 回归：本次新增 Python 资产均可编译导入
    _section("7) py_compile / import 回归")
    import py_compile
    ok = True
    for p in (BACKEND_ROOT / "h6_fixtures" / "gen_fixtures.py",
              BACKEND_ROOT / "_v21_h6_stub.py",
              BACKEND_ROOT / "_v21_h6_matrix.py"):
        try:
            py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as e:
            ok = False
            print(f"  py_compile 失败：{p}: {e}", file=sys.stderr)
    _assert(ok, "新增 Python 资产 py_compile 全部通过")
    import_ok = True
    err = ""
    try:
        from h6_fixtures import gen_fixtures as gf
        import _v21_h6_stub as st
        if gf.load_resume_doc() is None or st.app is None:
            raise RuntimeError("导入返回 None")
    except Exception as ex:
        import_ok = False
        err = repr(ex)
    _assert(import_ok, "h6_fixtures / _v21_h6_stub 模块 import 成功", err)

    print()
    print("=" * 64)
    print(f"V2.1.0 H6 确定性矩阵：PASS={PASS_COUNT} FAIL={len(FAILURES)}")
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
