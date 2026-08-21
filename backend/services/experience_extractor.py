"""经历提取（AI 调用方）。

V1.1：文本预处理 → 章节切分 → 分段 LLM 提取 → 合并去重。
设计原则：程序负责确定结构，AI 负责理解内容。

边界约束：不 import langchain；通过 llm_service 间接调用 LLM。
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from api.schemas import ExperienceExtractionResult
from prompts import experience_extract
from services import llm_service, text_preprocessor

logger = logging.getLogger(__name__)

# 单段最大字符数（超过则截断，控制 LLM 输入长度）
_MAX_SECTION_CHARS = 1000


def extract_experiences(resume_text: str) -> List[dict]:
    """将简历原始文本预处理后分段提取，返回结构化经历列表。"""
    preprocessed = text_preprocessor.preprocess(resume_text)
    sections = preprocessed["sections"]
    unmatched = preprocessed.get("unmatched", "")

    # 没有识别到章节时，回退到全文处理
    if not sections:
        sections = [{"type": "resume", "title": "简历全文", "content": resume_text[:5000]}]
    elif unmatched:
        # 未匹配的自由文本也作为一段处理
        sections.append({"type": "resume", "title": "其他信息", "content": unmatched[:2000]})

    # 并发处理各章节
    all_experiences: List[dict] = []
    with ThreadPoolExecutor(max_workers=min(4, len(sections))) as executor:
        futures = {
            executor.submit(_extract_section, sec): sec
            for sec in sections
        }
        for future in as_completed(futures):
            sec = futures[future]
            try:
                all_experiences.extend(future.result())
            except Exception as e:
                logger.warning(f"章节提取失败({sec.get('title', '')}): {e}")

    # 去重：按 raw_text 去重，保留第一次出现
    seen: set[str] = set()
    deduped: List[dict] = []
    for exp in all_experiences:
        key = (exp.get("raw_text", "") or exp.get("title", "")).strip()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(exp)

    return deduped


def _extract_section(section: dict) -> List[dict]:
    """对单个章节调用 LLM 提取经历。"""
    sec_type = section.get("type", "resume")
    content = section.get("content", "")[:_MAX_SECTION_CHARS]

    result = llm_service.chat_structured(
        experience_extract.SYSTEM,
        experience_extract.USER_TEMPLATE,
        schema=ExperienceExtractionResult,
        default=ExperienceExtractionResult(),
        section_type=sec_type,
        section_content=content,
    )
    return [exp.model_dump() for exp in result.experiences]
