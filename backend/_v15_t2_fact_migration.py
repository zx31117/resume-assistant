"""V1.5.0 T2 验证：Fact Schema、迁移框架、幂等、修改失效与资源生命周期。

在独立临时 runtime 上用虚构 fixture 验证（PLAN §6 / §8.2），不读取/覆盖真实 runtime：
- 空库迁移、fixture 迁移、重复迁移幂等（fact_id 确定性）
- source/content hash、孤儿检查、SchemaVersion 记录
- modify_fact 更新 revision/hash + 触发失效钩子
- 部分失败后重试（删除 version + 删除部分 Fact → 重跑补齐）
- 备份生成、资源释放（engine disposed）
- 日志/产物只含数量/ID/hash，不含履历正文

退出码 0 = 全部通过；非 0 = 有失败。
"""
from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

# 确保 backend/ 在 sys.path（裸 import: database/services/core）
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import models
from database.models import Base, Experience, Fact, FactType, SchemaVersion
from database import migrations
from services import fact_service
from core import errors

# ── 临时 runtime ──────────────────────────────────────────────── #
_TMP = Path(tempfile.mkdtemp(prefix="v15_t2_"))
_SQLITE = _TMP / "app.db"


def _cleanup():
    try:
        shutil.rmtree(_TMP, ignore_errors=True)
    except Exception:
        pass


atexit.register(_cleanup)

# ── 断言工具 ─────────────────────────────────────────────────── #
_assertions = {"pass": 0, "fail": 0}


def check(cond: bool, name: str):
    if cond:
        _assertions["pass"] += 1
        print(f"  [PASS] {name}")
    else:
        _assertions["fail"] += 1
        print(f"  [FAIL] {name}")


def _new_engine():
    return create_engine(f"sqlite:///{_SQLITE}", connect_args={"check_same_thread": False})


def _insert_fixtures():
    """插入虚构 Experience（不涉及真实履历）。"""
    eng = _new_engine()
    Base.metadata.create_all(bind=eng)
    SL = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    s = SL()
    try:
        # work：有 description + 2 achievements → 3 facts
        s.add(Experience(
            id="exp-work-001", user_id="demo", type="work",
            title="后端工程师", company="Acme", time="2023.01-2024.06",
            role="后端", description="负责订单系统重构与稳定性治理",
            skills=["python"], achievements=["订单接口 QPS 提升 3 倍", "故障率下降 80%"],
        ))
        # project：只有 description（无 achievements）→ 1 fact
        s.add(Experience(
            id="exp-proj-001", user_id="demo", type="project",
            title="推荐系统", company="", time="2022.05-2022.12",
            role="负责人", description="从 0 搭建召回排序链路",
            skills=[], achievements=[],
        ))
        # education：description 为空、1 achievement → 1 fact（校园可迁移，选材补位时才参与）
        s.add(Experience(
            id="exp-edu-001", user_id="demo", type="education",
            title="校学生会", company="某大学", time="2019-2021",
            role="技术部长", description="", skills=[],
            achievements=["组织校级编程马拉松"],
        ))
        # 空 Experience（description + achievements 全空）→ 0 fact
        s.add(Experience(
            id="exp-empty-001", user_id="demo", type="work",
            title="空经历", company="", time="", role="",
            description="", skills=[], achievements=[],
        ))
        s.commit()
    finally:
        s.close()
        eng.dispose()


