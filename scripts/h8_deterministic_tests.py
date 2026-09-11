#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""H8 P2/P3/P4 确定性回归（开发侧单入口，机器断言 + 固定汇总行）。

覆盖（PLAN §20.2–§20.6；用户 H8 指令「三、最终回归」）：
- P2  DOCX→PDF 转换器与 PreviewAnchor：
      capability（Word 版本/build、converter_id）；真实模板 DOCX 转换（%PDF-/页数/大小）；
      anchors 命中/不可用诚实降级；负向 docx_missing / 损坏 / 超时 / 并发 busy；WINWORD 无泄漏。
- P3  generate 级纵向（**仅** mock LLM 边界，其余全真实链）：
      隔离 RESUME_DATA_DIR + 真实 sqlite 播种 + 真实 DOCX 渲染 + 真实 Word COM 转换 +
      真实 PDF 文本层锚点；断言 JD 分析恰 1、rewrite 次数、无输入页预分析、
      artifact 身份（pdf_sha256 / artifact_id 绑定）、不可变 revision 命名、
      P1–P4 服务端投影与终态「阶段和 vs 总耗时 ≤250ms」。
- P4  负向与清理：见 P2 负向 + WINWORD before/after 无新增泄漏。

用法：
  python scripts/h8_deterministic_tests.py            # 全部
  python scripts/h8_deterministic_tests.py --group p3
退出码：0=全部通过；1=存在 FAIL。输出含固定汇总行 `PASS=<n> FAIL=0`。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

# ── 必须在 import core.config 之前设置隔离 runtime 与剥离 Key ──
RUNTIME = Path(os.environ.get("H8_DET_RUNTIME") or tempfile.mkdtemp(prefix="h8det_"))
os.environ["RESUME_DATA_DIR"] = str(RUNTIME)
os.environ.pop("ARK_API_KEY", None)
sys.path.insert(0, str(BACKEND))

JD = ("高级后端研发工程师（Java）：负责电商平台交易链路设计、编码与线上稳定性，主导订单支付库存"
      "模块演进与高并发优化。要求 5 年+ Java、Spring Boot、MySQL、Redis，有分布式/消息队列实践"
      "优先，base 杭州，可尽快到岗。")
EXPERIENCES = [
    {"type": "work", "title": "后端研发工程师", "company": "示例科技有限公司",
     "time": "2022.03-2025.06", "role": "后端研发工程师",
     "description": "负责示例电商平台订单域的后端研发与稳定性建设。",
     "achievements": ["主导订单创建链路重构，核心接口 P99 从 820ms 降到 210ms",
                      "搭建库存扣减幂等与对账机制，超卖事故从月均 3 起降为 0"],
     "skills": ["Java", "Spring Boot", "MySQL", "Redis", "Kafka"],
     "raw_text": "示例科技有限公司 后端研发工程师 2022.03-2025.06"},
    {"type": "work", "title": "初级后端工程师", "company": "虚构网络股份有限公司",
     "time": "2020.07-2022.02", "role": "初级后端工程师",
     "description": "负责示例社区服务的接口开发与数据维护。",
     "achievements": ["完成用户中心服务拆分，接口平均延迟下降 35%"],
     "skills": ["Java", "MySQL"], "raw_text": "虚构网络股份有限公司 初级后端工程师 2020.07-2022.02"},
    {"type": "project", "title": "订单对账系统", "company": "示例科技有限公司",
     "time": "2024.05-2024.11", "role": "负责人",
     "description": "面向示例业务的订单对账与差异定位系统。",
     "achievements": ["设计差异定位算法，对账工单平均处理时长从 45 分钟降到 8 分钟"],
     "skills": ["Java", "Kafka"], "raw_text": "订单对账系统 负责人 2024.05-2024.11"},
    {"type": "education", "title": "计算机科学与技术", "company": "示例大学",
     "time": "2016.09-2020.06", "role": "", "description": "计算机科学与技术 本科",
     "achievements": [], "skills": [], "raw_text": "示例大学 计算机科学与技术 本科"},
]

