"""Prompt：P1 紧凑 JD 结构化（PLAN §2.1 / §2.2 / T6b）。

任务管线专用：temperature=0、response_format=json_object、
reasoning_effort=minimal，单次 HTTP attempt 的 completion token 上限为
JD_COMPACT_MAX_TOKENS（1024）。输出与 JDAnalysisOut 同构（7 字段），
但要求紧凑、技能名原子化，便于后续 P3 的 Fact/reason 阶段直接消费。

原始 JD 原文不由本 prompt 截断保存——原文按冻结 InputRevision 完整保存。
"""
SYSTEM = (
    "你是一位资深招聘分析师。任务：将岗位描述(JD)压缩为紧凑、结构化的岗位需求，"
    "供后续简历条目生成直接消费。要求输出原子化技能名，禁止输出完整句子。"
    "只输出 JSON，不要解释。"
)

USER_TEMPLATE = """请把以下岗位描述压缩为紧凑结构化岗位需求，输出 JSON，包含字段：
- position: 岗位名称
- industry: 所属行业
- required_skills: 硬性技能/能力要求数组 — 每项必须是原子化技能名（如"Python"、"需求分析"、"大模型"），禁止完整句子
- preferred_skills: 加分技能数组 — 同样原子化
- responsibilities: 岗位职责数组 — 每项可含完整描述
- keywords: 检索/匹配关键词数组 — 原子化术语
- experience_preferences: 经历偏好数组（指导经历选择，如"优先展示 AI 项目"）

重要规则：
- 拆分为独立技能名，不要保留完整句子；"计算机科学、人工智能等相关专业" → ["计算机科学", "人工智能"]
- 输出需紧凑，控制篇幅，务必在 completion token 上限内完成

输出格式：{{"position": "", "industry": "", "required_skills": [], "preferred_skills": [], "responsibilities": [], "keywords": [], "experience_preferences": []}}

岗位描述：
{jd_text}
"""