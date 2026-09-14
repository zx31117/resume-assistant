"""LLM 调用唯一入口（LangChain 专属层）。

边界约束：
- V1.5.0：rag_service 已删除，全仓库仅本文件 import langchain。
- 业务模块通过本模块间接调用 LLM，自身不接触 LangChain。
- 豆包（火山方舟）兼容 OpenAI API，直接用 ChatOpenAI 指向 Ark endpoint。

V2.0.0（T3）：
- 移除 import 期模块级单例 `_llm`（原先无 Key 时 import 即失败）。
- 改为每次调用时按当前配置快照惰性构建 client，使"配置激活后对新请求生效"，
  且错误候选不会覆盖可用配置（见 core.config_resolver）。

V1.3 strict failure：
- chat_structured(strict=True) 在所有重试均失败时抛出 LLMOutputInvalidError，
  而不是兜底空模型，杜绝"空成功"。

V2.2.0（T6，任务生成管线专用）：
- build_task_llm：temperature=0 + response_format=json_object + reasoning_effort=minimal
  + max_tokens（attempt completion 上限），用于紧凑 JD / Fact / reason 两阶段。
- TaskTokenBudget：任务级 completion token 预算（默认 16k，PLAN §2.2）。启动新逻辑调用
  前 reserve(attempt 上限)，调用后 refund(未用额度)；即将超限时拒绝启动而非截断。
- invoke_observed_json：单逻辑调用最多 3 个 HTTP attempt（成功即停；可重试失败重试，
  不可重试立即失败），解析响应 usage.completion_tokens，返回结构化结果与观测记录
  （attempts/retry 原因/completion_tokens），供调用/Token 门禁上报。
"""
import json
import logging
import re
import threading

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from core.config import settings
from core.errors import LLMOutputInvalidError
from core.task import LLM_MAX_ATTEMPTS

logger = logging.getLogger(__name__)


def build_llm(
    api_key: str,
    base_url: str,
    model: str,
    *,
    temperature: float = 0.3,
    timeout: float = 300,
) -> ChatOpenAI:
    """按显式配置构建 ChatOpenAI（供业务与连接测试复用）。"""
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        # doubao-seed-evolving 是推理模型，复杂任务可能需要较长时间；
        # 设 300s 超时避免无限挂起（V1 单用户场景可接受较长等待）。
        timeout=timeout,
    )


def _build_llm_from_settings(temperature: float = 0.3) -> ChatOpenAI:
    """按当前 settings 快照构建 client（V2.0.0：惰性，配置生效于后续请求）。"""
    return build_llm(
        api_key=settings.ARK_API_KEY or "",
        base_url=settings.ARK_BASE_URL,
        model=settings.LLM_MODEL,
        temperature=temperature,
    )


def chat(system: str, user_template: str, **variables) -> str:
    """以 system + user 两条消息调用 LLM，返回文本。

    user_template 为 ChatPromptTemplate 模板：变量用 {name}，字面量大括号用 {{ }}。
    变量通过 variables 传入，由 ChatPromptTemplate 单次渲染，避免重复格式化。
    """
    prompt = ChatPromptTemplate.from_messages([("system", system), ("user", user_template)])
    chain = prompt | _build_llm_from_settings()
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
        structured_llm = _build_llm_from_settings().with_structured_output(schema)
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
            llm = _build_llm_from_settings(temperature=temp)
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


# ── V2.2.0 T6：任务生成管线的 LLM 调用/Token 门禁 ───────────────── #

def build_task_llm(
    *,
    max_tokens: int,
    temperature: float = 0.0,
    timeout: float = 300,
) -> ChatOpenAI:
    """按当前配置快照构建任务管线专用 client（PLAN §2.2）。

    temperature=0、response_format=json_object、reasoning_effort=minimal、max_tokens
    （单次 HTTP attempt 的 completion token 上限）。紧凑 JD / Fact / reason 均由此构建。
    """
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.ARK_API_KEY or "",
        base_url=settings.ARK_BASE_URL,
        temperature=temperature,
        timeout=timeout,
        model_kwargs={
            "response_format": {"type": "json_object"},
            "reasoning_effort": "minimal",
            "max_tokens": max_tokens,
        },
    )


