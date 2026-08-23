"""V1.5.0 T4 验证：两层选材与 SelectedEvidenceSet（PLAN §4.2/§4.3/§5/§8.1）。

在独立临时 runtime 上用虚构 fixture + mock embedder 验证，不读取真实 runtime：
第一层（固定槽位）：
- 0/1/2/3/4 次工作/实习 → 最近最多 3，缺位不补
- 项目/论文三年窗口（边界前/后/正好/进行中/日期缺失）、0/1/2/3 候选 → 最多 2，不用更早补位
- 合计 0/1/2 时校园分支；最多 1；无校园素材告警不虚构
第二层（事实选材）：
- 只引用第一层入选经历的 fact_refs；版本匹配
- is_expired：Fact 修改 / jd_hash / rule_version / baseline_date 变化 → 过期
- ensure_ready 阻断 PENDING；序列化可核对；不写回 Fact

退出码 0 = 全部通过；非 0 = 有失败。
"""
from __future__ import annotations

import atexit
import hashlib
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

from database.models import Base, Experience, Fact, FactEmbedding, EmbeddingStatus
from database import migrations
from services import embedding_service as es
from services import fact_service, selection_service as ss
from core import errors

_TMP = Path(tempfile.mkdtemp(prefix="v15_t4_"))
_SQLITE = _TMP / "app.db"
_VS_DIR = _TMP / "vectorstore"
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


def _new_engine(path=None):
    p = path or _SQLITE
    return create_engine(f"sqlite:///{p}", connect_args={"check_same_thread": False})


