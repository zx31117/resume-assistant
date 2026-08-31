"""V1.5.0 T3：SQLite BLOB Embedding 与内存精确检索（PLAN §6.2 / §7 T3）。

职责：
- compute_fingerprint：基于 EMBEDDING_MODEL + ARK_BASE_URL 派生稳定指纹
- _embed_text：调用豆包多模态向量化 API（urllib，无 LangChain，无隐藏 fallback）
- upsert_embedding：将向量以 BLOB(float32) 写入 fact_embeddings，记录 dimension/fingerprint/revision/hash
- rebuild_embeddings：全量重建 PENDING/INVALID/FAILED 向量；无 API Key 时停在 PENDING
- ensure_ready：生成链路前置检查，有非 VALID 向量时阻断（VectorIndexNotReadyError）
- query_facts：读取候选 Fact 向量到内存，做精确 cosine 相似度排序
- wire_fact_invalidation：注册 Fact 修改失效钩子到 fact_service

边界（PLAN §6.2 / §8.2）：
- numpy 仅作计算库（cosine / BLOB 编解码），不承担 JSON 持久化或 fallback 后端
- 无 ARK_API_KEY 时向量停在 PENDING，ensure_ready 显式阻断生成（§6.3.5 / §8.2）
- fingerprint / 维度 / Fact revision/hash 不匹配 → INVALID，重建前不得使用（§6.2）
- 不读取 Chroma 或 numpy+JSON 旧向量字节（§6.3）

测试接缝：rebuild_embeddings / upsert_embedding 接受可选 embedder(text)->vector，
仅用于注入确定性 mock；生产路径 embedder=None 时调用 _embed_text，无 API Key 即抛错。
"""
from __future__ import annotations

import hashlib
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime
from typing import Callable, Optional

import numpy as np
from sqlalchemy.orm import Session, sessionmaker

from core.config import settings
from core.errors import VectorIndexNotReadyError
from database.models import EmbeddingStatus, Fact, FactEmbedding
from services import fact_service

logger = logging.getLogger(__name__)

# 向量存储 dtype（固定 float32，跨平台稳定）
_VECTOR_DTYPE = "float32"
_NP_DTYPE = np.float32

# 单条 Embedding 网络超时（秒）：正常毫秒级返回；设短一点，避免 rebuild
# 逐条串行时因某条网络不通而长时间占用全局并发锁（V2.0.0 修复）。
_EMBED_TIMEOUT = 30


# ── fingerprint ──────────────────────────────────────────────── #

def compute_fingerprint() -> str:
    """fingerprint = sha256(EMBEDDING_MODEL @ ARK_BASE_URL)[:16]。

    模型或端点变化即失效（PLAN §6.2）。截断 16 位足以区分配置且避免过长。
    """
    raw = f"{settings.EMBEDDING_MODEL}@{settings.ARK_BASE_URL}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ── Embedding 计算（豆包 multimodal API，无 fallback） ────────── #