class TaskTokenBudget:
    """任务级 completion token 预算（PLAN §2.2：总量 16k，即将超限不启动新调用）。

    每个逻辑调用在发起前 reserve(尝试上限)，调用结束后 refund(未用额度)，从而
    "即将超限时不得启动新的 Fact/reason 调用，以明确失败/容量不足结束，不截断成功"。
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._used = 0
        self._lock = threading.Lock()

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def used(self) -> int:
        with self._lock:
            return self._used

    def remaining(self) -> int:
        with self._lock:
            return self._limit - self._used

    def can_accept(self, tokens: int) -> bool:
        with self._lock:
            return self._used + tokens <= self._limit

    def reserve(self, tokens: int) -> None:
        """发起前预留额度；即将超限时抛 CapacityError（不启动该调用）。"""
        with self._lock:
            if self._used + tokens > self._limit:
                from services.task_repository import TaskCapacityError  # 惰性，避免循环依赖
                raise TaskCapacityError(
                    f"任务 LLM completion token 即将超限：已用 {self._used}"
                    f" + 预留 {tokens} > 上限 {self._limit}",
                    details={"used": self._used, "requested": tokens, "limit": self._limit},
                    stage="task_llm_budget",
                )
            self._used += tokens

    def refund(self, tokens: int) -> None:
        """调用结束后退回未用额度（回吐预留与实际之差）。"""
        with self._lock:
            self._used = max(0, self._used - tokens)


class LLMCallRecord:
    """一次逻辑调用的观测记录（调用/Token/attempt/retry 上报）。"""

    def __init__(self, stage: str) -> None:
        self.stage = stage
        self.attempts = 0
        self.retry_reasons: list[str] = []
        self.completion_tokens = 0

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "attempts": self.attempts,
            "retry_reasons": list(self.retry_reasons),
            "completion_tokens": self.completion_tokens,
        }


def _completion_tokens(response) -> int:
    """从 LangChain 响应提取 completion tokens（output_tokens / usage）。"""
    um = getattr(response, "usage_metadata", None) or {}
    out = um.get("output_tokens")
    if isinstance(out, int):
        return out
    usage = getattr(response, "usage", None)
    if usage is not None:
        comp = getattr(usage, "completion_tokens", None)
        if isinstance(comp, int):
            return comp
        if isinstance(usage, dict):
            return int(usage.get("completion_tokens") or 0)
    return 0


def _retryable(exc: BaseException) -> bool:
    """可重试：网络/超时/解析/校验类；不可重试（如参数错误）立即失败。"""
    text = f"{type(exc).__name__}: {exc}"
    if any(k in text.lower() for k in ("timeout", "connection", "reset", "rate limit",
                                       "429", "too many", "json decode", "decodeerror",
                                       "validation")):
        return True
    return False


def invoke_observed_json(
    system: str,
    user_template: str,
    *,
    max_tokens: int,
    budget: TaskTokenBudget,
    stage: str,
    variables: dict | None = None,
    validate: object | None = None,
    embedder: object | None = None,
    provider: object | None = None,
) -> tuple[dict | list, LLMCallRecord]:
    """调用 LLM 返回 JSON，带 3-attempt 门禁与 completion token 记账。

    - 发起前 budget.reserve(max_tokens)；成功后 refund(未用额度)；
    - 每逻辑调用最多 3 个 HTTP attempt；成功即停；可重试失败重试，不可重试立即失败；
    - 每 attempt 把实际 completion token 记入 budget（reserve 上限+refund 差值即实际）；
    - 返回 (结构化 JSON, LLMCallRecord)。
    - provider: 可选注入的 LLM 调用可替代真实 client。签名
      provider(system, user_template, variables, max_tokens) -> (content_text, completion_tokens)。
      默认 None → 内部构建真实 ChatOpenAI（供生产路径复用）。
      假 LLM / 确定性门禁经此注入，不动生产调用公式。
    """
    vars = variables or {}
    try:
        budget.reserve(max_tokens)
    except Exception:
        raise
    record = LLMCallRecord(stage)
    last_exc: BaseException | None = None
    try:
        for _ in range(LLM_MAX_ATTEMPTS):
            record.attempts += 1
            try:
                if provider is not None:
                    content, completion = provider(system, user_template, vars, max_tokens)
                    record.completion_tokens += int(completion or 0)
                    data = _extract_json(content)
                    return data, record
                llm = build_task_llm(max_tokens=max_tokens)  # 惰性：仅真实路径构造
                prompt = ChatPromptTemplate.from_messages([("system", system), ("user", user_template)])
                chain = prompt | llm
                resp = chain.invoke(vars)
                content = resp.content if hasattr(resp, "content") else str(resp)
                data = _extract_json(content)
                record.completion_tokens += _completion_tokens(resp)
                return data, record
            except Exception as e:
                last_exc = e
                if not _retryable(_nested_base(e)) and record.attempts >= 1:
                    record.retry_reasons.append(f"non-retryable:{type(e).__name__}")
                    break
                if record.attempts < LLM_MAX_ATTEMPTS:
                    record.retry_reasons.append(f"attempt{record.attempts}:{type(e).__name__}")
                else:
                    break
        # 全部失败：严格失败（不伪装空成功）
        raise LLMOutputInvalidError(
            f"[{stage}] 结构化 JSON 输出连续 {record.attempts} 次失败",
            stage="llm_task_generation",
            details={"stage": stage, "attempts": record.attempts,
                     "last_error": repr(last_exc)},
        )
    finally:
        budget.refund(max_tokens - record.completion_tokens)


def _nested_base(e: BaseException) -> BaseException:
    while getattr(e, "__cause__", None) is not None:
        e = e.__cause__
    return e