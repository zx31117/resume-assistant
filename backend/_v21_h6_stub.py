"""V2.1.0 H6（PLAN §18.2）可移交 stub server 正式版（backend/_v21_h6_stub.py）。

来源：由 ignored validation-artifacts/h5/stub_backend.py 重构为仓库内正式测试资产；
- 无真实用户数据/Key；内容唯一来源 backend/h6_fixtures/（全虚构，见其 README 安全边界）；
- 无本机绝对路径：一切路径基于本文件/仓库相对或系统临时目录；
- 无在线依赖；Python 3.10+，fastapi/uvicorn/reportlab/python-docx 均属 backend/requirements.txt。

行为由「mode」控制（每次请求读取，运行中改即生效）：
    {
      "delay_ms": 0,          # generate-docx 人为延迟（毫秒），观察 processing 态用
      "fail_generate": false, # true -> 生成失败（DomainErrorOut 形状，HTTP 500，retryable）
      "pdf_gen": "good",      # good=完整 pdf_* 字段 / none=不返回任何 pdf_*（URL 空场景）
      "pdf_mode": "good",     # good=真 PDF / broken=损坏字节(200) / html=200非PDF / missing=404
      "anchors": "full",      # full=fixture 锚点（多 section、空/非空 fact_refs）/ empty=[] /
                              # mismatch=anchors.artifact_id != pdf_artifact_id
      "run_no": 1             # 每次新生成 run_no+1 → 新的 file_name/pdf_artifact_id（更换 artifact 用）
    }

mode 来源优先级：模块级 _MODE_OVERRIDE（矩阵直连逻辑层用）> mode 文件 > 默认。
mode 文件与 POST 计数日志都放「系统临时目录 /v21h6_stub_runtime」（H6_STUB_RUNTIME_DIR
可覆盖）——绝不写仓库，保证干净 checkout 无运行态副作用。

用法（命令行）：
    python backend/_v21_h6_stub.py [--port 8000] [--host 127.0.0.1]
        [--mode-json '{...}'] [--mode-file PATH] [--no-static]
        [--static PATH_TO_DIST]        # 可选：把指定目录作为 / 静态站点（production test build 用）
        [--set run_no=2 --set anchors=empty ...]   # 便捷逐键设置 mode 文件

静态托管默认探测仓库 frontend/dist；仅当目录存在时挂载（同源 http://host:port/ 即生产 build）。
接口（与旧 stub 对齐，供 R29 半自动矩阵/浏览器使用）：
    GET  /api/system/status
    GET  /api/experience/
    GET  /api/template/list
    POST /api/jd/analyze
    GET  /api/system/operations/{op_id}
    POST /api/resume/generate-docx        （唯一计数的 POST；写 stub_posts.log）
    GET  /api/template/download?path=...  （pdf_mode/docx 正反向；越界/未知一律 4xx）
    GET  /__stub/count                     （{count, total_bytes, path}：generate-docx 累计次数）
"""
# 注意：不要启用 `from __future__ import annotations`——本模块路由定义在闭包工厂内，
# 字符串化注解会让 FastAPI 无法把 `req: Request` 解析为请求对象（会被误当 query 参数）。
import json
import os
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

# ── 仓库相对路径（模块位于 backend/ 根）──
BACKEND_ROOT = Path(__file__).resolve().parent
FIXTURES_DIR = BACKEND_ROOT / "h6_fixtures"
DIST_DEFAULT = BACKEND_ROOT.parent / "frontend" / "dist"

# ── 运行态（绝不写仓库）──
RUNTIME_DIR = Path(
    os.environ.get("H6_STUB_RUNTIME_DIR")
    or (Path(tempfile.gettempdir()) / "v21h6_stub_runtime")
)
MODE_FILE = RUNTIME_DIR / "mode.json"
POST_LOG = RUNTIME_DIR / "stub_posts.log"

_lock = threading.Lock()
_MODE_OVERRIDE: dict | None = None  # 矩阵/进程内直连覆盖；None => 读 mode 文件

_DEFAULT_MODE = {
    "delay_ms": 0,
    "fail_generate": False,
    "pdf_gen": "good",
    "pdf_mode": "good",
    "anchors": "full",
    "run_no": 1,
}


