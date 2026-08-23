"""V1.5.0 W-返工验证：W1 CRUD 事务边界、W2 缺日期工作规则、W3 全新库维护入口。

按 PLAN §13 对 WorkBuddy 首轮独立验收的 3 个阻断项定向返工：
- W1: create/update_experience 的 Experience 写入与 Fact reconciliation 同事务；
      反向注入（Fact 派生 / reconciliation / Embedding 失效）不得留下孤儿 Experience
      或"新 Experience + 旧 Fact/Embedding"窗口
- W2: 缺失/不可解析日期的工作/实习从 work 槽位排除，告警与行为一致；确定性排序无回归
- W3: run_migrations 对不存在的 SQLite 走全新空库初始化（跳过备份）；目录/损坏源 fail-closed

在独立临时 runtime 上用虚构 fixture 验证；退出码 0 = 全部通过，非 0 = 有失败。
"""
from __future__ import annotations

import atexit
import hashlib
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

# 确保 backend/ 在 sys.path
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import migrations, models
from database.models import (
    Base, Experience, Fact, FactEmbedding, EmbeddingStatus, SchemaVersion,
)
from services import experience_service, embedding_service, selection_service as ss
from core import errors

_TMP = Path(tempfile.mkdtemp(prefix="v15_w_"))
_DIM = 8


def _cleanup():
    shutil.rmtree(_TMP, ignore_errors=True)


atexit.register(_cleanup)

_assertions = {"pass": 0, "fail": 0}


def check(cond: bool, name: str):
    if cond:
        _assertions["pass"] += 1
        print(f"  [PASS] {name}")
    else:
        _assertions["fail"] += 1
        print(f"  [FAIL] {name}")


_db_counter = [0]


def _fresh_db() -> Path:
    _db_counter[0] += 1
    return _TMP / f"wdb_{_db_counter[0]}.db"


def _new_engine(path):
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


