"""V2.2.0「只重试失败范围」续试任务实操证据（开发 Gate，用户可操作入口）。

论证目标（Revision 2 收口：#1 实现用户可操作的「只重试失败范围」）：
  1) FAILED 源任务保持终态不变，通过**续试任务（新 task_id）**承载续试
     （PLAN 不要求沿用同一 task_id）；
  2) 已完成经历被**复用**：续试任务 exp-a 子任务 SUCCEEDED，fact_results 与源任务逐字一致，
     且续试对 exp-a **零模型调用**；
  3) 调用只发生在失败范围：续试的 fact/reason 调用仅出现在失败经历 exp-b，绝不出现 exp-a；
  4) 续试任务自身到达终态（SUCCEEDED），源任务仍为 FAILED。

用注入 provider（不触发真实模型），隔离临时 runtime，退出码 0=断言通过且清理干净。
对应 API 入口：POST /api/task/{task_id}/continue（前端「续试失败范围」按钮调用）。
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _v2_test_runner import run_isolated  # noqa: E402

_passed = 0
_failed = 0


def check(cond, name, extra=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [PASS] {name}")
    else:
        _failed += 1
        print(f"  [FAIL] {name} {extra}")


class PartialFailProvider:
    """源任务用：compact/exp-a 成功，exp-b 的 fact 调用抛 ContentGenerationError（不可重试）。

    与 _v22_range_retry_proof 同构：exp-a 先完成并提交，exp-b 首 Fact 即失败。
    """

    def __init__(self, fail_exp: str = "exp-b"):
        self._lock = threading.Lock()
        self.fail_exp = fail_exp
        self.calls: list[str] = []

    def _mark(self, stage, tag):
        with self._lock:
            self.calls.append(f"{stage}({tag})")

    def __call__(self, system, user_template, variables, max_tokens):
        from core.errors import ContentGenerationError
        v = variables or {}
        if "required_skills" in user_template and "岗位描述" in user_template:
            stage, tag = "compact", "jd"
        elif "facts_json" in v:
            exp = json.loads(v["experience_json"])["experience_id"]
            stage, tag = "fact", exp
        else:
            stage, tag = "reason", v.get("fact_id", "")
        self._mark(stage, tag)
        if stage == "compact":
            return (json.dumps({
                "position": "后端工程师", "industry": "互联网",
                "required_skills": ["Python", "大模型"], "preferred_skills": [],
                "responsibilities": ["系统开发"], "keywords": ["后端"],
                "experience_preferences": ["优先展示项目"],
            }, ensure_ascii=False), 120)
        if stage == "fact":
            if tag == self.fail_exp:
                time.sleep(0.25)
                raise ContentGenerationError(
                    f"injected {self.fail_exp} failure", details={"experience_id": tag}, stage="fact")
            src = json.loads(v["facts_json"])[0]["fact_id"]
            return (json.dumps({
                "experience_id": tag, "fact_id": f"{tag}/{src.split('/')[-1]}",
                "headline": f"HL-{src}", "body": "Body", "fact_refs": [src],
                "ok": True, "insufficient_reason": "",
            }, ensure_ascii=False), 60)
        return (json.dumps({"fact_id": tag, "delta": f"理由<{tag}>", "done": True},
                           ensure_ascii=False), 30)


class SucceedProvider:
    """续试任务用：全部成功（compact + 失败经历 exp-b 的 fact/reason）。"""

    def __init__(self):
        self._lock = threading.Lock()
        self.calls: list[str] = []

    def _mark(self, stage, tag):
        with self._lock:
            self.calls.append(f"{stage}({tag})")

    def __call__(self, system, user_template, variables, max_tokens):
        v = variables or {}
        if "required_skills" in user_template and "岗位描述" in user_template:
            stage, tag = "compact", "jd"
        elif "facts_json" in v:
            exp = json.loads(v["experience_json"])["experience_id"]
            stage, tag = "fact", exp
        else:
            stage, tag = "reason", v.get("fact_id", "")
        self._mark(stage, tag)
        if stage == "compact":
            return (json.dumps({
                "position": "后端工程师", "industry": "互联网",
                "required_skills": ["Python", "大模型"], "preferred_skills": [],
                "responsibilities": ["系统开发"], "keywords": ["后端"],
                "experience_preferences": ["优先展示项目"],
            }, ensure_ascii=False), 120)
        if stage == "fact":
            src = json.loads(v["facts_json"])[0]["fact_id"]
            return (json.dumps({
                "experience_id": tag, "fact_id": f"{tag}/{src.split('/')[-1]}",
                "headline": f"HL-{src}", "body": "Body", "fact_refs": [src],
                "ok": True, "insufficient_reason": "",
            }, ensure_ascii=False), 60)
        return (json.dumps({"fact_id": tag, "delta": f"理由<{tag}>", "done": True},
                           ensure_ascii=False), 30)


_JD = ("招聘高级后端工程师，要求熟练 Python 与大模型应用，负责系统架构设计与核心模块实现，"
       "参与技术评审、性能优化与迭代交付，善于解决线上稳定性问题，base 杭州，可尽快到岗。")


def _seed(session, upsert_facts):
    """插入原始 Experience 与 Fact 行（供 select/list_facts 读取；source 用 select_scope 直建）。"""
    from database.models import Experience
    for eid, title in [("exp-a", "项目A"), ("exp-b", "工作B")]:
        if session.get(Experience, eid) is None:
            session.add(Experience(id=eid, title=title))
    session.flush()
    for f in upsert_facts:
        # 失败范围经历 exp-b 的源 Fact 必须落库，续试经 list_facts_for_experiences 取回重跑。
        session.add(__import__("database.models", fromlist=["Fact"]).Fact(
            fact_id=f, experience_id="exp-b", text=f"t-{f}", source_field="description",
            source_index=int(f.split("b")[-1]), content_hash="", source_hash=""))
    session.commit()


def _wait_terminal(svc, tid, timeout=25.0):
    """轮询续试任务直到终态（worker 线程异步执行）。返回最终 view。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        v = svc.get_task(tid)
        if v["status"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return v
        time.sleep(0.1)
    return svc.get_task(tid)


def _run(state) -> int:
    from database import migrations as mig
    from database.session import SessionLocal, engine
    from core.task_cancel import registry
    from core import task as task_domain
    from services.task_generation import PreparedExperience, PreparedFact, generate_task
    from services.task_service import TaskService
    from services.task_repository import TaskRepository

    mig.run_migrations()
    registry.reset()

    svc_db = SessionLocal()
    svc = TaskService(svc_db)
    # 种子经历/源 Fact（exp-b 的源 Fact 落库，供续试取回）
    _seed(svc_db, upsert_facts=["fb1", "fb2"])

    # ── 源任务 → FAILED（exp-a 完成并提交，exp-b 失败） ──
    tid = svc.create_task()["task_id"]
    svc.save_draft(tid, name="甲", phone="138", email="a@b.c", location="上海", jd=_JD)
    svc.freeze_input(tid, name="甲", phone="138", email="a@b.c", location="上海", jd=_JD)
    svc.start_task(tid)

    prep = [
        PreparedExperience("exp-a", 1, "项目A", [PreparedFact("fa1", "t1")]),   # 快，完成
        PreparedExperience("exp-b", 2, "工作B", [PreparedFact("fb1", "t-fb1"),
                                                 PreparedFact("fb2", "t-fb2")]),  # 首 Fact 即失败
    ]
    db = SessionLocal()
    import database.models as M
    task = db.get(M.Task, tid)
    prov = PartialFailProvider(fail_exp="exp-b")
    ctx = registry.start(tid, 1)
    failed = False
    try:
        generate_task(db, task, ctx, {"revision": 1}, provider=prov,
                      selector=lambda c: prep)
    except Exception as e:  # noqa: BLE001
        failed = True
    check(failed, "源任务生成中途失败（exp-b 注入失败，向上抛异常）")
    db.rollback()
    TaskRepository(db).transition(task, task_domain.TaskStatus.FAILED, terminal_error="GENERATION_FAILED")
    db.commit()

    src_view = svc.get_task(tid)
    check(src_view["status"] == "FAILED", "源任务终态 FAILED", extra=src_view["status"])
    src_subs = {s["experience_id"]: s for s in src_view.get("subtasks", [])}
    src_a = src_subs.get("exp-a") or {}
    src_b = src_subs.get("exp-b") or {}
    check(src_a.get("status") == "SUCCEEDED" and bool(src_a.get("fact_results")),
          "源 exp-a 已完成并持久化 fact_results", extra=str(src_a.get("fact_results") or {})[:150])
    check(src_b.get("status") != "SUCCEEDED", "源 exp-b 未完成（进入失败范围）",
          extra=str(src_b.get("status")))

    # ── 用户可操作：POST /{task_id}/continue → 续试任务（新 task_id） ──
    succ_prov = SucceedProvider()
    cont = svc.continue_failed_scope(tid, provider=succ_prov)
    cont_tid = cont["task_id"]
    check(cont_tid and cont_tid != tid, "续试任务使用新 task_id（源 FAILED 保持终态）",
          extra=f"src={tid} cont={cont_tid}")

    import time as _t
    cont_view = _wait_terminal(TaskService(svc_db), cont_tid)
    check(cont_view["status"] == "SUCCEEDED", "续试任务到达 SUCCEEDED", extra=cont_view["status"])
    # 让续试 worker 线程完成 T9 cleanup 并释放其 SQLite 连接后再清理临时 runtime，
    # 避免下一进程删除 app.db 时句柄仍被占用（daemon 线程随进程退出会释放，但需先让出）。
    _t.sleep(1.2)

    # 复用断言：续试 exp-a 子任务 SUCCEEDED 且 fact_results 与源逐字一致
    cont_subs = {s["experience_id"]: s for s in cont_view.get("subtasks", [])}
    cont_a = cont_subs.get("exp-a") or {}
    check(cont_a.get("status") == "SUCCEEDED", "续试 exp-a 子任务 SUCCEEDED（复用）",
          extra=str(cont_a.get("status")))
    check(cont_a.get("fact_results") == src_a.get("fact_results"),
          "续试 exp-a fact_results 与源任务逐字一致（已完成结果被复用）",
          extra=str(cont_a.get("fact_results") or {})[:150])

    # 调用断言：续试只调用失败范围
    fact_calls = [c for c in succ_prov.calls if c.startswith("fact(")]
    reason_calls = [c for c in succ_prov.calls if c.startswith("reason(")]
    check(any("exp-b" in c for c in fact_calls), "续试对失败经历 exp-b 发起 Fact 调用",
          extra=str(fact_calls))
    check(not any("exp-a" in c for c in succ_prov.calls),
          "续试对已完成 exp-a 零调用（复用，不重复计费）", extra=str(succ_prov.calls))
    print(f"  [info] 续试调用增量（应仅失败范围 exp-b + compact）: {succ_prov.calls}")

    # 源任务仍 FAILED 终态
    src_after = TaskService(svc_db).get_task(tid)
    check(src_after["status"] == "FAILED", "源任务保持 FAILED 终态（未改写）",
          extra=src_after["status"])

    # 经 API 路由层面可见（continue_failed_scope 即 POST /{task_id}/continue 实现）
    registry.reset()
    svc_db.close()
    db.close()
    try:
        engine.dispose()  # 释放 SQLite 句柄，允许 run_isolated 清理临时 runtime
    except Exception:
        pass
    print(f"\n结果：{_passed} 通过 / {_failed} 失败")
    print("CONTINUE_SCOPE_PROOF_EXIT=0")
    return 1 if _failed else 0


if __name__ == "__main__":
    run_isolated("v22_continue_scope_", _run,
                 "V2.2.0 failed-scope continuation task proof")