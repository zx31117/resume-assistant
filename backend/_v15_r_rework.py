"""V1.5.0 R-返工验证：R1 CRUD 生命周期、R3 fail-closed 与资源、R7 逐 bullet 来源闭环。

补齐 PLAN §12.10 测试矩阵中首次候选缺失的断言（不重复 T2-T6 已覆盖项）：
- R1: create/update/delete_experience 的 Fact reconciliation + Embedding 清理
      + 无孤儿 + 同事务失效（不依赖下次迁移）
- R3: 备份验证 + manifest + copy 失败注入 fail-closed + 备份失败不继续破坏性步骤
- R7: BuildMeta.bullet_fact_refs 序列化往返 + 逐 bullet（非经历级压缩）保留
      + 空 fact_refs 的非 insufficient bullet 使生成失败

在独立临时 runtime 上用虚构 fixture 验证；退出码 0 = 全部通过，非 0 = 有失败。
"""
from __future__ import annotations

import atexit
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# 确保 backend/ 在 sys.path
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import models, migrations
from database.models import Base, Experience, Fact, FactEmbedding, EmbeddingStatus
from services import experience_service, embedding_service, resume_builder as rb
from api.schemas import (
    BuildMeta, GeneratedBullet, GeneratedExperienceItemV15, GeneratedResumeContentV15,
)
from core import errors

# ── 临时 runtime ──────────────────────────────────────────────── #
_TMP = Path(tempfile.mkdtemp(prefix="v15_r_"))
_SQLITE = _TMP / "app.db"
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


def _new_engine(path=None):
    p = path or _SQLITE
    return create_engine(f"sqlite:///{p}", connect_args={"check_same_thread": False})


def _session(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _mock_embedder(text: str) -> list[float]:
    import hashlib
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


def _migrate(backup=True):
    return migrations.run_migrations(str(_SQLITE), backup=backup)


# ============================================================ #
# R1: Experience CRUD 全生命周期
# ============================================================ #

def test_r1_crud_lifecycle():
    print("\n=== R1: Experience CRUD 全生命周期 ===")
    eng = _new_engine()
    Base.metadata.create_all(bind=eng)
    eng.dispose()
    r = _migrate(backup=False)
    check(r.get("error") is None, f"空库迁移无错误 (实际 {r.get('error')})")

    eng = _new_engine()
    s = _session(eng)
    try:
        s.add(models.User(id="u1", name="测试"))
        s.commit()

        # [1] create 立即生成 Fact（不等下次迁移）
        print("[1] create 立即生成 Fact")
        exp = experience_service.create_experience(s, "u1", {
            "type": "work", "title": "后端", "company": "Acme",
            "time": "2023.01-2023.12", "role": "开发",
            "description": "负责支付系统", "skills": ["python"],
            "achievements": ["QPS提升3倍", "故障率下降"],
        })
        facts_after_create = s.query(Fact).filter(Fact.experience_id == exp.id).all()
        check(len(facts_after_create) == 3, f"create 立即生成 3 Fact (实际 {len(facts_after_create)})")
        check(all(f.source_text for f in facts_after_create), "Fact 均有 source_text（不空）")

        # 重建 embedding，准备失效测试
        embedding_service.rebuild_embeddings(s, embedder=_mock_embedder)
        valid_before = s.query(FactEmbedding).filter(
            FactEmbedding.fact_id.in_([f.fact_id for f in facts_after_create]),
            FactEmbedding.status == EmbeddingStatus.VALID,
        ).count()
        check(valid_before == 3, f"重建后 3 VALID embedding (实际 {valid_before})")

        # [2] update 修改 description → Fact revision/hash 更新 + 旧 Embedding 同事务 INVALID
        print("[2] update 修改 description → reconciliation + 同事务失效")
        old_desc_fact = next(f for f in facts_after_create if f.source_field == "description")
        old_rev = old_desc_fact.revision
        old_hash = old_desc_fact.content_hash
        experience_service.update_experience(s, exp.id, {"description": "负责支付系统与风控"})
        s.commit()
        new_desc_fact = s.get(Fact, old_desc_fact.fact_id)
        check(new_desc_fact.text == "负责支付系统与风控", "description Fact text 已更新")
        check(new_desc_fact.revision == old_rev + 1, f"revision 自增 (旧 {old_rev} → 新 {new_desc_fact.revision})")
        check(new_desc_fact.content_hash != old_hash, "content_hash 变化")
        emb = s.query(FactEmbedding).filter(FactEmbedding.fact_id == new_desc_fact.fact_id).all()
        check(all(e.status == EmbeddingStatus.INVALID for e in emb),
              f"update 后旧 Embedding 同事务 INVALID (实际 {[e.status.value for e in emb]})")
        ach_fact = next(f for f in facts_after_create if f.source_field == "achievements")
        ach_emb = s.query(FactEmbedding).filter(FactEmbedding.fact_id == ach_fact.fact_id).all()
        check(all(e.status == EmbeddingStatus.VALID for e in ach_emb),
              "未修改的 achievement Fact embedding 不受影响")

        # [3] update 删除一个 achievement → 对应 Fact 删除，无孤儿 Embedding
        print("[3] update 删除 achievement → Fact 删除 + 无孤儿")
        # achievements 原为 ["QPS提升3倍"(idx0), "故障率下降"(idx1)]；
        # 保留 idx0，删除 idx1。追踪将被删除的 idx1 fact_id。
        ach_facts = [f for f in facts_after_create if f.source_field == "achievements"]
        kept_ach_fact_id = ach_facts[0].fact_id   # idx0 "QPS提升3倍" 保留
        deleted_ach_fact_id = ach_facts[1].fact_id  # idx1 "故障率下降" 将被删除
        experience_service.update_experience(s, exp.id, {"achievements": ["QPS提升3倍"]})
        s.commit()
        facts_after_del = s.query(Fact).filter(Fact.experience_id == exp.id).all()
        check(len(facts_after_del) == 2, f"删除 1 achievement → 2 Fact (实际 {len(facts_after_del)})")
        check(s.get(Fact, deleted_ach_fact_id) is None, "被删除的 achievement Fact（idx1）已移除")
        check(s.get(Fact, kept_ach_fact_id) is not None, "保留的 achievement Fact（idx0）仍在")
        orphan = s.query(FactEmbedding).filter(FactEmbedding.fact_id == deleted_ach_fact_id).count()
        check(orphan == 0, f"被删除 Fact 无孤儿 Embedding (实际 {orphan})")

        # [4] delete_experience → 全部 Fact + Embedding 清理，无孤儿
        print("[4] delete_experience → 清理 Fact + Embedding")
        exp_id = exp.id
        fact_ids = [f.fact_id for f in s.query(Fact).filter(Fact.experience_id == exp_id).all()]
        ok = experience_service.delete_experience(s, exp_id)
        check(ok is True, "delete 返回 True")
        check(s.query(Experience).filter(Experience.id == exp_id).first() is None, "Experience 已删除")
        check(s.query(Fact).filter(Fact.experience_id == exp_id).count() == 0, "Fact 全部清理")
        orphan_after = s.query(FactEmbedding).filter(FactEmbedding.fact_id.in_(fact_ids)).count()
        check(orphan_after == 0, f"delete 后无孤儿 Embedding (实际 {orphan_after})")

        # [5] 幂等：重复 delete 不报错且不产生孤儿
        print("[5] 幂等：重复 delete")
        ok2 = experience_service.delete_experience(s, exp_id)
        check(ok2 is False, "重复 delete 返回 False（不存在）")
        check(s.query(FactEmbedding).filter(FactEmbedding.fact_id.in_(fact_ids)).count() == 0,
              "重复 delete 不产生孤儿")
    finally:
        s.close()
        eng.dispose()


# ============================================================ #
# R3: 备份 fail-closed 与资源生命周期
# ============================================================ #

def test_r3_backup_fail_closed():
    print("\n=== R3: 备份 fail-closed 与资源 ===")
    # [1] 备份成功 + manifest + 完整性核对
    print("[1] 备份成功 + manifest + 大小核对")
    src_path = _TMP / "r3src.db"
    eng = create_engine(f"sqlite:///{src_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    s = _session(eng)
    s.add(models.User(id="r3u", name="r3"))
    s.commit()
    s.close()
    eng.dispose()

    bak_result = migrations._backup_sources(str(src_path))
    check(not bak_result["errors"], f"备份无错误 (实际 {bak_result['errors']})")
    check(bak_result["sqlite"] is not None, "sqlite 备份路径已记录")
    check(bak_result["manifest"] is not None, "manifest 路径已记录")
    bak_p = Path(bak_result["sqlite"])
    check(bak_p.exists(), "备份文件存在")
    check(bak_p.stat().st_size == src_path.stat().st_size, "备份大小 == 源大小")
    manifest_p = Path(bak_result["manifest"])
    check(manifest_p.exists(), "manifest 文件存在")
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    check(manifest.get("verified") is True, "manifest 标记 verified=True")
    check("履历" not in str(manifest), "manifest 不含履历正文")

    # [2] 源不存在 → fail-closed
    print("[2] 源不存在 → fail-closed")
    missing_result = migrations._backup_sources(str(_TMP / "nonexistent.db"))
    check(len(missing_result["errors"]) > 0, "源缺失记入 errors")
    check(missing_result["sqlite"] is None, "源缺失时不生成备份")

    # [3] copy2 失败注入 → run_migrations fail-closed，不继续破坏性步骤
    print("[3] copy2 失败注入 → MigrationError，不继续 schema/data 步骤")
    fail_src = _TMP / "r3fail.db"
    eng2 = create_engine(f"sqlite:///{fail_src}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng2)
    eng2.dispose()
    copy_call_count = {"n": 0}

    def _fail_copy2(src, dst, *a, **kw):
        copy_call_count["n"] += 1
        raise OSError("injected copy2 failure (R3 test)")

    with patch("shutil.copy2", _fail_copy2), patch("sqlite3.connect", side_effect=OSError("injected connect failure (R3 test)")):
        raised = False
        err = None
        try:
            migrations.run_migrations(str(fail_src), backup=True)
        except errors.MigrationError as e:
            raised = True
            err = str(e)
        except Exception as e:
            raised = True
            err = f"wrong exception type: {type(e).__name__}: {e}"
    check(raised is True, f"copy2 失败 → 抛 MigrationError (实际 {err})")
    check(copy_call_count["n"] >= 1, "copy2 被调用并注入失败")
    # 备份失败后不得继续破坏性 schema/data 步骤：SchemaVersion 表不存在或为 0 行
    eng3 = create_engine(f"sqlite:///{fail_src}", connect_args={"check_same_thread": False})
    s3 = _session(eng3)
    try:
        has_schema_version = True
        try:
            cnt = s3.query(models.SchemaVersion).count()
        except Exception:
            cnt = -1
            has_schema_version = False
        check((not has_schema_version) or cnt == 0,
              f"备份失败不继续 schema 步骤 (SchemaVersion 存在={has_schema_version}, cnt={cnt})")
    finally:
        s3.close()
        eng3.dispose()

    # [4] 同名备份冲突 → 追加后缀，不覆盖既有只读备份
    print("[4] 同名备份冲突 → 追加后缀不覆盖")
    bak1 = migrations._backup_sources(str(src_path))
    bak2 = migrations._backup_sources(str(src_path))
    check(not bak1["errors"] and not bak2["errors"], "两次备份均无错误")
    check(bak1["sqlite"] != bak2["sqlite"], "冲突时生成不同备份名")
    check(Path(bak1["sqlite"]).exists() and Path(bak2["sqlite"]).exists(), "两个备份文件都存在")


# ============================================================ #
# R7: 逐 bullet 来源闭环
# ============================================================ #

def test_r7_per_bullet_source():
    print("\n=== R7: 逐 bullet 来源闭环 ===")
    # [1] BuildMeta.bullet_fact_refs 序列化往返
    print("[1] BuildMeta.bullet_fact_refs 序列化往返")
    meta_dict = {
        "builder_mode": "v15_selection",
        "bullet_fact_refs": {
            "exp-1": [["f1"], ["f2", "f3"]],
            "exp-2": [["f4"]],
        },
        "fact_refs_per_experience": {"exp-1": ["f1", "f2", "f3"], "exp-2": ["f4"]},
    }
    meta1 = BuildMeta.model_validate(meta_dict)
    dumped = meta1.model_dump()
    meta2 = BuildMeta.model_validate(dumped)
    check(meta2.bullet_fact_refs == meta_dict["bullet_fact_refs"],
          "bullet_fact_refs 序列化往返保留逐 bullet 结构")
    check(isinstance(meta2.bullet_fact_refs.get("exp-1"), list)
          and len(meta2.bullet_fact_refs["exp-1"]) == 2,
          "exp-1 保留 2 个 bullet 的 fact_refs（非经历级压缩）")
    check(meta2.builder_mode == "v15_selection", "builder_mode 往返保留")

    # [2] build_v15 逐 bullet（非经历级）保留
    print("[2] build_v15 逐 bullet 保留")
    eng = _new_engine()
    Base.metadata.create_all(bind=eng)
    s = _session(eng)
    try:
        s.add(models.User(id="u7", name="r7"))
        s.commit()
        w = experience_service.create_experience(s, "u7", {
            "type": "work", "title": "后端", "company": "Acme",
            "time": "2023.01-2023.12", "role": "开发",
            "description": "支付系统", "skills": [], "achievements": ["QPS提升"],
        })
        p = experience_service.create_experience(s, "u7", {
            "type": "project", "title": "网关", "company": "",
            "time": "2023.06-2023.10", "role": "",
            "description": "自研网关", "skills": [], "achievements": ["降延迟"],
        })
        w_id, p_id = w.id, p.id
    finally:
        s.close()
        eng.dispose()

    _migrate(backup=False)
    eng = _new_engine()
    s = _session(eng)
    try:
        embedding_service.rebuild_embeddings(s, embedder=_mock_embedder)
        from database.models import Experience
        from services import selection_service as ss
        from datetime import date
        all_exps = s.query(Experience).all()
        cset = ss.select_experiences(all_exps, _jd(), baseline_date=date(2024, 1, 1))
        evidence = ss.select_evidence(s, cset, _jd(), embedder=_mock_embedder)

        # 为每个入选经历构造 2 个 bullet，各自引用不同 fact_ref
        v15_items = []
        for entry in evidence.entries:
            if not entry.fact_refs:
                v15_items.append(GeneratedExperienceItemV15(
                    experience_id=entry.experience_id, bullets=[], insufficient=True,
                    insufficient_reason="无可用事实",
                ))
                continue
            exp_facts = entry.fact_refs
            b1_ref = exp_facts[0].fact_id
            b2_ref = exp_facts[1].fact_id if len(exp_facts) > 1 else exp_facts[0].fact_id
            v15_items.append(GeneratedExperienceItemV15(
                experience_id=entry.experience_id,
                bullets=[
                    GeneratedBullet(bullet="第一项成果表达", fact_refs=[b1_ref]),
                    GeneratedBullet(bullet="第二项成果表达", fact_refs=[b2_ref]),
                ],
            ))
        v15_content = GeneratedResumeContentV15(experiences=v15_items)

        doc, meta = rb.build_v15(
            s, "u7", cset, _jd(), v15_content,
            request_profile={"name": "李四", "phone": "13900000000"},
            all_experiences=all_exps,
        )

        bfr = meta.get("bullet_fact_refs", {})
        for w_item in doc.work:
            if w_item.experience_id:
                per_bullet = bfr.get(w_item.experience_id, [])
                check(isinstance(per_bullet, list) and all(isinstance(b, list) for b in per_bullet),
                      f"{w_item.experience_id} bullet_fact_refs 为 list of list（逐 bullet）")
                check(len(per_bullet) == 2, f"{w_item.experience_id} 保留 2 bullet 的 fact_refs (实际 {len(per_bullet)})")
                flat_union = sorted({r for refs in per_bullet for r in refs})
                check(sorted(w_item.fact_refs) == flat_union,
                      f"{w_item.experience_id} 经历级 fact_refs == 扁平并集")
        for p_item in doc.projects:
            if p_item.experience_id:
                per_bullet = bfr.get(p_item.experience_id, [])
                check(len(per_bullet) == 2, f"project {p_item.experience_id} 保留 2 bullet 的 fact_refs")

        # [3] 空 fact_refs 的非 insufficient bullet → ContentGenerationError
        print("[3] 空 fact_refs 非 insufficient bullet → 生成失败")
        bad_items = []
        for entry in evidence.entries:
            if not entry.fact_refs:
                bad_items.append(GeneratedExperienceItemV15(
                    experience_id=entry.experience_id, bullets=[], insufficient=True,
                    insufficient_reason="无可用事实",
                ))
                continue
            bad_items.append(GeneratedExperienceItemV15(
                experience_id=entry.experience_id,
                bullets=[GeneratedBullet(bullet="无来源 bullet", fact_refs=[])],
            ))
        bad_content = GeneratedResumeContentV15(experiences=bad_items)
        raised = False
        try:
            rb.build_v15(
                s, "u7", cset, _jd(), bad_content,
                request_profile={"name": "李四", "phone": "13900000000"},
                all_experiences=all_exps,
            )
        except errors.ContentGenerationError:
            raised = True
        except Exception as e:
            raised = f"wrong type: {type(e).__name__}"
        check(raised is True, f"空 fact_refs 非 insufficient bullet 抛 ContentGenerationError (实际 {raised})")

        # [4] campus 分支：bullets + fact_refs 进入 ResumeDocument
        print("[4] campus 分支 bullets + fact_refs 进入 ResumeDocument")
        c = experience_service.create_experience(s, "u7", {
            "type": "campus", "title": "社团", "company": "校学生会",
            "time": "2020.01-2021.01", "role": "部长",
            "description": "组织活动", "skills": [], "achievements": ["参与人数翻倍"],
        })
        experience_service.delete_experience(s, w_id)
        experience_service.delete_experience(s, p_id)
        s.commit()
        # R1: create_experience 只生成 Fact，不生成 Embedding；选材前需 rebuild
        embedding_service.rebuild_embeddings(s, embedder=_mock_embedder)
        all_exps2 = s.query(Experience).all()
        cset2 = ss.select_experiences(all_exps2, _jd(), baseline_date=date(2024, 1, 1))
        campus_slots = [sl for sl in cset2.slots if sl.slot_type == "campus"]
        check(len(campus_slots) == 1, f"合计<2 触发 1 项校园补位 (实际 {len(campus_slots)})")
        evidence2 = ss.select_evidence(s, cset2, _jd(), embedder=_mock_embedder)
        campus_items = []
        for entry in evidence2.entries:
            if not entry.fact_refs:
                campus_items.append(GeneratedExperienceItemV15(
                    experience_id=entry.experience_id, bullets=[], insufficient=True,
                    insufficient_reason="无可用事实",
                ))
                continue
            campus_items.append(GeneratedExperienceItemV15(
                experience_id=entry.experience_id,
                bullets=[GeneratedBullet(bullet="校园成果表达", fact_refs=[entry.fact_refs[0].fact_id])],
            ))
        campus_content = GeneratedResumeContentV15(experiences=campus_items)
        doc2, meta2 = rb.build_v15(
            s, "u7", cset2, _jd(), campus_content,
            request_profile={"name": "李四", "phone": "13900000000"},
            all_experiences=all_exps2,
        )
        edu_with_campus = [e for e in doc2.education if e.experience_id == c.id]
        check(len(edu_with_campus) == 1, "campus 入选后进入 ResumeDocument.education")
        if edu_with_campus:
            ce = edu_with_campus[0]
            check(len(ce.bullets) >= 1, f"campus EducationItem 带 bullets (实际 {len(ce.bullets)})")
            check(len(ce.fact_refs) >= 1, f"campus EducationItem 带 fact_refs (实际 {len(ce.fact_refs)})")
            check(c.id in meta2.get("bullet_fact_refs", {}), "campus 进入 bullet_fact_refs 映射")
    finally:
        s.close()
        eng.dispose()


def main():
    test_r1_crud_lifecycle()
    test_r3_backup_fail_closed()
    test_r7_per_bullet_source()
    total = _assertions["pass"] + _assertions["fail"]
    print(f"\n=== R-返工 汇总: PASS={_assertions['pass']} FAIL={_assertions['fail']} (total={total}) ===")
    return 0 if _assertions["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
