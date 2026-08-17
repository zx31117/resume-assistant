"""文本预处理 + 简历章节切分（V1.1 新增）。

边界约束：纯业务/工具层，不调用 AI，不 import langchain。

设计原则：程序负责确定结构，AI 负责理解内容。
- 清理多余空格、空行、特殊字符
- 按关键词识别简历章节（教育/工作/项目/技能）
- 输出结构化章节列表，供 experience_extractor 分段调用 LLM
"""
import re
from typing import List

# 章节关键词映射（按优先级排列，先匹配先归属）
_SECTION_KEYWORDS: List[tuple[str, List[str]]] = [
    ("education", ["教育背景", "教育经历", "education background", "education"]),
    ("work", ["工作经历", "实习经历", "professional experience", "work experience", "工作与实习"]),
    ("project", ["项目经历", "项目经验", "project experience", "projects"]),
    ("skill", ["技能", "专业技能", "技术栈", "skills", "technical skills"]),
]


def clean_text(raw: str) -> str:
    """清理简历文本：合并多余空格、去除连续空行、移除特殊控制字符。"""
    # 移除 Unicode 控制字符（保留换行和制表符）
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", raw)
    # 合并连续空格为单个（保留缩进行）
    text = re.sub(r"[ \t]{2,}", " ", text)
    # 去除行尾空格
    text = re.sub(r" +\n", "\n", text)
    # 连续空行压缩为最多 1 个
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _match_section_type(line: str) -> str | None:
    """判断某行是否为章节标题，返回 section_type 或 None。"""
    lower = line.strip().lower()
    if not lower or len(lower) > 50:
        return None
    for sec_type, keywords in _SECTION_KEYWORDS:
        for kw in keywords:
            if kw in lower:
                return sec_type
    return None


def split_sections(cleaned: str) -> dict:
    """将清理后的文本切分为章节。

    返回结构：
    {
        "cleaned_text": "...",
        "sections": [{"type": "work", "title": "工作经历", "content": "..."}],
        "unmatched": "..."
    }
    """
    lines = cleaned.split("\n")
    sections: List[dict] = []
    unmatched_lines: List[str] = []

    current_type: str | None = None
    current_title: str = ""
    current_lines: List[str] = []

    def _flush():
        nonlocal current_type, current_title, current_lines
        if current_type is not None and current_lines:
            content = "\n".join(current_lines).strip()
            if content:
                sections.append({
                    "type": current_type,
                    "title": current_title,
                    "content": content,
                })
        current_type = None
        current_title = ""
        current_lines = []

    for line in lines:
        sec_type = _match_section_type(line)
        if sec_type is not None:
            # 遇到新章节标题，先保存上一段
            _flush()
            current_type = sec_type
            current_title = line.strip()
            current_lines = []
        elif current_type is not None:
            # 当前章节内容
            current_lines.append(line)
        else:
            # 尚未进入任何章节的自由文本
            unmatched_lines.append(line)

    _flush()

    return {
        "cleaned_text": cleaned,
        "sections": sections,
        "unmatched": "\n".join(unmatched_lines).strip(),
    }


def preprocess(raw_text: str) -> dict:
    """文本预处理入口：清理 → 章节切分。"""
    cleaned = clean_text(raw_text)
    return split_sections(cleaned)
