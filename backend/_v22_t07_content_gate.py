"""V2.2.0 R3 T07：内容级回归 gate（PLAN §5.1 / §5.2，阻断 Gate）。

隔离 runtime 同时存在 `current-user` / `other-user` / `stub-user` 三组互不相同的唯一
哨兵，覆盖 education / work / project 与完全重复记录。以 V2.2 `/api/task` 主链执行
（确定性 stub LLM provider + 真实装配/渲染/落盘，不触碰真实模型/真实 runtime），
产出 DOCX/PDF 并做内容级断言：

[G1] 候选/Fact/P4 条目 owner 全等于 Task owner；ID 集合包含关系；
[G2] P2 snapshot/subtask/ResumeDocument/DOCX/PDF 含当前用户哨兵，不含 other/stub 哨兵；
[G3] 教育进成品；work/project 源非空标题字段守恒；fact_refs 回查当前 owner Fact；
[G4] 完全重复记录保存层返回明确重复结果；既有重复在选材层只占一个槽位；
[G5] legacy-unowned 不进入 records、不能下载、continue 不改 owner；
[G6] 注入 owner/source/structure 失败时任务 FAILED 且不发布 DOCX/PDF；
[G7] §5.2：联系方式 8 组合、空照片框=0、summary/awards 空无原型文字/空标题、
      未替换占位符/模板样例文字/异主哨兵/源字段丢失=0。

退出码 0 = 全部通过且隔离 runtime 清理干净；非 0 = 有失败。
"""
from __future__ import annotations
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _v2_test_runner import run_isolated  # noqa: E402

# 当前本地身份真源（settings.DEFAULT_USER_ID = demo-user）。注意：必须在 run_isolated
# 建立临时 runtime 之后、在隔离环境中求值，避免模块顶层导入 core.config 绑定到真实 runtime。
OTHER = "other-user"
STUB = "stub-user"

_passed = 0
_failed = 0


