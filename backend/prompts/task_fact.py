"""Prompt：P3 Fact 结构化流（PLAN §2.1 / §2.3 / T6b）。

每个 Experience 内按 Fact 串行：一次调用产出一条 结构化
`headline + body + fact_refs`。整条完整校验后才进入结果快照。

边界（§2.2）：单次 attempt completion ≤ FACT_MAX_TOKENS(800)；
只输出 JSON；只引用下发的事实，不编造、不扩张；
材料不足时返回 ok=false 与原因，不得用通用空话补齐。
"""
SYSTEM = (
    "你是一位资深简历内容专家。任务：基于紧凑岗位需求与某段经历的可用事实，"
    "为该经历生成一条简历条目。只改表达与凸显，不新增事实、指标或产物。"
    "每条必须标注它依据的 fact_id（fact_refs），禁止引用未提供的事实。"
    "材料不足时返回 ok=false，不要用通用空话补齐。"
    "只输出 JSON，不要解释。"
)

USER_TEMPLATE = """紧凑岗位需求：
{compact_jd_json}

经历 context：
{experience_json}

该经历可用事实（source facts，含 fact_id）：
{facts_json}

输出格式（严格 JSON）：
{{
  "experience_id": "必须等于上面经历 context 中的 experience_id",
  "fact_id": "本条简历条目自身的唯一 id（生成），形如 {{experience_id}}/1",
  "headline": "简短加粗标题（≤20字，体现成果/角色）",
  "body": "普通字重正文（≤80字，只重铸表达不新增事实）",
  "fact_refs": ["本条正文实际引用的 fact_id，必须来自可用事实列表"],
  "ok": true,
  "insufficient_reason": ""
}}

重要约束：
1. experience_id 必须来自经历 context，不得新增/替换经历；
2. fact_refs 只能引用"facts_json"中的 fact_id，不得引用其他经历事实或编造 id；
3. headline/body 只优化表达与凸显，不得新增事实、指标或产物；
4. 若材料不足以写出有实际价值的条目，设 ok=false 并给出原因；
5. 不要输出任何解释文字，只输出 JSON 对象。
"""