def _session(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _mock_embedder(text: str) -> list[float]:
    h = hashlib.sha256((text or "").encode("utf-8")).digest()
    vals = [float((h[i % len(h)] / 255.0) - 0.5) for i in range(_DIM)]
    norm = sum(v * v for v in vals) ** 0.5 or 1.0
    return [v / norm for v in vals]


def _add_exp(session, **kw):
    exp = Experience(**kw)
    session.add(exp)
    session.commit()
    return exp


def _setup_empty_db():
    """每次调用创建独立 SQLite 文件，避免跨测试 id 冲突。"""
    _db_counter[0] += 1
    path = _TMP / f"test_{_db_counter[0]}.db"
    eng = _new_engine(path)
    Base.metadata.create_all(bind=eng)
    return eng


def _run_migrations():
    return migrations.run_migrations(str(_SQLITE), backup=True, vectorstore_dir=str(_VS_DIR))


def _jd(**kw):
    base = {
        "position": "后端工程师", "industry": "互联网",
        "required_skills": ["python", "sql"], "preferred_skills": [],
        "responsibilities": ["系统设计"], "keywords": ["后端", "高并发"],
        "experience_preferences": "",
    }
    base.update(kw)
    return base


# ── 第一层测试 ───────────────────────────────────────────────── #
def test_first_layer():
    print("\n=== 第一层：固定槽位 ===")
    baseline = date(2024, 6, 1)  # 窗口 [2021.06, 2024.06]

    # [1] 4 次工作 → 最多 3，排除 1
    print("\n[1] 工作/实习最近最多 3")
    eng = _setup_empty_db()
    s = _session(eng)
    try:
        for i, t in enumerate(["2024.01-2024.05", "2023.06-2023.12", "2022.01-2022.12", "2021.01-2021.05"]):
            _add_exp(s, id=f"w{i}", user_id="demo", type="work", title="后端", company="C", time=t, description="d", skills=["python"], achievements=[])
        cset = ss.select_experiences(s.query(Experience).all(), _jd(), baseline_date=baseline)
        work_slots = [x for x in cset.slots if x.slot_type == "work"]
        check(len(work_slots) == 3, f"4 次工作 → 3 个槽 (实际 {len(work_slots)})")
        check(work_slots[0].experience_id == "w0", "最近工作排第一 (w0)")
        check("w3" in cset.excluded_ids, "最旧工作 w3 被排除")
    finally:
        s.close(); eng.dispose()

    # [2] 在职视为最新
    print("\n[2] 在职=最新")
    eng = _setup_empty_db()
    s = _session(eng)
    try:
        _add_exp(s, id="w-old", user_id="demo", type="work", title="后端", company="C", time="2020.01-2020.12", description="d", skills=[], achievements=[])
        _add_exp(s, id="w-now", user_id="demo", type="work", title="后端", company="C", time="2023.06-至今", description="d", skills=[], achievements=[])
        cset = ss.select_experiences(s.query(Experience).all(), _jd(), baseline_date=baseline)
        work_slots = [x for x in cset.slots if x.slot_type == "work"]
        check(work_slots[0].experience_id == "w-now", "在职排第一")
    finally:
        s.close(); eng.dispose()

    # [3] 不足 3 次不补位
    print("\n[3] 不足 3 次不补位")
    eng = _setup_empty_db()
    s = _session(eng)
    try:
        _add_exp(s, id="w0", user_id="demo", type="work", title="后端", company="C", time="2024.01-2024.05", description="d", skills=[], achievements=[])
        cset = ss.select_experiences(s.query(Experience).all(), _jd(), baseline_date=baseline)
        check(len([x for x in cset.slots if x.slot_type == "work"]) == 1, "1 次工作 → 1 槽（不补）")
    finally:
        s.close(); eng.dispose()

    # [4] 项目三年窗口：边界前/后/正好/进行中
    print("\n[4] 项目三年窗口")
    eng = _setup_empty_db()
    s = _session(eng)
    try:
        _add_exp(s, id="p-in", user_id="demo", type="project", title="推荐", company="", time="2024.01-至今", description="召回排序", skills=["python"], achievements=[])  # 进行中
        _add_exp(s, id="p-ok", user_id="demo", type="project", title="搜索", company="", time="2022.06-2023.06", description="搜索引擎", skills=["python"], achievements=[])  # 窗口内
        _add_exp(s, id="p-edge", user_id="demo", type="project", title="分析", company="", time="2021.06-2021.12", description="数据分析", skills=["python"], achievements=[])  # 正好边界
        _add_exp(s, id="p-old", user_id="demo", type="project", title="旧", company="", time="2020.01-2020.12", description="旧项目", skills=[], achievements=[])  # 窗口外
        _add_exp(s, id="p-nodate", user_id="demo", type="project", title="无日期", company="", time="", description="无日期项目", skills=[], achievements=[])  # 日期缺失
        cset = ss.select_experiences(s.query(Experience).all(), _jd(), baseline_date=baseline)
        proj_ids = [x.experience_id for x in cset.slots if x.slot_type == "project"]
        check("p-old" in cset.excluded_ids, "窗口外项目 p-old 排除")
        check("p-nodate" in cset.excluded_ids, "日期缺失项目 p-nodate 排除")
        check(len(proj_ids) <= 2, f"项目最多 2 (实际 {len(proj_ids)})")
        check("p-in" in proj_ids, "进行中项目纳入窗口")
    finally:
        s.close(); eng.dispose()

    # [5] 3 个窗口内项目 → 最多 2，排除 1
    print("\n[5] 项目候选超额")
    eng = _setup_empty_db()
    s = _session(eng)
    try:
        for i, t in enumerate(["2024.01-2024.05", "2023.06-2023.12", "2022.06-2023.06"]):
            _add_exp(s, id=f"pp{i}", user_id="demo", type="project", title="项目", company="", time=t, description=f"项目{i}", skills=["python"], achievements=[])
        cset = ss.select_experiences(s.query(Experience).all(), _jd(), baseline_date=baseline)
        proj = [x for x in cset.slots if x.slot_type == "project"]
        check(len(proj) == 2, f"3 候选 → 2 入选 (实际 {len(proj)})")
        check(len([x for x in cset.excluded_ids if x.startswith("pp")]) == 1, "1 个项目被排除")
    finally:
        s.close(); eng.dispose()

    # [6] 校园补位：合计 <2 触发
    print("\n[6] 校园补位")
    # 合计 0，有校园 → 1 校园
    eng = _setup_empty_db()
    s = _session(eng)
    try:
        _add_exp(s, id="camp1", user_id="demo", type="campus", title="竞赛", company="", time="2020.01-2020.06", description="ACM 金牌", skills=["算法"], achievements=[])
        cset = ss.select_experiences(s.query(Experience).all(), _jd(), baseline_date=baseline)
        campus = [x for x in cset.slots if x.slot_type == "campus"]
        check(len(campus) == 1, f"合计0 → 1 校园 (实际 {len(campus)})")
    finally:
        s.close(); eng.dispose()

    # 合计 2 → 不触发校园
    eng = _setup_empty_db()
    s = _session(eng)
    try:
        _add_exp(s, id="w0", user_id="demo", type="work", title="后端", company="C", time="2024.01-2024.05", description="d", skills=[], achievements=[])
        _add_exp(s, id="p0", user_id="demo", type="project", title="P", company="", time="2023.06-2023.12", description="d", skills=["python"], achievements=[])
        _add_exp(s, id="edu1", user_id="demo", type="education", title="竞赛", company="", time="2020.01-2020.06", description="ACM", skills=[], achievements=[])
        cset = ss.select_experiences(s.query(Experience).all(), _jd(), baseline_date=baseline)
        campus = [x for x in cset.slots if x.slot_type == "campus"]
        check(len(campus) == 0, "合计2 → 不触发校园")
    finally:
        s.close(); eng.dispose()

    # 合计 <2 无校园 → 告警不虚构
    eng = _setup_empty_db()
    s = _session(eng)
    try:
        _add_exp(s, id="w0", user_id="demo", type="work", title="后端", company="C", time="2024.01-2024.05", description="d", skills=[], achievements=[])
        cset = ss.select_experiences(s.query(Experience).all(), _jd(), baseline_date=baseline)
        check(any("campus" in w and "no campus" in w for w in cset.warnings), "无校园素材时告警")
        check(len([x for x in cset.slots if x.slot_type == "campus"]) == 0, "无校园素材不生成虚构校园")
    finally:
        s.close(); eng.dispose()

    # [7] 0 工作 0 项目 0 校园 → 空名单 + 告警
    print("\n[7] 全空")
    eng = _setup_empty_db()
    s = _session(eng)
    try:
        cset = ss.select_experiences([], _jd(), baseline_date=baseline)
        check(len(cset.slots) == 0, "空输入 → 空名单")
        check(len(cset.warnings) >= 1, "空输入 → 告警")
    finally:
        s.close(); eng.dispose()

    # [8] 名单不可变：CandidateExperienceSet 序列化
    print("\n[8] 序列化与名单不变")
    eng = _setup_empty_db()
    s = _session(eng)
    try:
        _add_exp(s, id="w0", user_id="demo", type="work", title="后端", company="C", time="2024.01-2024.05", description="d", skills=["python"], achievements=["QPS提升"])
        cset = ss.select_experiences(s.query(Experience).all(), _jd(), baseline_date=baseline)
        d = cset.to_dict()
        check("generation_baseline_date" in d and "rule_version" in d, "to_dict 含基准日/规则版本")
        check(cset.selected_ids() == [x.experience_id for x in cset.slots], "selected_ids 一致")
    finally:
        s.close(); eng.dispose()


# ── 第二层测试 ───────────────────────────────────────────────── #
def test_second_layer():
    print("\n=== 第二层：事实选材与 SelectedEvidenceSet ===")

    # 建库 + 迁移 Fact + 重建 embedding
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
        s.commit()
    finally:
        s.close()
    eng.dispose()

    r = _run_migrations()
    assert r["error"] is None, f"迁移失败: {r['error']}"

    eng = _new_engine()
    s = _session(eng)
    try:
        # 重建 embedding（注入 mock）
        es.rebuild_embeddings(s, embedder=_mock_embedder)
        all_facts = s.query(Fact).all()
        check(len(all_facts) >= 3, f"迁移后 Fact >=3 (实际 {len(all_facts)})")

        cset = ss.select_experiences(s.query(Experience).all(), _jd(), baseline_date=date(2024, 6, 1))
        check(len(cset.slots) >= 2, f"第一层入选 >=2 (实际 {len(cset.slots)})")

        # [9] 第二层选材
        print("\n[9] select_evidence 基本流程")
        evidence = ss.select_evidence(s, cset, _jd(), embedder=_mock_embedder)
        check(len(evidence.entries) == len(cset.slots), "每个入选经历一个 EvidenceEntry")
        check(evidence.selection_id, "有 selection_id")
        check(evidence.jd_hash, "有 jd_hash")
        check(evidence.rule_version == ss.RULE_VERSION, "rule_version 匹配")

        # [10] fact_refs 只引用入选经历 + 版本匹配
        print("\n[10] fact_refs 约束")
        selected_ids = set(cset.selected_ids())
        for entry in evidence.entries:
            check(entry.experience_id in selected_ids, f"entry 属于入选经历 {entry.experience_id}")
            for ref in entry.fact_refs:
                fact = s.get(Fact, ref.fact_id)
                check(fact is not None, f"fact_ref {ref.fact_id} 存在")
                if fact is not None:
                    check(fact.experience_id == entry.experience_id, f"fact 属于该经历 {ref.fact_id}")
                    check(ref.revision == (fact.revision or 1), f"fact_ref revision 匹配 {ref.fact_id}")
                    check(ref.content_hash == (fact.content_hash or ""), f"fact_ref hash 匹配 {ref.fact_id}")

        # [11] 序列化可核对
        print("\n[11] 序列化与核对")
        j = evidence.to_json()
        check(isinstance(j, str) and "selection_id" in j, "to_json 可序列化")
        check(not evidence.is_expired(s, current_jd_hash=evidence.jd_hash), "未修改时未过期")

        # [12] Fact 修改 → 过期
        print("\n[12] Fact 修改 → SelectedEvidenceSet 过期")
        es.unwire_fact_invalidation()
        es.wire_fact_invalidation(sessionmaker(bind=eng, autoflush=False, autocommit=False))
        first_ref = evidence.all_fact_refs()[0]
        fact_service.modify_fact(s, first_ref.fact_id, "订单系统重构与稳定性治理 v2 改写")
        check(evidence.is_expired(s, current_jd_hash=evidence.jd_hash), "Fact 修改后过期")
        es.unwire_fact_invalidation()

        # [13] jd_hash 变化 → 过期
        print("\n[13] JD 变化 → 过期")
        other_jd = _jd(position="前端工程师", required_skills=["react", "css"])
        check(evidence.is_expired(s, current_jd_hash=ss._jd_hash(other_jd)), "JD 变化 → 过期")

        # [14] rule_version 变化 → 过期
        print("\n[14] rule_version 变化 → 过期")
        check(evidence.is_expired(s, current_rule_version="v9.9.9"), "rule_version 变化 → 过期")

        # [15] baseline_date 变化 → 过期
        print("\n[15] baseline_date 变化 → 过期")
        check(evidence.is_expired(s, current_baseline_date="2099-01-01"), "baseline_date 变化 → 过期")

        # [16] 更换 JD 不修改 Experience/Fact
        print("\n[16] 换 JD 不改事实源")
        before_facts = {f.fact_id: (f.revision, f.content_hash) for f in s.query(Fact).all()}
        before_exps = {e.id: (e.time, e.description) for e in s.query(Experience).all()}
        ss.select_experiences(s.query(Experience).all(), other_jd, baseline_date=date(2024, 6, 1))
        after_facts = {f.fact_id: (f.revision, f.content_hash) for f in s.query(Fact).all()}
        after_exps = {e.id: (e.time, e.description) for e in s.query(Experience).all()}
        check(before_facts == after_facts, "换 JD 不改 Fact")
        check(before_exps == after_exps, "换 JD 不改 Experience")

        # [17] ensure_ready 阻断 PENDING
        print("\n[17] embedding PENDING 阻断第二层")
        # 删除某 fact 的 embedding → PENDING
        target = all_facts[0]
        s.query(FactEmbedding).filter(FactEmbedding.fact_id == target.fact_id).delete()
        s.commit()
        es.mark_pending_for_missing(s)
        blocked = False
        try:
            ss.select_evidence(s, cset, _jd(), embedder=_mock_embedder)
        except errors.VectorIndexNotReadyError:
            blocked = True
        check(blocked, "PENDING embedding 阻断第二层选材")
        # 恢复
        es.rebuild_embeddings(s, embedder=_mock_embedder)

        # [18] 第二层不写回 Fact
        print("\n[18] 不写回事实库")
        rev_before = {f.fact_id: f.revision for f in s.query(Fact).all()}
        ss.select_evidence(s, cset, _jd(), embedder=_mock_embedder)
        rev_after = {f.fact_id: f.revision for f in s.query(Fact).all()}
        check(rev_before == rev_after, "第二层选材不改 Fact revision（不写回）")

    finally:
        s.close()
    eng.dispose()


def main() -> int:
    print(f"V1.5.0 T4 验证 | tmp={_TMP} | baseline window 3y")
    test_first_layer()
    test_second_layer()
    print(f"\n=== T4 汇总: PASS={_assertions['pass']} FAIL={_assertions['fail']} ===")
    return 0 if _assertions["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
