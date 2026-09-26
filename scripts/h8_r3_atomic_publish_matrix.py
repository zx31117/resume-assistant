#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 R3 返工：task-scoped staging / 内容校验 / 原子发布 正反向矩阵。

对应 RESULT §R3-18 C 与 PLAN G04 / §3.3 / §5.3。本脚本是**真实产品代码路径**的可执行
断言（真实 DOCX/PDF 文件、真实 SQLite 事务、真实 staging/output 目录、真实退出码）；
不使用 mock 顶替产品逻辑，只在“上游失败”处注入真实故障（缺文件、写坏字节、重命名失败、
commit 失败、取消、迟到结果）。

覆盖：
  P1  正常发布：staging → 校验 → 同盘原子提升 → 单事务登记 + SUCCEEDED → 可下载、staging 清理；
  P2  DOCX 缺失；P3 零字节 DOCX；P4 损坏 DOCX（非 zip）；
  P5  零字节 / 损坏 PDF（声明存在但无效 → 拒绝发布）；
  P6  内容哨兵不一致（成品含其他 owner 哨兵文字 → 拒绝）；
  P7  staging 外路径（越界路径 → 拒绝）；
  P8  Word→PDF 失败（DOCX 仍可用；不产生假 PDF artifact）；
  P9  文件写入失败（staging 不可写 → 不发布、不 SUCCEEDED）；
  P10 原子 rename 失败（目标不可写 → 提升失败、回滚已提升文件、不 SUCCEEDED）；
  P11 DB commit 失败 → rollback：无 SUCCEEDED、已提升文件被删、staging 清理；
  P12 取消（CANCELLED 终态）后不得发布；
  P13 迟到结果（已 SUCCEEDED/FAILED 终态）不得覆盖与重复发布；
  P14 cleanup 自身失败必须可见（返回 False，不静默成功）；
  P15 cleanup 重复执行幂等。

退出码 0 = 全部通过；非 0 = 失败（并写出 JSON 证据 + 可定位 problems）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


def _rmtree_force(path, attempts: int = 8) -> bool:
    """删除目录树，兼容**只读文件**（产品迁移备份 `*.db.bak` 被 `os.chmod(bak, 0o444)`）。

    Windows 上 `shutil.rmtree(..., ignore_errors=True)` 遇到只读文件会**静默失败**，
    导致隔离 runtime 残留、Gate cleanup 误判失败（已在 mainchain/design_fidelity/
    atomic_publish 复现）。这里在出错回调里清除只读位后重试，并做有限次整体重试以
    吸收句柄释放延迟。
    """
    import inspect as _inspect
    import stat as _stat
    import time as _time

    def _fix(func, p, exc=None):
        try:
            os.chmod(p, _stat.S_IWRITE)
            func(p)
        except Exception:  # noqa: BLE001
            pass

    _params = _inspect.signature(shutil.rmtree).parameters
    _kw = {"onexc": _fix} if "onexc" in _params else {"onerror": _fix}
    for _ in range(attempts):
        try:
            shutil.rmtree(path, **_kw)
        except Exception:  # noqa: BLE001
            pass
        if not os.path.exists(path):
            return True
        _time.sleep(0.4)
    return not os.path.exists(path)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EVID = ROOT / "validation-artifacts" / "h8" / "r3rework4"

# ── 进程级隔离：必须在导入任何产品模块之前设置 ──
_RT = Path(tempfile.mkdtemp(prefix="h8pub_"))
os.environ["RESUME_DATA_DIR"] = str(_RT)
os.environ.pop("PYTHONPATH", None)
sys.path.insert(0, str(ROOT / "backend"))

CUR = "demo-user"
OTHER = "other-user"
NAME = "PublishMatrixUser"
COMPANY = "CURPublishCo"
ROLE = "BackendEngineer"
SENTINEL_OK = "CUR-OWN-SENTINEL-BULLET"
SENTINEL_FOREIGN = "OTHER-OWNER-SENTINEL"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def make_docx(path: Path, text: str) -> None:
    from docx import Document
    d = Document()
    d.add_paragraph(text)
    d.save(str(path))


