# V2.2.0 T11 返工：短/典型/长 × cold/warm 真实模型延迟矩阵（n≥3）。
#
# 目的：为 CHALLENGE_OPEN 的首 Fact ≤15s 提供统计证据（中位数+最大值）。
# 指标（同一单调时钟，点击零点 = run_generation 启动瞬间，与事件 created_at(naive utc) 同基）：
#   first_fact_s : 首个 fact.done 相对点击零点的秒数（已绑定+校验的完整 Fact）
#   total_s      : 端到端 P1-P4 总耗时（perf_counter）
#
# 定义：
#   cold : 每次采样用全新隔离 runtime 目录（新进程 + 新 DB，包含 P1 首次连接/进程冷启动）
#   warm : 同一进程内复用已预热 runtime，先做一次不计数 warmup，再连续计数 n 次
#
# 用法：
#   python _e2e_v22_matrix.py --size typical --mode cold --n 3     # 3 个全新目录（每采样独立）
#   python _e2e_v22_matrix.py --size typical --mode warm --n 3     # 1 warmup + 3 计数（同目录同进程）
#
# 退出码 0 = 全部样本 SUCCEEDED；任一失败非 0。结果打印为 JSON 列表。
from __future__ import annotations
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime as _dt
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

_ENV_KEY = "RESUME_DATA_DIR"


def _sh(s: str) -> str:
    import hashlib
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def _exp(db, idx, *, etype, title, company, role, time, description, skills, achievements):
    from database.models import Experience, Fact, FactType
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
        db.add(Fact(fact_id=f"e{idx}f{i}", experience_id=e.id, fact_type=FactType.RESULT,
                    text=ach, source_text=ach, source_field="achievements",
                    source_index=i - 1, content_hash=_sh(ach), source_hash=_sh(ach),
                    revision=1))
    return e


def _seed_short(db):
    _exp(db, 1, etype="work", title="项目专员", company="YY 咨询", role="项目专员",
         time="2020.03-2021.02",
         description="负责项目排期与进度追踪，协调客户与开发资源，控制交付质量。",
         skills=["项目管理"], achievements=["按期交付 3 个对外项目"])
    db.commit()


def _seed_typical(db):
    _exp(db, 1, etype="work", title="产品经理", company="XX 科技", role="高级产品经理",
         time="2021.06-至今",
         description=("作为高级产品经理，负责线上下单产品的规划与交付：输出产品路线图、"
                      "进行需求分析与竞品调研，组织跨职能团队完成月迭代，并用埋点与 A/B 实验"
                      "驱动转化率优化。"),
         skills=["产品规划", "需求分析", "项目管理", "数据分析", "用户研究", "A/B 实验"],
         achievements=["主导改版后订单转化率从 2.1% 提升至 3.4%",
                       "搭建需求池与优先级模型，需求交付准时率提升至 92%",
                       "推动 4 个大型跨团队项目按期上线"])
    _exp(db, 2, etype="work", title="项目专员", company="YY 咨询", role="项目负责人",
         time="2019.03-2021.05",
         description=("负责咨询项目立项、排期与进度追踪，协调客户与开发资源，控制项目风险与"
                      "交付质量，沉淀项目复盘与流程规范。"),
         skills=["项目管理", "需求分析", "跨团队协作"],
         achievements=["管理 15+ 个对外项目全部按期交付",
                       "建立项目风险管理清单，延期项目比例下降 40%"])
    _exp(db, 3, etype="project", title="校园二手平台", company="项目", role="产品负责人",
         time="2018.09-2019.02",
         description=("发起并负责校园二手交易平台产品设计、原型与上线，覆盖用户调研、信息架构"
                      "与上线推广，验证产品可行性。"),
         skills=["产品设计", "用户研究", "原型"],
         achievements=["上线 3 个月注册用户 8000+，周活留存 35%"])
    db.commit()


def _seed_long(db):
    _seed_typical(db)
    _exp(db, 4, etype="work", title="运营专员", company="ZZ 零售", role="运营负责人",
         time="2017.06-2019.02",
         description=("负责线上商城的日常运营与活动策划，搭建用户分层与召回体系，通过数据看板"
                      "监控流量转化，配合投放团队优化获客成本并沉淀运营 SOP。"),
         skills=["活动策划", "用户运营", "数据分析"],
         achievements=["策划大促活动拉动 GMV 环比提升 26%",
                       "建立用户召回分层，流失用户召回率提升 18%"])
    _exp(db, 5, etype="project", title="会员积分体系", company="项目", role="产品负责人",
         time="2016.09-2017.05",
         description=("负责会员积分体系的产品设计与落地，涵盖积分获取/消耗规则、营销触达与"
                      "后台管理，支撑会员复购与活跃度目标。"),
         skills=["产品设计", "会员体系"],
         achievements=["积分体系上线后会员月活跃提升 15%"])
    db.commit()


def _seeds():
    return {"short": _seed_short, "typical": _seed_typical, "long": _seed_long}