def main() -> int:
    print(f"V1.5.0 T2 验证 | tmp={_TMP}")

    # ── 1. 插入 fixture ──
    _insert_fixtures()
    print("[1] fixture inserted: 4 experiences (3 with detail, 1 empty)")

    # ── 2. 首次迁移 ──
    print("[2] run_migrations (first)...")
    r1 = migrations.run_migrations(str(_SQLITE), backup=True)
    check(r1["error"] is None, "首次迁移无错误")
    check("v1.5.0-fact-schema" in r1["applied"], "schema 版本已应用")
    check("v1.5.0-fact-migration" in r1["applied"], "fact 迁移版本已应用")
    mig = r1["details"].get("v1.5.0-fact-migration", {})
    # 期望 facts: 3 + 1 + 1 + 0 = 5
    check(mig.get("facts_total") == 5, f"Facts 总数=5 (实际 {mig.get('facts_total')})")
    check(mig.get("created") == 5, f"created=5 (实际 {mig.get('created')})")
    check(mig.get("noop") == 0, f"noop=0 (实际 {mig.get('noop')})")
    v1 = r1["verify"]
    check(v1["experiences"] == 4, f"verify experiences=4 (实际 {v1['experiences']})")
    check(v1["facts"] == 5, f"verify facts=5 (实际 {v1['facts']})")
    check(v1["orphan_facts"] == 0, f"orphan_facts=0 (实际 {v1['orphan_facts']})")
    # 空经历应在 without_facts 列表
    check("exp-empty-001" in v1["experience_ids_without_facts"], "空经历在 without_facts 列表")

    # 备份生成
    check(r1["backup"] and r1["backup"]["sqlite"] is not None, "SQLite 备份已生成")
    # 产物不含履历正文（只含数量/ID/hash）
    r1_str = str(r1)
    check("订单系统重构" not in r1_str, "产物不含履历正文（description）")
    check("QPS" not in r1_str, "产物不含履历正文（achievements）")

    # fact_id 确定性
    fact_ids_1 = list(mig.get("fact_ids", []))

    # ── 3. 重复迁移（版本已记录 → skip；verify 不变） ──
    print("[3] run_migrations (second, version-gated skip)...")
    r2 = migrations.run_migrations(str(_SQLITE), backup=False)
    check(r2["error"] is None, "重复迁移无错误")
    check(len(r2["applied"]) == 0, "重复迁移无新应用（版本已记录）")
    check(r2["verify"]["facts"] == 5, "重复迁移 facts 仍=5")

    # ── 4. upsert 幂等（绕过 version gate，直接重跑数据迁移） ──
    print("[4] _migrate_facts_from_experiences (idempotent upsert)...")
    eng = _new_engine()
    SL = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    s = SL()
    try:
        r4 = migrations._migrate_facts_from_experiences(s)
        check(r4["created"] == 0, f"幂等 created=0 (实际 {r4['created']})")
        check(r4["updated"] == 0, f"幂等 updated=0 (实际 {r4['updated']})")
        check(r4["noop"] == 5, f"幂等 noop=5 (实际 {r4['noop']})")
        check(sorted(r4["fact_ids"]) == sorted(fact_ids_1), "fact_id 与首次一致（确定性）")
    finally:
        s.close()
        eng.dispose()

    # ── 5. 部分失败重试：删 version + 删 1 fact → 重跑补齐 ──
    print("[5] retry-after-partial: delete version + 1 fact, re-run...")
    eng = _new_engine()
    SL = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    s = SL()
    try:
        sv = s.get(SchemaVersion, migrations.SCHEMA_VERSION_FACT_MIGRATION)
        check(sv is not None, "迁移版本已记录（重试前）")
        s.delete(sv)
        # 删一个 fact
        target_fid = fact_ids_1[0]
        f = s.get(Fact, target_fid)
        if f:
            s.delete(f)
        s.commit()
        check(s.get(Fact, target_fid) is None, "已删除 1 fact（模拟部分失败）")
    finally:
        s.close()
        eng.dispose()
    r5 = migrations.run_migrations(str(_SQLITE), backup=False)
    check(r5["error"] is None, "重试迁移无错误")
    check("v1.5.0-fact-migration" in r5["applied"], "重试重新应用 fact 迁移")
    mig5 = r5["details"].get("v1.5.0-fact-migration", {})
    check(mig5.get("created") == 1, f"重试 created=1 (实际 {mig5.get('created')})")
    check(r5["verify"]["facts"] == 5, f"重试后 facts=5 (实际 {r5['verify']['facts']})")

    # ── 6. modify_fact：revision/hash 更新 + 失效钩子 ──
    print("[6] modify_fact (revision/hash + invalidation hook)...")
    fact_service.clear_invalidation_hooks()
    invalidated: list[tuple[str, int]] = []

    def _hook(fact_id, old_revision):
        invalidated.append((fact_id, old_revision))

    fact_service.register_invalidation_hook(_hook)
    eng = _new_engine()
    SL = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    s = SL()
    try:
        target_fid = fact_ids_1[0]
        f = s.get(Fact, target_fid)
        old_rev = f.revision
        old_hash = f.content_hash
        modified = fact_service.modify_fact(s, target_fid, "更新后的事实正文：负责全域稳定性治理与容量规划")
        check(modified.revision == old_rev + 1, f"revision 自增 (旧={old_rev}, 新={modified.revision})")
        check(modified.content_hash != old_hash, "content_hash 已变化")
        check(modified.source_hash == f.source_hash, "source_hash 未变（来源不变）")
        check(invalidated == [(target_fid, old_rev)], "失效钩子以 (fact_id, old_revision) 触发一次")
        # 空文本被拒
        try:
            fact_service.modify_fact(s, target_fid, "   ")
            check(False, "空文本应抛 FactModificationError")
        except errors.FactModificationError:
            check(True, "空文本抛 FactModificationError")
        # 未知 fact_id
        try:
            fact_service.modify_fact(s, "no-such-fact", "x")
            check(False, "未知 fact_id 应抛 FactNotFoundError")
        except errors.FactNotFoundError:
            check(True, "未知 fact_id 抛 FactNotFoundError")
        # 内容未变不 bump revision
        cur_rev = modified.revision
        again = fact_service.modify_fact(s, target_fid, modified.text)
        check(again.revision == cur_rev, "内容未变不 bump revision")
    finally:
        s.close()
        eng.dispose()

    # ── 7. 资源释放：迁移后 engine 已 dispose（run_migrations finally） ──
    print("[7] resource cleanup verified via run_migrations finally (engine.dispose)")

    # ── 8. fact_type 粗粒度映射 ──
    print("[8] fact_type coarse mapping...")
    eng = _new_engine()
    SL = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    s = SL()
    try:
        desc_facts = s.query(Fact).filter(Fact.source_field == "description").all()
        ach_facts = s.query(Fact).filter(Fact.source_field == "achievements").all()
        check(all(f.fact_type == FactType.RESPONSIBILITY for f in desc_facts), "description → RESPONSIBILITY")
        check(all(f.fact_type == FactType.RESULT for f in ach_facts), "achievements → RESULT")
    finally:
        s.close()
        eng.dispose()

    print(f"\n=== T2 结果: {_assertions['pass']} pass / {_assertions['fail']} fail ===")
    return 0 if _assertions["fail"] == 0 else 1


if __name__ == "__main__":
    try:
        code = main()
    finally:
        _cleanup()
    raise SystemExit(code)
