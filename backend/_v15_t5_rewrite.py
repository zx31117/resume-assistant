"""V1.5.0 T5 验证：受约束改写与 Builder 收缩（PLAN §4.4 / §5.3 / §7 T5 / §8.1）。

在独立临时 runtime 上用虚构 fixture + mock LLM 验证，不读取真实 runtime：
- 越界经历被拒绝（LLM 不得重选）
- 越界 fact_refs 被拒绝（只保留允许引用）
- LLM 不写回事实库（Fact revision 不变）
- 材料不足返回 insufficient=true
- Builder 收缩：build_v15 按 slot 顺序装配、不排序、不裁剪、fact_refs 保留到 WorkItem/ProjectItem

退出码 0 = 全部通过；非 0 = 有失败。
"""
from __future__ import annotations

import atexit
import json
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.schemas import (
    GeneratedBullet,
    GeneratedExperienceItemV15,
    GeneratedResumeContentV15,
)
from database.models import Base, Experience, Fact
from database import migrations
from services import embedding_service as es
from services import fact_service, selection_service as ss
from services import constrained_rewrite as cr
from services import resume_builder as rb

_TMP = Path(tempfile.mkdtemp(prefix="v15_t5_"))
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


def _add_exp(session, **kw):
    exp = Experience(**kw)
    session.add(exp)
    session.commit()
    return exp


def _run_migrations():
    return migrations.run_migrations(str(_SQLITE), backup=True)


def _jd(**kw):
    base = {
        "position": "后端工程师", "industry": "互联网",
        "required_skills": ["python", "sql"], "preferred_skills": [],
        "responsibilities": ["系统设计"], "keywords": ["后端", "高并发"],
        "experience_preferences": "",
    }
    base.update(kw)
    return base


# ── mock LLM：返回带越界引用的 V15 内容 ──────────────────────── #

def _make_mock_llm(scenario: str = "mixed"):
    """构造 mock LLM，根据 scenario 返回不同的 V15 内容。

    scenario:
    - "valid": 全部合法 bullet + fact_refs
    - "mixed": 合法 + 越界经历 + 越界 fact_ref + 缺失一条经历
    - "insufficient": 材料不足
    """

    def _llm(system, user_template, schema, **variables):
        evidence_json = variables.get("evidence_json", "[]")
        payload = json.loads(evidence_json)

        items: list[GeneratedExperienceItemV15] = []
        if scenario == "valid":
            for entry in payload:
                exp_id = entry["experience_id"]
                facts = entry.get("usable_facts", [])
                if not facts:
                    items.append(GeneratedExperienceItemV15(
                        experience_id=exp_id, bullets=[], insufficient=True,
                        insufficient_reason="无可用事实",
                    ))
                    continue
                fid = facts[0]["fact_id"]
                items.append(GeneratedExperienceItemV15(
                    experience_id=exp_id,
                    bullets=[GeneratedBullet(
                        bullet=f"{entry.get('expression_focus', '职责')} 优化表达",
                        fact_refs=[fid],
                    )],
                ))

        elif scenario == "mixed":
            for i, entry in enumerate(payload):
                exp_id = entry["experience_id"]
                facts = entry.get("usable_facts", [])
                if i == 0 and facts:
                    # 第一条经历：合法 fact_ref + 越界 fact_ref
                    fid = facts[0]["fact_id"]
                    items.append(GeneratedExperienceItemV15(
                        experience_id=exp_id,
                        bullets=[GeneratedBullet(
                            bullet="优化表达含越界引用",
                            fact_refs=[fid, "fake-out-of-bound-fact-id"],
                        )],
                    ))
                # i >= 1: 跳过（测试缺失 → 缺失经历标记 insufficient）
            # 越界经历（不在入选名单）
            items.append(GeneratedExperienceItemV15(
                experience_id="fake-not-selected-exp",
                bullets=[GeneratedBullet(bullet="越界经历", fact_refs=[])],
            ))

        elif scenario == "insufficient":
            for entry in payload:
                items.append(GeneratedExperienceItemV15(
                    experience_id=entry["experience_id"],
                    bullets=[],
                    insufficient=True,
                    insufficient_reason="材料不足以写出有效 bullet",
                ))

        return GeneratedResumeContentV15(experiences=items)

    return _llm


