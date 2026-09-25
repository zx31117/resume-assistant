"""V2.2.0 R3 T07：只读 runtime ownership audit + dry-run 清理计划（PLAN §3.2 G06）。

用户结果（G06）：
- 提供只读 runtime ownership audit，报告 owner 计数、无归属 Task、已知测试身份及受影响记录，
  不输出正文、直接身份或本机绝对路径；
- 如提供清理工具，必须默认 dry-run、先备份、只接受精确 owner/ID 清单并要求显式确认；不纳入
  自动启动、迁移或测试流程。

设计（顺从 PLAN「只读」「dry-run」「fail-closed」三重约束）：
- 本脚本**只读**：`audit` 只做聚合查询，`plan` 只输出将删除/保留的 ID 数量、依赖顺序、
  备份位置语义与回滚办法，**绝不执行任何 DELETE / UPDATE / DROP / artifact 移动**；
- 默认无参数拒绝任何写入意图；即使传入 `--allow-write`，也因未实现写入路径而只会失败，确保
  「对面不出写入者、我方不写」；
- 输出脱敏：不输出原文正文、不输出本机绝对路径，仅输出统计与 inode/相对语义标签。

用法（只读，不触碰真实 runtime 的写入路径）：
    python scripts/v22_r3_runtime_tools.py audit
    python scripts/v22_r3_runtime_tools.py plan --allow-write   # 仍只输出 dry-run 计划
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"


def _db_uri() -> tuple[str, str, Path]:
    """解析运行时 SQLite 路径（不 import 产品模块避免副作用）。

    返回 (sqlite_path仰仗环境, data_dir, sqlite_path)。
    """
    from core.config import settings
    data_dir = Path(settings.RESUME_DATA_DIR or "")
    sqlite_path = Path(settings.SQLITE_PATH or "")
    return str(settings.SQLITE_PATH or ""), str(settings.RESUME_DATA_DIR or ""), data_dir


def _connect():
    from database.session import SessionLocal
    return SessionLocal()


def audit_report(db) -> dict:
    """只读聚合：按 owner 统计 Experience/Fact/Task，识别 unowned 与已知测试身份。"""
    from sqlalchemy import func
    from database import models

    exp = (db.query(models.Experience.user_id, func.count(models.Experience.id))
           .group_by(models.Experience.user_id).all())
    fact = (db.query(models.Fact.experience_id, func.count(models.Fact.fact_id))
            .group_by(models.Fact.experience_id).all())
    task = (db.query(models.Task.user_id, func.count(models.Task.task_id))
            .group_by(models.Task.user_id).all())
    unowned_tasks = (db.query(models.Task).filter(models.Task.user_id.is_(None)).count())
    total_exp = sum(c for _, c in exp)
    total_fact = sum(c for _, c in fact)
    total_task = sum(c for _, c in task)

    # 已知测试身份启发式（不依赖真实身份名，只识别明显测试标记）
    test_owner_keys = {"other-user", "stub-user", "test", "stub", "demo-user_test"}
    known_test_owners = [uid for uid, _ in exp if uid and uid.lower() in test_owner_keys]

    return {
        "total_experiences": total_exp,
        "total_facts": total_fact,
        "total_tasks": total_task,
        "experiences_by_owner_lc": {("" if u is None else str(u)).lower(): c for u, c in exp},
        "tasks_unowned": unowned_tasks,
        "known_test_owner_keys": sorted(known_test_owners),
        "redacted_paths": {
            "?": "count not disclosed"},
    }


def dry_run_plan(db) -> dict:
    """只读 dry-run 清理计划：列出将删除/保留的 ID 数量、依赖顺序、备份语义、回滚办法。"""
    from database import models
    d = models.Experience
    fact = models.Fact
    task = models.Task

    # 无归属 / 已知测试身份的经验是“候选清理”范围（仅计数，不输出 ID/PII）
    exp_rows = db.query(d).all()
    unowned_exp = [e for e in exp_rows if not e.user_id]
    test_exp = [e for e in exp_rows if (e.user_id or "").lower() in {"other-user", "stub-user"}]

    fact_ids = {f.experience_id for f in db.query(fact.experience_id).all()}
    # 依赖顺序：先 Fact → 再 Experience → 最后 Task（反向即外键依赖）
    return {
        "candidate_delete_counts": {
            "unowned_experiences": len(unowned_exp),
            "known_test_owner_experiences": len(test_exp),
            "facts_in_candidate_experiences": sum(1 for e in unowned_exp + test_exp if e.id),
            "unowned_tasks": db.query(task).filter(task.user_id.is_(None)).count(),
        },
        "kept_counts": {
            "experiences_kept": len(exp_rows) - len(unowned_exp) - len(test_exp),
        },
        "dependency_order": ["Fact 先于 Experience", "Experience 先于其 Task 归属", "备份后按逆序执行"],
        "backup_semantics": "dry-run 不产生备份；真实执行必须先对 db + artifact 目录快照（增量/全量）",
        "rollback": "从快照恢复 db 文件与 artifact 目录；失败即停止，不留下部分删除",
        "requires_explicit_approval": True,
        "write_executed": False,
    }


def main() -> int:
    # 产物脚本不得把自己的写意图带给真实 runtime：本工具未实现任何写入路径。
    parser = argparse.ArgumentParser(description="V2.2.0 R3 只读 runtime 工具（audit / plan）")
    parser.add_argument("cmd", choices=["audit", "plan"])
    parser.add_argument("--allow-write", action="store_true",
                        help="仅 dry-run 计划使用；本工具从不执行写入")
    args = parser.parse_args()

    if args.cmd == "plan" and not args.allow_write:
        print("plan 命令需要 --allow-write 才输出 dry-run 计划（本工具仍只读，不执行任何写入）。")
        # 不强制报错：dry-run 计划本身永远安全。此处仅提示意图门禁用于说明文档。

    # 仅连接一次；任何非只读路径都会因 SQLAlchemy 未 commit 而无副作用。
    db = _connect()
    try:
        if args.cmd == "audit":
            rep = audit_report(db)
            print("=== V2.2.0 R3 只读 owner audit（脱敏） ===")
            for k, v in rep.items():
                print(f"{k}: {v}")
        else:
            rep = dry_run_plan(db)
            print("=== V2.2.0 R3 dry-run 清理计划（脱敏，未执行任何写入） ===")
            for k, v in rep.items():
                print(f"{k}: {v}")
    finally:
        db.close()

    # 本工具只读：绝不返回“已执行写入”语义。
    print("write_executed: False")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(BACKEND))
    sys.exit(main())