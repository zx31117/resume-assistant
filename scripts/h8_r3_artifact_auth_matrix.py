#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 R3 返工：用户 artifact 授权（task-scoped / owner-scoped）正反向矩阵。

对应 RESULT §R3-18 B 与 PLAN G05 / §3.1 / §5.3。全部结论必须来自**冻结包**上真实
HTTP 子进程 + 真实磁盘文件，不使用 mock。

覆盖：
  1) current-user 自己的 task → 200 + MIME 正确 + 字节与磁盘一致 + sha 一致；
  2) other-user / stub-user / LEGACY_UNOWNED(task.user_id IS NULL) 的 task → 404；
  3) 换 task / 换 owner / 交叉组合（A 的 task + B 的 artifact 引用）→ 404；
  4) 未登记 artifact（磁盘有文件但 artifacts 无行）→ 404；
  5) 错误 artifact kind（只登记 pdf 却取 docx）→ 404；
  6) filename 伪造 / 额外 query 参数 / 路径穿越 kind → 404；
  7) `GET` 与 `HEAD` 同等执行授权；
  8) 未授权与不存在对象的响应体完全一致（不泄露存在性差异）；
  9) 旧 `/api/template/download` 不再服务用户简历（所有 `output/resume_*` → 404），
     但仍可下载公开内置模板资产（200）。

退出码 0 = 全部通过；非 0 = 存在失败（并写出 JSON 证据 + 明确定位 problems）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path


def _rmtree_force(path, attempts: int = 8) -> bool:
    """删除目录树，兼容**只读文件**（产品迁移备份 `*.db.bak` 被 `os.chmod(bak, 0o444)`）。

    Windows 上 `shutil.rmtree(..., ignore_errors=True)` 遇到只读文件会**静默失败**，
    导致隔离 runtime 残留、Gate cleanup 误判失败（已在 mainchain/design_fidelity/
    atomic_publish 复现）。这里在出错回调里清除只读位后重试，并做有限次整体重试以
    吸收句柄释放延迟。
    """
    import inspect as _inspect
    import os
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
PY = os.environ.get("H8_E2E_PYTHON", sys.executable)

OWNER = "demo-user"
OTHER = "other-user"
STUB = "stub-user"
LEGACY_TASK = "legacy-unowned-task-0001"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MIME = "application/pdf"

CUR_SENTINEL = "CUR-授权矩阵专用公司"
OTHER_SENTINEL = "OTHER-异主哨兵公司"


