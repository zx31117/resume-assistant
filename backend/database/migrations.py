"""V1.5.0 迁移框架：schema version + 顺序迁移 + 备份 + 幂等 Fact 生成（PLAN §6）。

设计原则：
- 确定性迁移，不调用 LLM（PLAN §6.1）
- 迁移前备份源数据库与旧索引（只读副本，PLAN §6.3.1）
- 幂等：fact_id 由 experience_id + source locator 确定性派生，重复迁移同身份不重复创建（§6.1.5）
- 中途失败不写入 SchemaVersion，可安全重试；成功后写入（§6.3.8）
- 成功/异常/提前退出均释放 engine 与文件句柄（§6.3）
- 日志与产物只记数量/ID/hash，不记履历正文、API Key 或本机用户名（§6.3）
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import settings
from core.errors import MigrationError
from core.operations import Recording, ResourceType, optional_stage
from database.models import Base, Experience, Fact, FactType, SchemaVersion

logger = logging.getLogger(__name__)

# 确定性 fact_id 派生命名空间（固定值，保证跨机器/跨重跑同 identity）
_FACT_NAMESPACE = uuid.UUID("7f5e2a1b-1c40-4d2a-9b6e-000000000001")

SCHEMA_VERSION_FACT_SCHEMA = "v1.5.0-fact-schema"
SCHEMA_VERSION_FACT_MIGRATION = "v1.5.0-fact-migration"

# 顺序迁移注册表：(version, description, callable(session_or_engine))
# schema 步骤接收 engine；数据步骤接收 session
_MIGRATIONS = [
    (SCHEMA_VERSION_FACT_SCHEMA, "Create Fact + SchemaVersion tables", "engine"),
    (SCHEMA_VERSION_FACT_MIGRATION, "Deterministic Experience -> Fact migration", "session"),
]


# ── 哈希与确定性派生 ─────────────────────────────────────────── #

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _normalize_text(s: str) -> str:
    return (s or "").strip()


def derive_fact_id(experience_id: str, source_field: str, source_index: Optional[int]) -> str:
    """fact_id = uuid5(NAMESPACE, f"{experience_id}|{source_field}|{source_index}").

    确定性派生：相同 experience + locator → 相同 fact_id（PLAN §6.1.5 幂等）。
    """
    locator = f"{source_field}|{'' if source_index is None else source_index}"
    return str(uuid.uuid5(_FACT_NAMESPACE, f"{experience_id}|{locator}"))


# ── Fact 候选派生（确定性，无 LLM） ──────────────────────────── #

def _iter_fact_candidates(experience: Experience) -> list[dict]:
    """从单个 Experience 确定性派生 Fact 候选（PLAN §6.1）。

    首批范围只迁移 description + achievements 的非空项：
    - skills 不迁移（技能走确定性结构，§4.1）
    - raw_text 不迁移（它是源不是可表达细节）
    - description 无法安全拆细 → 保留为较粗 Fact（§6.1.3）
    fact_type 粗粒度赋值，不调 LLM 细分（§5.2 粗粒度 bullet 可参与流程）。
    """
    candidates: list[dict] = []
    desc = _normalize_text(experience.description or "")
    if desc:
        candidates.append({
            "source_field": "description",
            "source_index": None,
            "source_text": desc,
            "text": desc,
            "fact_type": FactType.RESPONSIBILITY,
        })
    achievements = experience.achievements or []
    for i, ach in enumerate(achievements):
        a = _normalize_text(ach or "")
        if a:
            candidates.append({
                "source_field": "achievements",
                "source_index": i,
                "source_text": a,
                "text": a,
                "fact_type": FactType.RESULT,
            })
    return candidates


def _upsert_fact(session: Session, experience_id: str, cand: dict) -> tuple[str, str]:
    """幂等 upsert 单条 Fact。返回 (fact_id, status)。

    status:
    - created：新插入
    - noop：已存在且 source_hash 相同（Experience 未变）
    - updated：已存在但 source_hash 不同（Experience 被改后重跑迁移）→ 更新文本/hash + bump revision
    """
    fact_id = derive_fact_id(experience_id, cand["source_field"], cand["source_index"])
    content_hash = _sha256(_normalize_text(cand["text"]))
    source_hash = _sha256(cand["source_text"])

    fact = session.get(Fact, fact_id)
    if fact is None:
        fact = Fact(
            fact_id=fact_id,
            experience_id=experience_id,
            fact_type=cand["fact_type"],
            text=cand["text"],
            source_text=cand["source_text"],
            source_field=cand["source_field"],
            source_index=cand["source_index"],
            content_hash=content_hash,
            source_hash=source_hash,
            revision=1,
        )
        session.add(fact)
        return fact_id, "created"

    if fact.source_hash == source_hash:
        return fact_id, "noop"

    # Experience 被改后重跑迁移：更新文本/来源/hash 并 bump revision（触发派生数据失效）
    fact.text = cand["text"]
    fact.source_text = cand["source_text"]
    fact.source_hash = source_hash
    fact.content_hash = content_hash
    fact.revision = (fact.revision or 1) + 1
    fact.updated_at = datetime.utcnow()
    return fact_id, "updated"


# ── 备份 ─────────────────────────────────────────────────────── #

def _backup_sources(sqlite_path: str) -> dict:
    """R3: 复制源数据库为只读备份并验证完整性。

    R3 fail closed: 备份失败或完整性核对失败均记入 errors。
    调用方（run_migrations）检查 errors 非空时 raise，不继续破坏性步骤。
    保存不含履历正文的 manifest（只记数量/hash/路径）。
    """
    import json as _json
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backups: dict = {"timestamp": ts, "sqlite": None, "errors": [], "manifest": None}

    sqlite_p = Path(sqlite_path)
    if not sqlite_p.exists():
        backups["errors"].append(f"sqlite_backup: source not found: {sqlite_path}")
        return backups

    # R3: 处理同名备份冲突（同一 UTC 秒内重复迁移、或历史同名只读备份）。
    # 不覆盖既有备份——追加数字后缀生成唯一名，避免破坏已有只读快照。
    bak = sqlite_p.with_name(f"{sqlite_p.stem}.{ts}.db.bak")
    suffix = 1
    while bak.exists():
        bak = sqlite_p.with_name(f"{sqlite_p.stem}.{ts}.{suffix}.db.bak")
        suffix += 1
    try:
        shutil.copy2(sqlite_p, bak)
    except Exception as e:
        # R3 fix: Windows file lock — fall back to sqlite3.backup() API
        # which works even when the database is open by another connection
        try:
            import sqlite3 as _sqlite3
            src_conn = _sqlite3.connect(str(sqlite_p))
            try:
                dst_conn = _sqlite3.connect(str(bak))
                try:
                    src_conn.backup(dst_conn)
                finally:
                    dst_conn.close()
            finally:
                src_conn.close()
            logger.info("sqlite_backup: shutil.copy2 failed (%r), used sqlite3.backup() fallback", e)
        except Exception as e2:
            backups["errors"].append(f"sqlite_backup copy failed: {e!r}; sqlite3.backup fallback also failed: {e2!r}")
            return backups

    # R3: 验证备份完整性（存在性 + 可读性 + 大小匹配）
    if not bak.exists():
        backups["errors"].append(f"sqlite_backup verify: backup not found after copy: {bak}")
        return backups
    src_size = sqlite_p.stat().st_size
    bak_size = bak.stat().st_size
    if src_size != bak_size:
        backups["errors"].append(
            f"sqlite_backup verify: size mismatch src={src_size} bak={bak_size}"
        )
        return backups
    # 可读性验证：尝试打开读取前 4 字节
    try:
        with open(bak, "rb") as f:
            f.read(4)
    except Exception as e:
        backups["errors"].append(f"sqlite_backup verify: unreadable: {e!r}")
        return backups

    try:
        os.chmod(bak, 0o444)
    except Exception:
        pass  # Windows 只读语义有限，best-effort

    backups["sqlite"] = str(bak)

    # R3: 保存不含履历正文的 manifest（只记路径/大小/时间）
    manifest = {
        "timestamp": ts,
        "source": str(sqlite_p),
        "source_size": src_size,
        "backup": str(bak),
        "backup_size": bak_size,
        "verified": True,
    }
    manifest_path = sqlite_p.with_name(f"{bak.stem}.manifest.json")
    try:
        manifest_path.write_text(_json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        backups["manifest"] = str(manifest_path)
    except Exception as e:
        backups["errors"].append(f"manifest write failed: {e!r}")

    return backups


# ── 迁移步骤 ─────────────────────────────────────────────────── #

def _migrate_fact_schema(engine) -> dict:
    """创建 Fact / SchemaVersion 表（create_all 幂等，只建缺失表）。"""
    Base.metadata.create_all(bind=engine)
    return {"tables_ensured": True}


def _migrate_facts_from_experiences(session: Session) -> dict:
    """确定性 Experience → Fact 迁移（幂等 upsert）。"""
    experiences = session.query(Experience).all()
    created = updated = noop = 0
    fact_ids: list[str] = []
    for exp in experiences:
        for cand in _iter_fact_candidates(exp):
            fid, status = _upsert_fact(session, exp.id, cand)
            fact_ids.append(fid)
            if status == "created":
                created += 1
            elif status == "updated":
                updated += 1
            else:
                noop += 1
    session.commit()
    fact_ids.sort()
    return {
        "experiences": len(experiences),
        "facts_total": len(fact_ids),
        "created": created,
        "updated": updated,
        "noop": noop,
        "fact_ids": fact_ids,
    }


# ── 版本记录 ─────────────────────────────────────────────────── #

def _is_applied(session: Session, version: str) -> bool:
    return session.get(SchemaVersion, version) is not None


def _record_version(session: Session, version: str, description: str) -> None:
    if not _is_applied(session, version):
        session.add(SchemaVersion(version=version, description=description))
        session.commit()


# ── 核对 ─────────────────────────────────────────────────────── #

def verify_migration(session: Session) -> dict:
    """核对 Experience、Fact 数量、孤儿 Fact 与无 Fact 的 Experience（PLAN §6.3.3）。"""
    experiences = session.query(Experience).all()
    facts = session.query(Fact).all()
    exp_ids = {e.id for e in experiences}
    fact_exp_ids = {f.experience_id for f in facts}
    orphan_facts = [f.fact_id for f in facts if f.experience_id not in exp_ids]
    exps_without_facts = sorted(exp_ids - fact_exp_ids)
    return {
        "experiences": len(experiences),
        "facts": len(facts),
        "orphan_fact_ids": orphan_facts,
        "orphan_facts": len(orphan_facts),
        "experience_ids_without_facts": exps_without_facts,
    }


# ── 迁移运行器 ───────────────────────────────────────────────── #

def run_migrations(
    db_path: Optional[str] = None,
    *,
    backup: bool = True,
    recording: Optional[Recording] = None,
) -> dict:
    """运行顺序迁移（PLAN §6.3）。

    - backup=True 时先复制源数据库与旧索引为只读备份
    - 按 SchemaVersion 记录顺序应用未执行的迁移；中途失败不写入 version，可安全重试
    - 成功/异常路径均释放 engine 与文件句柄

    V2.0.1（T3）：真实阶段（前置检查 / 备份 / 应用迁移 / 后置核验 / 资源释放）进入
    统一 operation 记录（PLAN §5.3）；recording 为 None 时打点退化 no-op，行为不变。

    返回 summary：{backup, applied, skipped, details, verify}
    """
    sqlite_path = db_path or settings.SQLITE_PATH
    summary: dict = {
        "db_path": sqlite_path,
        "backup": None,
        "applied": [],
        "skipped": [],
        "details": {},
        "verify": None,
        "error": None,
    }

    engine = None
    session: Optional[Session] = None
    _cleanup_errors: list[str] = []
    try:
        # 1) 前置检查（PLAN §5.3）
        with optional_stage(recording, "pre_check", "前置检查", ResourceType.LOCAL_DB):
            src_p = Path(sqlite_path)
            if src_p.exists() and src_p.is_dir():
                # W3: 既有路径是目录而非 SQLite 文件，不得误判为新库或继续迁移
                summary["error"] = f"migration source is a directory, not a SQLite file: {sqlite_path}"
                raise MigrationError(summary["error"], stage="migration")
            is_fresh = not src_p.exists()

        # 2) SQLite/旧派生数据备份（PLAN §5.3）
        with optional_stage(recording, "backup", "SQLite/旧派生数据备份", ResourceType.LOCAL_FILE):
            if backup:
                if is_fresh:
                    # W3: 全新空库——文件尚不存在，无需备份；仅建库并应用迁移
                    summary["backup"] = {
                        "timestamp": None, "sqlite": None,
                        "errors": [], "manifest": None,
                        "note": "fresh empty database; backup skipped",
                    }
                else:
                    summary["backup"] = _backup_sources(sqlite_path)
                    # R3: fail closed — backup errors mean we must not continue
                    if summary["backup"].get("errors"):
                        summary["error"] = "backup failed: " + "; ".join(summary["backup"]["errors"])
                        raise MigrationError(summary["error"], stage="migration")

        # 3) 应用迁移（PLAN §5.3）
        applied_count = 0
        skipped_count = 0
        with optional_stage(recording, "apply_migration", "应用迁移", ResourceType.LOCAL_DB) as s:
            engine = create_engine(
                f"sqlite:///{sqlite_path}",
                connect_args={"check_same_thread": False},
            )
            Base.metadata.create_all(bind=engine)  # 确保 schema_versions 表存在
            SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            session = SessionLocal()

            for version, description, kind in _MIGRATIONS:
                if _is_applied(session, version):
                    summary["skipped"].append(version)
                    skipped_count += 1
                    logger.info("migration skipped (already applied): %s", version)
                    continue
                try:
                    if kind == "engine":
                        result = _migrate_fact_schema(engine)
                    else:
                        result = _migrate_facts_from_experiences(session)
                    _record_version(session, version, description)
                    summary["applied"].append(version)
                    applied_count += 1
                    summary["details"][version] = result
                    logger.info("migration applied: %s (%s)", version, description)
                except Exception as e:
                    session.rollback()
                    summary["error"] = f"{version}: {e!r}"
                    logger.exception("migration FAILED at %s", version)
                    raise
            if s is not None:
                s.counts(applied=applied_count, skipped=skipped_count)

        # 4) 后置核验（PLAN §5.3）
        with optional_stage(recording, "verify", "后置核验", ResourceType.LOCAL_DB) as s:
            summary["verify"] = verify_migration(session)
            if s is not None:
                ver = summary["verify"]
                s.counts(experiences=ver.get("experiences", 0), facts=ver.get("facts", 0))

        return summary
    finally:
        # 5) 资源释放（PLAN §5.3）：无论正常/异常均执行并记录真实结果
        release_scope = recording.stage("release", "资源释放", ResourceType.LOCAL_DB) if recording is not None else None
        try:
            # R3: track cleanup errors instead of swallowing with pass
            if session is not None:
                try:
                    session.close()
                except Exception as e:
                    _cleanup_errors.append(f"session.close: {e!r}")
            if engine is not None:
                try:
                    engine.dispose()
                except Exception as e:
                    _cleanup_errors.append(f"engine.dispose: {e!r}")
        finally:
            if release_scope is not None:
                if _cleanup_errors:
                    release_scope.__exit__(MigrationError, MigrationError("cleanup failure"), None)
                else:
                    release_scope.__exit__(None, None, None)
            # R3: cleanup failure after retries → non-zero
            if _cleanup_errors:
                logger.error("cleanup errors: %s", _cleanup_errors)
                if not summary.get("error"):
                    summary["error"] = "cleanup failed: " + "; ".join(_cleanup_errors)
                    raise MigrationError(summary["error"], stage="cleanup")
