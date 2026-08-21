"""V1.3 T7：向量索引同步编排。

职责：
- execute_job：单条 Job 幂等执行（DONE 跳过，FAILED/PENDING → 实际调用 rag_service 并更新状态）；
- ensure_user_index_ready：生成前检查 + 处理 PENDING + 重试 FAILED；全部失败则抛 VectorIndexNotReadyError；
- rebuild_user_index_from_sql：从 SQL 全量重建用户向量，输出失败 ID。

不直接操作 Experience CRUD（CRUD 的事务内 Job 创建在 experience_service 里）。
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from core.errors import VectorIndexNotReadyError, VectorIndexOperationError
from database import models
from database.models import IndexJobStatus, IndexOperation
from services import rag_service, experience_service

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 单 Job 幂等执行
# ═══════════════════════════════════════════════════════════════════════════

def execute_job(db: Session, job: models.VectorIndexJob) -> None:
    """执行单条索引 Job（DONE 直接跳过；否则实际调用 rag_service 并写状态）。"""
    if job.status == IndexJobStatus.DONE:
        return

    job.status = IndexJobStatus.RUNNING
    db.commit()

    try:
        if job.operation == IndexOperation.UPSERT:
            exp = db.query(models.Experience).filter(models.Experience.id == job.experience_id).first()
            if not exp:
                # SQL 里都找不到经历，直接标记删除 + DONE
                try:
                    rag_service.delete_experience(job.experience_id)
                except Exception:
                    pass
                job.status = IndexJobStatus.DONE
                db.commit()
                return
            text = experience_service.build_index_text(exp)
            rag_service.index_experience(exp.id, text, experience_service._metadata(exp) if hasattr(experience_service, "_metadata") else {
                "user_id": exp.user_id or "",
                "type": exp.type or "",
                "title": exp.title or "",
                "skills": ",".join(exp.skills or []),
            })
            exp.vector_id = exp.id
        elif job.operation == IndexOperation.DELETE:
            rag_service.delete_experience(job.experience_id)
        else:
            raise ValueError(f"未知 IndexOperation: {job.operation}")

        job.status = IndexJobStatus.DONE
        job.last_error = ""
    except Exception as e:
        job.status = IndexJobStatus.FAILED
        job.retry_count = (job.retry_count or 0) + 1
        job.last_error = repr(e)
        logger.error(f"[VectorIndex] Job {job.id} ({job.operation.value} {job.experience_id}) FAILED: {e!r}")
        db.commit()
        raise VectorIndexOperationError(
            f"向量索引 {job.operation.value} 失败: experience_id={job.experience_id}",
            details={"job_id": job.id, "experience_id": job.experience_id, "error": repr(e)},
        ) from e
    finally:
        db.commit()


# ═══════════════════════════════════════════════════════════════════════════
# 生成前：索引就绪检查（处理 PENDING + 重试 FAILED）
# ═══════════════════════════════════════════════════════════════════════════

def ensure_user_index_ready(db: Session, user_id: str, *, max_retry_per_job: int = 2) -> dict:
    """确保该用户所有 PENDING/FAILED 索引 Job 都至少尝试执行一次。

    规则（PLAN §5）：
    - 先处理 PENDING → execute_job；
    - 再处理 FAILED（retry_count < max_retry_per_job）→ 再执行；
    - 仍有 FAILED → 抛 VectorIndexNotReadyError，附带 failed_ids / pending_ids。

    返回执行统计（processed/pending/failed）。
    """
    # 1) 执行 PENDING
    pending_jobs = (
        db.query(models.VectorIndexJob)
        .filter(
            models.VectorIndexJob.user_id == user_id,
            models.VectorIndexJob.status == IndexJobStatus.PENDING,
        )
        .all()
    )
    for job in pending_jobs:
        try:
            execute_job(db, job)
        except VectorIndexOperationError:
            pass  # 状态已写成 FAILED，下面统一汇总

    # 2) 重试 FAILED（仍有重试配额的）
    failed_retry_jobs = (
        db.query(models.VectorIndexJob)
        .filter(
            models.VectorIndexJob.user_id == user_id,
            models.VectorIndexJob.status == IndexJobStatus.FAILED,
            (models.VectorIndexJob.retry_count or 0) < max_retry_per_job,
        )
        .all()
    )
    for job in failed_retry_jobs:
        try:
            execute_job(db, job)
        except VectorIndexOperationError:
            pass

    # 3) 汇总最终状态
    final_pending = (
        db.query(models.VectorIndexJob)
        .filter(
            models.VectorIndexJob.user_id == user_id,
            models.VectorIndexJob.status == IndexJobStatus.PENDING,
        )
        .count()
    )
    final_failed_jobs = (
        db.query(models.VectorIndexJob)
        .filter(
            models.VectorIndexJob.user_id == user_id,
            models.VectorIndexJob.status == IndexJobStatus.FAILED,
        )
        .all()
    )

    failed_ids = sorted({j.experience_id for j in final_failed_jobs})
    pending_ids = []
    if final_pending > 0:
        # 理论上前面执行过应无 PENDING；若有，收集给用户查看
        remaining = (
            db.query(models.VectorIndexJob)
            .filter(
                models.VectorIndexJob.user_id == user_id,
                models.VectorIndexJob.status == IndexJobStatus.PENDING,
            )
            .all()
        )
        pending_ids = sorted({j.experience_id for j in remaining})

    stats = {
        "processed": len(pending_jobs) + len(failed_retry_jobs),
        "pending": final_pending,
        "failed": len(final_failed_jobs),
        "failed_ids": failed_ids,
        "pending_ids": pending_ids,
    }

    if final_failed_jobs or final_pending:
        raise VectorIndexNotReadyError(
            f"用户 {user_id} 仍有 {final_pending} 条 PENDING + {len(final_failed_jobs)} 条 FAILED 索引任务，"
            "请先修复向量索引或调用 rebuild_user_index_from_sql 全量重建",
            failed_ids=failed_ids,
            pending_ids=pending_ids,
        )
    return stats


# ═══════════════════════════════════════════════════════════════════════════
# 运维工具：从 SQL 全量重建用户向量（幂等，输出失败 ID）
# ═══════════════════════════════════════════════════════════════════════════

def rebuild_user_index_from_sql(db: Session, user_id: str) -> dict:
    """PLAN §5 (6)：按用户从 SQL 全量重建向量索引。

    返回：{ "total_sql", "upserted", "deleted_stale", "failed_ids", "errors": [...] }
    """
    # 1) 从 SQL 取所有经历
    all_exps = experience_service.list_experiences(db, user_id)
    total_sql = len(all_exps)
    failed_ids: list[str] = []
    errors: list[str] = []
    upserted = 0

    for exp in all_exps:
        # 为每条经历创建 Job（事务内创建）
        job = models.VectorIndexJob(
            experience_id=exp.id,
            user_id=user_id,
            operation=IndexOperation.UPSERT,
            status=IndexJobStatus.PENDING,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        try:
            execute_job(db, job)
            upserted += 1
        except VectorIndexOperationError as e:
            failed_ids.append(exp.id)
            errors.append(repr(e))

    # 2) 清理向量库中多余但不在 SQL 里的条目（尽力而为，依赖 chroma_store 接口有限）
    #    注：chroma_store/numpy_store 没有 list_ids 全量接口，V1.3 不强制做
    #    残留项对检索影响较小（RAG 会按 user_id where 过滤；即便命中 SQL 回读会过滤空）
    deleted_stale = 0

    return {
        "total_sql": total_sql,
        "upserted": upserted,
        "deleted_stale": deleted_stale,
        "failed_ids": failed_ids,
        "errors": errors,
    }
