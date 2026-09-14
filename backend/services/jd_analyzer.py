"""JD 分析（AI 调用方）。

V1.1：7 字段输出 + 结构化输出。
V1.3：strict failure 生效，position 为空抛 JDValidationError。
V2.2.0（T6b）：新增 analyze_jd_task —— 任务管线 P1 紧凑 JD 结构化，
  走 llm_service.invoke_observed_json（temperature=0 / json_object / minimal），
  受单任务 Token 预算与 JD_COMPACT_MAX_TOKENS 门禁约束。

边界约束：不 import langchain；通过 llm_service 间接调用 LLM。
"""
from __future__ import annotations

from api.schemas import JDAnalysisOut
from core import task as task_core
from core.errors import JDValidationError
from prompts import jd_analyze, task_compact_jd
from services import llm_service


def analyze_jd(jd_text: str, *, strict: bool = True) -> JDAnalysisOut:
    """将 JD 文本交给 LLM，返回结构化岗位需求（7 字段）。

    strict=True（V1.3 默认）：
      - LLM 结构化输出失败 → 抛 LLMOutputInvalidError；
      - 返回 position 为空 → 抛 JDValidationError。
    strict=False：保留 V1.1 行为，失败时返回空实例，兼容旧调用方。

    向后兼容：在返回对象的 model_dump() 里仍能得到 requirements=required_skills。
    """
    if strict:
        result = llm_service.chat_structured(
            jd_analyze.SYSTEM,
            jd_analyze.USER_TEMPLATE,
            schema=JDAnalysisOut,
            strict=True,
            jd_text=jd_text,
        )
        if not (result.position or "").strip():
            raise JDValidationError(
                "JD 分析结果 position（岗位名称）为空，无法继续简历生成",
                details={"jd_text_length": len(jd_text or "")},
            )
    else:
        result = llm_service.chat_structured(
            jd_analyze.SYSTEM,
            jd_analyze.USER_TEMPLATE,
            schema=JDAnalysisOut,
            default=JDAnalysisOut(),
            jd_text=jd_text,
        )
    return result


def analyze_jd_task(
    jd_text: str,
    *,
    budget: llm_service.TaskTokenBudget,
    provider: object | None = None,
) -> tuple[JDAnalysisOut, llm_service.LLMCallRecord]:
    """任务管线 P1：紧凑 JD 结构化（PLAN §2.1 / §2.2 / T06b）。

    - 走 invoke_observed_json：temperature=0、json_object、minimal、3-attempt 门禁；
    - budget.reserve(JD_COMPACT_MAX_TOKENS) 发起前占用，完成后 refund未用额度；
    - 单次 attempt completion ≤ JD_COMPACT_MAX_TOKENS（1024，允许区间 512–2048）；
    - 原始 JD 原文不在此截断——按冻结 InputRevision 原样保存。

    Returns:
        (JDAnalysisOut, LLMCallRecord)：结构化结果 + 调用/Token 观测记录。
    Raises:
        JDValidationError: position 为空；
        LLMOutputInvalidError: 连续失败；
        TaskCapacityError: 任务 Token 预算即将超限。
    """
    data, record = llm_service.invoke_observed_json(
        task_compact_jd.SYSTEM,
        task_compact_jd.USER_TEMPLATE,
        max_tokens=task_core.JD_COMPACT_MAX_TOKENS,
        budget=budget,
        stage="compact_jd",
        variables={"jd_text": jd_text},
        provider=provider,
    )
    result = JDAnalysisOut.model_validate(data)
    if not (result.position or "").strip():
        raise JDValidationError(
            "紧凑 JD 结果 position（岗位名称）为空，无法继续简历生成",
            details={"jd_text_length": len(jd_text or "")},
            stage="compact_jd",
        )
    return result, record

