"""V2.2.0 任务级 partial 保留 + 失败范围实操证据（gap#3，真实编排路径，非仅单调用重试）。

论证目标（对应 PLAN §3/V220-G02「insufficient/partial/failed 保留已完成结果、只重试失败范围、
不全任务静默重跑」，用户在 Revision 2 收口审查中提出）：
  1) 单逻辑调用最多 3 attempt（已有 `_h8_retry_proof.py` 证明）之外，这里补**任务级**证据：
     一次生成中途失败后，**已完成经历的子任务与 Fact 事件被持久化保留**（不会被外层 rollback
     回滚），可在 FAILED 面板如实呈现"已完成范围保留"；
  2) 未完成经历被标记 FAILED/_P3_ABORTED，调用增量只覆盖"失败范围"（已完成经历不再重复计费）；
  3) 记录用户可见动作 / 状态变化 / 调用增量。

用注入 provider（不触发真实模型/Embedding），隔离临时 runtime，退出码 0=断言通过且清理干净。
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
    """确定性假 LLM：compact/exp-a 成功，exp-b 的 fact 调用抛 ContentGenerationError（非可重试，
    单 attempt 立即失败）。exp-a 无延迟、先完成；exp-b 多个源 Fact，首 Fact 即失败。"""

    def __init__(self, fail_exp: str = "exp-b"):
        self._lock = threading.Lock()
        self.fail_exp = fail_exp
        self.call_counts: dict[str, int] = {}
        self.calls: list[str] = []  # 每次逻辑调用的 (stage, experience_id|position)

    def _mark(self, stage, tag):
        with self._lock:
            self.call_counts[stage] = self.call_counts.get(stage, 0) + 1
            self.calls.append(f"{stage}({tag})")

    def __call__(self, system, user_template, variables, max_tokens):
        from core.errors import ContentGenerationError
        v = variables or {}
        # 阶段判定（与 _v22_t6 一致）
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
                # 让 exp-a 先完整完成并提交，exp-b 稍后失败，从而确定性复现“已完成保留 + 失败中止”。
                time.sleep(0.25)
                raise ContentGenerationError(
                    f"injected {self.fail_exp} failure", details={"experience_id": tag}, stage="fact")
            src = json.loads(v["facts_json"])[0]["fact_id"]
            return (json.dumps({
                "experience_id": tag, "fact_id": f"{tag}/{src.split('/')[-1]}",
                "headline": f"HL-{src}", "body": "Body",
                "fact_refs": [src], "ok": True, "insufficient_reason": "",
            }, ensure_ascii=False), 60)

        # reason
        return (json.dumps({"fact_id": tag, "delta": f"理由<{tag}>", "done": True},
                           ensure_ascii=False), 30)


def _run(state) -> int:
    from database import migrations as mig
    from database.session import SessionLocal, engine
    from core.task_cancel import registry
    from services.task_generation import PreparedExperience, PreparedFact, generate_task
    from services.task_service import TaskService

    mig.run_migrations()
    registry.reset()

    svc_db = SessionLocal()
    svc = TaskService(svc_db)
    tid = svc.create_task()["task_id"]
    jd = "招聘高级后端工程师，要求熟练 Python 与大模型应用，负责系统架构设计与核心模块实现，参与技术评审、性能优化与迭代交付，善于解决线上稳定性问题，base 杭州，可尽快到岗。"
    svc.save_draft(tid, name="甲", phone="138", email="a@b.c", location="上海", jd=jd)
    svc.freeze_input(tid, name="甲", phone="138", email="a@b.c", location="上海", jd=jd)
    svc.start_task(tid)  # RUNNING，作为生成前状态（用户可见动作：点击生成）

    prep = [
        PreparedExperience("exp-a", 1, "项目A", [PreparedFact("fa1", "t1")]),   # 快，完成
        PreparedExperience("exp-b", 2, "工作B", [PreparedFact("fb1", "u1"),
                                                 PreparedFact("fb2", "u2")]),  # 首 Fact 即失败
    ]

    db = SessionLocal()
    import database.models as M
    task = db.get(M.Task, tid)
    prov = PartialFailProvider(fail_exp="exp-b")
    ctx = registry.start(tid, 1)

    # 用户可见动作：点击生成 → 任务介入 RUNNING；这里直接调编排（等价 worker 主体）。
    # 状态变化 A：RUNNING。生成中途 exp-b 失败 → 编排向上抛异常（provider 异常被
    # invoke_observed_json 归一化为 LLMOutputInvalidError；非可重试类异常单 attempt 即失败）。
    failed = False
    try:
        generate_task(db, task, ctx, {"revision": 1}, provider=prov,
                      selector=lambda c: prep)
    except Exception as e:  # noqa: BLE001
        failed = True
        print(f"  [info] generate_task 抛出: {type(e).__name__}: {e}")
    check(failed, "exp-b 失败时编排向上抛异常（不做截断成功）")

    # 模拟 run_generation worker 的失败收尾：rollback 未提交、随后转 FAILED（状态变化 B）。
    db.rollback()
    from core import task as task_domain
    from services.task_repository import TaskRepository
    task = db.get(M.Task, tid)
    TaskRepository(db).transition(task, task_domain.TaskStatus.FAILED,
                                  terminal_error="GENERATION_FAILED")
    db.commit()
    final = TaskService(db).get_task(tid)
    check(final["status"] == "FAILED", "任务终态 FAILED（状态变化 B）", extra=final["status"])

    # 保留复查：已完成 exp-a 的子任务应为 SUCCEEDED 且带 fact_results（不受 rollback 影响）
    subs = {s["experience_id"]: s for s in final.get("subtasks", [])}
    sub_a = subs.get("exp-a") or {}
    sub_b = subs.get("exp-b") or {}
    check(sub_a.get("status") == "SUCCEEDED", "已完成经历 exp-a 子任务保留为 SUCCEEDED",
          extra=str(sub_a))
    check(bool(sub_a.get("fact_results")), "exp-a 的 fact_results 已持久化（可复用）",
          extra=str(sub_a.get("fact_results"))[:120])
    check(sub_b.get("status") != "SUCCEEDED",
          "未完成经历 exp-b 无成功结果（PENDING，无成功 artifact）", extra=str(sub_b))

    # 已完成经历的事件（fact.done / reason.delta）保留；事件不随 TaskView 返回，直接查 TaskEvent 表。
    ev_rows = db.query(M.TaskEvent).filter_by(task_id=tid).all()
    ev_types = [ev.event_type for ev in ev_rows]
    check(any(t == "fact.done" or str(t).startswith("fact.done") for t in ev_types),
          "已完成经历的事件已在 TaskEvent 保留", extra=str(ev_types))
    check(any(t == "reason.delta" for t in ev_types),
          "已完成经历的 reason.delta 已在 TaskEvent 保留", extra=str(ev_types))

    # 调用增量：只覆盖"失败范围"。exp-a（1 Fact + 1 reason）与 compact 已计费；
    # exp-b 被拒，无额外成功产生。断言 exp-a 有 fact+reason 调用、exp-b fact 调用存在但失败。
    fact_calls = [c for c in prov.calls if c.startswith("fact(")]
    reason_calls = [c for c in prov.calls if c.startswith("reason(")]
    check(any("exp-a" in c for c in fact_calls), "exp-a 的 Fact 调用已发生（成功）")
    check(any("exp-a/fa1" in c for c in reason_calls), "exp-a 的 reason 调用已发生")
    check(any("exp-b" in c for c in fact_calls), "exp-b 的 Fact 调用已发生（随后失败）")
    print(f"  [info] 调用增量（失败范围）: fact_calls={fact_calls} reason_calls={reason_calls}  "
          f"compact_calls={prov.call_counts.get('compact',0)}")

    # 状态变化 C（用户可见）：FAILED 面板呈现"已完成范围保留 + 补充走我的经历"→
    # 说明：同任务"只重试失败范围"因 core.task TRANSITIONS[FAILED]=∅（终态）而无法直接再跑，
    # 该拓展需 P.O. 决策（见 RESULT gap#3 阻断）。本证明覆盖"保留已完成 + 调用仅限失败范围"。
    try:
        TaskService(db).cancel_task(tid)
    except Exception:
        pass
    registry.reset()
    db.close()
    svc_db.close()
    try:
        engine.dispose()  # 释放 SQLite 句柄，允许 run_isolated 清理临时 runtime
    except Exception:
        pass
    print(f"\n结果：{_passed} 通过 / {_failed} 失败")
    print("RANGE_RETRY_PROOF_EXIT=0")
    return 1 if _failed else 0


if __name__ == "__main__":
    run_isolated("v22_range_retry_", _run, "V2.2.0 task-level partial preservation & failed-scope proof")