def _jd(size: str) -> str:
    if size == "short":
        return ("岗位名称：项目专员。职责：负责项目排期与进度追踪，协调资源，控制交付质量，"
                "及时向各方同步风险与进度。必备技能：项目管理、计划排期、跨团队沟通。"
                "优先：有跟进多项目并行推进的经验。")
    if size == "long":
        return ("岗位名称：高级产品经理/运营负责人（在线零售方向）。\n"
                "职责：负责产品路线图与季度规划、需求池管理，组织跨团队敏捷迭代；搭建用户分层"
                "与召回、策划大促活动，利用数据/AB 实验优化转化率、留存与获客；主导会员积分等"
                "增长体系；与研发、设计、运营、投放紧密协作。\n"
                "必备技能：产品规划、需求分析、项目管理、数据分析、A/B 实验、用户运营、活动策划。\n"
                "优先：有电商/下单转化、会员体系与多项目团队经验。")
    return ("岗位名称：高级产品经理（在线零售方向）。\n"
            "职责：负责产品路线图与季度规划，主导需求分析与需求池管理，组织跨团队敏捷迭代，"
            "利用数据埋点、A/B 实验与分析工具持续优化转化率与留存；与研发、设计、运营紧密协作。\n"
            "必备技能：产品规划、需求分析、项目管理、数据分析、A/B 实验、用户研究。\n"
            "优先：有电商/下单转化优化经验、主导过多团队项目。")


def _run_one(datadir: str, size: str, seed: bool) -> dict:
    os.environ[_ENV_KEY] = datadir
    from database import migrations as mig
    from database.models import Task, TaskEvent, InputRevision
    from database.session import SessionLocal, engine
    from core.task import TaskStatus
    from services.task_service import TaskService

    # 导入产品模块后再设置 state（本脚本不依赖 _v2_test_runner 的清理；目录由调用方管理）
    _ = mig.run_migrations()
    db = SessionLocal()
    if seed:
        _seeds()[size](db)
        from services.embedding_service import rebuild_embeddings
        er = rebuild_embeddings(db)
        if er.get("failed"):
            db.close()
            return {"status": "EMBED_FAIL", "first_fact_s": None, "total_s": None}
        db.close()
        db = SessionLocal()
    jd = _jd(size)
    svc = TaskService(db)
    t = svc.create_task()
    tid = t["task_id"]
    svc.save_draft(tid, name="王小明", phone="13800000000", email="wang@example.com",
                   location="北京", jd=jd)
    svc.freeze_input(tid, name="王小明", phone="13800000000", email="wang@example.com",
                     location="北京", jd=jd)
    svc.start_task(tid)

    t0 = _dt.utcnow().timestamp()   # 与事件 created_at(naive utc) 同基
    t0_ns = time.perf_counter_ns()
    svc.run_generation(tid)

    final = None
    for _ in range(900):
        time.sleep(0.2)
        st = db.query(Task).filter_by(task_id=tid).first().status
        if TaskStatus(st) in (TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            final = st
            break
    total_s = round((time.perf_counter_ns() - t0_ns) / 1e9, 2)

    first_fact_s = None
    first_reason_s = None
    evs = (db.query(TaskEvent).filter_by(task_id=tid).order_by(TaskEvent.seq.asc()).all())
    for e in evs:
        if e.event_type == "fact.done" and first_fact_s is None:
            first_fact_s = round(e.created_at.timestamp() - t0, 2)
        if e.event_type == "reason.delta" and first_reason_s is None:
            first_reason_s = round(e.created_at.timestamp() - t0, 2)
    db.close()
    return {"status": final, "first_fact_s": first_fact_s,
            "first_reason_s": first_reason_s, "total_s": total_s}


def _usage():
    print("usage: --size short|typical|long --mode cold|warm --n N")
    return 2


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    def _get(k, default=None):
        for i, a in enumerate(args):
            if a == k:
                return args[i + 1] if i + 1 < len(args) else default
        return default
    size = _get("--size", "typical")
    mode = _get("--mode", "cold")
    n = int(_get("--n", "3"))
    if size not in ("short", "typical", "long") or mode not in ("cold", "warm"):
        return _usage()
    out: list[dict] = []
    failures = 0
    if mode == "cold":
        for i in range(n):
            tmp = tempfile.mkdtemp(prefix=f"v22mat_cold_{size}_")
            try:
                m = _run_one(tmp, size, seed=True)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            m.update({"size": size, "mode": "cold", "sample": i + 1})
            out.append(m)
            if m["status"] != "SUCCEEDED":
                failures += 1
    else:  # warm：同一目录/进程，先 warmup 再计数 n
        tmp = tempfile.mkdtemp(prefix=f"v22mat_warm_{size}_")
        try:
            warm = _run_one(tmp, size, seed=True)  # 预热（不计数）
            if warm["status"] != "SUCCEEDED":
                print("WARMUP_FAILED", json.dumps(warm, ensure_ascii=False))
                return 1
            for i in range(n):
                m = _run_one(tmp, size, seed=False)
                m.update({"size": size, "mode": "warm", "sample": i + 1})
                out.append(m)
                if m["status"] != "SUCCEEDED":
                    failures += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    for m in out:
        print(json.dumps(m, ensure_ascii=False), flush=True)
    firsts = [m["first_fact_s"] for m in out if m["first_fact_s"] is not None]
    if firsts:
        s_firsts = sorted(firsts)
        median = s_firsts[len(s_firsts) // 2] if len(s_firsts) % 2 else (
            (s_firsts[len(s_firsts) // 2 - 1] + s_firsts[len(s_firsts) // 2]) / 2)
        print(f"SUMMARY size={size} mode={mode} n={len(out)} "
              f"first_fact median={median} max={max(firsts)} "
              f"total median={sorted(m['total_s'] for m in out)[len(out)//2]}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())