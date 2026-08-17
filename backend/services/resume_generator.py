"""简历生成（AI 调用方）。

边界约束：不 import langchain；通过 llm_service 间接调用 LLM。
"""
import json

from prompts import resume_generate
from services import llm_service


def generate_resume(jd_analysis: dict, experiences: list) -> str:
    """基于 JD 分析 + 命中经历，生成 Markdown 简历正文。"""
    return llm_service.chat(
        resume_generate.SYSTEM,
        resume_generate.USER_TEMPLATE,
        jd_analysis=json.dumps(jd_analysis, ensure_ascii=False, indent=2),
        experiences=json.dumps(experiences, ensure_ascii=False, indent=2),
    )
