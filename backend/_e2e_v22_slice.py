"""V2.2.0 首条真实纵切：真实 LLM(P1-P3) + 真实 DOCX/PDF(P4)，端到端产出验证（T10）。

退出码 0 = SUCCEEDED 且 DOCX/PDF 产物真实存在、非平凡；非 0 = 失败/异常/清理失败。
仅使用 ARK_API_KEY 真实模型（LLM + Embedding），不注入 mock provider。
"""
from __future__ import annotations
import hashlib
import sys
import time
from datetime import datetime
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _v2_test_runner import run_isolated  # noqa: E402


def _sh(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def _seed(db) -> None:
    from database.models import Experience, Fact, FactType

    def exp(idx, *, etype, title, company, role, time, description, skills, achievements):
        e = Experience(id=f"exp{idx}", type=etype, title=title, company=company,
                       role=role, time=time, description=description, skills=skills,
                       achievements=achievements, raw_text=description)
        db.add(e)
        db.flush()
        n = 0
        # description → RESPONSIBILITY fact（粗粒度整块）
        f = Fact(fact_id=f"e{idx}f0", experience_id=e.id, fact_type=FactType.RESPONSIBILITY,
                 text=description, source_text=description, source_field="description",
                 source_index=None, content_hash=_sh(description), source_hash=_sh(description),
                 revision=1)
        db.add(f)
        n += 1
        # 每条 achievement → RESULT fact
        for i, ach in enumerate(achievements, start=1):
            f = Fact(fact_id=f"e{idx}f{i}", experience_id=e.id, fact_type=FactType.RESULT,
                     text=ach, source_text=ach, source_field="achievements",
                     source_index=i - 1, content_hash=_sh(ach), source_hash=_sh(ach),
                     revision=1)
            db.add(f)
            n += 1
        return e, n

    exp(1, etype="work", title="产品经理", company="XX 科技", role="高级产品经理",
        time="2021.06-至今",
        description=("作为高级产品经理，负责线上下单产品的规划与交付：输出产品路线图、"
                     "进行需求分析与竞品调研，组织跨职能团队完成月迭代，并用埋点与 A/B 实验"
                     "驱动转化率优化。"),
        skills=["产品规划", "需求分析", "项目管理", "数据分析", "用户研究", "A/B 实验"],
        achievements=["主导改版后订单转化率从 2.1% 提升至 3.4%",
                      "搭建需求池与优先级模型，需求交付准时率提升至 92%",
                      "推动 4 个大型跨团队项目按期上线"])

    exp(2, etype="work", title="项目专员", company="YY 咨询", role="项目负责人",
        time="2019.03-2021.05",
        description=("负责咨询项目立项、排期与进度追踪，协调客户与开发资源，控制项目风险与"
                     "交付质量，沉淀项目复盘与流程规范。"),
        skills=["项目管理", "需求分析", "跨团队协作"],
        achievements=["管理 15+ 个对外项目全部按期交付",
                      "建立项目风险管理清单，延期项目比例下降 40%"])

    exp(3, etype="project", title="校园二手平台", company="项目", role="产品负责人",
        time="2018.09-2019.02",
        description=("发起并负责校园二手交易平台产品设计、原型与上线，覆盖用户调研、信息架构"
                     "与上线推广，验证产品可行性。"),
        skills=["产品设计", "用户研究", "原型"],
        achievements=["上线 3 个月注册用户 8000+，周活留存 35%"])

    db.commit()


def _run_tests_inner(state) -> int:
    import json
    from database.session import SessionLocal, engine
    from database import migrations as mig
    from database.models import Task, TaskEvent
    from services.task_service import TaskService
    from core.task import TaskStatus

    state.register_engine(engine)
    _ = mig.run_migrations()
    db = SessionLocal()
    _seed(db)
    # 为候选 Fact 计算真实向量（PLAN §7 T3 / §8.2）：否则 ensure_ready 依 §8.2 阻断生成
    from services.embedding_service import rebuild_embeddings
    er = rebuild_embeddings(db)
    print("embed_rebuild=", er.get("pending_count"), "succeeded=", er.get("succeeded"),
          "failed=", er.get("failed"), flush=True)
    if er.get("failed"):
        print("EMBED_REBUILD_HAD_FAILURES", flush=True)
        return 1

    jd = (
        "岗位名称：高级产品经理（在线零售方向）。\n"
        "职责：负责产品路线图与季度规划，主导需求分析与需求池管理，组织跨团队敏捷迭代，"
        "利用数据埋点、A/B 实验与分析工具持续优化转化率与留存；与研发、设计、运营紧密协作。\n"
        "必备技能：产品规划、需求分析、项目管理、数据分析、A/B 实验、用户研究。\n"
        "优先：有电商/下单转化优化经验、主导过多团队项目。"
    )

    svc = TaskService(db)
    t = svc.create_task()
    tid = t["task_id"]
    svc.save_draft(tid, name="王小明", phone="13800000000", email="wang@example.com",
                   location="北京", jd=jd)
    svc.freeze_input(tid, name="王小明", phone="13800000000", email="wang@example.com",
                     location="北京", jd=jd)
    svc.start_task(tid)  # RUNNING

    t0 = time.time()
    svc.run_generation(tid)  # 真实 LLM + 真实 DOCX/PDF 装配链
    total_start_ns = time.perf_counter_ns()

    final = None
    for _ in range(600):  # 最多 ~600s
        time.sleep(1.0)
        st = db.query(Task).filter_by(task_id=tid).first().status
        if TaskStatus(st) in (TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            final = st
            break
    elapsed_s = round(time.time() - t0, 2)
    total_ms = round((time.perf_counter_ns() - total_start_ns) / 1e6, 1)

    # 阶段耗时（事件时间戳）
    ev = (db.query(TaskEvent).filter_by(task_id=tid)
          .order_by(TaskEvent.seq.asc()).all())
    evs = []
    first_fact_seq = None
    first_fact_at = None
    for e in ev:
        evs.append((e.seq, e.event_type, e.phase,
                    e.created_at.isoformat() if e.created_at else "",
                    (e.payload or {}).get("headline", "")))
        if e.event_type == "fact.done" and first_fact_seq is None:
            first_fact_seq = e.seq
            first_fact_at = e.created_at

    status = db.query(Task).filter_by(task_id=tid).first()
    view = svc.get_task(tid)

    print("\n===== 真实纵切结果 =====", flush=True)
    print("status=", final, "task_id=", tid, flush=True)
    print("total_sec=", elapsed_s, "perf_ms=", total_ms, flush=True)
    print("published_docx=", view.get("published_docx_path"),
          "published_pdf=", view.get("published_pdf_path"), flush=True)
    print("rev=", status.current_input_revision,
          "seq=", status.seq, flush=True)
    print("num_events=", len(evs), "first_fact_seq=", first_fact_seq,
          "first_fact_at=", first_fact_at, flush=True)
    for row in evs[:8]:
        print("  event", row, flush=True)

    if final != "SUCCEEDED":
        print("RESULT=FAIL_NOT_SUCCEEDED", flush=True)
        return 1

    # 验证产物（docx_path 相对 RESUME_DATA_DIR，解析到临时 runtime 内）
    import os as _os
    data_root = _os.environ.get("RESUME_DATA_DIR") or "."
    docx = view.get("published_docx_path")
    pdf = view.get("published_pdf_path")
    ok = True
    for label, p in (("docx", docx), ("pdf", pdf)):
        pp = Path(p)
        if not pp.is_absolute():
            pp = Path(data_root) / pp
        exist = pp.exists()
        size = pp.stat().st_size if exist else 0
        print(f"artifact {label}: exist={exist} size={size} resolved={pp}", flush=True)
        if not (exist and size > 512):
            ok = False
    if not ok:
        print("RESULT=ARTIFACT_MISSING", flush=True)
        return 1

    print("RESULT=OK", flush=True)
    db.close()
    return 0


if __name__ == "__main__":
    run_isolated("v22slice_", _run_tests_inner, "V2.2.0 真实纵切")