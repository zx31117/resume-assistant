"""V1.4 T3: 本地数据迁移与向量全量重建（一次性脚本，运行后归档）。

原则：
- 旧 backend/data/app.db 只复制，不删不改不覆盖；
- 新库复制到 settings.SQLITE_PATH（runtime root 下）；
- 向量从迁移后的 SQL 全量重建（不依赖旧 Chroma 文件）；
- 回滚：设置 SQLITE_PATH=./data/app.db 即可切回旧库；
- 输出：T3_MIGRATION.json（docs 版本，脱敏）与 runtime/logs 下完整版本。
"""

# V1.5.0 GUARD: 旧向量链路（rag_service / vector_index_sync / chroma_store）已删除。
# 本脚本依赖已退出的模块，在 V1.5.0 上无法运行。
# 请使用 _v13_stub_e2e.py（V1.5.0 适配版）或 _v15_t*.py 系列。
import sys
print("[GUARD] _v14_t3_migrate.py depends on deleted V1.3/V1.4 modules (rag_service/vector_index_sync/chroma_store).")
print("[GUARD] V1.5.0: use _v13_stub_e2e.py or _v15_t*.py instead.")
sys.exit(0)

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# T3 迁移默认强制使用 runtime root 下的新数据目录（不依赖用户本机 .env）。
# 这样 migration 脚本即使在老环境（设置了 SQLITE_PATH/CHROMA_PATH/...）里执行，
# 也会把数据搬到真正的 V1.4 runtime root。
# 如需迁移到自定义目录，运行时显式设置 RESUME_DATA_DIR 环境变量即可。
# ---------------------------------------------------------------------------
_FORCE_VARS = ["SQLITE_PATH", "CHROMA_PATH", "DOCX_OUTPUT_DIR"]
for _k in _FORCE_VARS:
    os.environ.pop(_k, None)

# Monkey patch：不让 load_dotenv 把 backend/.env 里的旧值重新灌回 os.environ
import dotenv as _dotenv
_original_load_dotenv = _dotenv.load_dotenv
def _noop_load_dotenv(*args, **kwargs):
    return False
_dotenv.load_dotenv = _noop_load_dotenv

from core.config import settings  # noqa: E402  # 初始化完成后才能 import

OLD_SQLITE = BACKEND_DIR / "data" / "app.db"
NEW_SQLITE = Path(settings.SQLITE_PATH)
NEW_VECTORSTORE = Path(settings.CHROMA_PATH)
RUNTIME_ROOT = settings.RESUME_DATA_DIR
RUNTIME_LOGS = Path(settings.LOGS_DIR)
DOCS_DIR = BACKEND_DIR / ".." / "docs" / "versions" / "v1.4"
DOCS_REPORT = DOCS_DIR / "T3_MIGRATION.json"
FULL_REPORT = RUNTIME_LOGS / "v1.4-t3-migration-report.json"


def conn_info(path: Path) -> dict:
    c = sqlite3.connect(str(path))
    cur = c.cursor()
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    counts: dict[str, int | None] = {}
    key_ids: dict[str, list] = {}
    for t in tables:
        try:
            counts[t] = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except Exception:
            counts[t] = None
    for t, col in [("users", "id"), ("experiences", "id"), ("vector_index_jobs", "id")]:
        if t in tables:
            try:
                key_ids[t] = [
                    r[0]
                    for r in cur.execute(f'SELECT {col} FROM "{t}" ORDER BY {col}').fetchall()
                ]
            except Exception:
                key_ids[t] = None
    c.close()
    return {"tables": tables, "counts": counts, "key_ids": key_ids}


def summarize(node):
    """去掉真实 ID 列表内容，仅保留数量与布尔/大小等非敏感字段。"""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k.endswith("_ids") and isinstance(v, list):
                out[k] = {"count": len(v)}
            else:
                out[k] = summarize(v)
        return out
    if isinstance(node, list):
        return [summarize(x) for x in node]
    return node


