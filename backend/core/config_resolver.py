"""单一配置 resolver（PLAN §3.2）。

优先级（单一真源，禁止 UI、环境变量、模块级缓存各自形成不同真源）：

- ARK_API_KEY：
  1. Credential Manager（Windows 系统凭据库，长期）
  2. 环境变量 / .env（开发、自动化、故障恢复入口）
- ARK_BASE_URL / LLM_MODEL / EMBEDDING_MODEL：
  1. runtime 版本化配置（RESUME_DATA_DIR/config/connection.json）
  2. 环境变量 / .env
  3. 内置默认值

职责：
- resolve：读取每项有效值与来源；
- snapshot：供配置元数据接口展示（脱敏，永不返回完整 Key）；
- activate：校验 + 测试通过后，持久化非密钥配置到版本化配置、Key 到凭据库，
  并同步更新 core.config.settings 内存快照（后续请求生效，不回头覆盖旧可用配置）；
- apply_startup_overlay：进程启动时把持久化配置叠加进 settings（幂等）。
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from core import credential_manager
from core.config import settings

logger = logging.getLogger(__name__)

# 内置默认值与 core.config.Settings 对齐（配置项仅 3 个 secret 无关项）
_DEFAULTS = {
    "ARK_BASE_URL": "https://ark.cn-beijing.volces.com/api/v3",
    "LLM_MODEL": "doubao-seed-evolving",
    "EMBEDDING_MODEL": "doubao-embedding-vision-251215",
}

# 非密钥配置字段（secret 仅 ARK_API_KEY，走凭据库）
_NON_SECRET_FIELDS = ("ARK_BASE_URL", "LLM_MODEL", "EMBEDDING_MODEL")
_ALL_FIELDS = _NON_SECRET_FIELDS + ("ARK_API_KEY",)

_RUNTIME_CONFIG_PATH = settings.RESUME_DATA_DIR / "config" / "connection.json"
_RUNTIME_SCHEMA_VERSION = 1

_startup_overlay_applied = False

# 激活后会整体更新 settings 的字段名映射（resolver 名 -> settings 属性名同构）
_SETTINGS_FIELDS = {
    "ARK_API_KEY": "ARK_API_KEY",
    "ARK_BASE_URL": "ARK_BASE_URL",
    "LLM_MODEL": "LLM_MODEL",
    "EMBEDDING_MODEL": "EMBEDDING_MODEL",
}


# ── runtime 版本化配置读写 ────────────────────────────────────── #

def _read_runtime_config() -> dict:
    try:
        if not _RUNTIME_CONFIG_PATH.exists():
            return {}
        data = json.loads(_RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:  # noqa: BLE001
        logger.warning("读取 runtime 配置失败（忽略，沿用 env/默认）: %r", e)
        return {}


def _write_runtime_config(config: dict) -> None:
    _RUNTIME_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": _RUNTIME_SCHEMA_VERSION}
    for key in _NON_SECRET_FIELDS:
        payload[key.lower()] = config.get(key, "")
    _RUNTIME_CONFIG_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── 单项解析 ─────────────────────────────────────────────────── #

def _env_value(field: str) -> str | None:
    v = os.getenv(field)
    return None if v is None else v


def resolve_api_key() -> tuple[str, str]:
    """返回 (value, source)。source ∈ credential_manager | env。"""
    try:
        key = credential_manager.get_api_key()
        if key:
            return key, "credential_manager"
    except credential_manager.CredentialError as e:
        logger.warning("凭据库读取失败，回退 env：%r", e)
    env = _env_value("ARK_API_KEY")
    if env:
        return env, "env"
    return "", "none"


def resolve_non_secret(field: str) -> tuple[str, str]:
    runtime = _read_runtime_config()
    key = field.lower()
    if key in runtime and runtime[key]:
        return str(runtime[key]), "runtime_config"
    env = _env_value(field)
    if env:
        return env, "env"
    return _DEFAULTS[field], "default"


# ── 快照（供元数据接口） ──────────────────────────────────────── #

def snapshot() -> dict[str, Any]:
    """返回每字段 {value/masked, source, configured}；API Key 只回掩码。"""
    out: dict[str, Any] = {}
    for field in _NON_SECRET_FIELDS:
        value, source = resolve_non_secret(field)
        out[field] = {
            "value": value,
            "source": source,
            "configured": bool(value) and source != "default",
        }
    key, source = resolve_api_key()
    out["ARK_API_KEY"] = {
        "masked": credential_manager.mask_key(key),
        "source": source,
        "configured": bool(key),
    }
    return out


# ── 激活（校验 + 测试 + 持久化 + 更新内存快照） ────────────────── #

def apply_active_config(
    *,
    ark_base_url: str,
    llm_model: str,
    embedding_model: str,
    ark_api_key: str,
) -> dict[str, Any]:
    """把候选配置持久化并激活。

    - 非密钥三项写入 runtime 版本化配置；
    - API Key 写入凭据库（失败抛 CredentialError，且不落任何明文持久化；
      已写入的 runtime 配置在凭据失败时回滚，避免"半个配置已激活"）；
    - 成功后同步更新 settings 内存快照（后续请求生效）。
    """
    base_url = (ark_base_url or "").strip()
    llm = (llm_model or "").strip()
    emb = (embedding_model or "").strip()
    api_key = (ark_api_key or "").strip()

    validate_fields(base_url=base_url, llm_model=llm, embedding_model=emb, api_key=api_key)

    new_runtime = {
        "ARK_BASE_URL": base_url,
        "LLM_MODEL": llm,
        "EMBEDDING_MODEL": emb,
    }

    # 先写凭据（最易失败，且失败时无需回滚 runtime）
    try:
        credential_manager.set_api_key(api_key)
    except credential_manager.CredentialError:
        # 凭据写失败：显式失败，绝不退回明文
        raise

    try:
        _write_runtime_config(new_runtime)
    except Exception as e:  # noqa: BLE001
        # runtime 写失败：回滚凭据，避免"Key 已激活但配置未持久化"的不一致。
        try:
            credential_manager.delete_api_key()
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(f"runtime 配置写入失败：{e}") from e

    # 更新内存快照
    settings.ARK_API_KEY = api_key
    settings.ARK_BASE_URL = base_url
    settings.LLM_MODEL = llm
    settings.EMBEDDING_MODEL = emb

    logger.info(
        "激活配置：base_url=%s llm=%s emb=%s key=%s",
        base_url, llm, emb, credential_manager.mask_key(api_key),
    )
    return snapshot()


def validate_fields(*, base_url: str, llm_model: str, embedding_model: str, api_key: str) -> None:
    """字段级校验（不触网）。缺失/格式错误抛 ValueError。"""
    missing = []
    if not base_url:
        missing.append("ark_base_url")
    if not llm_model:
        missing.append("llm_model")
    if not embedding_model:
        missing.append("embedding_model")
    if not api_key:
        missing.append("ark_api_key")
    if missing:
        raise ValueError(f"必填字段缺失：{', '.join(missing)}")
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        raise ValueError("ark_base_url 必须是 http(s) 地址")


# ── 启动叠加 ─────────────────────────────────────────────────── #

def apply_startup_overlay() -> None:
    """进程启动时把持久化配置叠加进 settings（幂等）。

    - 凭据库不可用/缺失时不破坏启动（保留 env/.env 值）；
    - runtime 配置存在时覆盖 env 对应值。
    """
    global _startup_overlay_applied
    if _startup_overlay_applied:
        return
    for field in _NON_SECRET_FIELDS:
        value, source = resolve_non_secret(field)
        if source in ("runtime_config", "env"):
            setattr(settings, field, value)
    key, source = resolve_api_key()
    # 凭据库（Credential Manager）优先于 env/.env：仅当凭据存在时覆盖内存快照
    if source == "credential_manager" and key:
        settings.ARK_API_KEY = key
    _startup_overlay_applied = True
    logger.info(
        "配置叠加完成：base_url=%s key=%s",
        settings.ARK_BASE_URL, credential_manager.mask_key(settings.ARK_API_KEY),
    )


apply_startup_overlay()