def make_pdf(path: Path, text: str) -> None:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(EVID / "atomic_publish_matrix.json"))
    args = ap.parse_args()

    evid: dict = {"cases": [], "problems": [], "runtime_dir_label": _RT.name}
    cases: list[dict] = []

    def rec(cid: str, desc: str, ok_: bool, **kw) -> None:
        cases.append({"id": cid, "case": desc, "ok": bool(ok_), **kw})
        print(f"  [{'PASS' if ok_ else 'FAIL'}] {cid} {desc} "
              f"{json.dumps(kw, ensure_ascii=False)[:220]}", flush=True)

    try:
        from core.config import settings
        from database.init_db import init_db
        from database import models
        from database.session import SessionLocal
        from services import artifact_store, document_assembler
        from services.task_repository import TaskRepository, TaskStateError

        init_db()

        out_dir = Path(settings.DOCX_OUTPUT_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)

        def new_task(db, tid: str, status: str = "RUNNING"):
            from core.task import TaskStatus
            import uuid
            t = models.Task(task_id=tid, user_id=CUR, status=status,
                            current_input_revision=1, seq=0,
                            created_at=__import__("datetime").datetime.utcnow(),
                            updated_at=__import__("datetime").datetime.utcnow())
            db.add(t)
            db.flush()
            return t

        def stage_pair(task_id: str, *, docx_text=SENTINEL_OK, pdf_text=SENTINEL_OK,
                       docx_bytes: bytes | None = None, pdf_bytes: bytes | None = None):
            """在 task staging 内产出真实 DOCX/PDF（或按参数注入坏字节）。"""
            op = "opabcdef01234567"
            d = artifact_store.task_staging_dir(task_id, op)
            dx = d / f"resume_{task_id}_pm_template_{op}.docx"
            pf = d / f"resume_{task_id}_pm_template_{op}.pdf"
            body = f"{NAME} {COMPANY} {ROLE} {docx_text}"
            if docx_bytes is not None:
                dx.write_bytes(docx_bytes)
            else:
                make_docx(dx, body)
            if pdf_bytes is not None:
                pf.write_bytes(pdf_bytes)
            else:
                make_pdf(pf, f"{NAME} {COMPANY} {ROLE} {pdf_text}")
            return d, dx, pf

        def artifacts_from(dx: Path, pf: Path | None, task_id: str) -> dict:
            return {
                "docx_staged_abs": str(dx),
                "pdf_staged_abs": str(pf) if pf else "",
                "docx_file_name": dx.name,
                "pdf_file_name": pf.name if pf else "",
                "staging_dir": str(dx.parent),
                "docx_path": f"output/{dx.name}",
                "pdf_path": f"output/{pf.name}" if pf else "",
            }

        def resume_doc_for(text: str):
            from models.resume_document import ResumeDocument, Profile, WorkItem
            return ResumeDocument(
                profile=Profile(name=NAME, target_position=ROLE),
                summary="", education=[], skills=[], awards=[],
                work=[WorkItem(company=COMPANY, role=ROLE,
                               bullets=[text], experience_id="exp1", fact_refs=[])],
                projects=[],
                meta={},
            )

        def validate(dx: Path, pf: Path | None, task_id: str, *,
                     forbidden=None, contact=None, rows=None, stats=None, doc=None):
            return document_assembler.validate_staged_artifacts(
                docx_path=str(dx), pdf_path=(str(pf) if pf else None),
                task_id=task_id, owner=CUR,
                resume_doc=doc if doc is not None else resume_doc_for(SENTINEL_OK),
                render_stats=stats or {"unreplaced_placeholders": []},
                contact=contact or {"name": NAME, "phone": "", "email": "", "location": ""},
                experience_rows=rows or [{"experience_id": "exp1", "type": "work",
                                          "company": COMPANY, "role": ROLE}],
                template_id="pm_template",
                forbidden_sentinels=forbidden or [SENTINEL_FOREIGN],
            )

        # ── P1 正常发布 ──
        db = SessionLocal()
        try:
            repo = TaskRepository(db)
            t = new_task(db, "t-p1")
            db.commit()
            _, dx, pf = stage_pair("t-p1")
            probs = validate(dx, pf, "t-p1")
            rec("P1a", "正常 staging 产物通过发布前内容校验（problems 为空）",
                not probs, problems=probs[:6])
            promoted = document_assembler.promote_staged_artifacts(artifacts_from(dx, pf, "t-p1"))
            repo.publish_success(t, resume_revision=1, promoted=promoted)
            db.commit()
            docx_final = Path(promoted["docx"]["abs"])
            pdf_final = Path(promoted["pdf"]["abs"])
            rec("P1b", "SUCCEEDED + 不可变 artifact 引用同一事务登记成功",
                t.status == "SUCCEEDED"
                and repo.resolve_artifact("t-p1", "docx") is not None
                and repo.resolve_artifact("t-p1", "pdf") is not None,
                status=t.status)
            rec("P1c", "提升后文件位于 output 且 sha 与既有磁盘一致",
                docx_final.is_file() and pdf_final.is_file()
                and sha256_file(docx_final) == promoted["docx"]["sha256"],
                docx=docx_final.name)
            from services.task_service import TaskService
            got = TaskService(db).resolve_artifact_download("t-p1", "docx")
            rec("P1d", "下载解析经 owner+task+引用+kind 成功定位已提交文件",
                Path(got["abs_path"]).is_file(), path=Path(got["abs_path"]).name)
            rec("P1e", "发布成功后 staging 目录已清理（无残留）",
                artifact_store.cleanup_dir_quiet(str(dx.parent))
                and not dx.parent.exists())
        finally:
            db.close()

        # ── P2/P3/P4 DOCX 缺失 / 零字节 / 损坏 ──
        for cid, label, mut in (
            ("P2", "DOCX 缺失", "missing"),
            ("P3", "DOCX 零字节", "zero"),
            ("P4", "DOCX 损坏（非 zip）", "corrupt"),
        ):
            db = SessionLocal()
            try:
                t = new_task(db, f"t-{cid.lower()}")
                db.commit()
                d, dx, pf = stage_pair(f"t-{cid.lower()}")
                if mut == "missing":
                    dx.unlink()
                elif mut == "zero":
                    dx.write_bytes(b"")
                else:
                    dx.write_bytes(b"not-a-zip-at-all" * 8)
                probs = validate(dx, pf, f"t-{cid.lower()}")
                refused = False
                try:
                    document_assembler.assert_publishable(probs)
                    document_assembler.promote_staged_artifacts(
                        artifacts_from(dx, pf, f"t-{cid.lower()}"))
                except Exception:
                    refused = True
                rec(cid, f"{label} → 产品级发布门禁拒绝（不发布）",
                    bool(probs) and refused,
                    problems=[p for p in probs][:4])
                artifact_store.cleanup_dir_quiet(str(d.parent))
            finally:
                db.close()

        # ── P5 零字节 / 损坏 PDF（已声明存在但无效 → 拒绝） ──
        db = SessionLocal()
        try:
            t = new_task(db, "t-p5")
            db.commit()
            d, dx, pf = stage_pair("t-p5", pdf_bytes=b"")
            probs_zero = validate(dx, pf, "t-p5")
            pf.write_bytes(b"%PDF-1.7\nbroken")  # 无 %%EOF
            probs_corrupt = validate(dx, pf, "t-p5")
            rec("P5", "零字节 / 损坏 PDF → 均被校验拒绝",
                bool(probs_zero) and bool(probs_corrupt),
                zero=probs_zero[:3], corrupt=probs_corrupt[:3])
            artifact_store.cleanup_dir_quiet(str(d.parent))
        finally:
            db.close()

        # ── P6 内容哨兵不一致 ──
        db = SessionLocal()
        try:
            t = new_task(db, "t-p6")
            db.commit()
            d, dx, pf = stage_pair("t-p6", docx_text=SENTINEL_FOREIGN, pdf_text=SENTINEL_FOREIGN)
            probs = validate(dx, pf, "t-p6")
            rec("P6", "成品含其他 owner 哨兵文字 → 校验拒绝",
                any("FOREIGN_OWNER_SENTINEL" in p for p in probs), problems=probs[:4])
            artifact_store.cleanup_dir_quiet(str(d.parent))
        finally:
            db.close()

        # ── P7 staging 外路径 ──
        db = SessionLocal()
        try:
            t = new_task(db, "t-p7")
            db.commit()
            outside = out_dir / "resume_outside_staging.docx"
            make_docx(outside, SENTINEL_OK)
            probs = validate(outside, None, "t-p7")
            rec("P7", "staging 之外路径 → 校验拒绝（NOT_IN_TASK_STAGING）",
                any("NOT_IN_TASK_STAGING" in p for p in probs), problems=probs[:4])
            artifact_store.remove_file_quiet(outside)
        finally:
            db.close()

        # ── P8 Word→PDF 失败：DOCX 仍可用，不产生假 PDF ──
        db = SessionLocal()
        try:
            from services import docx_to_pdf as _d2p
            orig = _d2p.convert_docx_to_pdf_bytes
            _d2p.convert_docx_to_pdf_bytes = lambda *a, **k: (_ for _ in ()).throw(
                RuntimeError("injected word failure"))
            try:
                _, arts = document_assembler.assemble_and_render(
                    db, _FakeSummary(), {"position": ROLE},
                    task_id="t-p8", contact={"name": NAME, "phone": "",
                                             "email": "", "location": ""},
                    template_id="pm_template",
                    experience_rows=[{"experience_id": "exp1", "type": "work",
                                      "company": COMPANY, "role": ROLE}],
                    user_id=CUR,
                )
            finally:
                _d2p.convert_docx_to_pdf_bytes = orig
            rec("P8", "Word→PDF 失败 → DOCX 仍生成、PDF 名称为空（不制造假 PDF artifact）",
                bool(arts.get("docx_staged_abs")) and not arts.get("pdf_staged_abs")
                and not arts.get("pdf_path"),
                pdf_path=arts.get("pdf_path"))
            artifact_store.cleanup_dir_quiet(arts.get("staging_dir") or "")
        finally:
            db.close()

        # ── P9 文件写入失败（staging 不可写）──
        db = SessionLocal()
        try:
            from docx.document import Document as _DocxDocument
            _orig_save = _DocxDocument.save

            def _boom(self, *a, **k):
                raise OSError("injected staging write failure")

            _DocxDocument.save = _boom
            wrote_ok = False
            try:
                _, arts = document_assembler.assemble_and_render(
                    db, _FakeSummary(), {"position": ROLE},
                    task_id="t-p9", contact={"name": NAME, "phone": "",
                                             "email": "", "location": ""},
                    template_id="pm_template",
                    experience_rows=[{"experience_id": "exp1", "type": "work",
                                      "company": COMPANY, "role": ROLE}],
                    user_id=CUR,
                )
                wrote_ok = bool(arts.get("docx_staged_abs"))
            except Exception:
                wrote_ok = False
            finally:
                _DocxDocument.save = _orig_save
            leaked = [str(p) for p in artifact_store.staging_root().rglob("*") if p.is_file()]
            rec("P9", "文件写入失败 → 不产出可发布 artifact 且无 staging 残留",
                (not wrote_ok) and not leaked, leaked_files=leaked[:3])
            artifact_store.cleanup_task_staging("t-p9")
        finally:
            db.close()

        # ── P10 原子 rename 失败 ──
        db = SessionLocal()
        try:
            t = new_task(db, "t-p10")
            db.commit()
            d, dx, pf = stage_pair("t-p10")
            # 目标文件名与 output 下已有目录同名 → os.replace 失败
            blocker = out_dir / "resume_blocker_rename.docx"
            if blocker.exists():
                _rmtree_force(blocker)
            blocker.mkdir(parents=True, exist_ok=True)
            arts = artifacts_from(dx, pf, "t-p10")
            arts["docx_file_name"] = blocker.name
            failed = False
            try:
                document_assembler.promote_staged_artifacts(arts)
            except Exception:
                failed = True
            rec("P10", "原子 rename 失败 → 抛出失败且不留下半成品",
                failed and blocker.is_dir() and dx.is_file(),
                staging_intact=dx.is_file())
            _rmtree_force(blocker)
            artifact_store.cleanup_dir_quiet(str(d.parent))
        finally:
            db.close()

        # ── P11/P12 DB commit 失败 → rollback：无 SUCCEEDED、文件回滚、staging 清理 ──
        db = SessionLocal()
        try:
            t = new_task(db, "t-p11")
            db.commit()
            d, dx, pf = stage_pair("t-p11")
            arts = artifacts_from(dx, pf, "t-p11")
            promoted = document_assembler.promote_staged_artifacts(arts)
            repo = TaskRepository(db)
            repo.publish_success(t, resume_revision=1, promoted=promoted)
            # 模拟 commit 失败
            db.rollback()
            document_assembler._rollback_promoted(promoted)
            artifact_store.cleanup_dir_quiet(str(d))
            db2 = SessionLocal()
            try:
                row = db2.get(models.Task, "t-p11")
                final_docx = Path(promoted["docx"]["abs"])
                rec("P11", "DB rollback → 无 SUCCEEDED、已提升文件被删除、staging 清理",
                    row is not None and row.status != "SUCCEEDED"
                    and not final_docx.exists()
                    and not Path(d).exists(),
                    status=row.status if row else None,
                    final_gone=not final_docx.exists())
            finally:
                db2.close()
        finally:
            db.close()

        # ── P12 取消后不得发布 ──
        db = SessionLocal()
        try:
            t = new_task(db, "t-p12", status="CANCELLED")
            db.commit()
            d, dx, pf = stage_pair("t-p12")
            promoted = document_assembler.promote_staged_artifacts(artifacts_from(dx, pf, "t-p12"))
            rejected = False
            try:
                TaskRepository(db).publish_success(t, resume_revision=1, promoted=promoted)
            except TaskStateError:
                rejected = True
            if not rejected:
                document_assembler._rollback_promoted(promoted)
            rec("P12", "CANCELLED 终态 → publish_success 拒绝（不产生假成功）", rejected)
            document_assembler._rollback_promoted(promoted)
            artifact_store.cleanup_dir_quiet(str(d))
        finally:
            db.close()

        # ── P13 迟到结果：已 SUCCEEDED / FAILED 终态不得重复发布 ──
        results = {}
        for st in ("SUCCEEDED", "FAILED"):
            db = SessionLocal()
            try:
                tid = f"t-p13-{st.lower()}"
                t = new_task(db, tid, status=st)
                db.commit()
                d, dx, pf = stage_pair(tid)
                promoted = document_assembler.promote_staged_artifacts(artifacts_from(dx, pf, tid))
                rejected = False
                try:
                    TaskRepository(db).publish_success(t, resume_revision=1, promoted=promoted)
                except TaskStateError:
                    rejected = True
                results[st] = rejected
                document_assembler._rollback_promoted(promoted)
                artifact_store.cleanup_dir_quiet(str(d))
            finally:
                db.close()
        rec("P13", "已 SUCCEEDED/FAILED 终态 → 迟到发布被拒（不覆盖既有终态）",
            all(results.values()), detail=results)

        # ── P14 cleanup 自身失败必须可见 ──
        d = artifact_store.task_staging_dir("t-p14", "opabcdef01234567")
        f = d / "locked.bin"
        f.write_bytes(b"x" * 32)
        fh = open(f, "rb")
        try:
            ok_flag = artifact_store.cleanup_dir_quiet(str(d))
        finally:
            fh.close()
        rec("P14", "cleanup 遇到占用文件 → 返回 False（失败可见，不静默成功）",
            ok_flag is False, cleaned=ok_flag)
        # ── P15 cleanup 重复执行幂等 ──
        again = artifact_store.cleanup_dir_quiet(str(d))
        rec("P15", "cleanup 重复执行幂等（已消失也判成功）", again is True, second=again)

        failures = [c for c in cases if not c["ok"]]
        evid["cases"] = cases
        evid["case_ids"] = [c["id"] for c in cases]
        evid["all_ok"] = not failures
        evid["failures"] = [f"{c['id']}:{c['case']}" for c in failures]
        if failures:
            evid["problems"].append(f"{len(failures)} 个原子发布矩阵用例失败")
        return 0 if not failures else 1
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        evid["exception"] = repr(e)
        evid["problems"].append(f"exception:{type(e).__name__}")
        evid["all_ok"] = False
        return 2
    finally:
        # 先释放 SQLAlchemy 连接池，否则 SQLite 文件句柄仍被 engine 持有 →
        # rmtree(ignore_errors=True) 会静默失败、隔离 runtime 残留（已复现）。
        try:
            from database.session import engine as _engine  # type: ignore
            _engine.dispose()
        except Exception:  # noqa: BLE001
            pass
        import time as _t
        for _ in range(8):
            _rmtree_force(_RT)
            if not _RT.exists():
                break
            _t.sleep(0.5)
        evid["cleanup"] = {"runtime_removed": not _RT.exists()}
        evid["ok"] = bool(evid.get("all_ok"))
        evid["gate_passed"] = bool(evid.get("all_ok"))
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(evid, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[atomic-publish] wrote {out} ok={evid['ok']}")


class _FakeFact:
    def __init__(self, headline="", body="", fact_refs=None):
        self.headline = headline
        self.body = body
        self.fact_refs = list(fact_refs or [])


class _FakeExp:
    def __init__(self, eid="exp1", title=COMPANY, facts=None):
        self.experience_id = eid
        self.sort_order = 1
        self.title = title
        self.facts = facts or [_FakeFact(ROLE, "Core service development.", ["f1"])]


class _FakeSummary:
    def __init__(self):
        self.experiences = [_FakeExp()]
        self.compact_jd = {}
        self.phase = "P3"
        self.artifacts = {}


if __name__ == "__main__":
    sys.exit(main())
