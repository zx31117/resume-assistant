# V2.2.0 T11 返工：真实模型首 Fact 延迟分解（点击零点→各阶段单调时钟），用于 CHALLENGE_OPEN。
#
# 复用 _e2e_v22_slice 的种子与真实 LLM channel，但按事件时间戳差分输出各段耗时：
#   t0(点击零点) → P1 jd.done → 首 fact.done → 首 reason.delta → P3 内后续 fact/reason
#   → P4(装配/DOCX/PDF 落在 SUCCEEDED) → total
# 全部来自同一条 task 的 TaskEvent.created_at（同一单调时钟来源，非跨时钟拼接）。
# 退出码 0 = SUCCEEDED 且产物存在；非 0 = 失败。
from __future__ import annotations
import sys
import time
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _v2_test_runner import run_isolated  # noqa: E402


def _sh(s: str) -> str:
    import hashlib
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def _seed(db) -> None:
    from database.models import Experience, Fact, FactType

    def exp(idx, *, etype, title, company, role, time, description, skills, achievements):
        e = Experience(id=f"exp{idx}", type=etype, title=title, company=company,
                       role=role, time=time, description=description, skills=skills,
                       achievements=achievements, raw_text=description)
        db.add(e)
        db.flush()
        f = Fact(fact_id=f"e{idx}f0", experience_id=e.id, fact_type=FactType.RESPONSIBILITY,
                 text=description, source_text=description, source_field="description",
                 source_index=None, content_hash=_sh(description), source_hash=_sh(description),
                 revision=1)
        db.add(f)
        for i, ach in enumerate(achievements, start=1):
            f = Fact(fact_id=f"e{idx}f{i}", experience_id=e.id, fact_type=FactType.RESULT,
                     text=ach, source_text=ach, source_field="achievements",
                     source_index=i - 1, content_hash=_sh(ach), source_hash=_sh(ach),
                     revision=1)
            db.add(f)
        return e

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
    from database.session import SessionLocal, engine
    from database import migrations as mig
    from database.models import Task, TaskEvent
    from services.task_service import TaskService
    from core.task import TaskStatus

    state.register_engine(engine)
    _ = mig.run_migrations()
    db = SessionLocal()
    _seed(db)
    from services.embedding_service import rebuild_embeddings
    er = rebuild_embeddings(db)
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
    svc.start_task(tid)

    from datetime import datetime as _dt
    t0 = _dt.utcnow().timestamp()  # 与事件 created_at(naive utcnow) 同基，消除 UTC/local 偏移
    t0_ns = time.perf_counter_ns()
    svc.run_generation(tid)

    final = None
    for _ in range(900):
        time.sleep(0.2)
        st = db.query(Task).filter_by(task_id=tid).first().status
        if TaskStatus(st) in (TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            final = st
            break
    total_s = round(time.time() - t0, 2)
    total_ms = round((time.perf_counter_ns() - t0_ns) / 1e6, 1)

    ev = (db.query(TaskEvent).filter_by(task_id=tid)
          .order_by(TaskEvent.seq.asc()).all())
    rows = []
    for e in ev:
        ts = e.created_at
        rows.append({"seq": e.seq, "type": e.event_type, "phase": e.phase,
                     "t": ts.timestamp() if ts else None,
                     "hd": (e.payload or {}).get("headline", "")})

    ref = rows[0]["t"] if rows and rows[0]["t"] else t0
    print("\n===== DELAY BREAKDOWN =====", flush=True)
    print(f"total_s={total_s} perf_ms={total_ms} status={final}", flush=True)
    prev = ref
    for r in rows:
        if r["t"] is None:
            continue
        d = r["t"] - t0       # 相对点击零点(进程 start 前)
        dprev = r["t"] - prev  # 相对上一条事件
        print(f"seq={r['seq']:>2} {r['type']:<14} ph={r['phase']} "
              f"rel_click={d:.2f}s  rel_prev={dprev:.2f}s  {r['hd'][:16]}", flush=True)
        prev = r["t"]
    if rows:
        print(f"chain_end(最后事件) rel_click={rows[-1]['t']-t0:.2f}s", flush=True)

    if final != "SUCCEEDED":
        print("RESULT=FAIL_NOT_SUCCEEDED", flush=True)
        return 1
    view = svc.get_task(tid)
    import os as _os
    data_root = _os.environ.get("RESUME_DATA_DIR") or "."
    ok = True
    for label, p in (("docx", view.get("published_docx_path")), ("pdf", view.get("published_pdf_path"))):
        pp = Path(p)
        if not pp.is_absolute():
            pp = Path(data_root) / pp
        exist = pp.exists()
        size = pp.stat().st_size if exist else 0
        print(f"artifact {label}: exist={exist} size={size}", flush=True)
        if not (exist and size > 512):
            ok = False
    db.close()
    if not ok:
        print("RESULT=ARTIFACT_MISSING", flush=True)
        return 1
    print("RESULT=OK", flush=True)
    return 0


if __name__ == "__main__":
    run_isolated("v22profile_", _run_tests_inner, "V2.2.0 首 Fact 延迟分解")