# ── 测试：受约束改写 ──────────────────────────────────────────── #

def test_constrained_rewrite():
    print("\n=== 受约束改写（rewrite_with_evidence）===")

    # 建库 + 迁移 + 重建 embedding
    eng = _new_engine()
    Base.metadata.create_all(bind=eng)
    s = _session(eng)
    try:
        _add_exp(s, id="exp-work-001", user_id="demo", type="work",
                 title="后端工程师", company="Acme", time="2024.01-2024.05",
                 role="后端", description="负责订单系统重构",
                 skills=["python", "sql"], achievements=["QPS提升3倍", "故障率下降"])
        _add_exp(s, id="exp-proj-001", user_id="demo", type="project",
                 title="推荐系统", company="", time="2023.06-2023.12",
                 role="负责人", description="搭建召回排序链路",
                 skills=["python"], achievements=[])
        _add_exp(s, id="exp-edu-001", user_id="demo", type="education",
                 title="竞赛", company="", time="2020.01-2020.06",
                 role="算法", description="ACM 金牌",
                 skills=["算法"], achievements=[])
        s.commit()
    finally:
        s.close()
    eng.dispose()

    r = _run_migrations()
    assert r["error"] is None, f"迁移失败: {r['error']}"

    eng = _new_engine()
    s = _session(eng)
    try:
        es.rebuild_embeddings(s, embedder=_mock_embedder)
        all_facts = s.query(Fact).all()
        check(len(all_facts) >= 3, f"迁移后 Fact >=3 (实际 {len(all_facts)})")

        baseline = date(2024, 6, 1)
        cset = ss.select_experiences(s.query(Experience).all(), _jd(), baseline_date=baseline)
        check(len(cset.slots) >= 2, f"第一层入选 >=2 (实际 {len(cset.slots)})")

        evidence = ss.select_evidence(s, cset, _jd(), embedder=_mock_embedder)

        # [1] 合法场景：全部 bullet + fact_refs 在边界内
        print("\n[1] 合法改写")
        content, warnings = cr.rewrite_with_evidence(
            s, cset, evidence, _jd(), llm=_make_mock_llm("valid"),
        )
        check(len(content.experiences) == len(cset.slots), "返回经历数 == 入选数")
        check(len(warnings) == 0, f"合法改写无告警 (实际 {len(warnings)})")
        for item in content.experiences:
            check(not item.insufficient, f"{item.experience_id} 非 insufficient")

        # [2] 越界经历 + 越界 fact_ref 被拒绝
        print("\n[2] 越界拒绝")
        content2, warnings2 = cr.rewrite_with_evidence(
            s, cset, evidence, _jd(), llm=_make_mock_llm("mixed"),
        )
        selected_ids = set(cset.selected_ids())
        for item in content2.experiences:
            check(item.experience_id in selected_ids, f"越界经历被拒绝 {item.experience_id}")
        # 越界 fact_ref 被过滤
        for item in content2.experiences:
            for b in item.bullets:
                for ref in (b.fact_refs or []):
                    allowed = set()
                    for e in evidence.entries:
                        if e.experience_id == item.experience_id:
                            allowed = {r.fact_id for r in e.fact_refs}
                    check(ref in allowed, f"越界 fact_ref 被过滤 {ref}")
        has_boundary_warning = any("越界" in w for w in warnings2)
        check(has_boundary_warning, "越界引用产生告警")
        has_outbound_exp = any("fake-not-selected-exp" in w for w in warnings2)
        check(has_outbound_exp, "越界经历被拒绝并告警")
        has_outbound_fact = any("fake-out-of-bound-fact-id" in w for w in warnings2)
        check(has_outbound_fact, "越界 fact_ref 被拒绝并告警")

        # [3] LLM 不写回事实库
        print("\n[3] 不写回事实库")
        rev_before = {f.fact_id: f.revision for f in s.query(Fact).all()}
        text_before = {f.fact_id: f.text for f in s.query(Fact).all()}
        cr.rewrite_with_evidence(s, cset, evidence, _jd(), llm=_make_mock_llm("mixed"))
        rev_after = {f.fact_id: f.revision for f in s.query(Fact).all()}
        text_after = {f.fact_id: f.text for f in s.query(Fact).all()}
        check(rev_before == rev_after, "改写不改 Fact revision（不写回）")
        check(text_before == text_after, "改写不改 Fact text（不写回）")

        # [4] 材料不足返回 insufficient
        print("\n[4] 材料不足")
        content4, warnings4 = cr.rewrite_with_evidence(
            s, cset, evidence, _jd(), llm=_make_mock_llm("insufficient"),
        )
        for item in content4.experiences:
            check(item.insufficient, f"{item.experience_id} insufficient=True")
            check(len(item.bullets) == 0, f"{item.experience_id} bullets 为空（不补造）")

        # [5] 缺失经历标记 insufficient
        print("\n[5] 缺失经历标记 insufficient")
        content5, _ = cr.rewrite_with_evidence(
            s, cset, evidence, _jd(), llm=_make_mock_llm("mixed"),
        )
        returned_ids = {i.experience_id for i in content5.experiences}
        missing = set(cset.selected_ids()) - returned_ids
        # mixed 场景跳过了部分经历，但这些经历应该被补回为 insufficient
        all_returned = set(cset.selected_ids()) <= returned_ids
        check(all_returned, "缺失经历被补回为 insufficient")
        insufficient_items = [i for i in content5.experiences if i.insufficient]
        check(len(insufficient_items) >= 1, "至少 1 条 insufficient（缺失经历）")

    finally:
        s.close()
    eng.dispose()


