"""Prompt：分析岗位描述(JD)，提取 7 字段结构化岗位需求（V1.1）。"""

SYSTEM = "你是一位资深招聘分析师。任务：分析岗位描述(JD)，提取结构化岗位需求。"

USER_TEMPLATE = """分析以下岗位描述，输出 JSON，包含字段：
- position: 岗位名称
- industry: 所属行业
- required_skills: 硬性技能/能力要求数组 — 每项必须是原子化的技能名称（如"Python"、"需求分析"、"大模型"），禁止输出完整句子
- preferred_skills: 加分技能数组（非硬性要求）— 同样输出原子化技能名称
- responsibilities: 岗位职责数组 — 每项可包含完整描述
- keywords: 检索关键词数组（技术或领域关键词）— 原子化术语
- experience_preferences: 经历偏好数组（指导简历经历选择，如"优先展示 AI 项目"）

重要规则：
- required_skills 和 preferred_skills 必须拆分为独立的技能名，不要保留完整句子
- 示例："计算机科学、人工智能等相关专业" → ["计算机科学", "人工智能"]
- 示例："了解大模型原理、长期记忆机制" → ["大模型", "长期记忆机制"]
- 示例："具备需求文档撰写、原型图绘制能力" → ["需求文档撰写", "原型图绘制"]

输出格式：{{"position": "", "industry": "", "required_skills": [], "preferred_skills": [], "responsibilities": [], "keywords": [], "experience_preferences": []}}
只输出 JSON，不要解释。

岗位描述：
{jd_text}
"""