def embed_text_with_config(
    text: str,
    *,
    api_key: str,
    base_url: str,
    model: str,
) -> list[float]:
    """用显式配置调用豆包多模态向量化 API（供连接测试与生产共用）。

    无 api_key 时抛 RuntimeError（不静默 fallback，PLAN §6.3.5）。
    """
    if not api_key:
        raise RuntimeError("ARK_API_KEY 未配置，无法计算 Embedding（无隐藏 fallback）")

    url = f"{base_url}/embeddings/multimodal"
    payload = json.dumps({
        "model": model,
        "encoding_format": "float",
        "input": [{"type": "text", "text": text}],
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=_EMBED_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body["data"]["embedding"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8")[:500]
        raise RuntimeError(f"Embedding API HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Embedding API 连接失败或超时：{e.reason}") from e


def _embed_text(text: str) -> list[float]:
    """按当前 settings 快照计算向量（V2.0.0：惰性读取生效配置）。"""
    return embed_text_with_config(
        text,
        api_key=settings.ARK_API_KEY or "",
        base_url=settings.ARK_BASE_URL,
        model=settings.EMBEDDING_MODEL,
    )


def _resolve_embedder(embedder: Optional[Callable[[str], list[float]]]) -> Callable[[str], list[float]]:
    """生产路径用 _embed_text；测试注入 mock。无静默 fallback。"""
    return embedder if embedder is not None else _embed_text


# ── BLOB 编解码 ──────────────────────────────────────────────── #

def _encode_vector(vector: list[float]) -> tuple[bytes, int]:
    """list[float] → (BLOB float32, dimension)。"""
    arr = np.asarray(vector, dtype=_NP_DTYPE)
    return arr.tobytes(), int(arr.shape[0])


def _decode_vector(blob: bytes, dtype: str, dimension: int) -> np.ndarray:
    """BLOB → numpy float32 向量。dtype 不匹配时视为不可用（返回空）。"""
    if not blob or dimension <= 0:
        return np.zeros(0, dtype=_NP_DTYPE)
    if dtype != _VECTOR_DTYPE:
        # dtype 不匹配：不猜测转换，直接判不可用（PLAN §6.2）
        return np.zeros(0, dtype=_NP_DTYPE)
    arr = np.frombuffer(blob, dtype=_NP_DTYPE)
    if arr.shape[0] != dimension:
        return np.zeros(0, dtype=_NP_DTYPE)
    return arr


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """精确 cosine 相似度（内存计算，PLAN §6.2）。"""
    if a.shape[0] == 0 or b.shape[0] == 0 or a.shape[0] != b.shape[0]:
        return 0.0
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ── 写入 / 更新 ──────────────────────────────────────────────── #

def upsert_embedding(
    session: Session,
    fact: Fact,
    vector: list[float],
    *,
    embedder: Optional[Callable[[str], list[float]]] = None,
) -> FactEmbedding:
    """写入/更新 Fact 向量（BLOB float32）。

    - 以 (fact_id, fingerprint) 唯一定位（PLAN §6.2）
    - 记录 dimension、dtype、fact_revision、fact_content_hash、status=VALID
    - 幂等：同 fact+fp 重复写入为更新，不新增行
    """
    fp = compute_fingerprint()
    blob, dim = _encode_vector(vector)

    row = (
        session.query(FactEmbedding)
        .filter(FactEmbedding.fact_id == fact.fact_id, FactEmbedding.embedding_fingerprint == fp)
        .one_or_none()
    )
    if row is None:
        row = FactEmbedding(fact_id=fact.fact_id, embedding_fingerprint=fp)
        session.add(row)

    row.dimension = dim
    row.vector_blob = blob
    row.vector_dtype = _VECTOR_DTYPE
    row.fact_revision = fact.revision or 1
    row.fact_content_hash = fact.content_hash or ""
    row.status = EmbeddingStatus.VALID
    row.error = ""
    row.updated_at = datetime.utcnow()
    session.commit()
    logger.info(
        "FactEmbedding upsert: fact_id=%s fp=%s dim=%d rev=%d",
        fact.fact_id, fp, dim, fact.revision,
    )
    return row


# ── 失效（Fact 修改钩子） ─────────────────────────────────────── #

def invalidate_fact_embedding(session: Session, fact_id: str, *, commit: bool = True) -> int:
    """将该 fact_id 的所有 VALID 向量标记为 INVALID（PLAN §6.2 / §4.1）。

    返回受影响行数。用于 fact_service 修改钩子与维度/fingerprint 不匹配场景。

    R4：commit=False 时不提交，允许调用方在同一事务内完成 Fact 更新 + 向量失效，
    保证不存在"新 Fact 已提交但旧 Embedding 仍 VALID"的一致性窗口。
    """
    rows = (
        session.query(FactEmbedding)
        .filter(FactEmbedding.fact_id == fact_id, FactEmbedding.status == EmbeddingStatus.VALID)
        .all()
    )
    now = datetime.utcnow()
    for row in rows:
        row.status = EmbeddingStatus.INVALID
        row.updated_at = now
    if commit:
        session.commit()
    return len(rows)


# 模块级失效钩子状态（幂等注册）
_invalidation_session_factory: Optional[Callable[[], Session]] = None
_invalidation_hook_registered = False


def wire_fact_invalidation(session_factory: Optional[Callable[[], Session]] = None) -> None:
    """注册 Fact 修改失效钩子到 fact_service（幂等）。

    - session_factory：默认懒加载 database.session.SessionLocal（生产）
    - 测试可注入临时 DB 的 sessionmaker
    """
    global _invalidation_session_factory, _invalidation_hook_registered
    if _invalidation_hook_registered:
        return
    _invalidation_session_factory = session_factory

    def _hook(fact_id: str, old_revision: int) -> None:
        factory = _invalidation_session_factory or _default_session_factory()
        if factory is None:
            logger.warning("invalidation hook: no session factory; skip fact_id=%s", fact_id)
            return
        sess = factory()
        try:
            n = invalidate_fact_embedding(sess, fact_id)
            logger.info("invalidation hook: fact_id=%s old_rev=%d invalidated=%d", fact_id, old_revision, n)
        except Exception as e:  # noqa: BLE001 - 钩子不得中断 modify_fact
            sess.rollback()
            logger.warning("invalidation hook error fact_id=%s: %r", fact_id, e)
        finally:
            sess.close()

    fact_service.register_invalidation_hook(_hook)
    _invalidation_hook_registered = True


def unwire_fact_invalidation() -> None:
    """测试用：清空钩子注册状态与 fact_service 回调表。"""
    global _invalidation_session_factory, _invalidation_hook_registered
    _invalidation_session_factory = None
    _invalidation_hook_registered = False
    fact_service.clear_invalidation_hooks()


def _default_session_factory():
    """懒加载生产 SessionLocal，避免循环导入。"""
    try:
        from database.session import SessionLocal
        return SessionLocal
    except Exception:  # noqa: BLE001
        return None


# ── 全量重建 ─────────────────────────────────────────────────── #

def mark_pending_for_missing(session: Session) -> int:
    """为无 VALID 向量的 Fact 创建 PENDING 占位行（当前 fingerprint）。

    迁移后 / 无 Key 时调用：确保事实迁移完成、索引明确 pending（PLAN §6.3.4 / §8.2）。
    """
    fp = compute_fingerprint()
    facts = session.query(Fact).all()
    created = 0
    for fact in facts:
        existing = (
            session.query(FactEmbedding)
            .filter(FactEmbedding.fact_id == fact.fact_id, FactEmbedding.embedding_fingerprint == fp)
            .one_or_none()
        )
        if existing is None:
            session.add(FactEmbedding(
                fact_id=fact.fact_id,
                embedding_fingerprint=fp,
                dimension=0,
                fact_revision=fact.revision or 1,
                fact_content_hash=fact.content_hash or "",
                status=EmbeddingStatus.PENDING,
            ))
            created += 1
    session.commit()
    return created


def rebuild_embeddings(
    session: Session,
    *,
    embedder: Optional[Callable[[str], list[float]]] = None,
) -> dict:
    """全量重建 PENDING / INVALID / FAILED 向量（PLAN §6.3.5 / §7 T3）。

    - 有 API Key（或注入 embedder）时逐条计算并 upsert
    - 无 API Key 且无 embedder 时：仅标记 PENDING 并返回 skipped（不抛错，§6.3.5）
    - 单条失败标记 FAILED（可重试），不中断其余
    """
    fp = compute_fingerprint()
    resolve = _resolve_embedder(embedder)

    # 先补齐 PENDING 占位
    mark_pending_for_missing(session)

    # 收集待重建：PENDING / INVALID / FAILED（当前 fingerprint）
    pending_rows = (
        session.query(FactEmbedding)
        .filter(
            FactEmbedding.embedding_fingerprint == fp,
            FactEmbedding.status.in_([EmbeddingStatus.PENDING, EmbeddingStatus.INVALID, EmbeddingStatus.FAILED]),
        )
        .all()
    )

    summary = {
        "fingerprint": fp,
        "pending_count": len(pending_rows),
        "succeeded": 0,
        "failed": 0,
        "skipped_no_key": False,
        "errors": [],
    }

    # 无 API Key 且未注入 embedder：停在 PENDING（§6.3.5）
    if embedder is None and not settings.ARK_API_KEY:
        summary["skipped_no_key"] = True
        logger.info("rebuild skipped: ARK_API_KEY 未配置，%d 条向量停在 PENDING", len(pending_rows))
        return summary

    for row in pending_rows:
        fact = session.get(Fact, row.fact_id)
        if fact is None:
            row.status = EmbeddingStatus.FAILED
            row.error = "orphan: fact not found"
            row.updated_at = datetime.utcnow()
            summary["failed"] += 1
            summary["errors"].append({"fact_id": row.fact_id, "error": "orphan fact"})
            continue
        text = (fact.text or "").strip()
        if not text:
            row.status = EmbeddingStatus.FAILED
            row.error = "empty fact text"
            row.updated_at = datetime.utcnow()
            summary["failed"] += 1
            summary["errors"].append({"fact_id": row.fact_id, "error": "empty text"})
            continue
        try:
            vector = resolve(text)
            blob, dim = _encode_vector(vector)
            row.dimension = dim
            row.vector_blob = blob
            row.vector_dtype = _VECTOR_DTYPE
            row.fact_revision = fact.revision or 1
            row.fact_content_hash = fact.content_hash or ""
            row.status = EmbeddingStatus.VALID
            row.error = ""
            row.updated_at = datetime.utcnow()
            summary["succeeded"] += 1
        except Exception as e:  # noqa: BLE001 - 单条失败不中断
            row.status = EmbeddingStatus.FAILED
            row.error = repr(e)[:300]
            row.updated_at = datetime.utcnow()
            summary["failed"] += 1
            summary["errors"].append({"fact_id": row.fact_id, "error": repr(e)[:300]})
            logger.warning("rebuild fact_id=%s failed: %r", row.fact_id, e)

    session.commit()
    logger.info(
        "rebuild done: fp=%s pending=%d succeeded=%d failed=%d skipped_no_key=%s",
        fp, summary["pending_count"], summary["succeeded"], summary["failed"], summary["skipped_no_key"],
    )
    return summary


# ── 生成前置检查 ──────────────────────────────────────────────── #

def ensure_ready(session: Session, candidate_fact_ids: list[str]) -> None:
    """生成链路前置检查：候选 Fact 中有非 VALID 向量时阻断（PLAN §8.2 / §6.3.5）。

    - 无 API Key → 向量停在 PENDING → 此处抛 VectorIndexNotReadyError 阻断生成
    - INVALID / FAILED / 缺失 同样阻断
    """
    if not candidate_fact_ids:
        return
    fp = compute_fingerprint()
    rows = (
        session.query(FactEmbedding)
        .filter(FactEmbedding.fact_id.in_(candidate_fact_ids))
        .all()
    )
    by_fact: dict[str, list[FactEmbedding]] = {}
    for r in rows:
        by_fact.setdefault(r.fact_id, []).append(r)

    pending_ids: list[str] = []
    invalid_ids: list[str] = []
    failed_ids: list[str] = []
    missing_ids: list[str] = []

    for fid in candidate_fact_ids:
        fact_rows = by_fact.get(fid, [])
        # 当前 fingerprint 下是否有 VALID
        valid = [r for r in fact_rows if r.embedding_fingerprint == fp and r.status == EmbeddingStatus.VALID]
        if valid:
            continue
        any_row = [r for r in fact_rows if r.embedding_fingerprint == fp]
        if not any_row:
            missing_ids.append(fid)
        elif any(r.status == EmbeddingStatus.PENDING for r in any_row):
            pending_ids.append(fid)
        elif any(r.status == EmbeddingStatus.FAILED for r in any_row):
            failed_ids.append(fid)
        else:
            invalid_ids.append(fid)

    blockers = pending_ids or invalid_ids or failed_ids or missing_ids
    if blockers:
        raise VectorIndexNotReadyError(
            f"候选 Fact 向量未就绪：pending={len(pending_ids)} invalid={len(invalid_ids)} "
            f"failed={len(failed_ids)} missing={len(missing_ids)}（PLAN §8.2）",
            failed_ids=failed_ids,
            pending_ids=pending_ids + missing_ids,
        )


# ── 内存精确检索 ──────────────────────────────────────────────── #

def query_facts(
    session: Session,
    query_vector: list[float],
    candidate_fact_ids: list[str],
    *,
    top_k: Optional[int] = None,
) -> list[dict]:
    """读取候选 Fact 向量到内存，做精确 cosine 相似度排序（PLAN §6.2）。

    - 只使用当前 fingerprint + status=VALID + 维度匹配 + revision 匹配的向量
    - 任一不匹配视为不可用，排除（不 fallback）
    - 返回 [{fact_id, score, revision}, ...] 按 score 降序
    """
    if not candidate_fact_ids:
        return []
    fp = compute_fingerprint()
    rows = (
        session.query(FactEmbedding)
        .filter(
            FactEmbedding.fact_id.in_(candidate_fact_ids),
            FactEmbedding.embedding_fingerprint == fp,
            FactEmbedding.status == EmbeddingStatus.VALID,
        )
        .all()
    )

    q_dim = len(query_vector)
    q = np.asarray(query_vector, dtype=_NP_DTYPE)
    results: list[dict] = []
    health_issues: list[str] = []  # R6: collect health issues

    for row in rows:
        # R6: health checks — failures collected, not silently skipped
        if row.dimension != q_dim:
            health_issues.append(f"dimension mismatch: fact_id={row.fact_id} stored={row.dimension} query={q_dim}")
            continue
        if row.dimension <= 0:
            health_issues.append(f"zero dimension: fact_id={row.fact_id}")
            continue
        v = _decode_vector(row.vector_blob or b"", row.vector_dtype, row.dimension)
        if v.shape[0] != q_dim:
            health_issues.append(f"blob length mismatch: fact_id={row.fact_id} blob={v.shape[0]} query={q_dim}")
            continue
        fact = session.get(Fact, row.fact_id)
        if fact is None:
            health_issues.append(f"orphan fact: fact_id={row.fact_id}")
            continue
        if (fact.revision or 1) != row.fact_revision:
            health_issues.append(f"revision mismatch: fact_id={row.fact_id} fact={fact.revision} emb={row.fact_revision}")
            continue
        if (fact.content_hash or "") != row.fact_content_hash:
            health_issues.append(f"content_hash mismatch: fact_id={row.fact_id}")
            continue
        # All health checks passed — compute score
        score = _cosine(q, v)
        results.append({
            "fact_id": row.fact_id,
            "score": round(score, 6),
            "revision": row.fact_revision,
        })

    # R6: health issues must block — not confused with healthy low relevance
    if health_issues:
        from core.errors import RetrievalHealthError
        raise RetrievalHealthError(
            f"检索健康检查失败: {len(health_issues)} issues (R6)",
            issues=health_issues[:20],
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    if top_k is not None:
        results = results[:top_k]
    return results


def status_summary(session: Session) -> dict:
    """诊断用：按状态统计当前 fingerprint 下的向量数量。"""
    fp = compute_fingerprint()
    rows = session.query(FactEmbedding).filter(FactEmbedding.embedding_fingerprint == fp).all()
    summary = {"fingerprint": fp, "total": len(rows), "VALID": 0, "PENDING": 0, "INVALID": 0, "FAILED": 0}
    for r in rows:
        summary[r.status.name] = summary.get(r.status.name, 0) + 1
    return summary