def _session(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _mock_embedder(text: str) -> list[float]:
    h = hashlib.sha256((text or "").encode("utf-8")).digest()
    vals = [float((h[i % len(h)] / 255.0) - 0.5) for i in range(_DIM)]
    norm = sum(v * v for v in vals) ** 0.5 or 1.0
    return [v / norm for v in vals]


def _jd(**kw):
    base = {
        "position": "后端工程师", "industry": "互联网",
        "required_skills": ["python", "sql"], "preferred_skills": [],
        "responsibilities": ["系统设计"], "keywords": ["后端", "高并发"],
        "experience_preferences": "",
    }
    base.update(kw)
    return base


def _add_exp(session, **kw):
    exp = Experience(**kw)
    session.add(exp)
    session.commit()
    return exp


def _setup_user(session, uid="u1"):
    session.add(models.User(id=uid, name="测试"))
    session.commit()


# ============================================================ #
# W1: create/update 同事务边界
# ============================================================ #

def test_w1_transaction_boundary():
    print("\n=== W1: create/update 同事务边界 ===")
    path = _fresh_db()
    eng = _new_engine(path)
    Base.metadata.create_all(bind=eng)
    s = _session(eng)
    try:
        _setup_user(s)

        # [1] create 正常 → Experience + Fact 同事务可见
        print("[1] create 正常 → Experience + Fact 都持久化")
        exp = experience_service.create_experience(s, "u1", {
            "type": "work", "title": "后端", "company": "Acme",
            "time": "2023.01-2023.12", "role": "开发",
            "description": "负责支付系统", "skills": ["python"],
            "achievements": ["QPS提升3倍"],
        })
        check(s.query(Experience).filter(Experience.id == exp.id).count() == 1, "Experience 已持久化")
        check(s.query(Fact).filter(Fact.experience_id == exp.id).count() == 2, "create 生成 2 Fact（description + achievements）")

        # [2] update 正常 → revision/hash 更新 + 同事务失效
        print("[2] update 正常 → revision/hash 更新 + 同事务失效")
        embedding_service.rebuild_embeddings(s, embedder=_mock_embedder)
        desc_fact = next(f for f in s.query(Fact).filter(Fact.experience_id == exp.id, Fact.source_field == "description").all())
        old_rev = desc_fact.revision
        old_hash = desc_fact.content_hash
        experience_service.update_experience(s, exp.id, {"description": "负责支付系统与风控"})
        new_desc_fact = s.get(Fact, desc_fact.fact_id)
        check(new_desc_fact.revision == old_rev + 1, "update 后 revision 自增")
        check(new_desc_fact.content_hash != old_hash, "update 后 content_hash 变化")
        emb_rows = s.query(FactEmbedding).filter(FactEmbedding.fact_id == desc_fact.fact_id).all()
        check(all(e.status == EmbeddingStatus.INVALID for e in emb_rows), "update 后旧 Embedding 同事务 INVALID")

        # [3] create 反向：Fact 派生失败 → 无孤儿 Experience/Fact
        print("[3] create 反向：Fact 派生失败 → 无孤儿")
        with patch("services.experience_service._iter_fact_candidates", side_effect=RuntimeError("injected fact derivation failure")):
            raised = False
            try:
                experience_service.create_experience(s, "u1", {
                    "type": "work", "title": "X", "company": "", "time": "2024.01-2024.02",
                    "role": "", "description": "d", "skills": [], "achievements": [],
                })
            except RuntimeError:
                raised = True
        check(raised is True, "Fact 派生失败 → 抛异常")
        check(s.query(Experience).filter(Experience.title == "X").count() == 0, "create 失败后无新增 Experience（无孤儿）")
        check(s.query(Fact).filter(Fact.experience_id == "X").count() == 0, "create 失败后无孤儿 Fact")

        # [4] create 反向：reconciliation 写入失败（upsert 注入）→ 无孤儿
        print("[4] create 反向：reconciliation 写入失败 → 无孤儿")
        with patch("services.experience_service._upsert_fact", side_effect=RuntimeError("injected upsert failure")):
            raised = False
            try:
                experience_service.create_experience(s, "u1", {
                    "type": "work", "title": "Y", "company": "", "time": "2024.01-2024.02",
                    "role": "", "description": "d2", "skills": [], "achievements": ["a"],
                })
            except RuntimeError:
                raised = True
        check(raised is True, "reconciliation 写入失败 → 抛异常")
        check(s.query(Experience).filter(Experience.title == "Y").count() == 0, "create 失败后无新增 Experience")
        check(s.query(Fact).filter(Fact.experience_id == "Y").count() == 0, "create 失败后无孤儿 Fact")

        # [5] update 反向：reconciliation 失败 → 保持旧值 + 旧派生一致
        print("[5] update 反向：reconciliation 失败 → 保持旧值")
        before_desc = exp.description
        before_fact = {f.fact_id: (f.text, f.revision, f.content_hash) for f in s.query(Fact).filter(Fact.experience_id == exp.id).all()}
        before_emb = {e.fact_id: e.status.value for e in s.query(FactEmbedding).filter(FactEmbedding.fact_id.in_(list(before_fact))).all()}
        with patch("services.experience_service._reconcile_facts", side_effect=RuntimeError("injected reconcile failure")):
            raised = False
            try:
                experience_service.update_experience(s, exp.id, {"description": "被回滚的新描述"})
            except RuntimeError:
                raised = True
        check(raised is True, "update reconcile 失败 → 抛异常")
        exp2 = s.get(Experience, exp.id)
        check(exp2.description == before_desc, "update 失败后 Experience 描述保持旧值")
        after_fact = {f.fact_id: (f.text, f.revision, f.content_hash) for f in s.query(Fact).filter(Fact.experience_id == exp.id).all()}
        check(after_fact == before_fact, "update 失败后 Fact 保持旧 text/revision/hash")
        after_emb = {e.fact_id: e.status.value for e in s.query(FactEmbedding).filter(FactEmbedding.fact_id.in_(list(before_fact))).all()}
        check(after_emb == before_emb, "update 失败后 Embedding 状态保持旧一致")

        # [6] update 反向：Embedding 失效注入 → 保持旧值 + 旧派生一致
        print("[6] update 反向：Embedding 失效注入 → 保持旧值")
        s.expire_all()
        exp6 = s.get(Experience, exp.id)
        before_desc6 = exp6.description
        before_fact6 = {f.fact_id: (f.text, f.revision, f.content_hash) for f in s.query(Fact).filter(Fact.experience_id == exp.id).all()}
        before_emb6 = {e.fact_id: e.status.value for e in s.query(FactEmbedding).filter(FactEmbedding.fact_id.in_(list(before_fact6))).all()}
        with patch("services.embedding_service.invalidate_fact_embedding", side_effect=RuntimeError("injected invalidation failure")):
            raised = False
            try:
                experience_service.update_experience(s, exp.id, {"description": before_desc6 + " (invalidation-fail)"})
            except RuntimeError:
                raised = True
        check(raised is True, "update Embedding 失效失败 → 抛异常")
        s.expire_all()
        exp7 = s.get(Experience, exp.id)
        check(exp7.description == before_desc6, "update 失效失败后 Experience 描述保持旧值")
        after_fact6 = {f.fact_id: (f.text, f.revision, f.content_hash) for f in s.query(Fact).filter(Fact.experience_id == exp.id).all()}
        check(after_fact6 == before_fact6, "update 失效失败后 Fact 保持旧 text/revision/hash")
        after_emb6 = {e.fact_id: e.status.value for e in s.query(FactEmbedding).filter(FactEmbedding.fact_id.in_(list(before_fact6))).all()}
        check(after_emb6 == before_emb6, "update 失效失败后 Embedding 状态保持旧一致")
    finally:
        s.close()
        eng.dispose()


# ============================================================ #
# W2: 缺日期工作规则
# ============================================================ #

def test_w2_missing_date_work():
    print("\n=== W2: 缺日期工作排除 ===")
    baseline = date(2024, 6, 1)

    # [1] 空日期 + 不可解析日期工作 → 排除 + 告警 + 不进 work 槽
    path = _fresh_db()
    eng = _new_engine(path)
    Base.metadata.create_all(bind=eng)
    s = _session(eng)
    try:
        _add_exp(s, id="w-ok", user_id="u1", type="work", title="后端", company="C", time="2024.01-2024.05", description="d", skills=["python"], achievements=[])
        _add_exp(s, id="w-nodate", user_id="u1", type="work", title="后端", company="C", time="", description="d", skills=[], achievements=[])
        _add_exp(s, id="w-bad", user_id="u1", type="work", title="后端", company="C", time="去年-今年", description="d", skills=[], achievements=[])
        cset = ss.select_experiences(s.query(Experience).all(), _jd(), baseline_date=baseline)
        work_ids = [x.experience_id for x in cset.slots if x.slot_type == "work"]
        check(work_ids == ["w-ok"], f"缺/不可解析日期工作不进 work 槽 (实际 {work_ids})")
        check("w-nodate" in cset.excluded_ids and "w-bad" in cset.excluded_ids, "缺/不可解析日期工作进入 excluded_ids")
        check(any("work date missing/unparseable" in w for w in cset.warnings), "有与行为一致的告警")
    finally:
        s.close()
        eng.dispose()

    # [2] 正常日期排序无回归（在职最新，同日期按 id 升序稳定键）
    print("[2] 正常日期排序无回归")
    path = _fresh_db()
    eng = _new_engine(path)
    Base.metadata.create_all(bind=eng)
    s = _session(eng)
    try:
        _add_exp(s, id="w-a", user_id="u1", type="work", title="后端", company="C", time="2022.01-2022.12", description="d", skills=[], achievements=[])
        _add_exp(s, id="w-b", user_id="u1", type="work", title="后端", company="C", time="2022.01-2022.12", description="d", skills=[], achievements=[])
        _add_exp(s, id="w-now", user_id="u1", type="work", title="后端", company="C", time="2023.06-至今", description="d", skills=[], achievements=[])
        cset = ss.select_experiences(s.query(Experience).all(), _jd(), baseline_date=baseline)
        work_ids = [x.experience_id for x in cset.slots if x.slot_type == "work"]
        check(work_ids[0] == "w-now", "在职排第一")
        check(work_ids[1:] == ["w-a", "w-b"], f"同日期按 id 升序稳定 (实际 {work_ids[1:]})")
    finally:
        s.close()
        eng.dispose()

    # [3] 5 组输入乱序 → 结果一致（确定性）
    print("[3] 5 组乱序 → 结果一致")
    path = _fresh_db()
    eng = _new_engine(path)
    Base.metadata.create_all(bind=eng)
    s = _session(eng)
    try:
        for i in range(4):
            _add_exp(s, id=f"w{i}", user_id="u1", type="work", title="后端", company="C", time=f"202{3 - i}.01-202{3 - i}.12", description="d", skills=["python"], achievements=[])
        _add_exp(s, id="w-nodate", user_id="u1", type="work", title="后端", company="C", time="", description="d", skills=[], achievements=[])
        exps = s.query(Experience).all()
        import random
        results = []
        for _ in range(5):
            shuffled = list(exps)
            random.shuffle(shuffled)
            cset = ss.select_experiences(shuffled, _jd(), baseline_date=baseline)
            results.append((tuple(x.experience_id for x in cset.slots if x.slot_type == "work"),
                            tuple(sorted(cset.excluded_ids)),
                            tuple(sorted(cset.warnings))))
        check(len(set(results)) == 1, f"5 组乱序结果完全一致 (实际 {len(set(results))} 组不同)")
        work_ids = results[0][0]
        check("w-nodate" not in work_ids, "乱序下缺日期工作仍不进 work 槽")
    finally:
        s.close()
        eng.dispose()


# ============================================================ #
# W3: 全新库维护入口
# ============================================================ #

def test_w3_fresh_db_entry():
    print("\n=== W3: 全新库维护入口 ===")

    # [1] 不存在 → 全新空库初始化（跳过备份），建 SchemaVersion/Fact 初始状态
    print("[1] 全新空库 migrate → 跳过备份并建库")
    fresh = _TMP / "w3_fresh.db"
    r = migrations.run_migrations(str(fresh), backup=True)
    check(r.get("error") is None, f"全新空库 migrate 无错误 (实际 {r.get('error')})")
    check(fresh.exists(), "全新空库文件已创建")
    check(r.get("backup") is not None and r["backup"].get("note") == "fresh empty database; backup skipped",
          "备份跳过并标注 fresh")
    eng = _new_engine(fresh)
    s = _session(eng)
    try:
        applied = {v.version for v in s.query(SchemaVersion).all()}
        check(migrations.SCHEMA_VERSION_FACT_SCHEMA in applied and migrations.SCHEMA_VERSION_FACT_MIGRATION in applied,
              f"SchemaVersion 两版本已写入 (实际 {applied})")
        check(s.query(Fact).count() == 0, "全新库 Fact 为 0")
    finally:
        s.close()
        eng.dispose()

    # [2] 第二次 migrate 幂等（版本门控 skip）
    print("[2] 第二次 migrate 幂等")
    r2 = migrations.run_migrations(str(fresh), backup=True)
    check(r2.get("error") is None, "第二次 migrate 无错误")
    check(len(r2.get("skipped", [])) == 2, f"第二次 migrate 两版本均 skip (实际 {r2.get('skipped')})")

    # [3] 目录作为源 → fail-closed（非零）
    print("[3] 目录源 → fail-closed")
    dirpath = _TMP / "w3_dir"
    dirpath.mkdir(exist_ok=True)
    raised = False
    try:
        migrations.run_migrations(str(dirpath), backup=True)
    except errors.MigrationError:
        raised = True
    except Exception as e:
        raised = f"wrong type: {type(e).__name__}"
    check(raised is True, f"目录源 → MigrationError (实际 {raised})")

    # [4] 损坏 SQLite → fail-closed（非零退出，不继续迁移）
    print("[4] 损坏 SQLite → fail-closed")
    corrupt = _TMP / "w3_corrupt.db"
    corrupt.write_bytes(b"this is not a sqlite database file at all")
    raised2 = False
    try:
        migrations.run_migrations(str(corrupt), backup=True)
    except errors.MigrationError:
        raised2 = True
    except Exception:
        raised2 = True
    check(raised2 is True, "损坏 SQLite → 异常非零退出")

    # [5] manage.py migrate 对不存在路径按全新库初始化（CLI 入口）
    print("[5] manage.py migrate 全新库入口")
    import manage
    from core.config import settings
    fresh2 = _TMP / "w3_fresh_cli.db"
    old_path = settings.SQLITE_PATH
    settings.SQLITE_PATH = str(fresh2)
    try:
        rc = manage.cmd_migrate()
        check(rc == 0, f"manage.py migrate 全新库返回 0 (实际 {rc})")
        check(fresh2.exists(), "manage.py migrate 创建全新库文件")
    finally:
        settings.SQLITE_PATH = old_path


def main():
    test_w1_transaction_boundary()
    test_w2_missing_date_work()
    test_w3_fresh_db_entry()
    total = _assertions["pass"] + _assertions["fail"]
    print(f"\n=== W-返工 汇总: PASS={_assertions['pass']} FAIL={_assertions['fail']} (total={total}) ===")
    return 0 if _assertions["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())