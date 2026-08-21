"""向量存储封装（纯存储层，无 LangChain，无 AI）。

边界约束：
- 本文件不依赖 LangChain，也不调用任何 AI/Embedding 模型。
- 仅负责按"已计算好的 embedding 向量"做增删查。
- Embedding 的计算由 services/rag_service.py（LangChain 层）完成，再交给本模块存储。

实现策略（保证 V1 可跑通）：
- 优先使用 Chroma（PersistentClient）。
- 若当前环境 Chroma 不可用（如缺少 VC++ 运行时导致 chromadb_rust_bindings DLL 加载失败，
  或缺少 MSVC 导致 chroma-hnswlib 无法构建），自动回退到 numpy 余弦检索 + JSON 持久化。
- 两种后端对外接口完全一致（upsert / delete / query_by_embedding），
  返回结构也保持 Chroma 风格（嵌套列表），上层 rag_service 无需感知。
- 未来环境就绪后，移除回退分支即可纯用 Chroma，无需改动其它模块。
"""
import json
import os
from typing import Optional

from core.config import settings

COLLECTION_NAME = "experiences"

# numpy 回退的持久化文件（先定义，供 try 内使用）
_NP_FILE = os.path.join(settings.CHROMA_PATH, "vectors.json")

# ---- 尝试初始化 Chroma，失败则回退 numpy ----
# 整个初始化（含目录创建 + Chroma import + Client 创建）必须全部包裹在 try 内，
# 确保任何一步失败都能安全回退到 numpy 后端，不会导致模块加载直接崩溃。
_chroma_client = None
try:
    os.makedirs(settings.CHROMA_PATH, exist_ok=True)
    import chromadb  # noqa: F401

    _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
    _chroma_client.get_or_create_collection(COLLECTION_NAME)
    _BACKEND = "chroma"
except Exception as _e:  # pragma: no cover - 环境相关
    _chroma_client = None
    _BACKEND = "numpy"
    _INIT_ERR = repr(_e)
    # 回退路径也要保证目录可写（vectors.json 要写入）
    try:
        os.makedirs(settings.CHROMA_PATH, exist_ok=True)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Chroma 后端
# --------------------------------------------------------------------------- #
def _chroma_collection():
    return _chroma_client.get_or_create_collection(COLLECTION_NAME)


def _chroma_upsert(exp_id, embedding, document, metadata):
    _chroma_collection().upsert(
        ids=[exp_id],
        embeddings=[embedding],
        documents=[document],
        metadatas=[metadata],
    )


def _chroma_delete(exp_id):
    _chroma_collection().delete(ids=[exp_id])


def _chroma_query(embedding, n_results, where):
    kwargs = {"query_embeddings": [embedding], "n_results": n_results}
    if where:
        kwargs["where"] = where
    return _chroma_collection().query(**kwargs)