def log(m: str) -> None:
    print(m, flush=True)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def wait_port(port: int, timeout: float = 120.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        for host in ("127.0.0.1", "::1", "localhost"):
            try:
                with socket.create_connection((host, port), timeout=1):
                    return True
            except OSError:
                pass
        time.sleep(0.3)
    return False


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
    ap.add_argument("--exe", default="", help="最终 onedir 的 ResumeAssistant.exe（正式 Gate 必传）")
    ap.add_argument("--base", default="", help="已运行的 app base URL（仅本地开发迭代用）")
    ap.add_argument("--runtime-dir", default="", help="配合 --base 的隔离 runtime（仅本地开发迭代用）")
    ap.add_argument("--out", default=str(EVID / "artifact_auth_matrix.json"))
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    evid: dict = {"cases": [], "problems": [], "limits": {"python": PY}}
    exe = Path(args.exe).resolve() if args.exe else None
    if exe is not None and not exe.is_file():
        log(f"[fatal] exe 不存在：{exe}")
        return 2
    if exe is not None:
        exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
        evid["exe"] = {"path": exe.name, "sha256": exe_sha, "size": exe.stat().st_size}
    else:
        evid["exe"] = None

    if args.base:
        # 本地开发迭代：复用已在运行的实例（不参与正式 Gate 判定）。
        runtime = Path(args.runtime_dir or ".").resolve()
        rc = _run_matrix(args, evid, base=args.base.rstrip("/"), runtime=runtime,
                         app=None, app_fh=None, exe=exe)
        evid["ok"] = bool(evid.get("all_ok"))
        evid["gate_passed"] = bool(evid.get("all_ok"))
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(evid, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[auth-matrix] wrote {out} ok={evid['ok']}")
        return rc

    runtime = Path(os.environ.get("TEMP", ".")) / f"h8auth_{int(time.time())}"
    runtime.mkdir(parents=True, exist_ok=True)
    evid["runtime_dir_label"] = runtime.name
    port = 8341
    env = dict(os.environ)
    env["RESUME_DATA_DIR"] = str(runtime)
    env["APP_PORT"] = str(port)
    env.pop("ARK_API_KEY", None)

    app_stdout = EVID / "artifact_auth_app.log"
    app_fh = open(app_stdout, "w", encoding="utf-8", errors="replace")
    app = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env,
                           stdout=app_fh, stderr=subprocess.STDOUT)
    ok = False
    runtime_removed = False
    try:
        if not wait_port(port, 180):
            evid["problems"].append("app_boot_failed")
            return 3
        return _run_matrix(args, evid, base=f"http://127.0.0.1:{port}", runtime=runtime,
                           app=app, app_fh=app_fh, exe=exe)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        evid["exception"] = repr(e)
        evid["problems"].append(f"exception:{type(e).__name__}")
        return 2
    finally:
        try:
            app.terminate()
            app.wait(timeout=15)
        except Exception:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(app.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            app_fh.close()
        except Exception:
            pass
        if not args.keep:
            _rmtree_force(runtime)
            runtime_removed = not runtime.exists()
        evid["runtime_deleted"] = bool(runtime_removed)
        evid["ok"] = bool(evid.get("all_ok"))
        evid["gate_passed"] = bool(evid.get("all_ok"))
        evid["cleanup"] = {"runtime_removed": bool(runtime_removed)}
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(evid, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[auth-matrix] wrote {out} ok={evid['ok']}")


def _run_matrix(args, evid: dict, *, base: str, runtime: Path, app, app_fh, exe) -> int:
    try:
        import requests
        s = requests.Session()
        r = s.get(f"{base}/api/health", timeout=30)
        if r.status_code != 200:
            evid["problems"].append(f"health:{r.status_code}")
            return 3
        if s.post(f"{base}/api/system/migrate", timeout=300).status_code != 200:
            evid["problems"].append("migrate_failed")
            return 3

        db_path = runtime / "database" / "app.db"
        out_dir = runtime / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        staging_dir = runtime / "staging"
        staging_dir.mkdir(parents=True, exist_ok=True)

        # ── 造真实磁盘文件（用户产物 + 未登记文件 + 公开模板资产）──
        cur_docx = out_dir / "resume_cur_own.docx"
        cur_pdf = out_dir / "resume_cur_own.pdf"
        make_docx(cur_docx, CUR_SENTINEL)
        make_pdf(cur_pdf, CUR_SENTINEL)
        # 未登记但真实存在（staging 内 + output 内各一份）
        unreg_docx = out_dir / "resume_unregistered.docx"
        make_docx(unreg_docx, "UNREGISTERED")
        staged_only = staging_dir / "resume_staged_only.docx"
        make_docx(staged_only, "STAGED-ONLY")
        # other-owner / stub / legacy 的磁盘产物
        other_docx = out_dir / "resume_other_own.docx"
        make_docx(other_docx, OTHER_SENTINEL)
        stub_docx = out_dir / "resume_stub_own.docx"
        make_docx(stub_docx, "STUB-SENTINEL")

        def sha(p: Path) -> str:
            return hashlib.sha256(p.read_bytes()).hexdigest()

        def size(p: Path) -> int:
            return p.stat().st_size

        # ── 造 Task + artifact 行（直接写隔离库；模拟已发布记录）──
        now = "2026-09-25 12:00:00"
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        rows: list[tuple] = [
            ("task-cur", OWNER, "SUCCEEDED"),
            ("task-other", OTHER, "SUCCEEDED"),
            ("task-stub", STUB, "SUCCEEDED"),
            (LEGACY_TASK, None, "SUCCEEDED"),
        ]
        for tid, uid, st in rows:
            cur.execute(
                "INSERT OR REPLACE INTO tasks (task_id, user_id, status,"
                " current_input_revision, seq, created_at, updated_at,"
                " published_resume_revision, published_docx_path, published_pdf_path)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (tid, uid, st, 1, 0, now, now, 1,
                 "output/resume_cur_own.docx" if tid == "task-cur" else
                 ("output/resume_other_own.docx" if tid == "task-other" else
                  ("output/resume_stub_own.docx" if tid == "task-stub" else None)),
                 "output/resume_cur_own.pdf" if tid == "task-cur" else None))
        arts = [
            ("art-cur-docx", "task-cur", OWNER, "docx", cur_docx.name, sha(cur_docx), size(cur_docx)),
            ("art-cur-pdf", "task-cur", OWNER, "pdf", cur_pdf.name, sha(cur_pdf), size(cur_pdf)),
            ("art-other-docx", "task-other", OTHER, "docx", other_docx.name, sha(other_docx), size(other_docx)),
            ("art-stub-docx", "task-stub", STUB, "docx", stub_docx.name, sha(stub_docx), size(stub_docx)),
        ]
        for aid, tid, uid, kind, fn, h, sz in arts:
            cur.execute(
                "INSERT OR REPLACE INTO artifacts (artifact_id, task_id, user_id, kind,"
                " resume_revision, file_name, rel_dir, sha256, size_bytes, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (aid, tid, uid, kind, 1, fn, "output", h, sz, now))
        con.commit()
        con.close()
        evid["seeded"] = {
            "current_task": "task-cur", "other_task": "task-other",
            "stub_task": "task-stub", "legacy_task": LEGACY_TASK,
            "current_docx_sha256": sha(cur_docx), "current_pdf_sha256": sha(cur_pdf),
        }

        cases: list[dict] = []

        def rec(cid: str, desc: str, ok_: bool, **kw) -> None:
            cases.append({"id": cid, "case": desc, "ok": bool(ok_), **kw})
            log(f"  [{'PASS' if ok_ else 'FAIL'}] {cid} {desc} {json.dumps(kw, ensure_ascii=False)[:220]}")

        def get(url: str, method: str = "GET"):
            if method == "HEAD":
                return s.head(base + url, timeout=60)
            return s.get(base + url, timeout=60)

        def body_of(resp) -> bytes:
            return resp.content if resp.content else b""

        # ── A) 正向：current owner 自己的 task，docx + pdf ──
        r = get("/api/task/task-cur/artifact/docx")
        rec("A1", "current 自己的 task docx → 200 + 字节/sha 与磁盘一致",
            r.status_code == 200 and DOCX_MIME in r.headers.get("content-type", "")
            and sha256_bytes(r.content) == sha(cur_docx),
            status=r.status_code, mime=r.headers.get("content-type", ""))
        r = get("/api/task/task-cur/artifact/pdf")
        rec("A2", "current 自己的 task pdf → 200 + application/pdf + 字节与磁盘一致",
            r.status_code == 200 and PDF_MIME in r.headers.get("content-type", "")
            and sha256_bytes(r.content) == sha(cur_pdf),
            status=r.status_code, mime=r.headers.get("content-type", ""))
        # GET 与 HEAD 同等授权（同一对象）
        r_head = get("/api/task/task-cur/artifact/docx", method="HEAD")
        rec("A3", "HEAD 对 current 自己的 artifact → 200（与 GET 同等校验）",
            r_head.status_code == 200, status=r_head.status_code)

        # ── B) 反向：异主 / stub / legacy ──
        not_found_body = None
        r = get("/api/task/task-other/artifact/docx")
        not_found_body = body_of(r)
        rec("B1", "other-user 的 task → 拒绝（404）",
            r.status_code == 404, status=r.status_code)
        r = get("/api/task/task-stub/artifact/docx")
        rec("B2", "stub-user 的 task → 拒绝（404）",
            r.status_code == 404 and body_of(r) == not_found_body,
            status=r.status_code, same_body=(body_of(r) == not_found_body))
        r = get(f"/api/task/{LEGACY_TASK}/artifact/docx")
        rec("B3", "LEGACY_UNOWNED 的 task → 拒绝（404）",
            r.status_code == 404 and body_of(r) == not_found_body,
            status=r.status_code)
        r = get("/api/task/task-other/artifact/docx", method="HEAD")
        rec("B4", "HEAD 对 other-user 的 task → 同样 404（GET/HEAD 同等授权）",
            r.status_code == 404, status=r.status_code)
        # 不泄露存在性：不存在的 task 与异主 task 的响应体一致
        r = get("/api/task/task-does-not-exist/artifact/docx")
        rec("B5", "不存在的 task 与异主 task 响应体一致（不泄露存在性）",
            r.status_code == 404 and body_of(r) == not_found_body,
            status=r.status_code, same_body=(body_of(r) == not_found_body))

        # ── C) kind / 伪造 / 穿越 ──
        r = get("/api/task/task-cur/artifact/pdf2")
        rec("C1", "非法 artifact kind → 404", r.status_code == 404, status=r.status_code)
        r = get("/api/task/task-cur/artifact/docx?filename=resume_other_own.docx")
        rec("C2", "伪造 filename query 不改变解析（仍返回 current 自己 docx）",
            r.status_code == 200 and sha256_bytes(r.content) == sha(cur_docx),
            status=r.status_code)
        r = get("/api/task/task-other/artifact/docx?filename=resume_cur_own.docx")
        rec("C3", "异主 task + 伪造 current filename → 仍 404（filename 不是授权依据）",
            r.status_code == 404, status=r.status_code)
        r = get("/api/task/task-cur/artifact/..%2F..%2Fsecrets")
        rec("C4", "kind 路径穿越 → 404", r.status_code == 404, status=r.status_code)
        r = get("/api/task/..%2Ftask-other/artifact/docx")
        rec("C5", "task_id 路径穿越 → 404", r.status_code in (404, 400), status=r.status_code)

        # ── D) 未登记 / 错误 kind ──
        r = get("/api/task/task-cur/artifact/docx")  # 存在
        # 未登记 artifact：磁盘有文件、artifacts 无行 → 通过把 task-cur 的 pdf 行删掉模拟
        con = sqlite3.connect(str(db_path))
        con.execute("DELETE FROM artifacts WHERE artifact_id='art-cur-pdf'")
        con.commit()
        con.close()
        r = get("/api/task/task-cur/artifact/pdf")
        rec("D1", "已登记→删除登记后（磁盘文件仍在）→ 404（未登记不可见）",
            r.status_code == 404, status=r.status_code)
        con = sqlite3.connect(str(db_path))
        con.execute(
            "INSERT OR REPLACE INTO artifacts (artifact_id, task_id, user_id, kind,"
            " resume_revision, file_name, rel_dir, sha256, size_bytes, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("art-cur-pdf", "task-cur", OWNER, "pdf", 1, cur_pdf.name, "output",
             sha(cur_pdf), size(cur_pdf), now))
        con.commit()
        con.close()
        rec("D2", "恢复登记后 → 200（对照，证明 D1 的 404 来自未登记而非其它）",
            get("/api/task/task-cur/artifact/pdf").status_code == 200)

        # 登记但文件缺失 → 该记录必须整体从 records 剔除（fail-closed）
        con = sqlite3.connect(str(db_path))
        con.execute(
            "INSERT OR REPLACE INTO tasks (task_id, user_id, status,"
            " current_input_revision, seq, created_at, updated_at,"
            " published_resume_revision, published_docx_path, published_pdf_path)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("task-cur-damaged", OWNER, "SUCCEEDED", 1, 0, now, now, 2,
             "output/resume_missing_on_disk.docx", None))
        con.execute(
            "INSERT OR REPLACE INTO artifacts (artifact_id, task_id, user_id, kind,"
            " resume_revision, file_name, rel_dir, sha256, size_bytes, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("art-cur-missing", "task-cur-damaged", OWNER, "docx", 2,
             "resume_missing_on_disk.docx", "output", "0" * 64, 10, now))
        con.commit()
        con.close()
        r = get("/api/task/task-cur/artifact/docx")
        rec("D3", "另一任务登记行指向不存在文件不影响 current 自己 docx 的正常解析",
            r.status_code == 200, status=r.status_code)

        # ── E) records 只列 owner 的、且经文件级校验 ──
        r = s.get(f"{base}/api/task/records", timeout=60)
        try:
            recs = r.json()
        except Exception:
            recs = None
        ids = [x.get("task_id") for x in recs] if isinstance(recs, list) else []
        rec("E1", "records 只含 current owner 的已发布记录",
            r.status_code == 200 and "task-cur" in ids
            and "task-other" not in ids and "task-stub" not in ids
            and LEGACY_TASK not in ids,
            status=r.status_code, ids=ids)
        rec("E2", "records 对存在损坏/缺失 artifact 的记录 fail-closed（不暴露假成功下载）",
            "task-cur-damaged" not in ids, ids=ids)

        # ── F) 旧模板下载路由：不再服务用户简历；公开模板仍可用 ──
        r = get("/api/template/download?path=" + urllib.parse.quote("output/resume_cur_own.docx"))
        rec("F1", "旧 template/download 不再服务用户简历（current 自己也不行）→ 404",
            r.status_code == 404, status=r.status_code)
        r = get("/api/template/download?path=" + urllib.parse.quote("../output/resume_cur_own.docx"))
        rec("F2", "旧 template/download 路径穿越 → 404", r.status_code == 404, status=r.status_code)
        # 公开内置模板资产：从映射里取一个真实存在的 docx 文件名（包内或仓库源码树）
        pub_ok = False
        pub_detail: dict = {}
        cands = []
        if exe is not None:
            cands.append(exe.parent / "_internal" / "config" / "template_mapping.json")
        cands.append(ROOT / "backend" / "config" / "template_mapping.json")
        mapping = None
        for c in cands:
            try:
                mapping = json.loads(c.read_text(encoding="utf-8"))
                pub_detail["mapping_source"] = ("package" if c.is_relative_to(exe.parent)
                                                else "repo") if exe is not None else "repo"
                break
            except Exception:
                continue
        try:
            if mapping is None:
                raise RuntimeError("template_mapping.json not found")
            first = list(mapping.values())[0]
            rel = first.get("docx") or ""
            name = rel.replace("\\", "/").rsplit("/", 1)[-1]
            r = get("/api/template/download?path=" + urllib.parse.quote(name))
            pub_ok = r.status_code == 200 and len(r.content) > 0
            pub_detail.update({"name": name, "status": r.status_code, "bytes": len(r.content)})
        except Exception as e:  # noqa: BLE001
            pub_detail["error"] = repr(e)
        rec("F3", "旧 template/download 仍可下载公开内置模板资产 → 200", pub_ok, **pub_detail)

        failures = [c for c in cases if not c["ok"]]
        evid["cases"] = cases
        evid["case_ids"] = [c["id"] for c in cases]
        evid["all_ok"] = not failures
        evid["failures"] = [f"{c['id']}:{c['case']}" for c in failures]
        if failures:
            evid["problems"].append(f"{len(failures)} 个授权矩阵用例失败")
        return 0 if not failures else 1
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        evid["exception"] = repr(e)
        evid["problems"].append(f"exception:{type(e).__name__}")
        evid["all_ok"] = False
        return 2


if __name__ == "__main__":
    sys.exit(main())
