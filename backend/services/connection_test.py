"""连接测试（候选配置，不落库、不改 active 配置）。

PLAN §3.2：连接配置按"填写候选 → 校验字段 → 测试 LLM / Embedding 能力 → 激活"。
本模块只负责测试能力：用候选配置发起最小 LLM 与 Embedding 调用，返回逐项结果；
不写入任何持久化配置，失败候选不影响当前可用配置。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 连接测试用最小输入（LLM 一句话、Embedding 一个短文本），控制成本与耗时
_LLM_TEST_PROMPT = "请只回复两个汉字：正常"
_EMBED_TEST_TEXT = "连接测试"


def _redact(message: str, api_key: str) -> str:
    """脱敏：错误信息中若混入 Key 或过长，替换/截断。"""
    if api_key and api_key in message:
        message = message.replace(api_key, "***")
    return message[:400]


def test_llm(*, api_key: str, base_url: str, model: str) -> dict:
    """测试 LLM 能力。返回 {ok, detail}。"""
    from services import llm_service
    try:
        llm = llm_service.build_llm(api_key, base_url, model, timeout=60)
        resp = llm.invoke(_LLM_TEST_PROMPT)
        content = getattr(resp, "content", None)
        if not content:
            return {"ok": False, "detail": "LLM 返回空内容"}
        return {"ok": True, "detail": ""}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": _redact(repr(e), api_key)}


def test_embedding(*, api_key: str, base_url: str, model: str) -> dict:
    """测试 Embedding 能力。返回 {ok, detail}。"""
    from services import embedding_service
    try:
        vector = embedding_service.embed_text_with_config(
            _EMBED_TEST_TEXT, api_key=api_key, base_url=base_url, model=model,
        )
        if not vector:
            return {"ok": False, "detail": "Embedding 返回空向量"}
        return {"ok": True, "detail": f"dim={len(vector)}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": _redact(repr(e), api_key)}


def test_connection(*, api_key: str, base_url: str, model: str, embedding_model: str) -> dict:
    """测试 LLM 与 Embedding 两项能力。返回 {llm, embedding, ok}。"""
    llm = test_llm(api_key=api_key, base_url=base_url, model=model)
    emb = test_embedding(api_key=api_key, base_url=base_url, model=embedding_model)
    return {"llm": llm, "embedding": emb, "ok": bool(llm["ok"] and emb["ok"])}