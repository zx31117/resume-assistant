"""JD 分析（AI 调用方）。

V1.1：7 字段输出 + 结构化输出。
V1.3：strict failure 生效，position 为空抛 JDValidationError。

边界约束：不 import langchain；通过 llm_service 间接调用 LLM。
"""
from __future__ import annotations

from api.schemas import JDAnalysisOut
from core.errors import JDValidationError
from prompts import jd_analyze
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