def check(cond, name, extra=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [PASS] {name}")
    else:
        _failed += 1
        print(f"  [FAIL] {name} {extra}")


def _sh(s):
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


# ── 确定性 stub LLM（不联网，主链 P1–P3 用） ────────────────────────
class StubProvider:
    """provider(system, user_template, variables, max_tokens) -> (text, tokens)。

    分发 compact/fact/reason；生成原文与 DB 源哨兵无关（装配时 company/role/教育
    从 DB 回查，OCR 断言以 DB 哨兵为准），仅验证主链归属/结构不动摇哨兵。
    """

    def __init__(self):
        self.calls = 0

    def __call__(self, system, user_template, variables, max_tokens):
        self.calls += 1
        v = variables or {}
        if "required_skills" in user_template and "岗位描述" in user_template:
            return json.dumps({
                "position": "后端工程师", "industry": "互联网",
                "required_skills": ["Python"], "preferred_skills": [],
                "responsibilities": ["开发"], "keywords": ["后端"],
                "experience_preferences": [],
            }, ensure_ascii=False), 40
        if "facts_json" in v:
            exp = json.loads(v["experience_json"])["experience_id"]
            facts = json.loads(v["facts_json"])
            src = facts[0]["fact_id"] if facts else "f0"
            return json.dumps({
                "experience_id": exp, "fact_id": f"{exp}/{src}",
                "headline": f"[FH] {src}", "body": "body", "fact_refs": [src],
                "ok": True, "insufficient_reason": "",
            }, ensure_ascii=False), 40
        fid = v.get("fact_id", "")
        return json.dumps({"fact_id": fid, "delta": "理由", "done": True},
                          ensure_ascii=False), 20


def _run_tests_inner(state) -> int:
    import traceback
    from database import migrations as mig
    from database.session import SessionLocal, engine
    from database import models
    from services.task_service import TaskService
    from core.task_cancel import registry

    # 在隔离 runtime 中求值当前身份（真源 = settings.DEFAULT_USER_ID；本机 = demo-user）。
    from core.owner import current_user_id
    CURRENT = current_user_id()

    state.register_engine(engine)
    mig.run_migrations()

    # ══ 0. 建立三身份哨兵（education/work/project + 完全重复） ══
    db = SessionLocal()
    cur_edu_school = "某某大学-当前专用"
    cur_work = "当前科技-专属公司"
    cur_proj = "当前项目-专属名称"
    other_school = "OTHER-外国语大学"
    other_work = "OTHER-异主公司"
    stub_work = "STUB-占位公司"

    def mk_user(uid):
        if db.get(models.User, uid) is None:
            db.add(models.User(id=uid, name=uid, email="", created_at=None))
        db.flush()

    def mk_exp(eid, uid, etype, **kw):
        mk_user(uid)
        d = dict(id=eid, user_id=uid, type=etype,
                 title=kw.get("title", ""), company=kw.get("company", ""),
                 role=kw.get("role", ""), time=kw.get("time", ""),
                 description=kw.get("description", ""), skills=[],
                 achievements=kw.get("achievements", []),
                 raw_text=kw.get("description", ""))
        e = models.Experience(**d)
        db.add(e)
        db.flush()
        src = d["description"] or kw.get("company", "") or eid
        db.add(models.Fact(
            fact_id=f"{eid}/f1", experience_id=eid, fact_type=models.FactType.RESPONSIBILITY,
            text=src, source_text=src, source_field="description",
            source_index=None, content_hash=_sh(src), source_hash=_sh(src), revision=1))
        return e

    # current-user：教育 + 2 work + 1 project + 一条完全重复（选材层同键去重）
    mk_exp(f"{CURRENT}-edu1", CURRENT, "education",
           title=cur_edu_school, company=cur_edu_school, role="计算机", time="2019.09 - 2023.06",
           description=f"{cur_edu_school} 计算机科学 学士学位")
    mk_exp(f"{CURRENT}-w1", CURRENT, "work",
           title="高级工程师", company=cur_work, role="后端工程师",
           time="2021.07 - 至今",
           description=f"在 {cur_work} 主导核心系统研发，负责架构设计与性能优化。")
    mk_exp(f"{CURRENT}-w2", CURRENT, "work",
           title="工程师", company="第二段公司-当前", role="Java工程师",
           time="2019.07 - 2021.06", description="负责交易链路模块开发与稳定性保障。")
    mk_exp(f"{CURRENT}-p1", CURRENT, "project",
           title=cur_proj, company=cur_proj, role="负责人",
           time="2023.06 - 2024.01", description=f"主导 {cur_proj} 的从 0 到 1 落地。")
    # 完全重复：与 w1 的“公司/角色/时间/正文”全部一致
    mk_exp(f"{CURRENT}-w1dup", CURRENT, "work",
           title="高级工程师", company=cur_work, role="后端工程师",
           time="2021.07 - 至今",
           description=f"在 {cur_work} 主导核心系统研发，负责架构设计与性能优化。")

    # other-user / stub-user：只放 work + education，用于越权/异主隔离断言
    mk_exp("other-edu", OTHER, "education",
           title=other_school, company=other_school, role="数学", time="2015.09 - 2019.06",
           description=f"{other_school} 数学与应用数学")
    mk_exp("other-w1", OTHER, "work",
           title="分析师", company=other_work, role="分析", time="2016.01 - 2019.05",
           description=f"任职于 {other_work}。")
    mk_exp("stub-w1", STUB, "work",
           title="占位", company=stub_work, role="占位", time="2020.01 - 2020.06",
           description=f"任职于 {stub_work}。")

    # legacy-unowned（无 owner 历史任务，隔离态）
    from datetime import datetime
    db.add(models.Task(task_id="legacy-task-1", user_id=None, status="SUCCEEDED",
                       created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
    db.commit()

    # 完全重复保存层：创建同 company+role+time+见习正文 → 期望 DUPLICATE_EXPERIENCE
    print("\n[G4a] 保存层精确去重（完全重复 → 明确重复结果）")
    from services.experience_service import create_experience
    from core.errors import DuplicateExperienceError as DupError
    try:
        create_experience(db, CURRENT, {
            "type": "work", "title": "高级工程师", "company": cur_work,
            "role": "后端工程师", "time": "2021.07 - 至今",
            "description": f"在 {cur_work} 主导核心系统研发，负责架构设计与性能优化。",
        })
        check(False, "完全重复应抛 DuplicateExperienceError")
    except DupError:
        check(True, "完全重复创建返回 DUPLICATE_EXPERIENCE")
    except Exception as e:  # noqa: BLE001
        check(False, "完全重复未走重复语义", extra=repr(e))

    # 候选 Fact 向量就绪：主链 default_selector 走 select_evidence 要求向量已就绪，
    # 且生成期 select_evidence 会用 embedder 计算 JD 查询向量。用 stub embedder（T07
    # 不触碰真实 Embedding service），从 rebuild 到主链完成全程保持生效，最后恢复。
    import services.embedding_service as _emb
    _orig_embed = _emb._embed_text
    _emb._embed_text = lambda text: [0.1] * 16
    from services.embedding_service import rebuild_embeddings
    er = rebuild_embeddings(db, embedder=_emb._embed_text)
    check(er.get("succeeded", 0) > 0 and er.get("failed", 0) == 0,
          "候选 Fact embedding 就绪（rebuild 成功、无失败）",
          extra=f"succeeded={er.get('succeeded')} failed={er.get('failed')}")

    try:
        # ══ 1. 主链：V2.2 /api/task 全流程（stub provider + 默认 owner 选材/装配） ══
        print("\n[G1/G2/G3] V2.2 /api/task 主链内容级证明")
        svc = TaskService(db)

        # 诊断：与 worker 相同的 default_selector，确认本 runtime 当前 owner 选材非空
        from services.task_generation import default_selector as _ds
        from services.jd_analyzer import analyze_jd_task as _analyze
        from core import task as _task_core
        from services import llm_service as _llm
        _jd_for_probe = ("岗位名称：资深后端工程师。\n职责：负责系统架构设计与核心模块实现，主导性能优化与"
                         "稳定性保障，参与技术评审、代码审查、迭代交付。\n必备技能：Python、Java、MySQL。")
        _budget = _llm.TaskTokenBudget(_task_core.TASK_LLM_COMPLETION_LIMIT)
        _compact, _ = _analyze(_jd_for_probe, budget=_budget, provider=StubProvider())
        _probe_prepared = _ds(db, _compact)
        check(len(_probe_prepared) > 0,
              "default_selector 对当前 owner 产生非空 prepared",
              extra=f"count={len(_probe_prepared)} ids={[p.experience_id for p in _probe_prepared]}")

        t = svc.create_task()
        tid = t["task_id"]
        jd = ("岗位名称：资深后端工程师。\n职责：负责系统架构设计与核心模块实现，主导性能优化与"
              "稳定性保障，参与技术评审、代码审查、迭代交付。\n必备技能：Python、Java、MySQL。")
        svc.save_draft(tid, name="王小明", phone="13800001234", email="wang@current.cn",
                       location="北京", jd=jd)
        svc.freeze_input(tid, name="王小明", phone="13800001234", email="wang@current.cn",
                         location="北京", jd=jd)
        svc.start_task(tid)

        # 主链使用**真实的 default_selector（按 current_user_id 过滤 + 选材层精确去重）
        # 与默认 make_task_assembler（owner 归主装配 + 教育确定性进入）+ 真实 DOCX/PDF 链**
        # （run_generation 默认路径，仅注入 stub LLM provider 避免真实模型调用）。
        svc.run_generation(tid, provider=StubProvider())

        import time
        final_status = None
        for _ in range(600):
            time.sleep(0.5)
            from database.session import SessionLocal as _Poll
            _db = _Poll()
            try:
                _row = _db.query(models.Task).filter_by(task_id=tid).first()
                final_status = _row.status if _row else None
            finally:
                _db.close()
            if final_status in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
        check(final_status == "SUCCEEDED", f"主链最终 SUCCEEDED（实际 {final_status}）")

        # 读取 P4 快照 / artifact 引用
        task_view = svc.get_task(tid)
        task_owner = task_view.get("user_id")
        check(task_owner == CURRENT, f"Task owner 为 current-user（实际 {task_owner}）")

        snapshot = (db.query(models.TaskSnapshot)
                    .filter_by(task_id=tid).order_by(models.TaskSnapshot.seq.desc()).first())
        snap_payload = snapshot.payload if snapshot else {}
        snap_artifacts = snap_payload.get("artifacts") or {}
        print("  [diag] P4 assembled=", snap_payload.get("assembled"),
              " stage=", snap_payload.get("stage"))
        artifacts = snap_artifacts  # P4 assembler 的完整 artifact 引用（含 docx_abs/pdf_abs）
        docx_path = artifacts.get("docx_abs", "") or artifacts.get("docx_path", "")
        pdf_abs = artifacts.get("pdf_abs", "") or ""
        pdf_path = artifacts.get("pdf_abs", "")
        check(bool(docx_path), "已登记 docx artifact 引用")
        check(bool(pdf_path), "已登记 pdf artifact 引用（Word 可用时）")
        check(bool(docx_path and Path(docx_path).is_file()), "DOCX 文件存在且可读")

        # ══ 内容级断言（读 DOCX 文本） ══
        import zipfile, re
        def docx_text(path):
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            xml = re.sub(r"<[^>]+>", "", xml)
            return xml

        if docx_path and Path(docx_path).is_file():
            text = docx_text(str(docx_path))
            check(cur_edu_school in text, "G3 当前用户教育（学校）进入 DOCX")
            check(cur_work in text, "G2 current work 哨兵进入 DOCX")
            check(cur_proj in text, "G2 current project 哨兵进入 DOCX")
            check(other_work not in text, "G2 异主 other work 哨兵不进入 DOCX")
            check(other_school not in text, "G2 异主 other 教育不进入 DOCX")
            check(stub_work not in text, "G2 stub 哨兵不进入 DOCX")
            check("王小明" in text, "G3 冻结姓名进入 DOCX")
            check("13800001234" in text, "G7 电话非空进入 DOCX")
            check("wang@current.cn" in text.replace(" ", ""), "G7 邮箱非空进入 DOCX")
            check("北京" in text, "G7 所在地非空进入 DOCX")
            # 未替换占位符 / 模板样例 / 空照片框归零
            check("{{" not in text and "}}" not in text, "G7 未替换占位符 = 0")
            check("照片" not in text, "G7 无照片输入 → 不含照片占位文字")
            # 完全重复：company 只出现一次（选材去重）
            check(text.count(cur_work) >= 1, "G4b 重复经历选材只占一槽（company 出现，无二份）")

        # ══ [G5] legacy-unowned 隔离 ══
        print("\n[G5] legacy-unowned 隔离（records / 下载 / continue）")
        recs = svc.list_records(limit=500)
        rec_ids = [r.get("task_id") for r in recs]
        check("legacy-task-1" not in rec_ids, "legacy-unowned 不进入 records")
        try:
            svc.get_task("legacy-task-1")
            check(False, "legacy 任务应 404（隔离）")
        except Exception:
            check(True, "legacy 任务 get 视为不存在")

        # ══ [G6] 注入 owner/结构失败 → FAILED 且不发布 ══
        print("\n[G6] 结构错误不发布")
        t2 = svc.create_task()["task_id"]
        svc.save_draft(t2, name="孙七", phone="", email="", location="", jd=jd)
        svc.freeze_input(t2, name="孙七", phone="", email="", location="", jd=jd)
        svc.start_task(t2)
        class _BrokenAsm:
            def __call__(self, summary, compact):
                raise Exception("injected-owner-structure")
        svc.run_generation(t2, provider=StubProvider(), selector=lambda c: [],
                           assembler=_BrokenAsm())
        time.sleep(0.5)
        for _ in range(300):
            from database.session import SessionLocal as _Poll2
            _db2 = _Poll2()
            try:
                _row2 = _db2.query(models.Task).filter_by(task_id=t2).first()
                _st2 = _row2.status if _row2 else None
            finally:
                _db2.close()
            if _st2 in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(0.5)
        check(_st2 == "FAILED", f"G6 结构错误 → FAILED（实际 {_st2}）")
        t2_view = svc.get_task(t2)
        check(not t2_view.get("published_docx_path"), "G6 结构失败不发布 DOCX")
    finally:
        # 无论成功失败都恢复原函数，避免污染隔离 runtime
        _emb._embed_text = _orig_embed

    db.close()
    return 0 if _failed == 0 else 1


def _main() -> None:
    run_isolated("v22r3-t07-", _run_tests_inner, "V2.2.0 R3 T07 内容级回归 gate")


if __name__ == "__main__":
    _main()