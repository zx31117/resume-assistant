"""V1.3 T3 ResumeContentGenerator。

职责：
- 输入：JDAnalysisOut + SQL 命中 Experience 列表（已经 RAG 筛选过的 TopK）
- 调用 LLM（strict 模式）生成 GeneratedResumeContent（bullets per experience_id）
- strict 校验：
  - experience_id 必须在命中集合内（未知 id → warning 并丢弃）
  - 不允许 AI 修改事实字段（本模块不接收事实字段，天然隔离）
  - LLM 输出全部失败 → 抛 LLMOutputInvalidError（上层终止）
  - 返回的 bullets 为空 → 让上层 ResumeBuilder 负责回退 SQL description/achievements
- PLAN §3.3：AI 只能生成已有经历的 bullets，不生成个人总结/自我评价
"""
from __future__ import annotations

import json
import logging
from typing import Sequence

from api.schemas import (
    GeneratedExperienceItem,
    GeneratedResumeContent,
    JDAnalysisOut,
)
from core.errors import ContentGenerationError, LLMOutputInvalidError
from database import models
from prompts import resume_content_generate
from services import llm_service

logger = logging.getLogger(__name__)


def _experiences_for_prompt(exps: Sequence[models.Experience]) -> list[dict]:
    """构造 prompt 用的经历列表（事实字段只读地交给 prompt，作为真实性锚点）。

    AI 只能看这些事实，但输出中不允许重复这些事实字段（只回 experience_id + bullets）。
    """
    result = []
    for exp in exps:
        result.append({
            "experience_id": exp.id,
            "type": exp.type or "",
            "title": exp.title or "",
            "company": exp.company or "",
            "role": exp.role or "",
            "time": exp.time or "",
            "raw_description": exp.description or "",
            "raw_achievements": list(exp.achievements or []),
            "skills": list(exp.skills or []),
        })
    return result


def generate_content(
    jd_analysis: JDAnalysisOut,
    matched_experiences: Sequence[models.Experience],
    *,
    strict: bool = True,
) -> tuple[GeneratedResumeContent, list[str]]:
    """生成带 experience_id 的结构化简历内容。

    返回：(GeneratedResumeContent, warnings)

    Raises:
      - LLMOutputInvalidError：LLM 结构化输出连续失败（strict=True）
      - ContentGenerationError：没有任何一条有效经历在匹配集合内
    """
    if not matched_experiences:
        raise ContentGenerationError(
            "matched_experiences 为空，无法生成简历内容",
            stage="content_generation",
        )

    matched_ids: set[str] = {exp.id for exp in matched_experiences}
    jd_json = json.dumps(jd_analysis.model_dump(), ensure_ascii=False, indent=2)
    exps_json = json.dumps(_experiences_for_prompt(matched_experiences), ensure_ascii=False, indent=2)

    warnings: list[str] = []

    # ── LLM 调用（strict 模式） ──
    try:
        structured: GeneratedResumeContent = llm_service.chat_structured(
            resume_content_generate.SYSTEM,
            resume_content_generate.USER_TEMPLATE,
            schema=GeneratedResumeContent,
            strict=strict,
            jd_analysis_json=jd_json,
            experiences_json=exps_json,
        )
    except LLMOutputInvalidError as e:
        e.stage = "content_generation"
        raise

    # ── T3 strict 校验：experience_id 必须在命中集合内 ──
    filtered_experiences: list[GeneratedExperienceItem] = []
    for item in structured.experiences:
        if item.experience_id not in matched_ids:
            warnings.append(
                f"丢弃未知 experience_id={item.experience_id}（不在本次 RAG 命中集合内）"
            )
            continue
        filtered_experiences.append(item)

    valid_ids = {e.experience_id for e in filtered_experiences}
    for eid in matched_ids - valid_ids:
        warnings.append(
            f"命中 experience_id={eid} 未在 AI 输出中出现 bullets（将回退 SQL description+achievements）"
        )

    content = GeneratedResumeContent(
        experiences=filtered_experiences,
    )
    return content, warnings
