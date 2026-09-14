"""Prompt：P3 reason 真增量流（PLAN §2.1 / A06 / T6b）。

旁侧对同一 fact_id 流式输出"选择该条目的理由"。单次 attempt completion
≤ REASON_MAX_TOKENS(256)。为满足"reason 真增量"与快照"保存当前完整文本"，
本 prompt 让 LLM 返回相对已输出部分的 `delta`（新增文本）与 `done`（是否结束）。
调用方把 delta 追加到该 fact 的 reason 累积文本；断线重连不重放、不回放思维链。

边界：reason 是面向用户的选取理由，不是模型私有思维链；must bind 同一 fact_id。
"""
SYSTEM = (
    "你是一位资深简历顾问。任务：针对上一条已生成的简历条目，流式输出一条"
    "面向用户的选取理由，解释为何该条目契合目标岗位。避免暴露模型内部思维过程，"
    "行文面向求职者，简洁有据。只输出 JSON，不要解释。"
)

USER_TEMPLATE = """目标岗位关键词：{position}
获得条目（fact_id={fact_id}）：
- headline：{fact_headline}
- body：{fact_body}
已输出的理由文本（可能为空）：
{reason_so_far}

请继续（增量补充）面向用户的选取理由。若理由已完整，设 done=true。
输出格式（严格 JSON）：
{{
  "fact_id": "{fact_id}",
  "delta": "本次新增的理由文本（追加在已输出之后，可为空串）",
  "done": true
}}

重要约束：
1. fact_id 必须等于上方的 fact_id，不得改动；
2. delta 为相对已输出文本的增量，不得重复已输出的内容；
3. 理由须面向用户、简洁、有依据，不编造不存在的成果；
4. 理由已完整时 done=true；不要输出解释文字，只输出 JSON 对象。
"""