def do_migrate(
    backend_root: Path | None = None,
    settings_module=None,
    rebuild_vectors: bool = False,
    strict_sql: bool = True,
) -> dict:
    """T7 友好的可调用迁移入口。返回结构化报告，副作用与 main() 一致。

    参数：
    - backend_root / settings_module：兼容旧 T7 夹具（实现上忽略，仅为了 T7 测试 API 稳定）；
    - rebuild_vectors：True → 触发 T3.3 向量重建（需要 ARK_API_KEY）；
    - strict_sql：True → 发现任何不一致时在返回 dict 里标 `strict_sql_failed=True`。
    """
    # —— 无论 T7 如何传参，迁移始终使用本脚本在 import 时已经强制生效的
    #    OLD_SQLITE / NEW_SQLITE / NEW_VECTORSTORE（RESUME_DATA_DIR 优先）。
    report: dict = {"ts_utc": time.time()}
    report["before"] = {
        "old_sqlite": str(OLD_SQLITE),
        "old_sqlite_exists": OLD_SQLITE.exists(),
        "old_sqlite_size": OLD_SQLITE.stat().st_size if OLD_SQLITE.exists() else None,
        "new_sqlite": str(NEW_SQLITE),
        "new_sqlite_exists_pre": NEW_SQLITE.exists(),
        "new_vectorstore": str(NEW_VECTORSTORE),
    }

    if not OLD_SQLITE.exists():
        report["old_db"] = None
        report["warning"] = "OLD SQLITE NOT FOUND — skip copy."
    else:
        report["old_db"] = conn_info(OLD_SQLITE)
        NEW_SQLITE.parent.mkdir(parents=True, exist_ok=True)

        # 历史残留：新 runtime root 下若存在名为 app.db 的目录（误把文件路径当目录创建），
        # 先把它重命名为 .bad-<timestamp> 再继续（不删除、可回滚）。
        if NEW_SQLITE.exists() and NEW_SQLITE.is_dir():
            bad_backup = NEW_SQLITE.with_name(NEW_SQLITE.name + f".bad-dir-{int(time.time())}")
            NEW_SQLITE.rename(bad_backup)
            report["preexisting_new_db_path_was_dir_renamed_to"] = str(bad_backup)

        if NEW_SQLITE.exists() and NEW_SQLITE.is_file():
            backup = NEW_SQLITE.with_name(NEW_SQLITE.name + f".bak-{int(time.time())}")
            try:
                shutil.copy2(NEW_SQLITE, backup)
                report["preexisting_new_db_backed_up_to"] = str(backup)
            except (PermissionError, OSError) as e:
                report["preexisting_new_db_backup_skipped"] = repr(e)
        shutil.copy2(OLD_SQLITE, NEW_SQLITE)
        report["copy_done"] = True
        report["after_copy"] = {
            "new_sqlite_size": NEW_SQLITE.stat().st_size,
            "size_equal": NEW_SQLITE.stat().st_size == OLD_SQLITE.stat().st_size,
        }
        report["new_db_after_copy"] = conn_info(NEW_SQLITE)
        od = report["old_db"]
        nd = report["new_db_after_copy"]
        report["migration_checks"] = {
            "tables_equal": od["tables"] == nd["tables"],
            "counts_equal": od["counts"] == nd["counts"],
            "users_ids_equal": od["key_ids"].get("users") == nd["key_ids"].get("users"),
            "experiences_ids_equal": od["key_ids"].get("experiences") == nd["key_ids"].get("experiences"),
            "jobs_ids_equal": od["key_ids"].get("vector_index_jobs") == nd["key_ids"].get("vector_index_jobs"),
        }
        # —— 给 T7 用的扁平化 sql_identical 视图 —— #
        new_counts = (nd or {}).get("counts") or {}
        users_ids = set((nd or {}).get("key_ids", {}).get("users") or [])
        exp_ids = set((nd or {}).get("key_ids", {}).get("experiences") or [])
        jobs_ids = set((nd or {}).get("key_ids", {}).get("vector_index_jobs") or [])
        users_ids_old = set((od or {}).get("key_ids", {}).get("users") or [])
        exp_ids_old = set((od or {}).get("key_ids", {}).get("experiences") or [])
        jobs_ids_old = set((od or {}).get("key_ids", {}).get("vector_index_jobs") or [])
        report["sql_identical"] = {
            **(report["migration_checks"]),
            "new_counts": new_counts,
            "old_counts": (od or {}).get("counts"),
            "users_ids_set_equal": users_ids == users_ids_old,
            "experiences_ids_set_equal": exp_ids == exp_ids_old,
            "jobs_ids_set_equal": jobs_ids == jobs_ids_old,
        }
        if strict_sql and not all(report["sql_identical"].values()):
            report["strict_sql_failed"] = True

    # 旧数据仍然存在（不删除、不覆盖、不改动）
    report["OLD_DATA_NOT_DELETED"] = OLD_SQLITE.exists()
    report["rollback_hint"] = (
        "Set env SQLITE_PATH=str(OLD_SQLITE) to switch back to old data."
    )

    # T3.3：向量从迁移后 SQL 全量重建（仅当显式调用方要求 rebuild_vectors=True）
    if rebuild_vectors:
        try:
            from database.init_db import init_db
            from database.session import SessionLocal
            from services.vector_index_sync import rebuild_user_index_from_sql
            init_db()
            db = SessionLocal()
            try:
                # 自动从数据库获取实际 user_id（而非依赖 settings.DEFAULT_USER_ID
                # 可能与真实数据不一致——如本库 user_id 是 UUID 而非 'demo-user'）
                from database.models import User
                actual_user = db.query(User).first()
                actual_uid = str(actual_user.id) if actual_user else settings.DEFAULT_USER_ID
                report["vector_rebuild_user_id"] = actual_uid
                report["vector_rebuild_user_id_source"] = "sql_first_user" if actual_user else "settings_default"
                rebuild = rebuild_user_index_from_sql(db, actual_uid)
            finally:
                db.close()
            report["vector_rebuild_from_new_sql"] = rebuild
            report["vector_rebuild_all_ok"] = not (rebuild.get("failed_ids") or [])
        except Exception as e:
            report["vector_rebuild_error"] = repr(e)
            import traceback
            report["vector_rebuild_tb"] = traceback.format_exc()

    # 落盘两份报告：runtime 完整版（含 key_ids）+ docs 脱敏版
    RUNTIME_LOGS.mkdir(parents=True, exist_ok=True)
    with open(FULL_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    with open(DOCS_REPORT, "w", encoding="utf-8") as f:
        json.dump(summarize(report), f, ensure_ascii=False, indent=2, default=str)

    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild-vectors", action="store_true",
                        help="执行 T3.3：从迁移后 SQL 全量重建 Chroma（需要本机已配置 ARK_API_KEY）")
    args = parser.parse_args()

    report = do_migrate(
        backend_root=BACKEND_DIR,
        settings_module=None,
        rebuild_vectors=args.rebuild_vectors,
        strict_sql=True,
    )

    print(json.dumps(summarize(report), ensure_ascii=False, indent=2))
    print()
    print("FULL_REPORT =", FULL_REPORT)
    print("DOCS_REPORT =", DOCS_REPORT)
    print("OLD_DATA_DELETED =", not report.get("OLD_DATA_NOT_DELETED", False), "  (must be False)")
    if report.get("strict_sql_failed"):
        print("STRICT SQL FAILED — migration_checks:", report.get("migration_checks"))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
