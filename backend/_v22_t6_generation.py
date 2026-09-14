"""V2.2.0 T6e 验证：紧凑 JD ＋ Fact/reason 两阶段、经历并发 2、调用/Token 门禁
（PLAN §2.1 / §2.2 / V220-R1-T06）。

用"假 LLM provider + 确定性 selector"注入 orchestrator（不触发真实模型/Embedding），
断言 T06 完成证据：typed / binding / 顺序 / 并发 / 重试 / 超限 / 真实模型缺省分支。

退出码 0 = 业务断言通过且临时 runtime 清理干净；非 0 = 有失败/异常/清理失败。

门禁用例：
- [T1] P1 紧凑 JD：typed 7 字段 + position 校验 + completion token 记账；
- [T2] Fact typed：experience_id/fact_refs 绑定性，越界即拒，输出经 TaskFactOut 校验；
- [T3] reason 绑定：同一 fact_id，delta 累积为完整理由，快照保留完整文本；
- [T4] 顺序：合并按冻结 sort_order，与完成顺序无关（用假 provider 反转完成时序）；
- [T5] 并发：经历并发上限 min(E,2)，同步实测最大同时调用深度 <= 2；
- [T6] 重试：假 provider 先 fail 后成功，单逻辑调用最多 3 attempt，计数正确；
- [T7] 超限：任务 Token 预算不足时不启动新调用 → TaskCapacityError（截断成功被拒）；
- [T8] 取消/fence：协作取消后写回被拒，编排安全点抛 TaskCancelledError；
- [T9] 端到端 run_generation worker：READY->RUNNING->SUCCEEDED，快照到位。
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


class FakeProvider:
    """确定性假 LLM：provider(system, user_template, variables, max_tokens) -> (text, tokens)。

    按 user_template 特征分发 compact/fact/reason；附带并发深度/完成序/按阶段调用计数，
    供门禁断言。可配置：某阶段先 fail 若干次再成功；某 experience 延迟以反转完成时序。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._active = 0
        self._max_concurrent = 0
        self.completion_order: list[str] = []   # 各经历实际完成顺序（fact 阶段首完成记录）
        self.call_counts: dict[str, int] = {}   # stage -> 逻辑调用次数
        self.attempt_counts: dict[str, int] = {}  # stage -> 总 attempt 数
        self.fail_first: dict[str, int] = {}    # stage -> 前 N 次 attempt 抛可重试异常
        self.delay_experience: dict[str, float] = {}  # exp -> 该经历单次 fact 延迟(秒)

    def _enter(self):
        with self._lock:
            self._active += 1
            if self._active > self._max_concurrent:
                self._max_concurrent = self._active

    def _leave(self):
        with self._lock:
            self._active -= 1

    def _mark(self, stage):
        with self._lock:
            self.call_counts[stage] = self.call_counts.get(stage, 0) + 1
            self.attempt_counts[stage] = self.attempt_counts.get(stage, 0) + 1

    def __call__(self, system, user_template, variables, max_tokens):
        v = variables or {}
        # 分发阶段
        tid = v.get("_stage")
        if tid is None:
            if "required_skills" in user_template and "岗位描述" in user_template:
                tid = "compact"
            elif "facts_json" in v:
                tid = "fact"
            else:
                tid = "reason"
        stage = tid
        self._enter()
        try:
            self._mark(stage)
            # 可注入失败：前 N 次 attempt 抛可重试错误（触发 LLM_MAX_ATTEMPTS 重试）
            ff = self.fail_first.get(stage, 0)
            if self.attempt_counts.get(stage, 0) <= ff:
                raise ConnectionError(f"injected transient failure for {stage}")

            if stage == "compact":
                return json.dumps({
                    "position": "后端工程师", "industry": "互联网",
                    "required_skills": ["Python", "大模型"], "preferred_skills": [],
                    "responsibilities": ["系统开发"], "keywords": ["后端"],
                    "experience_preferences": ["优先展示项目"],
                }, ensure_ascii=False), 120

            if stage == "fact":
                exp = json.loads(v["experience_json"])["experience_id"]
                facts = json.loads(v["facts_json"])
                src_id = facts[0]["fact_id"] if facts else "f0"
                d = self.delay_experience.get(exp, 0.0)
                if d:
                    time.sleep(d)
                with self._lock:
                    if exp not in self.completion_order:
                        self.completion_order.append(exp)
                return json.dumps({
                    "experience_id": exp, "fact_id": f"{exp}/{src_id.split('/')[-1]}",
                    "headline": f"HL-{src_id}", "body": "Body",
                    "fact_refs": [src_id], "ok": True, "insufficient_reason": "",
                }, ensure_ascii=False), 60

            # reason
            fid = v.get("fact_id", "")
            return json.dumps({"fact_id": fid, "delta": f"理由<{fid}>", "done": True},
                              ensure_ascii=False), 30
        finally:
            self._leave()


