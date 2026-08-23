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

def _backup_sources(sqlite_path: str, vectorstore_dir: Optional[str]) -> dict:
    """复制源数据库与旧索引为只读备份（PLAN §6.3.1）。

    不删除原文件；备份只读（Windows chmod 为 best-effort）。
    """
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backups: dict = {"timestamp": ts, "sqlite": None, "vectorstore": None, "errors": []}

    sqlite_p = Path(sqlite_path)
    if sqlite_p.exists():
        bak = sqlite_p.with_name(f"{sqlite_p.stem}.{ts}.db.bak")
        try:
            shutil.copy2(sqlite_p, bak)
            try:
                os.chmod(bak, 0o444)
            except Exception:
                pass  # Windows 只读语义有限，best-effort
            backups["sqlite"] = str(bak)
        except Exception as e:
            backups["errors"].append(f"sqlite_backup: {e!r}")

    if vectorstore_dir:
        vs = Path(vectorstore_dir)
        if vs.exists():
            bak = vs.parent / f"{vs.name}.{ts}.bak"
            if bak.exists():
                bak = vs.parent / f"{vs.name}.{ts}.{uuid.uuid4().hex[:6]}.bak"
            try:
                shutil.copytree(vs, bak)
                backups["vectorstore"] = str(bak)
            except Exception as e:
                backups["errors"].append(f"vectorstore_backup: {e!r}")

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
    vectorstore_dir: Optional[str] = None,
) -> dict:
    """运行顺序迁移（PLAN §6.3）。

    - backup=True 时先复制源数据库与旧索引为只读备份
    - 按 SchemaVersion 记录顺序应用未执行的迁移；中途失败不写入 version，可安全重试
    - 成功/异常路径均释放 engine 与文件句柄

    返回 summary：{backup, applied, skipped, details, verify}
    """
    sqlite_path = db_path or settings.SQLITE_PATH
    vs_dir = vectorstore_dir if vectorstore_dir is not None else settings.CHROMA_PATH
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
    try:
        if backup:
            summary["backup"] = _backup_sources(sqlite_path, vs_dir)

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
                logger.info("migration skipped (already applied): %s", version)
                continue
            try:
                if kind == "engine":
                    result = _migrate_fact_schema(engine)
                else:
                    result = _migrate_facts_from_experiences(session)
                _record_version(session, version, description)
                summary["applied"].append(version)
                summary["details"][version] = result
                logger.info("migration applied: %s (%s)", version, description)
            except Exception as e:
                session.rollback()
                summary["error"] = f"{version}: {e!r}"
                logger.exception("migration FAILED at %s", version)
                raise

        summary["verify"] = verify_migration(session)
        return summary
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass
