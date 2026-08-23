"""V1.5.0 T5：受约束改写（PLAN §4.4 / §5.3 / T5）。

职责：
- rewrite_with_evidence：基于 SelectedEvidenceSet 做受约束改写
- LLM 只接收目标岗位 + 入选经历 + 表达侧重 + 可使用事实
- 每条 bullet 返回 fact_refs；越界引用被拒绝并告警
- 材料不足返回明确 insufficient 状态
- 不重选经历，不写回事实库

边界（PLAN §4.4 / §5.3）：
- LLM 不得重选经历、加入未入选经历、生成新事实或写回 Fact
- 越界引用（未选/跨经历/版本不匹配）必须拒绝并告警
- Builder 只做确定性装配，不执行第二套 JD 相关性判断
"""
from __future__ import annotations

import json
import logging
from typing import Callable, Optional

from sqlalchemy.orm import Session

from api.schemas import GeneratedExperienceItemV15, GeneratedResumeContentV15
from core.errors import ContentGenerationError, LLMOutputInvalidError
from database.models import Experience, Fact
from prompts import constrained_rewrite as prompt
from services.selection_service import (
    CandidateExperienceSet,
    SelectedEvidenceSet,
)

logger = logging.getLogger(__name__)


def _build_evidence_payload(
    session: Session,
    candidate_set: CandidateExperienceSet,
    evidence_set: SelectedEvidenceSet,
) -> tuple[list[dict], dict[str, set[str]]]:
    """构造 LLM prompt 用的入选经历 + 可使用事实。

    返回 (payload, allowed_refs_per_exp)。
    payload 用于 prompt；allowed_refs_per_exp 用于后续 fact_refs 边界校验。
    """
    evidence_by_exp = {e.experience_id: e for e in evidence_set.entries}
    allowed: dict[str, set[str]] = {}

    payload: list[dict] = []
    for slot in candidate_set.slots:
        exp = session.get(Experience, slot.experience_id)
        if exp is None:
            logger.warning("rewrite: experience not found %s, skip", slot.experience_id)
            continue
        entry = evidence_by_exp.get(slot.experience_id)
        fact_ids = {r.fact_id for r in (entry.fact_refs if entry else [])}
        allowed[slot.experience_id] = fact_ids

        facts_payload: list[dict] = []
        if entry:
            for ref in entry.fact_refs:
                fact = session.get(Fact, ref.fact_id)
                if fact is None:
                    continue
                facts_payload.append({
                    "fact_id": fact.fact_id,
                    "text": fact.text or "",
                    "fact_type": (fact.fact_type.value if fact.fact_type else ""),
                })

        payload.append({
            "experience_id": exp.id,
            "slot_type": slot.slot_type,
            "title": exp.title or "",
            "company": exp.company or "",
            "role": exp.role or "",
            "time": exp.time or "",
            "expression_focus": (entry.expression_focus if entry else ""),
            "usable_facts": facts_payload,
        })
    return payload, allowed


def rewrite_with_evidence(
    session: Session,
    candidate_set: CandidateExperienceSet,
    evidence_set: SelectedEvidenceSet,
    jd_analysis: dict,
    *,
    strict: bool = True,
    llm: Optional[Callable] = None,
) -> tuple[GeneratedResumeContentV15, list[str]]:
    """基于 SelectedEvidenceSet 做受约束改写（PLAN §4.4 / T5）。

    返回 (GeneratedResumeContentV15, warnings)。

    校验（T5 退出条件）：
    - experience_id 必须在入选名单内（LLM 不得重选/新增/替换）
    - 每条 bullet 的 fact_refs 必须属于该经历的可用事实集合（越界拒绝+告警）
    - 材料不足返回 insufficient=true（不用通用空话补齐）

    Raises:
      - LLMOutputInvalidError：LLM 结构化输出连续失败（strict=True）
      - ContentGenerationError：入选名单为空或 SQL 中全部缺失
    """
    selected_ids = set(candidate_set.selected_ids())
    if not selected_ids:
        raise ContentGenerationError(
            "入选经历名单为空，无法进行受约束改写",
            stage="content_generation",
        )

    payload, allowed_refs_per_exp = _build_evidence_payload(
        session, candidate_set, evidence_set,
    )
    if not payload:
        raise ContentGenerationError(
            "入选经历在 SQL 中全部缺失，无法进行受约束改写",
            stage="content_generation",
        )

    target_position = (jd_analysis.get("position") or "").strip()
    evidence_json = json.dumps(payload, ensure_ascii=False, indent=2)

    warnings: list[str] = []

    # ── LLM 调用 ──
    try:
        if llm is not None:
            structured = llm(
                prompt.SYSTEM,
                prompt.USER_TEMPLATE,
                GeneratedResumeContentV15,
                target_position=target_position,
                evidence_json=evidence_json,
            )
        else:
            from services import llm_service
            structured = llm_service.chat_structured(
                prompt.SYSTEM,
                prompt.USER_TEMPLATE,
                schema=GeneratedResumeContentV15,
                strict=strict,
                target_position=target_position,
                evidence_json=evidence_json,
            )
    except LLMOutputInvalidError as e:
        e.stage = "content_generation"
        raise

    if not isinstance(structured, GeneratedResumeContentV15):
        structured = GeneratedResumeContentV15.model_validate(structured)

    # ── 校验：experience_id 边界 + fact_refs 边界（PLAN §4.4 / T5 退出条件） ──
    filtered: list[GeneratedExperienceItemV15] = []
    for item in structured.experiences:
        if item.experience_id not in selected_ids:
            warnings.append(
                f"拒绝越界经历 experience_id={item.experience_id}"
                f"（不在第一层入选名单，LLM 不得重选经历）"
            )
            continue
        allowed = allowed_refs_per_exp.get(item.experience_id, set())
        clean_bullets = []
        for b in item.bullets:
            bad = [r for r in (b.fact_refs or []) if r not in allowed]
            if bad:
                warnings.append(
                    f"拒绝越界 fact_refs {bad}"
                    f"（experience_id={item.experience_id}，不在该经历可用事实集合）"
                )
                keep = [r for r in (b.fact_refs or []) if r in allowed]
                b = b.model_copy(update={"fact_refs": keep})
            clean_bullets.append(b)
        item = item.model_copy(update={"bullets": clean_bullets})
        filtered.append(item)

    # 入选但 LLM 未返回 → 标记材料不足（不补造，PLAN §4.4）
    returned_ids = {i.experience_id for i in filtered}
    for sid in selected_ids - returned_ids:
        warnings.append(
            f"入选经历 experience_id={sid} 未在 LLM 输出中出现（标记材料不足，不补造）"
        )
        filtered.append(GeneratedExperienceItemV15(
            experience_id=sid,
            bullets=[],
            insufficient=True,
            insufficient_reason="LLM 未返回该经历的改写结果",
        ))

    content = GeneratedResumeContentV15(experiences=filtered)
    logger.info(
        "rewrite_with_evidence: entries=%d warnings=%d",
        len(content.experiences), len(warnings),
    )
    return content, warnings
