"""V2.2.0 T6c：任务生成编排器（PLAN §2.1 / §2.2 / §2.3）。

按冻结 InputRevision 执行四阶段渐进生成：
- P1 紧凑 JD 结构化：invoke_observed_json，受单任务 Token 预算与 JD_COMPACT_MAX_TOKENS 门禁；
- P2 本地索引/候选准备：选定入选经历与可用 Fact（selector 可注入，默认走 selection_service）；
- P3 Fact＋reason 两阶段：Experience 级并发上限 min(E, 2)，同一经历内按 Fact 串行；
  每 Fact 一次 Fact 结构化调用（headline+body+fact_refs）+ 一次 reason 调用；
  结果按冻结 sort_order 合并，reason 绑定同一 fact_id；
- P4 装配：assembler 钩子产出 ResumeDocument/artifact 状态（T07 接入真实 DOCX/PDF 链）。

调用/Token 门禁（PLAN §2.2）：
- 每逻辑调用发起前 budget.reserve(尝试上限)，结束后 refund(未用额度)；
- 单任务 completion ≤ 16k；即将超限时以明确失败/容量不足结束，不返回截断成功；
- 协作式取消与 revision fence：worker 在安全点 run_ctx.assert_writable()（先 fence 再取消信号）。

并发与线程安全：
- 只有编排主线程写 DB（snapshot/event/subtask），Experience worker 线程仅做纯 LLM 调用，
  返回结果；因此不共享 SQLAlchemy session，规避 SQLite 线程不安全。
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from api.schemas import TaskFactOut, TaskReasonOut
from core import task as task_core
from core.config import settings
from core.errors import ContentGenerationError
from core.task_cancel import TaskRunContext
from prompts import task_fact, task_reason
from services import fact_service, jd_analyzer, llm_service, selection_service

logger = logging.getLogger(__name__)


# ── P2 候选准备的可序列化结构 ──────────────────────────────────── #

@dataclass
class PreparedFact:
    fact_id: str
    text: str
    fact_type: str = ""
    source_text: str = ""


@dataclass
class PreparedExperience:
    experience_id: str
    sort_order: int
    title: str
    facts: list[PreparedFact] = field(default_factory=list)


# ── P3 生成结果 ────────────────────────────────────────────────── #

@dataclass
class GeneratedFact:
    fact_id: str
    headline: str
    body: str
    fact_refs: list[str]
    reason: str


@dataclass
class GeneratedExperience:
    experience_id: str
    sort_order: int
    title: str
    facts: list[GeneratedFact] = field(default_factory=list)


@dataclass
class GenerationSummary:
    compact_jd: dict[str, Any]
    experiences: list[GeneratedExperience]  # 已按冻结 sort_order 排序
    phase: str
    llm_records: list[dict[str, Any]] = field(default_factory=list)
    completion_tokens: int = 0
    assembled: bool = False
    artifacts: dict[str, Any] = field(default_factory=dict)


# ── P2 默认选材（走 selection_service，两层决策） ───────────────── #

def default_selector(db: Session, jd_analysis: JDAnalysisOutLike,
                     jd_query_vector: Optional[list[float]] = None) -> list[PreparedExperience]:
    """第一层经历 + 第二层 Fact 选材，产出 P3 需要的经历/Fact 名单。

    ``jd_query_vector``：V2.2.0 R3-§6 并行预嵌入的 JD 查询向量（由主编排在 P1
    期间后台线程计算）。传入时 select_evidence 复用该向量，跳过 P2 串行向量化，
    从而把"首向量化"与 P1 的 JD chat 并行重叠（首 Fact ≤15s 门禁）。None 时回退
    原有串行 resolve 路径，行为不变。
    """
    from core.owner import current_user_id
    from database.models import Experience

    # V2.2.0 P0：第一层经历选材只取当前 owner 的职业资产（隔离异主/LEGACY 素材）。
    experiences = (db.query(Experience)
                   .filter(Experience.user_id == current_user_id())
                   .order_by(Experience.created_at)
                   .all())
    jd_dict = _compact_dict(jd_analysis)
    candidate = selection_service.select_experiences(experiences, jd_dict)
    evidence = selection_service.select_evidence(db, candidate, jd_dict,
                                                 jd_query_vector_override=jd_query_vector)
    facts_by_exp: dict[str, list[PreparedFact]] = {}
    fact_objects = fact_service.list_facts_for_experiences(db, candidate.selected_ids())
    for f in fact_objects:
        facts_by_exp.setdefault(f.experience_id, []).append(
            PreparedFact(fact_id=f.fact_id, text=f.text or "",
                         fact_type=f.fact_type.value if hasattr(f.fact_type, "value") else str(f.fact_type),
                         source_text=f.source_text or "")
        )
    result: list[PreparedExperience] = []
    for rank, slot in enumerate(candidate.slots, start=1):
        title = _exp_title(db, slot.experience_id)
        result.append(PreparedExperience(
            experience_id=slot.experience_id, sort_order=rank, title=title,
            facts=facts_by_exp.get(slot.experience_id, []),
        ))
    return result


def _compact_dict(jd_analysis) -> dict[str, Any]:
    if isinstance(jd_analysis, dict):
        return jd_analysis
    return jd_analysis.model_dump() if hasattr(jd_analysis, "model_dump") else dict(jd_analysis)


def _exp_title(db: Session, experience_id: str) -> str:
    from database.models import Experience
    exp = db.get(Experience, experience_id)
    if exp is None:
        return ""
    return exp.title or exp.role or exp.company or exp.id


# ── P3 单经历处理（纯 LLM，worker 线程执行，不触碰 DB） ──────────── #

JDAnalysisOutLike = Any


def _process_experience(
    prep: PreparedExperience,
    compact: Any,
    budget: llm_service.TaskTokenBudget,
    provider: object | None,
    run_ctx: TaskRunContext,
    progress_q: Optional["queue.Queue"] = None,
) -> GeneratedExperience:
    """同一经历内按 Fact 串行：Fact 结构化 + reason。返回结果，不写 DB。