PASS = 0
FAILS: list[str] = []


def ok(label: str, extra: str = "") -> None:
    global PASS
    PASS += 1
    print(f"[PASS] {label}" + (f" :: {extra}" if extra else ""), flush=True)


def bad(label: str, why: str) -> None:
    FAILS.append(f"{label}: {why}")
    print(f"[FAIL] {label}: {why}", flush=True)


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def winword_pids() -> list[int]:
    try:
        r = __import__("subprocess").run(
            ["tasklist", "/FI", "IMAGENAME eq WINWORD.EXE", "/FO", "CSV", "/NH"],
            capture_output=True, timeout=20)
        txt = r.stdout.decode("utf-8", "replace")
        out = []
        for ln in txt.splitlines():
            parts = [x.strip('"') for x in ln.split(",")]
            if len(parts) >= 2 and parts[0].lower().startswith("winword"):
                out.append(int(parts[1]))
        return out
    except Exception:
        return []


# ── 引导：DB + 播种 + mock LLM 边界 ────────────────────────────
def bootstrap():
    import database.init_db as idb
    idb.init_db()
    from core.operations import tracker
    tracker.initialize()
    from core.config import settings
    from database.migrations import run_migrations
    from database.session import SessionLocal
    from services import experience_service, embedding_service
    mig = run_migrations(backup=False)
    print(f"[h8det] migrations={mig}")
    db = SessionLocal()
    for e in EXPERIENCES:
        experience_service.create_experience(db, settings.DEFAULT_USER_ID, e)
    emb = embedding_service.rebuild_embeddings(db, embedder=lambda t: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
    return db, emb


COUNTS = {"jd": 0, "rewrite": 0, "content": 0}


def install_mock_llm():
    from api import schemas
    from services import embedding_service, llm_service

    # 边界 2：Embedding（选择阶段需要 JD 查询向量）——确定性向量，不触网
    embedding_service._embed_text = lambda text: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

    def fake(system, user_template, schema, default=None, *, strict=False, **variables):
        if schema is schemas.JDAnalysisOut:
            COUNTS["jd"] += 1
            return schemas.JDAnalysisOut(
                position="高级后端研发工程师", industry="互联网",
                required_skills=["Java", "Spring Boot", "MySQL", "Redis"],
                preferred_skills=["Kafka"],
                responsibilities=["负责电商平台交易链路设计与线上稳定性"],
                keywords=["高并发", "分布式"], experience_preferences=["5 年+"])
        if schema is schemas.GeneratedResumeContentV15:
            COUNTS["rewrite"] += 1
            payload = json.loads(variables.get("evidence_json") or "[]")
            exps = []
            for e in payload:
                bullets = []
                for f in (e.get("usable_facts") or [])[:3]:
                    txt = (f.get("text") or "").strip()
                    if not txt:
                        continue
                    bullets.append(schemas.GeneratedBullet(bullet=txt[:70], fact_refs=[f["fact_id"]]))
                if bullets:
                    exps.append(schemas.GeneratedExperienceItemV15(
                        experience_id=e["experience_id"], bullets=bullets))
            return schemas.GeneratedResumeContentV15(experiences=exps)
        if schema is schemas.GeneratedResumeContent:
            COUNTS["content"] += 1
            return schemas.GeneratedResumeContent(experiences=[])
        raise AssertionError(f"mock LLM: unexpected schema {schema}")

    llm_service.chat_structured = fake


# ── P3：generate 级纵向 ───────────────────────────────────────
def run_p3(db) -> dict:
    from api.schemas import RequestProfile, ResumeDocxGenerateRequest
    from core.operations import tracker
    from services import resume_generation_service

    op_id = str(uuid.uuid4())
    req = ResumeDocxGenerateRequest(
        jd_text=JD, profile=RequestProfile(name="测试用户", target_position="高级后端研发工程师"))
    t0 = time.time()
    resp = resume_generation_service.generate_docx(db, req, operation_id=op_id)
    wall = int((time.time() - t0) * 1000)
    d = resp.model_dump()
    d["_wall_ms"] = wall
    d["_counts"] = dict(COUNTS)
    d["_op_detail"] = tracker.get_operation(op_id)

    # 断言 1：JD 恰 1；rewrite 次数据链路（本链为 1）；无输入页预分析（无额外 chat 调用）
    if COUNTS["jd"] != 1:
        bad("P3-jd-once", f"JD LLM 调用 {COUNTS['jd']}（期望 1）")
    else:
        ok("P3-jd-once", f"jd={COUNTS['jd']} rewrite={COUNTS['rewrite']} content={COUNTS['content']}")
    if COUNTS["rewrite"] != 1:
        bad("P3-rewrite-once", f"rewrite 调用 {COUNTS['rewrite']}（期望 1）")
    else:
        ok("P3-rewrite-once", "rewrite=1")

    # 断言 2：artifact 身份
    for f in ("download_url", "pdf_download_url", "pdf_sha256", "pdf_artifact_id"):
        if not d.get(f):
            bad("P3-artifact-fields", f"缺 {f}")
            break
    else:
        ok("P3-artifact-fields", f"art={d['pdf_artifact_id'][:12]} pdf_sha={d['pdf_sha256'][:12]}")

    # 断言 3：不可变 revision 命名（含 operation slug）
    fn = d.get("file_name") or ""
    slug = (op_id or "")[:16]
    if slug and slug in fn:
        ok("P3-revision-name", fn)
    else:
        bad("P3-revision-name", f"文件名未含 operation slug：{fn}")

    # 断言 4：anchors 全部绑定本 revision artifact
    arts = [a.get("artifact_id") for a in (d.get("pdf_anchors") or [])]
    if arts and all(a == d.get("pdf_artifact_id") for a in arts):
        ok("P3-anchors-bound", f"{len(arts)} 条全部绑定")
    else:
        bad("P3-anchors-bound", f"arts={arts[:4]} pdf_artifact_id={d.get('pdf_artifact_id')}")

    # 断言 5：PDF 落盘字节 == 响应 sha
    out_dir = RUNTIME / "output"
    pdfs = sorted(out_dir.glob("*.pdf"))
    docxs = sorted(out_dir.glob(f"*{slug}*.docx")) or sorted(out_dir.glob("*.docx"))
    if pdfs and sha_file(pdfs[-1]) == d.get("pdf_sha256"):
        ok("P3-pdf-disk-sha", f"{pdfs[-1].name} {d['pdf_sha256'][:12]}")
    else:
        bad("P3-pdf-disk-sha", f"disk={[p.name for p in pdfs][-2:]} resp={d.get('pdf_sha256')}")
    d["_docx_path"] = str(docxs[-1]) if docxs else ""
    d["_pdf_path"] = str(pdfs[-1]) if pdfs else ""
    if docxs:
        ok("P3-docx-disk", f"{docxs[-1].name} sha={sha_file(docxs[-1])[:12]}")
    else:
        bad("P3-docx-disk", "未找到 DOCX 落盘")

    # 断言 6：P1–P4 服务端投影 + 终态差 ≤250ms
    op = d["_op_detail"] or {}
    ups = op.get("user_phases") or []
    codes = [u.get("code") for u in ups]
    ssum = sum(int(u.get("elapsed_ms") or 0) for u in ups)
    elapsed = int(op.get("elapsed_ms") or 0)
    delta = abs(elapsed - ssum)
    if codes == ["P1", "P2", "P3", "P4"] and all(u.get("status") == "done" for u in ups):
        ok("P3-user-phases", f"{codes} 全部 done")
    else:
        bad("P3-user-phases", f"投影={[(u.get('code'), u.get('status')) for u in ups]}")
    if delta <= 250:
        ok("P3-terminal-delta", f"sum={ssum}ms elapsed={elapsed}ms delta={delta}ms ≤250")
    else:
        bad("P3-terminal-delta", f"sum={ssum} elapsed={elapsed} delta={delta} >250")
    stage_codes = {s.get("stage_code") for s in (op.get("stages") or [])}
    need = {"jd_analysis", "select_experiences", "content_generation", "resume_build", "render", "save_docx"}
    if need <= stage_codes:
        ok("P3-stage-coverage", f"{len(stage_codes)} internal stages")
    else:
        bad("P3-stage-coverage", f"缺 {sorted(need - stage_codes)}")
    d["_stage_codes"] = sorted(stage_codes)
    return d


# ── P2：转换器 + anchors ─────────────────────────────────────
def run_p2(p3: dict) -> None:
    from services import docx_to_pdf, pdf_anchors

    cap = docx_to_pdf.capability_probe()
    if cap.get("ok") and cap.get("converter") == docx_to_pdf.CONVERTER_ID:
        ok("P2-capability", f"word={cap.get('word_version')}/{cap.get('word_build')} conv={cap.get('converter')}")
    else:
        bad("P2-capability", f"{cap}")

    docx_path = p3.get("_docx_path")
    if not docx_path or not Path(docx_path).exists():
        bad("P2-convert", "缺少可用 DOCX")
        return
    r1 = docx_to_pdf.convert_docx_to_pdf_bytes(docx_path, timeout_s=90.0)
    fp = r1["fingerprint"]
    if r1["pdf_bytes"][:5] == b"%PDF-" and fp["pages"] >= 1 and fp["size_bytes"] > 1000:
        ok("P2-convert", f"pages={fp['pages']} size={fp['size_bytes']} sha={fp['pdf_sha256'][:12]} "
                         f"elapsed={fp['elapsed_s']}s conv={fp['converter']}")
    else:
        bad("P2-convert", f"{fp}")

    # anchors：真实 bullet 文本应命中；不存在的文本应诚实 unavailable
    rows = [{"text": "负责示例电商平台订单域的后端研发与稳定性建设。", "content_item_id": "x", "bullet_index": 0}]
    hit, un = pdf_anchors.build_anchors_from_word_pdf(r1["pdf_bytes"], rows, artifact_id="probe")
    if len(hit) == 1 and hit[0].get("artifact_id") == "probe":
        ok("P2-anchors-hit", "命中 1 条并绑定 artifact_id")
    else:
        bad("P2-anchors-hit", f"hit={hit} un={un}")
    ghost = [{"text": "这一行在 PDF 文本层中绝对不存在ZZZQ", "content_item_id": "y", "bullet_index": 0}]
    h2, u2 = pdf_anchors.build_anchors_from_word_pdf(r1["pdf_bytes"], ghost, artifact_id="probe")
    if not h2 and len(u2) == 1:
        ok("P2-anchors-unavailable", "不存在文本诚实降级为 unavailable（不产生坐标）")
    else:
        bad("P2-anchors-unavailable", f"hit={h2} un={u2}")


def run_p4(p3: dict) -> None:
    from services import docx_to_pdf
    ww_before = winword_pids()

    # 负向 1：docx_missing
    try:
        docx_to_pdf.convert_docx_to_pdf_bytes(str(RUNTIME / "nope.docx"))
        bad("P4-docx-missing", "未抛错")
    except docx_to_pdf.DocxToPdfError as e:
        if e.code == "docx_missing":
            ok("P4-docx-missing", f"code={e.code}")
        else:
            bad("P4-docx-missing", f"code={e.code}")

    # 负向 2：损坏 DOCX → fail closed
    bogus = RUNTIME / "bogus.docx"
    bogus.write_bytes(b"not-a-real-docx" * 40)
    try:
        docx_to_pdf.convert_docx_to_pdf_bytes(str(bogus), timeout_s=60.0)
        bad("P4-corrupt-docx", "未抛错（应 fail closed）")
    except docx_to_pdf.DocxToPdfError as e:
        ok("P4-corrupt-docx", f"fail closed code={e.code}")
    except Exception as e:  # noqa: BLE001
        bad("P4-corrupt-docx", f"非 DocxToPdfError：{type(e).__name__}: {e}")

    # 负向 3：极小超时 → code=timeout
    docx_path = p3.get("_docx_path")
    if docx_path and Path(docx_path).exists():
        t0 = time.time()
        try:
            docx_to_pdf.convert_docx_to_pdf_bytes(docx_path, timeout_s=1.2)
            bad("P4-timeout", "未抛错")
        except docx_to_pdf.DocxToPdfError as e:
            took = time.time() - t0
            if e.code == "timeout" and took < 30:
                ok("P4-timeout", f"code=timeout took={took:.1f}s")
            else:
                bad("P4-timeout", f"code={e.code} took={took:.1f}s")
        # 负向 3b：超时后应能恢复（再次转换成功）
        try:
            r = docx_to_pdf.convert_docx_to_pdf_bytes(docx_path, timeout_s=90.0)
            ok("P4-recover-after-timeout", f"pages={r['fingerprint']['pages']}")
        except Exception as e:  # noqa: BLE001
            bad("P4-recover-after-timeout", f"{type(e).__name__}: {e}")

    # 负向 4：并发 busy（持锁期间第二次调用）
    if docx_path and Path(docx_path).exists():
        res: dict = {}

        def first():
            try:
                res["a"] = docx_to_pdf.convert_docx_to_pdf_bytes(docx_path, timeout_s=90.0) and "ok"
            except Exception as e:  # noqa: BLE001
                res["a"] = f"{type(e).__name__}:{getattr(e, 'code', '')}"
        th = threading.Thread(target=first)
        th.start()
        time.sleep(0.4)
        try:
            # 第二路用**极小超时**：锁被第一路持有时 acquire(timeout) 超时 → code=busy
            docx_to_pdf.convert_docx_to_pdf_bytes(docx_path, timeout_s=1.2)
            res["b"] = "no-error"
        except docx_to_pdf.DocxToPdfError as e:
            res["b"] = e.code
        except Exception as e:  # noqa: BLE001
            res["b"] = type(e).__name__
        th.join(timeout=120)
        if res.get("b") == "busy":
            ok("P4-concurrent-busy", f"second={res.get('b')} first={res.get('a')}")
        else:
            bad("P4-concurrent-busy", f"{res}")

    # 负向 5：WINWORD 无泄漏
    time.sleep(1.5)
    after = winword_pids()
    leaked = sorted(set(after) - set(ww_before))
    if not leaked:
        ok("P4-winword-no-leak", f"before={ww_before} after={after}")
    else:
        bad("P4-winword-no-leak", f"leaked={leaked} before={ww_before} after={after}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", choices=("p2", "p3", "p4", "all"), default="all")
    args = ap.parse_args()
    print(f"[h8det] RESUME_DATA_DIR={RUNTIME}")
    print(f"[h8det] group={args.group}")
    db, emb = bootstrap()
    install_mock_llm()
    print(f"[h8det] seed embeddings={emb}")
    p3 = {}
    try:
        if args.group in ("p3", "all"):
            p3 = run_p3(db)
        if args.group in ("p2", "all"):
            run_p2(p3)
        if args.group in ("p4", "all"):
            run_p4(p3)
    finally:
        try:
            db.close()
        except Exception:
            pass
        summary = {"pass": PASS, "fails": FAILS, "counts": COUNTS,
                   "runtime": str(RUNTIME), "group": args.group}
        outp = ROOT / "validation-artifacts" / "h8"
        if outp.is_dir():
            (outp / "h8_deterministic_summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        if os.environ.get("H8_DET_KEEP") != "1":
            shutil.rmtree(RUNTIME, ignore_errors=True)
    print("=" * 60)
    print(f"PASS={PASS} FAIL={len(FAILS)}")
    for f in FAILS:
        print("  - " + f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
