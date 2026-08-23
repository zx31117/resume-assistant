"""LLM 调用唯一入口（LangChain 专属层）。

边界约束：
- V1.5.0：rag_service 已删除，全仓库仅本文件 import langchain。
- 业务模块通过本模块间接调用 LLM，自身不接触 LangChain。
- 豆包（火山方舟）兼容 OpenAI API，直接用 ChatOpenAI 指向 Ark endpoint。

V1.3 strict failure：
- chat_structured(strict=True) 在所有重试均失败时抛出 LLMOutputInvalidError，
  而不是兜底空模型，杜绝"空成功"。
"""
import json
import logging
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from core.config import settings

logger = logging.getLogger(__name__)

_llm = ChatOpenAI(
    model=settings.LLM_MODEL,
    api_key=settings.ARK_API_KEY,
    base_url=settings.ARK_BASE_URL,
    temperature=0.3,
    # doubao-seed-evolving 是推理模型，复杂任务可能需要较长时间；
    # 设 300s 超时避免无限挂起（V1 单用户场景可接受较长等待）。
    timeout=300,
)


def chat(system: str, user_template: str, **variables) -> str:
    """以 system + user 两条消息调用 LLM，返回文本。

    user_template 为 ChatPromptTemplate 模板：变量用 {name}，字面量大括号用 {{ }}。
    变量通过 variables 传入，由 ChatPromptTemplate 单次渲染，避免重复格式化。
    """
    prompt = ChatPromptTemplate.from_messages([("system", system), ("user", user_template)])
    chain = prompt | _llm
    resp = chain.invoke(variables)
    return resp.content


def chat_json(system: str, user_template: str, **variables) -> dict | list:
    """调用 LLM 并解析返回的 JSON（支持 dict 或 list，兼容代码围栏）。"""
    raw = chat(system, user_template, **variables)
    return _extract_json(raw)


def chat_structured(
    system: str,
    user_template: str,
    schema: type[BaseModel],
    default: BaseModel | None = None,
    *,
    strict: bool = False,
    **variables,
) -> BaseModel:
    """调用 LLM 并按 Pydantic schema 校验输出，支持重试。

    三层防护：
    1. 优先尝试 with_structured_output（Structured Output 能力）
    2. 回退到 chat_json + Pydantic 校验
    3. 校验失败时降低 temperature 重试，最多 2 次

    非 strict（默认）：全部失败则返回 default（若未提供则 schema 空实例），记录错误日志。
    strict=True：全部失败时抛出 LLMOutputInvalidError，杜绝空成功。
    """
    from core.errors import LLMOutputInvalidError

    # 第一层：尝试 Structured Output
    try:
        structured_llm = _llm.with_structured_output(schema)
        prompt = ChatPromptTemplate.from_messages([("system", system), ("user", user_template)])
        chain = prompt | structured_llm
        result = chain.invoke(variables)
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)
    except Exception as e:
        logger.warning(f"Structured Output 不可用，回退到 JSON+Pydantic 模式: {e}")

    # 第二、三层：chat_json + Pydantic 校验 + 降温重试
    temps = [0.3, 0.1, 0.0]
    last_err: Exception | None = None
    for i, temp in enumerate(temps):
        try:
            llm = _llm.bind(temperature=temp)
            prompt = ChatPromptTemplate.from_messages([("system", system), ("user", user_template)])
            chain = prompt | llm
            raw = chain.invoke(variables).content
            data = _extract_json(raw)
            return schema.model_validate(data)
        except Exception as e:
            last_err = e
            logger.warning(f"结构化校验失败（第{i + 1}次, temp={temp}）: {e}")

    if strict:
        logger.error(f"[strict] 结构化输出全部失败，抛出异常: {last_err}")
        raise LLMOutputInvalidError(
            f"{schema.__name__} 结构化输出连续 {len(temps)} 次校验失败",
            stage="llm_structured_output",
            details={"schema": schema.__name__, "last_error": repr(last_err)},
        )

    logger.error(f"结构化输出全部失败，返回默认值: {last_err}")
    return default if default is not None else schema()


def _extract_json(text: str) -> dict | list:
    text = text.strip()
    # 去掉 ```json ... ``` 围栏
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if not match:
        raise ValueError(f"未在返回中找到 JSON：{text[:200]}")
    return json.loads(match.group(1))