def _fake_selector(experiences):
    """按传入的 PreparedExperience 名单直接返回（跳过 Embedding/选材依赖）。"""
    return experiences


def _run_tests_inner(state) -> int:
    from database import migrations as mig
    from database.session import SessionLocal, engine
    from core.task_cancel import registry
    from services.task_generation import (
        PreparedExperience, PreparedFact, generate_task, MAX_WORKERS,
    )
    from services.task_repository import TaskRepository, TaskNotFoundError
    from services.task_service import TaskService

    state.register_engine(engine)
    mig.run_migrations()
    registry.reset()

    svc_db = SessionLocal()
    svc = TaskService(svc_db)

    def _make_ready():
        t = svc.create_task()
        tid = t["task_id"]
        svc.save_draft(tid, name="甲", phone="138", email="a@b.c", location="上海",
                       jd="招聘后端工程师，要求 Python 与大模型，开发系统。")
        svc.freeze_input(tid, name="甲", phone="138", email="a@b.c", location="上海",
                         jd="招聘后端工程师，要求 Python 与大模型，开发系统。")
        return tid

    # 准备 3 条经历，各含 2 个源 Fact（用于并发与顺序断言）
    prep = [
        PreparedExperience("exp-a", 1, "项目A", [PreparedFact("fa1", "t1"), PreparedFact("fa2", "t2")]),
        PreparedExperience("exp-b", 2, "工作B", [PreparedFact("fb1", "u1"), PreparedFact("fb2", "u2")]),
        PreparedExperience("exp-c", 3, "工作C", [PreparedFact("fc1", "v1")]),
    ]

    # ── [T1] P1 紧凑 JD：typed + 记账 ──
    print("\n[T1] P1 紧凑 JD")
    tid = _make_ready()
    db = SessionLocal()
    provider = FakeProvider()
    task = db.get(__import__("database.models", fromlist=["Task"]).Task, tid)
    ctx = registry.start(tid, 1)
    summary = generate_task(db, task, ctx, {"revision": 1},
                            provider=provider, selector=lambda c: prep)
    db.commit()  # 释放 T1 写锁，供后续用例继续写
    check(summary.compact_jd.get("position") == "后端工程师", "compact JD position typed")
    check(summary.compact_jd.get("required_skills") == ["Python", "大模型"], "required_skills typed")
    check(provider.call_counts.get("compact", 0) == 1, "JD 恰好 1 次逻辑调用")
    check(summary.completion_tokens > 0, "completion token 已记账", extra=str(summary.completion_tokens))
    check(len(summary.experiences) == 3, "3 条经历均已生成")
    check(summary.phase == "P4", "无 assembler 时 P4 登记为 pending 后阶段停在 P4")

    # ── [T2] Fact typed + 绑定性 ──
    print("\n[T2] Fact typed / binding")
    ok = True
    for e in summary.experiences:
        exp_fact_ids = {s.fact_id for s in dict((x.experience_id, x) for x in prep)[e.experience_id].facts}
        for f in e.facts:
            if not set(f.fact_refs).issubset(exp_fact_ids):
                ok = False
    check(ok, "每条 fact 的 fact_refs 均在所属经历允许集内")
    check(all(f.headline and f.body for e in summary.experiences for f in e.facts), "headline/body 非空")

    # 越界绑定应被编排器拒绝：注入越界 fact_refs 的 provider
    print("  越界绑定拒绝")
    class _BadFact(FakeProvider):
        def __call__(self, system, user_template, v, max_tokens):
            if "facts_json" in (v or {}):
                exp = json.loads(v["experience_json"])["experience_id"]
                src = json.loads(v["facts_json"])[0]["fact_id"]
                return json.dumps({"experience_id": exp, "fact_id": f"{exp}/1",
                                   "headline": "H", "body": "B", "fact_refs": ["NOPE"],
                                   "ok": True}, ensure_ascii=False), 50
            return super().__call__(system, user_template, v, max_tokens)

    from core.errors import ContentGenerationError
    tid2 = _make_ready()
    db2 = SessionLocal()
    task2 = db2.get(__import__("database.models", fromlist=["Task"]).Task, tid2)
    ctx2 = registry.start(tid2, 1)
    try:
        generate_task(db2, task2, ctx2, {"revision": 1}, provider=_BadFact(), selector=lambda c: [prep[0]])
        check(False, "越界 fact_refs 应抛 ContentGenerationError")
    except ContentGenerationError:
        check(True, "越界 fact_refs 被 ContentGenerationError 拒收")
    db2.close()

    # ── [T3] reason 绑定 + 快照完整文本 ──
    print("\n[T3] reason 绑定 / 快照")
    all_reasons = {}
    for e in summary.experiences:
        for f in e.facts:
            all_reasons[f.fact_id] = f.reason
    check(all_reasons and all(f"理由<{k}>" == v for k, v in all_reasons.items()),
          "每 fact 的 reason 等于 provider delta（同一 fact_id 绑定）")
    snap = db.query(__import__("database.models", fromlist=["TaskSnapshot"]).TaskSnapshot) \
        .filter_by(task_id=tid).first()
    check(snap is not None, "存在权威快照")
    snap_reasons = (snap.payload or {}).get("reasons", {}) if snap else {}
    check(snap_reasons == all_reasons, "快照保留每 fact 的 reason 完整文本")

    # ── [T4] 顺序：合并按 sort_order，与完成顺序无关 ──
    print("\n[T4] 顺序（反转完成时序）")
    tid3 = _make_ready()
    db3 = SessionLocal()
    task3 = db3.get(__import__("database.models", fromlist=["Task"]).Task, tid3)
    ctx3 = registry.start(tid3, 1)
    prov_order = FakeProvider()
    prov_order.delay_experience = {"exp-a": 0.05}  # exp-a(sort_order=1) 最慢完成
    s3 = generate_task(db3, task3, ctx3, {"revision": 1},
                       provider=prov_order, selector=lambda c: prep)
    merged_ids = [e.experience_id for e in s3.experiences]
    check(merged_ids == ["exp-a", "exp-b", "exp-c"], "合并按冻结 sort_order",
          extra=str(merged_ids))
    check(prov_order.completion_order and prov_order.completion_order[0] != "exp-a",
          "完成时序反转已发生（exp-a 最后完成）")
    db3.close()

    # ── [T5] 并发：min(E,2) ──
    print("\n[T5] 并发上限 2")
    check(MAX_WORKERS == 2, "经历并发上限固定为 2")
    check(provider._max_concurrent <= MAX_WORKERS, "实测最大同时 LLM 调用 <= 2",
          extra=f"max={provider._max_concurrent}")

    # ── [T6] 重试：最多 3 attempt，先 fail 后成功 ──
    print("\n[T6] 重试")
    t_retry = _make_ready()
    db_retry = SessionLocal()
    task_retry = db_retry.get(__import__("database.models", fromlist=["Task"]).Task, t_retry)
    ctx_retry = registry.start(t_retry, 1)
    prov_retry = FakeProvider()
    prov_retry.fail_first = {"compact": 1}  # compact 先失败 1 次再成功
    sr = generate_task(db_retry, task_retry, ctx_retry, {"revision": 1},
                       provider=prov_retry, selector=lambda c: [prep[0]])
    check(prov_retry.attempt_counts.get("compact", 0) == 2, "compact 重试后成功（2 attempt）",
          extra=str(prov_retry.attempt_counts))
    check(sr.compact_jd.get("position") == "后端工程师", "重试后仍返回 typed 结果")
    db_retry.close()

    # ── [T7] 超限：Token 预算不足不启动新调用 → TaskCapacityError ──
    print("\n[T7] Token 预算超限")
    from services.llm_service import TaskTokenBudget
    t_over = _make_ready()
    db_over = SessionLocal()
    task_over = db_over.get(__import__("database.models", fromlist=["Task"]).Task, t_over)
    ctx_over = registry.start(t_over, 1)
    tiny_budget = TaskTokenBudget(50)  # 连一次 JD(120 tokens) 都放不下
    from services.task_repository import TaskCapacityError
    try:
        generate_task(db_over, task_over, ctx_over, {"revision": 1},
                      budget=tiny_budget, provider=FakeProvider(), selector=lambda c: [prep[0]])
        check(False, "预算不足应抛 TaskCapacityError")
    except TaskCapacityError:
        check(True, "预算不足抛 TaskCapacityError（不返回截断成功）")
    db_over.close()

    # ── [T8] 取消/fence：协作取消后写回被拒 ──
    print("\n[T8] 取消 / fence")
    t_cancel = _make_ready()
    db_cancel = SessionLocal()
    task_cancel = db_cancel.get(__import__("database.models", fromlist=["Task"]).Task, t_cancel)
    cv = registry.start(t_cancel, 1)
    registry.request_cancel(t_cancel)  # 置位 token + 撤销 fence
    from core.task_cancel import TaskCancelledError, RevisionFenceError
    try:
        generate_task(db_cancel, task_cancel, cv, {"revision": 1},
                      provider=FakeProvider(), selector=lambda c: [prep[0]])
        check(False, "协作取消后 P1 边检应抛取消/拒写异常")
    except (TaskCancelledError, RevisionFenceError):
        check(True, "协作取消后写回在安全点被拒（fence/取消信号）")
    db_cancel.close()

    # ── [T9] 端到端 run_generation worker → SUCCEEDED ──
    print("\n[T9] run_generation 端到端")
    t_e2e = _make_ready()
    svc.start_task(t_e2e)
    prov_e2e = FakeProvider()
    stub_assembler = lambda _summary, _compact: (False, {})  # 单元门禁：绕过真实 Word/PDF
    sm = None
    try:
        result = svc.run_generation(t_e2e, provider=prov_e2e, selector=lambda c: [prep[0], prep[1]],
                                    assembler=stub_assembler)
        check(result["status"] == "RUNNING", "启动后 RUNNING（异步立即返回视图）")
        # 轮询到终态
        deadline = time.time() + 15
        status = None
        while time.time() < deadline:
            v = svc.get_task(t_e2e)
            status = v["status"]
            if status in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(0.1)
        sm = svc.get_task(t_e2e)
        check(status == "SUCCEEDED", "worker 终态 SUCCEEDED", extra=status)
        check((sm.get("snapshot") or {}).get("phase") in ("P3", "P4"), "快照 phase 到位")
    except Exception as ex:  # noqa: BLE001
        check(False, f"run_generation 异常: {ex!r}")
    finally:
        # 释放活动槽
        try:
            if sm and status != "SUCCEEDED":
                svc.cancel_task(t_e2e)
        except Exception:
            pass
    del sm

    # 收尾
    try:
        svc.cancel_task(t_e2e)
    except Exception:
        pass
    registry.reset()

    for df in (svc_db, db, db2, db3, db_retry, db_over, db_cancel):
        try:
            df.close()
        except Exception:
            pass
    print(f"\n结果：{_passed} 通过 / {_failed} 失败")
    return 1 if _failed else 0


if __name__ == "__main__":
    def _fn(state):
        return _run_tests_inner(state)

    run_isolated("v22_t6_", _fn, "V2.2.0 T6 generation/orchestrator gate")