``progress_q`` 非空时，通过线程安全队列把**已完成的 Fact**（结构化 + 绑定校验）立刻
传给编排主线程发布 fact.done，且 reason 单独以 reason.delta 发布——使"首个完整
Fact"以它真正完成的时间出现，而不是被挂到整段经历全部调用结束才统一写入（后者会
让首 Fact 计时被后续经历拉长）。不改变调用公式（仍 1+2F）、并发上限（MAX_WORKERS=2）
与任何内容/校验。队列项字面约定：
  ("fact",   experience_id, GeneratedFact)  → 主线程发 fact.done
  ("reason", experience_id, fact_id, reason) → 主线程发 reason.delta
"""
    compact_dict = _compact_dict(compact)
    facts: list[GeneratedFact] = []
    for src in prep.facts:
        run_ctx.assert_writable()  # fence + 取消信号（安全点）
        fact, _ = _fact_call(compact_dict, prep, src, budget, provider)
        # Fact（headline/body/fact_refs，已绑定+校验）在结构化调用返回即“完整”；
        # 立即发布，使“首个完整 Fact”以它真正完成时刻出现。reason 是旁侧渐进叙事，
        # 单独以 reason.delta 发布（schema：真增量流输出），不再阻塞 fact.done。
        if progress_q is not None:
            progress_q.put(("fact", prep.experience_id, GeneratedFact(
                fact_id=fact.fact_id, headline=fact.headline, body=fact.body,
                fact_refs=list(fact.fact_refs), reason="")))
        reason, _ = _reason_call(compact_dict, fact, budget, provider)
        run_ctx.assert_writable()
        if progress_q is not None:
            progress_q.put(("reason", prep.experience_id, fact.fact_id, reason))
        facts.append(GeneratedFact(
            fact_id=fact.fact_id, headline=fact.headline, body=fact.body,
            fact_refs=list(fact.fact_refs), reason=reason,
        ))
    return GeneratedExperience(
        experience_id=prep.experience_id, sort_order=prep.sort_order,
        title=prep.title, facts=facts,
    )


def _fact_call(
    compact: dict[str, Any],
    prep: PreparedExperience,
    src: PreparedFact,
    budget: llm_service.TaskTokenBudget,
    provider: object | None,
) -> tuple[TaskFactOut, llm_service.LLMCallRecord]:
    data, rec = llm_service.invoke_observed_json(
        task_fact.SYSTEM, task_fact.USER_TEMPLATE,
        max_tokens=task_core.FACT_MAX_TOKENS, budget=budget, stage="fact",
        variables={
            "compact_jd_json": _json_dumps(compact),
            "experience_json": _json_dumps({"experience_id": prep.experience_id, "title": prep.title}),
            "facts_json": _json_dumps([{"fact_id": src.fact_id, "text": src.text}]),
        },
        provider=provider,
    )
    fact = TaskFactOut.model_validate(data)
    # 绑定性门禁：experience_id / fact_id / fact_refs 必须落在已知集合内（PLAN §2.3 / Gate）
    if fact.experience_id and fact.experience_id != prep.experience_id:
        raise ContentGenerationError(
            f"Fact 输出 experience_id 越界：{fact.experience_id} != {prep.experience_id}",
            details={"expected": prep.experience_id, "got": fact.experience_id},
            stage="fact",
        )
    if not fact.fact_id:
        fact.fact_id = f"{prep.experience_id}/{_next_fact_index(compact, prep, src)}"
    allowed = {src.fact_id}
    if fact.fact_refs and not set(fact.fact_refs).issubset(allowed):
        raise ContentGenerationError(
            f"Fact 输出 fact_refs 越界：{fact.fact_refs} 不在允许集 {allowed} 内",
            details={"fact_refs": fact.fact_refs, "allowed": sorted(allowed)},
            stage="fact",
        )
    return fact, rec


def _next_fact_index(compact, prep, src) -> int:
    # 粗略序号：保证 fact_id 形如 {exp}/{n} 唯一即可（正式由 orchestrator 统一赋值）
    import hashlib
    return (int(hashlib.sha1(f"{prep.experience_id}:{src.fact_id}".encode()).hexdigest(), 16) % 9000) + 1


def _reason_call(
    compact: dict[str, Any],
    fact: TaskFactOut,
    budget: llm_service.TaskTokenBudget,
    provider: object | None,
) -> tuple[str, llm_service.LLMCallRecord]:
    """P3 旁侧 reason：一次逻辑调用返回 delta+done，delta 即该 fact 的完整理由文本。"""
    data, rec = llm_service.invoke_observed_json(
        task_reason.SYSTEM, task_reason.USER_TEMPLATE,
        max_tokens=task_core.REASON_MAX_TOKENS, budget=budget, stage="reason",
        variables={
            "position": compact.get("position", ""),
            "fact_id": fact.fact_id,
            "fact_headline": fact.headline,
            "fact_body": fact.body,
            "reason_so_far": "",
        },
        provider=provider,
    )
    out = TaskReasonOut.model_validate(data)
    if out.fact_id and out.fact_id != fact.fact_id:
        raise ContentGenerationError(
            f"reason 绑定越界：{out.fact_id} != {fact.fact_id}",
            details={"expected": fact.fact_id, "got": out.fact_id}, stage="reason",
        )
    return (out.delta or ""), rec


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


# ── 主编排入口 ──────────────────────────────────────────────────── #

MAX_WORKERS = 2


def generate_task(
    db: Session,
    task,
    run_ctx: TaskRunContext,
    input_revision: dict[str, Any],
    *,
    budget: Optional[llm_service.TaskTokenBudget] = None,
    provider: object | None = None,
    selector: Optional[Callable[[Any], list[PreparedExperience]]] = None,
    assembler: Optional[Callable[[GenerationSummary, Any], tuple[bool, dict[str, Any]]]] = None,
    preload: Optional[dict[str, list[dict[str, Any]]]] = None,
) -> GenerationSummary:
    """执行一次生成运行（应在 run_generation 的专用 worker 线程中调用，独占 db session）。

    ``preload``：experience_id → 该经历已完成的 Fact 视图列表（来自源 FAILED 任务 SUCCEEDED 子任务）。
    续试任务把已完成的经历**零调用复用**（直接入 P3 合并、子任务置 SUCCEEDED），只对未完成经历调用模型
    ——即「只重试失败范围，已完成结果被复用，调用只发生在失败范围」。PLAN 不要求沿用同一 task_id。
    """
    budget = budget or llm_service.TaskTokenBudget(task_core.TASK_LLM_COMPLETION_LIMIT)
    repo = None
    from services.task_repository import TaskRepository
    repo = TaskRepository(db)

    run_ctx.assert_writable()

    # ── P1 紧凑 JD ──
    from database.models import InputRevision
    rev = (db.query(InputRevision)
           .filter_by(task_id=task.task_id, revision=input_revision.get("revision", 0))
           .first())
    jd_text = (rev.jd if rev is not None else "").strip() or (input_revision.get("jd") or "")

    # ── V2.2.0 R3-§6 并行预嵌入 JD（首 Fact ≤15s 门禁） ──────────
    # P2 的 JD 查询向量原在 select_evidence 内串行 resolve（~4.7s）。这里在其上游
    # P1（JD chat ~6.5s）期间用后台线程对原始 jd_text 预嵌入，两者并行重叠，让 P2
    # 直接复用预计算结果，从而把"首向量化"移出首 Fact 串行临界路径。best-effort：
    # 线程异常/超时/无 Key 一律回退串行 resolve，行为与优化前一致，绝不改变结果正确性。
    _jd_box: dict[str, list[float]] = {}
    if (jd_text and settings.ARK_API_KEY):
        try:
            from services import embedding_service as _emb_svc

            def _preembed_jd() -> None:
                try:
                    _jd_box["vector"] = _emb_svc._embed_text(jd_text)
                except BaseException:  # noqa: BLE001 - 并行增强失败不影响主链
                    _jd_box["error"] = True

            _jd_thread = threading.Thread(target=_preembed_jd, name="jdPreembed",
                                          daemon=True)
            _jd_thread.start()
        except BaseException:  # noqa: BLE001
            _jd_thread = None
    else:
        _jd_thread = None

    compact, jd_rec = jd_analyzer.analyze_jd_task(jd_text, budget=budget, provider=provider)
    compact_dict = _compact_dict(compact)
    llm_records: list[dict[str, Any]] = [jd_rec.to_dict()]

    # 收敛并行预嵌入线程（已在 P1 期间完成，join 仅兜底短等），拿回 JD 查询向量。
    if _jd_thread is not None:
        try:
            _jd_thread.join(timeout=1.0)
        except BaseException:  # noqa: BLE001
            pass
    jd_query_vector = _jd_box.get("vector")

    repo.save_snapshot(task, phase="P1", payload={
        "compact_jd": compact_dict, "stage": "P1.compact_jd",
    })
    repo.append_event(task, input_revision=input_revision.get("revision", 0),
                      event_type="jd.done", phase="P1", payload={"position": compact_dict.get("position", "")})

    run_ctx.assert_writable()

    # ── P2 候选准备（selector 注入或默认选材） ──
    prepared = (selector(compact) if selector is not None
                else default_selector(db, compact, jd_query_vector=jd_query_vector))

    # 续试（只重试失败范围）：preload 命中的经历零调用复用；未命中者进入 P3 worker 重跑。
    preload = preload or {}

    def _reuse_experience(prep: PreparedExperience) -> Optional[GeneratedExperience]:
        """由 preload 复原已完成的经历（无任何模型调用）。"""
        facts = preload.get(prep.experience_id)
        if not facts:
            return None
        gen_facts = [
            GeneratedFact(fact_id=f.get("fact_id", ""), headline=f.get("headline", ""),
                          body=f.get("body", ""), fact_refs=list(f.get("fact_refs") or []),
                          reason=f.get("reason", ""))
            for f in facts
        ]
        return GeneratedExperience(experience_id=prep.experience_id,
                                   sort_order=prep.sort_order, title=prep.title,
                                   facts=gen_facts)

    # 初始化子任务；preload 命中的直接置 SUCCEEDED，其余待 P3 worker 写入。
    for prep in prepared:
        if _reuse_experience(prep) is not None:
            repo.upsert_subtask(task, prep.experience_id, sort_order=prep.sort_order)
            repo.update_subtask(task, prep.experience_id,
                                status=task_core.SubtaskStatus.SUCCEEDED,
                                fact_results=preload[prep.experience_id])
        else:
            repo.upsert_subtask(task, prep.experience_id, sort_order=prep.sort_order)
    # 续试中 preload 命中的已完成子任务立即提交：即使本轮其余经历再失败，复用的已完成
    # 结果也已持久化，不被后续 rollback 回滚（与 V220-G02 partial 保留一致）。
    if preload:
        db.commit()
    repo.save_snapshot(task, phase="P2", payload={
        "compact_jd": compact_dict,
        "experiences": [{"experience_id": e.experience_id, "sort_order": e.sort_order,
                         "title": e.title, "fact_count": len(e.facts)} for e in prepared],
        "stage": "P2.selected",
        "reused_experiences": sorted(k for k in preload if k in {e.experience_id for e in prepared}),
    })

    run_ctx.assert_writable()

    # ── P3 Fact＋reason（经历并发 2，经历内 Fact 串行，逐 Fact 渐进发布） ──
    merged: list[GeneratedExperience] = []
    # 续试：先并入零调用复用的已完成经历，再只对未完成的 prepared 起 worker。
    todo: list[PreparedExperience] = []
    for prep in prepared:
        reused = _reuse_experience(prep)
        if reused is not None:
            merged.append(reused)
        else:
            todo.append(prep)
    if todo:
        workers = min(len(todo), MAX_WORKERS)
        progress_q: queue.Queue = queue.Queue()

        def _drain_progress() -> None:
            """把已完成的 Fact/reason 事件从线程安全队列转到主线程 DB（单写者，seq 单调）。

            队列项为两元字面（见 ``_process_experience``）：
              ("fact", exp_id, gf)         → fact.done（首个完整 Fact 以其真实完成时刻发布）
              ("reason", exp_id, fact_id, r) → reason.delta（旁侧渐进叙事，紧随对应 fact）
            """
            while True:
                try:
                    kind = progress_q.get_nowait()
                except queue.Empty:
                    return
                if kind[0] == "fact":
                    _exp_id, gf = kind[1], kind[2]
                    repo.append_event(task, input_revision=input_revision.get("revision", 0),
                                      event_type="fact.done", phase="P3",
                                      payload={"experience_id": _exp_id,
                                               "fact_id": gf.fact_id, "headline": gf.headline,
                                               "body": gf.body, "fact_refs": list(gf.fact_refs)})
                elif kind[0] == "reason":
                    _exp_id, _fact_id, _reason = kind[1], kind[2], kind[3]
                    repo.append_event(task, input_revision=input_revision.get("revision", 0),
                                      event_type="reason.delta", phase="P3",
                                      payload={"fact_id": _fact_id, "delta": _reason})

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="taskGen") as ex:
            futures = {ex.submit(_process_experience, prep, compact, budget, provider,
                                 run_ctx, progress_q): prep
                       for prep in todo}
            pending = set(futures)
            try:
                while pending:
                    _drain_progress()  # a) 首完整 Fact 以其真实完成时刻发布（不等整段经历）
                    newly = [f for f in pending if f.done()]
                    for fut in newly:  # b) 收集已完成经历；事件已在 a) 逐 Fact 发布
                        pending.discard(fut)
                        prep = futures[fut]
                        res = fut.result()  # 取消/失败在此抛出
                        repo.update_subtask(
                            task, prep.experience_id, status=task_core.SubtaskStatus.SUCCEEDED,
                            fact_results=[_fact_result_view(f) for f in res.facts],
                        )
                        merged.append(res)
                        # V220-G02 partial 保留：逐已完成子任务提交，使单任务中途失败后
                        # 已完成经历/Fact/事件已被持久化，不被外层 rollback 回滚（供范围重试复用、
                        # 并在 FAILED 面板如实呈现"已完成范围保留"）。单一写者线程，无并发竞争。
                        db.commit()
                    if pending and not newly:
                        time.sleep(0.02)
            except BaseException:
                # 同任务下将未完成子任务标 FAILED（最终态由 run_generation 决定）
                try:
                    for prep in todo:
                        if repo is not None:
                            repo.update_subtask(task, prep.experience_id,
                                                status=task_core.SubtaskStatus.FAILED,
                                                failure_code="_P3_ABORTED")
                except Exception:
                    pass
                raise
            _drain_progress()  # 兜底：经历全完成后榨干最后几格队列（无 Fact 事件被挂起）
    else:
        # 无待重跑经历（preload 已覆盖全部，或无条件材料不足已在上层处理）：仍须校验是否有产出。
        if not merged:
            repo.save_snapshot(task, phase="P3", payload={"stage": "P3.no_retry_experiences",
                                                           "experiences": []})
            raise ContentGenerationError("续试任务无待重跑经历，且无已复用产出", stage="P2")
    # 完成顺序不得改变模板顺序：按冻结 sort_order 合并
    merged.sort(key=lambda x: x.sort_order)

    reasons_payload: dict[str, str] = {}
    for exp in merged:
        for f in exp.facts:
            reasons_payload[f.fact_id] = f.reason
    # 权威快照始终保留可恢复的 P1–P3 业务结果（覆盖式，但 P4 刷新不得丢结果/reason 文本）
    recoverable = {
        "compact_jd": compact_dict,
        "experiences": [_generated_view(e) for e in merged],
        "reasons": reasons_payload,
    }
    repo.save_snapshot(task, phase="P3", payload={**recoverable, "stage": "P3.done"})

    summary = GenerationSummary(compact_jd=compact_dict, experiences=merged, phase="P3",
                                llm_records=llm_records, completion_tokens=budget.used)
    run_ctx.assert_writable()

    # ── P4 装配（T07 接入真实 DOCX/PDF；默认仅登记状态） ──
    if assembler is not None:
        assembled, artifacts = assembler(summary, compact)
        summary.assembled = assembled
        summary.artifacts = artifacts or {}
        repo.save_snapshot(task, phase="P4", payload={**recoverable, "stage": "P4.assembled",
                                                       "assembled": assembled,
                                                       "artifacts": summary.artifacts})
        summary.phase = "P4"
    else:
        repo.save_snapshot(task, phase="P4", payload={**recoverable, "stage": "P4.pending",
                                                       "assembled": False})
        summary.phase = "P4"
    return summary


def _fact_result_view(f: GeneratedFact) -> dict[str, Any]:
    return {"fact_id": f.fact_id, "headline": f.headline, "body": f.body,
            "fact_refs": list(f.fact_refs), "reason": f.reason}


def _generated_view(e: GeneratedExperience) -> dict[str, Any]:
    return {"experience_id": e.experience_id, "sort_order": e.sort_order, "title": e.title,
            "facts": [{**f.__dict__, "fact_refs": list(f.fact_refs)} for f in e.facts]}