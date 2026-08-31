"""V2.0.0 连接配置路由（PLAN §3.2 / §4.1）。

只读快照、候选测试、激活三件事：
- GET  /api/config          返回每字段值/来源/是否已配置；ARK_API_KEY 只回脱敏末尾
- POST /api/config/test     用候选配置测试 LLM / Embedding（不落库、不改 active 配置）
- POST /api/config/activate 校验 + 持久化 + 更新内存快照；凭据失败显式失败无明文降级

本路由不返回完整 Key，也不回显任何明文密钥。
"""
from __future__ import annotations

from fastapi import APIRouter

from api import schemas
from core import config_resolver, credential_manager
from core.errors import ConfigInvalidError, CredentialStorageError
from services import connection_test

router = APIRouter()


@router.get("", response_model=schemas.ConfigSnapshotResponse)
def get_config_snapshot():
    """配置快照（脱敏）。"""
    return config_resolver.snapshot()


@router.post("/test", response_model=schemas.ConnectionTestResponse)
def test_config(req: schemas.ConnectionConfigRequest):
    """候选配置连接测试（LLM + Embedding，不写任何持久化配置）。"""
    try:
        config_resolver.validate_fields(
            base_url=req.ark_base_url,
            llm_model=req.llm_model,
            embedding_model=req.embedding_model,
            api_key=req.ark_api_key,
        )
    except ValueError as e:
        raise ConfigInvalidError(str(e), stage="config") from e

    return connection_test.test_connection(
        api_key=req.ark_api_key,
        base_url=req.ark_base_url,
        model=req.llm_model,
        embedding_model=req.embedding_model,
    )


@router.post("/activate", response_model=schemas.ConfigSnapshotResponse)
def activate_config(req: schemas.ConnectionConfigRequest):
    """激活候选配置：校验 → 持久化（版本化配置 + 凭据库）→ 更新内存快照。"""
    try:
        return config_resolver.apply_active_config(
            ark_base_url=req.ark_base_url,
            llm_model=req.llm_model,
            embedding_model=req.embedding_model,
            ark_api_key=req.ark_api_key,
        )
    except credential_manager.CredentialError as e:
        # 凭据库不可用/写失败：显式失败，绝不退回明文存储
        raise CredentialStorageError(str(e), stage="credential") from e
    except ValueError as e:
        raise ConfigInvalidError(str(e), stage="config") from e
    except RuntimeError as e:
        raise ConfigInvalidError(str(e), stage="config") from e