# --------------------------------------------------------------------------- #
# numpy 回退后端（余弦相似度 + JSON 持久化）
# --------------------------------------------------------------------------- #
def _np_load() -> dict:
    if os.path.exists(_NP_FILE):
        with open(_NP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _np_save(data: dict) -> None:
    with open(_NP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _np_match_where(metadata: dict, where: Optional[dict]) -> bool:
    if not where:
        return True
    return all(metadata.get(k) == v for k, v in where.items())


def _np_query(embedding, n_results, where):
    import numpy as np

    data = _np_load()
    if not data:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    q = np.asarray(embedding, dtype=float)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        q_norm = 1.0
    q = q / q_norm

    scored = []
    for exp_id, item in data.items():
        if not _np_match_where(item.get("metadata", {}), where):
            continue
        v = np.asarray(item["embedding"], dtype=float)
        v_norm = np.linalg.norm(v)
        if v_norm == 0:
            v_norm = 1.0
        v = v / v_norm
        sim = float(np.dot(q, v))  # 余弦相似度，越大越相关
        scored.append((sim, exp_id, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    scored = scored[:n_results]

    # 距离用 (1 - 相似度)，与 Chroma 的"越小越相关"语义对齐
    ids = [s[1] for s in scored]
    docs = [s[2].get("document", "") for s in scored]
    metas = [s[2].get("metadata", {}) for s in scored]
    dists = [1.0 - s[0] for s in scored]
    return {
        "ids": [ids],
        "documents": [docs],
        "metadatas": [metas],
        "distances": [dists],
    }


# --------------------------------------------------------------------------- #
# 对外统一接口
# --------------------------------------------------------------------------- #
def upsert(exp_id: str, embedding: list, document: str, metadata: dict) -> None:
    """按预计算 embedding 写入/更新一条经历向量。"""
    if _BACKEND == "chroma":
        _chroma_upsert(exp_id, embedding, document, metadata)
    else:
        data = _np_load()
        data[exp_id] = {"embedding": embedding, "document": document, "metadata": metadata}
        _np_save(data)


def delete(exp_id: str) -> None:
    """按 id 删除一条向量。"""
    if _BACKEND == "chroma":
        _chroma_delete(exp_id)
    else:
        data = _np_load()
        data.pop(exp_id, None)
        _np_save(data)


def query_by_embedding(
    embedding: list,
    n_results: int = 5,
    where: Optional[dict] = None,
) -> dict:
    """按预计算 embedding 做语义检索，返回 Chroma 风格结构。"""
    if _BACKEND == "chroma":
        return _chroma_query(embedding, n_results, where)
    return _np_query(embedding, n_results, where)


def backend() -> str:
    """当前实际使用的后端（便于调试/日志）。"""
    return _BACKEND


# --------------------------------------------------------------------------- #
# 运维 / 切回 Chroma 辅助接口
# --------------------------------------------------------------------------- #
def migration_available() -> bool:
    """是否存在 numpy 回退数据且当前 Chroma 后端可用 → 可切回迁移。"""
    if _BACKEND != "chroma" or _chroma_client is None:
        return False
    return os.path.exists(_NP_FILE)


def migrate_numpy_to_chroma(overwrite: bool = False) -> dict:
    """将 vectors.json（numpy 回退模式历史数据）迁移到 Chroma。

    返回：{ "migrated": int, "skipped_existing": int, "total_in_source": int, "errors": [str] }

    注意：
    - 本函数是**运维动作**（显式调用执行），不是初始化副作用，不会自动触发。
    - 向量维度一致性未内置校验：上层写入时已经保证；若不一致 Chroma 会在 upsert 抛异常被计入 errors。
    - 迁移成功后**不自动删除 vectors.json**，由运维确认无误后手动删除（避免破坏回退）。
    """
    errors: list[str] = []
    migrated = 0
    skipped = 0

    if not migration_available():
        return {
            "migrated": 0,
            "skipped_existing": 0,
            "total_in_source": 0,
            "errors": [
                f"Migration not available: backend={_BACKEND}, _chroma_client={'ok' if _chroma_client else 'None'}, vectors_json_exists={os.path.exists(_NP_FILE)}"
            ],
        }

    src = _np_load()
    total = len(src)
    col = _chroma_collection()

    # 预先取 Chroma 已有 ids，避免 overwrite=False 时查询 N 次
    existing_ids: set[str] = set()
    try:
        if total > 0:
            peek = col.get(ids=list(src.keys())[:1]) or {}
            peek_ids = peek.get("ids") or [] if isinstance(peek, dict) else []
            # Chroma 全量 get 可能较大 → 保守地逐个检查（不超过 几千条经历规模内可接受）
            for exp_id in src.keys():
                hit = col.get(ids=[exp_id]) or {}
                if isinstance(hit, dict) and (hit.get("ids") or []):
                    existing_ids.add(exp_id)
    except Exception as _e:
        errors.append(f"pre-check existing ids warning (continue): {_e!r}")

    for exp_id, item in src.items():
        if not overwrite and exp_id in existing_ids:
            skipped += 1
            continue
        try:
            emb = item.get("embedding")
            if not isinstance(emb, list) or not emb:
                errors.append(f"skip {exp_id}: invalid embedding type/dim")
                skipped += 1
                continue
            _chroma_upsert(
                exp_id,
                emb,
                item.get("document", ""),
                item.get("metadata", {}) or {},
            )
            migrated += 1
        except Exception as _e:
            errors.append(f"fail {exp_id}: {_e!r}")
            skipped += 1

    return {
        "migrated": migrated,
        "skipped_existing": skipped,
        "total_in_source": total,
        "errors": errors,
    }


def get_backend_stats() -> dict:
    """返回当前后端状态快照（运维排障 / 验收报告用）。"""
    stats = {
        "backend": _BACKEND,
        "chroma_client_ok": _chroma_client is not None,
        "chroma_path": settings.CHROMA_PATH,
        "collection": COLLECTION_NAME,
        "np_file": _NP_FILE,
        "np_file_exists": os.path.exists(_NP_FILE),
        "migration_available": migration_available(),
        "init_error_numpy_fallback": locals().get("_INIT_ERR") if _BACKEND == "numpy" else None,
    }

    # 记录条数
    try:
        if _BACKEND == "chroma" and _chroma_client is not None:
            stats["chroma_count"] = _chroma_collection().count()
    except Exception as _e:
        stats["chroma_count_error"] = repr(_e)

    if stats["np_file_exists"]:
        try:
            stats["np_count"] = len(_np_load())
        except Exception as _e:
            stats["np_count_error"] = repr(_e)

    # 验证是否完全绕开默认 embedding function（关键：防 onnxruntime DLL 崩溃）
    try:
        if _BACKEND == "chroma" and _chroma_client is not None:
            col = _chroma_collection()
            ef = getattr(col, "embedding_function", None)
            # None 或显式空 → 不会自动走默认 onnx embedding
            stats["default_embedding_disabled"] = ef is None
            stats["embedding_function_class"] = ef.__class__.__name__ if ef else None
    except Exception as _e:
        stats["default_embedding_check_error"] = repr(_e)

    return stats
