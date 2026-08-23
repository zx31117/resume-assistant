"""V1.5.0 R2: 唯一受支持的本地维护入口（CLI）。

PLAN §12.3 R2：正常用户不需要 import 私有 service 即可迁移、查状态、重试和重建。

用法：
    python manage.py migrate    # 运行迁移（备份 + schema + Fact 迁移）
    python manage.py status      # 查看迁移与 Embedding 状态
    python manage.py rebuild      # 全量重建 Embedding
    python manage.py retry        # 重试 FAILED 的 Embedding

退出码：成功 0，失败非零。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 确保 backend/ 在 sys.path
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import settings
from database.models import Base, SchemaVersion, Fact, FactEmbedding, EmbeddingStatus
from database.migrations import run_migrations, SCHEMA_VERSION_FACT_SCHEMA, SCHEMA_VERSION_FACT_MIGRATION
from services import embedding_service


def _get_engine():
    return create_engine(
        f"sqlite:///{settings.SQLITE_PATH}",
        connect_args={"check_same_thread": False},
    )


def _get_session(engine):
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def cmd_migrate():
    """运行迁移（备份 + schema + Fact 迁移）。"""
    print(f"[migrate] SQLite: {settings.SQLITE_PATH}")
    try:
        summary = run_migrations(backup=True)
    except Exception as e:
        print(f"[migrate] FAILED: {e}", file=sys.stderr)
        return 1
    print("[migrate] Result:")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    if summary.get("error"):
        print(f"[migrate] ERROR: {summary['error']}", file=sys.stderr)
        return 1
    print("[migrate] OK")
    return 0


def cmd_status():
    """查看迁移与 Embedding 状态。"""
    engine = _get_engine()
    try:
        Base.metadata.create_all(bind=engine)
        session = _get_session(engine)
        try:
            # 迁移状态
            applied = {row.version for row in session.query(SchemaVersion).all()}
            required = [SCHEMA_VERSION_FACT_SCHEMA, SCHEMA_VERSION_FACT_MIGRATION]
            missing = [v for v in required if v not in applied]

            # Fact 统计
            fact_count = session.query(Fact).count()

            # Embedding 统计
            emb_summary = embedding_service.status_summary(session)

            print("[status] Migration:")
            print(f"  applied: {sorted(applied)}")
            print(f"  missing: {missing}")
            print(f"[status] Facts: {fact_count}")
            print(f"[status] Embeddings: {json.dumps(emb_summary, ensure_ascii=False, indent=2)}")

            if missing:
                print(f"\n[status] WARNING: migrations not applied: {missing}", file=sys.stderr)
                print("[status] Run 'python manage.py migrate' to apply.", file=sys.stderr)
                return 1
            if fact_count == 0:
                print("\n[status] WARNING: no facts found. Import experiences first.", file=sys.stderr)
                return 1
            if emb_summary.get("PENDING", 0) > 0 or emb_summary.get("FAILED", 0) > 0:
                print(f"\n[status] WARNING: {emb_summary.get('PENDING', 0)} PENDING, "
                      f"{emb_summary.get('FAILED', 0)} FAILED embeddings.", file=sys.stderr)
                print("[status] Run 'python manage.py rebuild' to rebuild.", file=sys.stderr)
                return 1
            print("\n[status] OK: all migrations applied, embeddings ready.")
            return 0
        finally:
            session.close()
    finally:
        engine.dispose()


def cmd_rebuild():
    """全量重建 Embedding。"""
    engine = _get_engine()
    try:
        Base.metadata.create_all(bind=engine)
        session = _get_session(engine)
        try:
            print(f"[rebuild] Fingerprint: {embedding_service.compute_fingerprint()}")
            summary = embedding_service.rebuild_embeddings(session)
            print("[rebuild] Result:")
            print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
            if summary.get("skipped_no_key"):
                print("\n[rebuild] SKIPPED: ARK_API_KEY not configured.", file=sys.stderr)
                print("[rebuild] Facts migrated, embeddings stay PENDING.", file=sys.stderr)
                print("[rebuild] Configure ARK_API_KEY and run 'python manage.py rebuild'.", file=sys.stderr)
                return 1
            if summary.get("failed", 0) > 0:
                print(f"\n[rebuild] WARNING: {summary['failed']} embeddings FAILED.", file=sys.stderr)
                print("[rebuild] Run 'python manage.py retry' to retry failed.", file=sys.stderr)
                return 1
            print("[rebuild] OK")
            return 0
        finally:
            session.close()
    finally:
        engine.dispose()


def cmd_retry():
    """重试 FAILED 的 Embedding（等同于 rebuild，只处理 FAILED/PENDING/INVALID）。"""
    return cmd_rebuild()


_COMMANDS = {
    "migrate": cmd_migrate,
    "status": cmd_status,
    "rebuild": cmd_rebuild,
    "retry": cmd_retry,
}


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("Usage: python manage.py <command>")
        print("Commands:")
        for cmd, fn in _COMMANDS.items():
            print(f"  {cmd:10s} {fn.__doc__.strip().splitlines()[0] if fn.__doc__ else ''}")
        return 0
    cmd = argv[0]
    if cmd not in _COMMANDS:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(f"Available: {', '.join(_COMMANDS)}", file=sys.stderr)
        return 2
    return _COMMANDS[cmd]()


if __name__ == "__main__":
    sys.exit(main())