def set_mode_override(mode: dict) -> None:
    """矩阵用：进程内直连逻辑层时覆盖 mode（不经文件，避免污染运行态目录）。"""
    global _MODE_OVERRIDE
    _MODE_OVERRIDE = {**_DEFAULT_MODE, **(mode or {})}


def reset_mode_override() -> None:
    global _MODE_OVERRIDE
    _MODE_OVERRIDE = None


def _mode_from_file() -> dict:
    try:
        return {**_DEFAULT_MODE, **json.loads(MODE_FILE.read_text(encoding="utf-8"))}
    except Exception:
        return dict(_DEFAULT_MODE)


def current_mode() -> dict:
    if _MODE_OVERRIDE is not None:
        return {**_DEFAULT_MODE, **_MODE_OVERRIDE}
    return _mode_from_file()


# ── fixture 缓存（延迟到首次需要；确定性命中 fixture_hashes.json）──
_fixture_cache: dict = {}


def _ensure_fixtures() -> None:
    if "pdf" in _fixture_cache:
        return
    sys.path.insert(0, str(BACKEND_ROOT))
    from h6_fixtures import gen_fixtures as _g

    doc = _g.load_resume_doc()
    pdf, anchors = _g.build_fixture_pdf(
        artifact_id="ARTIFACT_ID_H6",
        bullet_fact_refs=doc.get("bullet_fact_refs") or {},
    )
    docx = _g.build_fixture_docx()
    _fixture_cache.update({"pdf": pdf, "docx": docx, "anchors": anchors, "doc": doc})


def fixture_pdf() -> bytes:
    _ensure_fixtures()
    return _fixture_cache["pdf"]


def fixture_docx() -> bytes:
    _ensure_fixtures()
    return _fixture_cache["docx"]


def fixture_doc() -> dict:
    _ensure_fixtures()
    return _fixture_cache["doc"]


def fixture_anchor_template() -> list[dict]:
    _ensure_fixtures()
    return _fixture_cache["anchors"]


# ── 身份/计数 辅助 ──
def _count_posts() -> int:
    if not POST_LOG.is_file():
        return 0
    try:
        return len([l for l in POST_LOG.read_text(encoding="utf-8").splitlines() if l.strip()])
    except OSError:
        return 0


def record_generate_post(op_id: str, mode_snapshot: dict) -> int:
    """POST 计数逻辑层：generate-docx 每次调用 +1，写运行态日志；返回当前计数。

    幂等语义：只有 generate-docx 调用走这里；GET/下载/轮询一律不计数（由路由直接不调本函数）。
    """
    try:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        with _lock:
            count = _count_posts() + 1
            with POST_LOG.open("a", encoding="utf-8") as f:
                f.write(f"{count}\t{op_id}\t{json.dumps(mode_snapshot, ensure_ascii=False)}\n")
            return count
    except OSError:
        return 0


def _domain_err(status: int, code: str, stage: str, msg: str, retryable: bool):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status,
        content={
            "ok": False,
            "error_code": code,
            "stage": stage,
            "message": msg,
            "retryable": retryable,
            "details": {},
        },
    )


# ── 响应组装 ──
def _anchors_for(artifact_id: str) -> list[dict]:
    kind = current_mode().get("anchors", "full")
    if kind == "empty":
        return []
    anchors = [dict(a) for a in fixture_anchor_template()]
    if kind == "mismatch":
        for a in anchors:
            a["artifact_id"] = "artifact_OTHER"
    else:  # full
        for a in anchors:
            a["artifact_id"] = artifact_id
    return anchors


def _doc_preview() -> list[dict]:
    """由虚构 resume_doc 生成 doc_preview（doc_preview 承担内容核对/无障碍依据，不做版式）。"""
    doc = fixture_doc()
    prof = doc.get("profile") or {}
    sections: list[dict] = []
    personal_entries = [{
        "heading": prof.get("name") or "",
        "subhead": " 丨 ".join(x for x in (
            f"电话：{prof.get('phone')}", f"邮箱：{prof.get('email')}",
            f"所在地：{prof.get('location')}",
        ) if x),
        "bullets": [f"目标岗位：{prof.get('target_position')}"] if prof.get("target_position") else [],
        "experience_id": None,
        "selection_reason": None,
    }]
    sections.append({"section": "personal", "title": "个人信息", "entries": personal_entries})

    def bullet_section(sec_key: str, title: str, items: list[dict]) -> list[dict]:
        entries = []
        for it in items:
            eid = it.get("experience_id") or ""
            if sec_key == "work":
                heading = f"{it.get('company')} · {it.get('role')}"
            elif sec_key == "project":
                heading = f"{it.get('name')} · {it.get('role')}"
            elif sec_key == "education":
                heading = f"{it.get('school')} · {it.get('major')}"
            else:
                heading = it.get("category") or ""
            subhead = (
                f"{it.get('start_time')}-{it.get('end_time')}"
                if it.get("start_time") else None
            )
            bullets = list(it.get("bullets") or []) if sec_key != "education" else [
                x for x in ((it.get("description") or ""), (it.get("gpa") or "")) if x
            ]
            if sec_key == "skills":
                bullets = it.get("items") or []
            entries.append({
                "heading": heading,
                "subhead": subhead,
                "bullets": bullets,
                "experience_id": eid or None,
                "selection_reason": ("与目标岗位强相关" if eid == "h6-work-1" else None),
            })
        return entries

    for sec_key, title, key in (
        ("education", "教育背景", "education"),
        ("work", "实习经历", "work"),
        ("project", "项目经历", "projects"),
        ("skills", "技能专长", "skills"),
    ):
        items = doc.get(key) or []
        if not items:
            continue
        sections.append({"section": sec_key, "title": title,
                         "entries": bullet_section(sec_key, title, items)})
    return sections


def _build_generate_response(op_id: str) -> dict:
    m = current_mode()
    run_no = int(m.get("run_no", 1))
    doc = fixture_doc()
    pdf_artifact_id = f"artifact_{run_no}_{op_id[:8]}"
    pdf_name = f"resume_{run_no}.pdf"
    docx_name = f"resume_{run_no}.docx"
    pdf_bytes = fixture_pdf()
    pdf_sha = __import__("hashlib").sha256(pdf_bytes).hexdigest()
    anchors = _anchors_for(pdf_artifact_id)
    docx_path = f"output/{docx_name}"
    work_ids = [w.get("experience_id") for w in doc.get("work") or [] if w.get("experience_id")]
    proj_ids = [p.get("experience_id") for p in doc.get("projects") or [] if p.get("experience_id")]
    all_ids = work_ids + proj_ids
    evidence = doc.get("evidence") or {}
    return {
        "ok": True,
        "file_path": docx_path,
        "file_name": docx_name,
        "download_url": f"/api/template/download?path=output/{docx_name}",
        "operation_id": op_id,
        "stages": [
            {"stage": "select_experiences", "status": "completed", "duration_ms": 800, "note": "固定槽位选材"},
            {"stage": "select_evidence", "status": "completed", "duration_ms": 700, "note": "第二层事实选材"},
            {"stage": "content_generation", "status": "completed", "duration_ms": 1200, "note": "受约束改写"},
            {"stage": "resume_build", "status": "completed", "duration_ms": 300, "note": "Builder 装配"},
            {"stage": "render", "status": "completed", "duration_ms": 150, "note": "PDF/Word 渲染"},
            {"stage": "save_docx", "status": "completed", "duration_ms": 90, "note": "保存 DOCX"},
            {"stage": "response_assembly", "status": "completed", "duration_ms": 40, "note": "响应组装"},
        ],
        "matched_experience_ids": all_ids,
        "rendered_experience_ids": all_ids,
        "profile_source": "request",
        "page_count": 2,
        "warnings": [],
        "build_counts": {
            "education": len(doc.get("education") or []),
            "work": len(doc.get("work") or []),
            "projects": len(doc.get("projects") or []),
            "awards": len(doc.get("awards") or []),
            "skill_groups": len(doc.get("skills") or []),
        },
        "build_meta": {
            "profile_source": "request",
            "ai_covered_experience_ids": work_ids,
            "fallback_sql_experience_ids": [],
            "ai_unrecognized_experience_ids": [],
            "max_items_trimmed": {},
            "bullet_fact_refs": doc.get("bullet_fact_refs") or {},
            "fact_refs_per_experience": {
                eid: [fid for lst in (doc.get("bullet_fact_refs") or {}).get(eid, []) for fid in lst]
                for eid in all_ids
            },
            "builder_mode": "v15",
            "counts": {
                "education": len(doc.get("education") or []),
                "work": len(doc.get("work") or []),
                "projects": len(doc.get("projects") or []),
                "awards": len(doc.get("awards") or []),
                "skill_groups": len(doc.get("skills") or []),
            },
        },
        "render_stats": {
            "sections": [
                {"section_id": "profile", "input_items": 1, "rendered_items": 1},
                {"section_id": "work", "input_items": len(doc.get("work") or []),
                 "rendered_items": len(doc.get("work") or [])},
            ],
            "unreplaced_placeholders": [],
            "capacity_warnings": [],
        },
        "template_id": "pm_template",
        "pdf_file_name": pdf_name,
        "pdf_download_url": f"/api/template/download?path=output/{pdf_name}",
        "pdf_artifact_id": pdf_artifact_id,
        "pdf_sha256": pdf_sha,
        "pdf_size_bytes": len(pdf_bytes),
        "pdf_anchors": anchors,
        "doc_preview": _doc_preview(),
        "evidence": evidence,
    }