# ── 测试：Builder 收缩 ──────────────────────────────────────────── #

def test_builder_shrinkage():
    print("\n=== Builder 收缩（build_v15）===")

    eng = _new_engine()
    Base.metadata.create_all(bind=eng)
    s = _session(eng)
    try:
        _add_exp(s, id="w1", user_id="demo", type="work",
                 title="后端工程师", company="Acme", time="2024.01-2024.05",
                 role="后端", description="负责订单系统重构",
                 skills=["python", "sql"], achievements=["QPS提升3倍"])
        _add_exp(s, id="w2", user_id="demo", type="work",
                 title="后端", company="Beta", time="2023.01-2023.12",
                 role="开发", description="支付系统",
                 skills=["python"], achievements=["故障率下降"])
        _add_exp(s, id="w3", user_id="demo", type="work",
                 title="实习", company="Gamma", time="2022.06-2022.12",
                 role="实习生", description="辅助开发",
                 skills=[], achievements=[])
        _add_exp(s, id="w4", user_id="demo", type="work",
                 title="旧", company="Delta", time="2021.01-2021.05",
                 role="开发", description="旧工作",
                 skills=[], achievements=[])
        s.commit()
    finally:
        s.close()
    eng.dispose()

    r = _run_migrations()
    assert r["error"] is None, f"迁移失败: {r['error']}"

    eng = _new_engine()
    s = _session(eng)
    try:
        es.rebuild_embeddings(s, embedder=_mock_embedder)
        baseline = date(2024, 6, 1)
        cset = ss.select_experiences(s.query(Experience).all(), _jd(), baseline_date=baseline)
        # 4 次工作 → 最多 3 个 work slot
        work_slots = [x for x in cset.slots if x.slot_type == "work"]
        check(len(work_slots) == 3, f"第一层 4 工作 → 3 slot (实际 {len(work_slots)})")

        evidence = ss.select_evidence(s, cset, _jd(), embedder=_mock_embedder)

        # 构造 V15 内容（每个入选经历一个 bullet + fact_ref）
        v15_items = []
        for entry in evidence.entries:
            if entry.fact_refs:
                v15_items.append(GeneratedExperienceItemV15(
                    experience_id=entry.experience_id,
                    bullets=[GeneratedBullet(
                        bullet=f"{entry.expression_focus} 优化",
                        fact_refs=[entry.fact_refs[0].fact_id],
                    )],
                ))
            else:
                v15_items.append(GeneratedExperienceItemV15(
                    experience_id=entry.experience_id,
                    bullets=[], insufficient=True,
                    insufficient_reason="无可用事实",
                ))
        v15_content = GeneratedResumeContentV15(experiences=v15_items)

        # [6] build_v15 按 slot 顺序装配
        print("\n[6] build_v15 装配")
        doc, meta = rb.build_v15(
            s, "demo", cset, _jd(), v15_content,
            request_profile={"name": "张三", "phone": "13800000000"},
            all_experiences=s.query(Experience).all(),
        )
        check(meta["builder_mode"] == "v15_selection", "builder_mode=v15_selection")
        # work 数量 == work slot 数量（不裁剪、不补位）
        check(len(doc.work) == len(work_slots), f"work 数 == slot 数 (实际 {len(doc.work)})")

        # [7] 来源映射 fact_refs 保留到 WorkItem
        print("\n[7] fact_refs 来源映射保留")
        for w in doc.work:
            if w.experience_id:
                entry = next((e for e in evidence.entries if e.experience_id == w.experience_id), None)
                if entry and entry.fact_refs:
                    check(len(w.fact_refs) >= 1, f"{w.experience_id} fact_refs 保留")
                    check(entry.fact_refs[0].fact_id in w.fact_refs, f"{w.experience_id} fact_id 正确")

        # [8] build_v15 不做 JD 相关性排序（用 slot 顺序）
        print("\n[8] 不做 JD 相关性排序")
        slot_order = [x.experience_id for x in work_slots]
        work_order = [w.experience_id for w in doc.work if w.experience_id]
        check(work_order == slot_order, f"work 顺序 == slot 顺序 (实际 {work_order})")

        # [9] build_v15 不做 max_items 裁剪
        print("\n[9] 不做 max_items 裁剪")
        check(meta["counts"]["work"] == len(work_slots), "work 不被 max_items 裁剪")

        # [10] 事实字段仍来自 SQL
        print("\n[10] 事实字段来自 SQL")
        exp_map = {e.id: e for e in s.query(Experience).all()}
        for w in doc.work:
            if w.experience_id in exp_map:
                exp = exp_map[w.experience_id]
                check(w.company == (exp.company or ""), f"{w.experience_id} company 来自 SQL")
                check(w.role == (exp.role or ""), f"{w.experience_id} role 来自 SQL")

        # [11] insufficient 标记保留
        print("\n[11] insufficient 保留")
        insuf_ids = meta.get("insufficient_experience_ids", [])
        for item in v15_content.experiences:
            if item.insufficient:
                check(item.experience_id in insuf_ids, f"{item.experience_id} insufficient 保留")

        # [12] Profile 只取 request
        print("\n[12] Profile 只取 request")
        check(doc.profile.name == "张三", "name 来自 request")
        check(doc.profile.target_position == "后端工程师", "target_position 来自 JD")
        check(doc.profile.summary == "", "summary 恒空")

        # [13] build_v15 不改 Fact / Experience
        print("\n[13] build_v15 不改事实源")
        rev_before = {f.fact_id: f.revision for f in s.query(Fact).all()}
        exp_before = {e.id: (e.time, e.description) for e in s.query(Experience).all()}
        rb.build_v15(s, "demo", cset, _jd(), v15_content,
                      all_experiences=s.query(Experience).all())
        rev_after = {f.fact_id: f.revision for f in s.query(Fact).all()}
        exp_after = {e.id: (e.time, e.description) for e in s.query(Experience).all()}
        check(rev_before == rev_after, "build_v15 不改 Fact revision")
        check(exp_before == exp_after, "build_v15 不改 Experience")

    finally:
        s.close()
    eng.dispose()


def main() -> int:
    print(f"V1.5.0 T5 验证 | tmp={_TMP}")
    test_constrained_rewrite()
    test_builder_shrinkage()
    print(f"\n=== T5 汇总: PASS={_assertions['pass']} FAIL={_assertions['fail']} ===")
    return 0 if _assertions["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