# ── FastAPI 应用 ──
def _create_app():
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, Response

    app = FastAPI(title="v21-h6-stub", version="2.1.0")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    @app.get("/api/system/status")
    def system_status():
        doc = fixture_doc()
        return {
            "version": "2.1.0",
            "migrations": {"applied": ["v1.5.0-fact-migration", "v1.5.0-fact-schema"], "missing": [], "applied_count": 2},
            "counts": {"experience": len(doc.get("work") or []), "fact": sum(len(v) for v in (doc.get("evidence") or {}).values())},
            "embeddings": {"fingerprint": "stub", "total": 0, "VALID": 0, "PENDING": 0, "INVALID": 0, "FAILED": 0},
            "ready": True,
            "next_steps": [],
        }

    @app.get("/api/experience/")
    def experience_list():
        out = []
        for w in fixture_doc().get("work") or []:
            out.append({
                "id": w.get("experience_id"), "type": "work",
                "title": w.get("role"), "company": w.get("company"),
                "time": f"{w.get('start_time')}-{w.get('end_time')}",
                "role": w.get("role"), "description": (w.get("bullets") or [""])[0],
                "skills": [], "achievements": (w.get("bullets") or [])[1:],
                "raw_text": "", "fact_count": len(fixture_doc().get("evidence") or {}).get(w.get("experience_id") or "", []),
                "summary_status": "ready",
            })
        return out

    @app.get("/api/template/list")
    def template_list():
        return {
            "templates": [{
                "template_id": "pm_template", "display_name": "pm_template", "version": "1.2",
                "page_limit": 1,
                "sections": ["profile", "education", "work", "project", "skills", "awards", "summary"],
                "is_default": True,
            }]
        }

    @app.post("/api/jd/analyze")
    def jd_analyze(req: Request):
        return {
            "position": "高级前端工程师",
            "industry": "互联网",
            "required_skills": ["React", "TypeScript", "性能优化"],
            "preferred_skills": ["低代码", "组件库", "架构设计"],
            "responsibilities": ["负责低代码平台前端研发", "推进性能优化与工程质量"],
            "keywords": ["React", "TypeScript", "低代码", "组件库"],
            "experience_preferences": ["3 年以上前端经验", "有组件库/低代码经验优先"],
        }

    @app.get("/api/system/operations/{op_id}")
    def operation_detail(op_id: str):
        import json as _json
        sample_path = FIXTURES_DIR / "identity_samples.json"
        try:
            sample = _json.loads(sample_path.read_text(encoding="utf-8")).get("operation") or {}
        except Exception:
            sample = {}
        sample = _json.loads(_json.dumps(sample).replace("<op_id>", op_id))
        return {"ok": True, "operation": sample, "diagnostics_health": "ok"}

    # 注意全部路由用同步 def：本 stub 无真正异步 I/O，同步 handler 在 TestClient/
    # uvicorn 线程池中稳定执行（避免 async portal 在本环境的偶发阻塞）。
    @app.post("/api/resume/generate-docx")
    def generate_docx(req: Request):
        m = current_mode()
        op_id = str(uuid.uuid4())
        # record_generate_post 内部自持锁；此处不再重复加锁（threading.Lock 不可重入，防死锁）。
        count = record_generate_post(op_id, m)
        _ = count
        delay = float(m.get("delay_ms", 0)) / 1000.0
        if delay > 0:
            time.sleep(delay)
        if m.get("fail_generate"):
            return _domain_err(500, "RESUME_GENERATION_FAILED", "resume_build",
                               "stub：内容改写模型调用失败（H6 注入）", True)
        resp = _build_generate_response(op_id)
        if m.get("pdf_gen") == "none":
            for k in ("pdf_file_name", "pdf_download_url", "pdf_artifact_id",
                      "pdf_sha256", "pdf_size_bytes", "pdf_anchors"):
                resp.pop(k, None)
        return resp

    @app.get("/api/template/download")
    def template_download(path: str):
        m = current_mode()
        # 安全边界：仅接受 output/<resume_<run>.pdf|docx> 形式的相对路径（诚实失败）。
        if not path or ".." in path or path.startswith(("/", "\\")) or ":" in path:
            return JSONResponse(status_code=400, content={"detail": "invalid path"})
        name = path.rsplit("/", 1)[-1]
        if not name.startswith("resume_") or not any(name.endswith(ext) for ext in (".pdf", ".docx")):
            return JSONResponse(status_code=404, content={"detail": "unknown file"})
        if name.endswith(".pdf"):
            pdf_mode = m.get("pdf_mode", "good")
            if pdf_mode == "broken":
                return Response(content=b"%PDF-corrupted-" + b"x" * 96, media_type="application/pdf")
            if pdf_mode == "html":
                return Response(content=b"<html><body>H6 stub not a pdf</body></html>", media_type="text/html")
            if pdf_mode == "missing":
                return JSONResponse(status_code=404, content={"detail": "not found"})
            return Response(content=fixture_pdf(), media_type="application/pdf")
        return Response(
            content=fixture_docx(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    @app.get("/__stub/count")
    def stub_count():
        return {"count": _count_posts(), "path": str(POST_LOG)}

    return app


app = _create_app()


def _maybe_mount_static(dist: Path | None) -> None:
    from fastapi.staticfiles import StaticFiles
    if dist is None:
        dist = DIST_DEFAULT
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="site")


def _ensure_runtime_mode(cli_mode: dict | None, set_kv: list[str] | None) -> None:
    """CLI 主入口：在运行态目录落一份 mode（随后手工改文件即可热切换）。"""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    mode = _DEFAULT_MODE
    if MODE_FILE.is_file():
        try:
            mode = {**_DEFAULT_MODE, **json.loads(MODE_FILE.read_text(encoding="utf-8"))}
        except Exception:
            mode = dict(_DEFAULT_MODE)
    if cli_mode:
        mode.update(cli_mode)
    for kv in (set_kv or []):
        if "=" in kv:
            k, _, v = kv.partition("=")
            if v.lower() == "true":
                mode[k.strip()] = True
            elif v.lower() == "false":
                mode[k.strip()] = False
            else:
                try:
                    mode[k.strip()] = int(v)
                except ValueError:
                    mode[k.strip()] = v
    MODE_FILE.write_text(json.dumps(mode, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    import argparse
    import uvicorn

    p = argparse.ArgumentParser(description="V2.1.0 H6 stub server（可移交测试资产）")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--mode-json", default=None, help="启动 mode（JSON 字符串）")
    p.add_argument("--mode-file", default=None, help="使用指定 mode 文件（默认运行态 mode.json）")
    p.add_argument("--set", action="append", default=None, metavar="K=V", help="便捷键值（可多次）")
    p.add_argument("--static", default=None, metavar="DIR", help="静态托管目录（production test build）")
    p.add_argument("--no-static", action="store_true", help="不探测/不挂载 frontend/dist")
    p.add_argument("--runtime-dir", default=None, help="覆盖运行态目录（默认系统临时目录）")
    args = p.parse_args(argv)

    global RUNTIME_DIR, MODE_FILE, POST_LOG
    if args.runtime_dir:
        _rd = Path(args.runtime_dir)
        RUNTIME_DIR = _rd
        MODE_FILE = _rd / "mode.json"
        POST_LOG = _rd / "stub_posts.log"

    cli_mode = json.loads(args.mode_json) if args.mode_json else None
    _ensure_runtime_mode(cli_mode, args.set)
    print(f"[H6 stub] mode 文件：{MODE_FILE}（运行中可改，下个请求生效）")
    print(f"[H6 stub] POST 计数：{POST_LOG}")

    if not args.no_static:
        try:
            _maybe_mount_static(Path(args.static) if args.static else None)
        except Exception as e:  # 缺 dist/依赖异常都不阻断 /api
            print("[H6 stub] static mount skipped:", e)

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
