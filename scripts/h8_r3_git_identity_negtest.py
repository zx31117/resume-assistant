"""V2.2.0 R3 §R3-15 §15.4-A-5：manifest Git 身份锚点 build/verify **正反向矩阵**受控自测。

独立验收判定旧 manifest 在错误 SRC/HANDOFF 下仍 rc 0 / `final_verdict=true`。本运行器在**一次性临时
Git repo**（不触碰正式历史）中，对 `scripts/h8_r3_manifest.py` 的 build 与 verify 逐例施加身份篡改，
断言每例都 **非零退出、`final_verdict=false`、`problems` 含可定位原因、不输出 PASS 摘要**；并保留一个
**正向对照**（正确身份 build+verify 必须通过）。

覆盖 §R3-15 §15.4-A-5 的 15 项身份负向用例（build 与 verify 双模式）：

  1 错误 SRC              2 错误 HANDOFF           3 SRC object 不存在
  4 HANDOFF object 不存在  5 blob/tree/tag 非 commit 6 HANDOFF parent 不是 SRC
  7 HANDOFF 多个 parent    8 SRC..HANDOFF 出现非 RESULT 文件
  9 tree SHA 被篡改        10 manifest parent/diff 被篡改
 11 缺少 --repo            12 repo 无效/非 Git repo
 13 build 时 repo HEAD 不等于 HANDOFF            14 build 时 tracked/index dirty
 15 verify 时传入错误 expected SRC/HANDOFF

用法：
  python scripts/h8_r3_git_identity_negtest.py --out <evidence.json>
退出码：0 = 正向对照通过且 15 例全部 fail-closed；1 = 存在逃逸；2 = 环境错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_MANIFEST = _THIS_DIR / "h8_r3_manifest.py"

_RESULT = "docs/versions/v2.2.0/RESULT.md"
_SRC_FILE = "backend/src.py"
_BUNDLE = "index-FAKE1234.js"
_EXE_BYTES = b"RESUME-ASSISTANT-FAKE-EXE-FIXTURE-0123456789"


# ───────────────────────────── 工具 ───────────────────────────── #

def _sh(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)


def _git(repo: Path, *args: str) -> str:
    p = _sh(["git", "-C", str(repo), *args])
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout.strip()


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _parse_payload(stdout: str) -> dict | None:
    for line in reversed(stdout.splitlines()):
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                continue
    return None


def _run(mode: str, argv: list[str]) -> dict:
    p = _sh([sys.executable, str(_MANIFEST), mode, *argv])
    payload = _parse_payload(p.stdout)
    return {"rc": p.returncode, "stdout": p.stdout, "stderr": p.stderr, "payload": payload}


# ───────────────────────────── 夹具 ───────────────────────────── #

def _init_repo(root: Path, name: str = "repo") -> Path:
    repo = root / name
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "config", "user.name", "Fixture")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def _commit_all(repo: Path, msg: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def _make_package(root: Path) -> tuple[Path, str]:
    pkg = root / "pkg" / "ResumeAssistant"
    exe = pkg / "ResumeAssistant.exe"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_bytes(_EXE_BYTES)
    asset = pkg / "_internal" / "frontend" / "dist" / "assets" / _BUNDLE
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_text("// fixture bundle\n", encoding="utf-8")
    return pkg, _sha256(_EXE_BYTES)


def _make_evidence(root: Path, exe_sha: str) -> Path:
    ev = root / "ev"
    ev.mkdir(parents=True, exist_ok=True)
    _write(ev / "package_audit.json", json.dumps(
        {"dir": "pkg", "files": 2, "pass": True, "exe_sha256": exe_sha}))
    _write(ev / "pyz_check.json", json.dumps(
        {"all_ok": True, "exe": {"sha256": exe_sha}}))
    _write(ev / "failure_matrix.json", json.dumps(
        {"final_pass": True, "exe_sha256": exe_sha, "cleanup_gate_ok": True}))
    _write(ev / "content_real_model.json", json.dumps(
        {"ok": True, "exe": {"sha256": exe_sha}, "runtime_deleted": True}))
    _write(ev / "real_model_e2e.json", json.dumps(
        {"ok": True, "exe": {"sha256": exe_sha}, "runtime_deleted": True,
         "cleanup": {"winword_leaked": []}}))
    _write(ev / "design_fidelity.json", json.dumps(
        {"exe_sha256": exe_sha, "summary": {"pass": 1, "fail": 0},
         "cleanup": {"runtime_removed": True}}))
    _write(ev / "six_grid_aggregate.json", json.dumps(
        {"pass": True, "exe": {"sha256": exe_sha}, "n_samples": 18,
         "first_fact_median_s": 1.0, "first_fact_max_s": 2.0}))
    cases = [{"case": c, "fail_closed": True, "exit_code": 1, "fail_messages": ["injected"]}
             for c in ("missing_sample", "dup_sample", "missing_grid", "embedding_2",
                       "false_check", "truncated_evidence", "cleanup_failed")]
    _write(ev / "six_grid_negative_selftest.json", json.dumps(
        {"cases": cases, "all_fail_closed": True, "all_exit_codes_nonzero": True,
         "nonzero_exit_failures": []}))
    # 身份矩阵证据（夹具内为占位；真实运行由本运行器产出后放入证据目录）。
    idm_cases = [{"id": i, "case": f"fixture_case_{i}", "mode": "build", "exit_code": 1,
                  "pass_emitted": False, "verdict_false": True, "problems_nonempty": True,
                  "problems": ["fixture"], "ok": True} for i in range(1, 16)]
    _write(ev / "git_identity_matrix.json", json.dumps(
        {"_meta": {"generator": "fixture"},
         "positive_control": {"ok": True},
         "cases": idm_cases,
         "case_ids": list(range(1, 16)),
         "all_ok": True, "failures": []}))
    _write(ev / "gates_run.json", json.dumps({
        "_meta": {"generator": "fixture"},
        "gates": [{"gate": "precheck", "command": "true", "exit_code": 0,
                   "runtime_s": 0, "evidence": "precheck.log", "evidence_sha256": None}],
        "all_exit_zero": True,
        "cleanup": {"content_runtime_deleted": True, "e2e_runtime_deleted": True,
                    "fidelity_runtime_removed": True,
                    "failure_matrix_cleanup_gate_ok": True, "winword_leaked": []},
        "verdicts": {"ok": True},
        "final_verdict": True,
    }))
    return ev


def _fixture(root: Path) -> dict:
    """标准夹具：BASE → SRC → HANDOFF（SRC..HANDOFF 只改 RESULT）。"""
    repo = _init_repo(root)
    _write(repo / _RESULT, "# RESULT\ninitial\n")
    _write(repo / _SRC_FILE, "x = 1\n")
    base = _commit_all(repo, "BASE")
    _write(repo / _SRC_FILE, "x = 2\n")
    src = _commit_all(repo, "SRC")
    _write(repo / _RESULT, "# RESULT\nfinal\n")
    handoff = _commit_all(repo, "HANDOFF")
    pkg, exe_sha = _make_package(root)
    ev = _make_evidence(root, exe_sha)
    outdir = root / "out"
    outdir.mkdir(exist_ok=True)
    return {"root": root, "repo": repo, "base": base, "src": src, "handoff": handoff,
            "pkg": pkg, "exe_sha": exe_sha, "ev": ev, "outdir": outdir}


def _build_argv(fx: dict, *, repo=None, src=None, handoff=None, out=None) -> list[str]:
    return [
        "--repo", str(repo if repo is not None else fx["repo"]),
        "--expected-src", src if src is not None else fx["src"],
        "--expected-handoff", handoff if handoff is not None else fx["handoff"],
        "--exe-sha", fx["exe_sha"],
        "--bundle", _BUNDLE,
        "--package-dir", str(fx["pkg"]),
        "--evidence-dir", str(fx["ev"]),
        "--gates-meta", str(fx["ev"] / "gates_run.json"),
        "--out", str(out if out is not None else (fx["outdir"] / "manifest.json")),
    ]


def _verify_argv(fx: dict, *, repo=None, src=None, handoff=None, out=None,
                 evidence=None) -> list[str]:
    argv = [
        "--out", str(out if out is not None else (fx["outdir"] / "manifest.json")),
        "--repo", str(repo if repo is not None else fx["repo"]),
        "--expected-src", src if src is not None else fx["src"],
        "--expected-handoff", handoff if handoff is not None else fx["handoff"],
    ]
    ev = evidence if evidence is not None else fx["ev"]
    if ev is not None:
        argv += ["--evidence-dir", str(ev)]
    return argv


# ───────────────────────────── 用例判定 ───────────────────────────── #

def _record(case_id: int, name: str, mode: str, run: dict, notes: str = "") -> dict:
    rc = run["rc"]
    payload = run["payload"] or {}
    problems = payload.get("problems") or []
    if not problems:
        blob = (run["stdout"] or "") + (run["stderr"] or "")
        problems = [ln.strip()[2:].strip() for ln in blob.splitlines()
                    if ln.strip().startswith("- ")] or \
                   ([blob.strip()[:200]] if blob.strip() else [])
    pass_emitted = (rc == 0)
    # build 必须写出 final_verdict=false；verify 以非零退出表达失败判定。
    verdict_false = (payload.get("final_verdict") is False) if mode == "build" else (rc != 0)
    ok = (not pass_emitted) and rc != 0 and bool(problems) and verdict_false
    return {
        "id": case_id, "case": name, "mode": mode, "exit_code": rc,
        "pass_emitted": pass_emitted, "verdict_false": bool(verdict_false),
        "problems_nonempty": bool(problems),
        "problems": problems[:6],
        "notes": notes,
        "ok": bool(ok),
    }


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_matrix(root: Path) -> dict:
    fx = _fixture(root)
    outdir = fx["outdir"]
    cases: list[dict] = []

    # 正向对照：正确身份 build + verify 必须通过。
    pos_manifest = outdir / "positive_manifest.json"
    b = _run("build", _build_argv(fx, out=pos_manifest))
    pos_build_ok = (b["rc"] == 0 and (b["payload"] or {}).get("final_verdict") is True)
    v = _run("verify", _verify_argv(fx, out=pos_manifest))
    pos_verify_ok = (v["rc"] == 0 and (v["payload"] or {}).get("final_verdict") is True)
    positive = {"build_rc": b["rc"], "build_final_verdict": (b["payload"] or {}).get("final_verdict"),
                "verify_rc": v["rc"], "verify_final_verdict": (v["payload"] or {}).get("final_verdict"),
                "ok": bool(pos_build_ok and pos_verify_ok)}
    if not positive["ok"]:
        return {"_meta": {"generator": "scripts/h8_r3_git_identity_negtest.py"},
                "positive_control": positive, "cases": [], "all_ok": False,
                "failures": ["positive_control_failed"],
                "positive_stdout": b["stdout"][-800:] + "\n" + v["stdout"][-800:]}

    # ---------- build 侧 ---------- #
    # 1 错误 SRC（完整 SHA 但为真实错误 commit = BASE）
    cases.append(_record(1, "wrong_src", "build",
                         _run("build", _build_argv(fx, src=fx["base"],
                                                   out=outdir / "c1.json"))))
    # 2 错误 HANDOFF（= SRC）
    cases.append(_record(2, "wrong_handoff", "build",
                         _run("build", _build_argv(fx, handoff=fx["src"],
                                                   out=outdir / "c2.json"))))
    # 3 SRC object 不存在
    cases.append(_record(3, "src_object_missing", "build",
                         _run("build", _build_argv(fx, src="0" * 40,
                                                   out=outdir / "c3.json"))))
    # 4 HANDOFF object 不存在
    cases.append(_record(4, "handoff_object_missing", "build",
                         _run("build", _build_argv(fx, handoff="1" * 40,
                                                   out=outdir / "c4.json"))))
    # 5 非 commit object（blob / tree / tag）
    blob = _git(fx["repo"], "rev-parse", f"HEAD:{_SRC_FILE}")
    tree = _git(fx["repo"], "rev-parse", "HEAD^{tree}")
    _git(fx["repo"], "tag", "-a", "fixturetag", "-m", "fixture", fx["handoff"])
    tag = _git(fx["repo"], "rev-parse", "refs/tags/fixturetag")
    for label, obj in (("blob", blob), ("tree", tree), ("tag", tag)):
        cases.append(_record(5, f"non_commit_object_{label}", "build",
                             _run("build", _build_argv(fx, handoff=obj,
                                                       out=outdir / f"c5_{label}.json"))))

    # 6 HANDOFF parent 不是 SRC：另一 repo，HANDOFF2 的 parent = BASE
    r6 = _init_repo(root, "repo_wrongparent")
    _write(r6 / _RESULT, "# RESULT\ninitial\n")
    _write(r6 / _SRC_FILE, "x = 1\n")
    base6 = _commit_all(r6, "BASE")
    _write(r6 / _SRC_FILE, "x = 2\n")
    src6 = _commit_all(r6, "SRC")
    _git(r6, "checkout", "-q", base6)
    _write(r6 / _RESULT, "# RESULT\nfinal\n")
    handoff6 = _commit_all(r6, "HANDOFF2-on-BASE")
    cases.append(_record(6, "handoff_parent_not_src", "build",
                         _run("build", _build_argv(fx, repo=r6, src=src6, handoff=handoff6,
                                                   out=outdir / "c6.json")),
                         notes="expected-src=SRC6, expected-handoff parent=BASE6"))

    # 7 HANDOFF 多 parent：merge commit
    r7 = _init_repo(root, "repo_merge")
    _write(r7 / _RESULT, "# RESULT\ninitial\n")
    _write(r7 / _SRC_FILE, "x = 1\n")
    _commit_all(r7, "BASE")
    _write(r7 / _SRC_FILE, "x = 2\n")
    src7 = _commit_all(r7, "SRC")
    _git(r7, "checkout", "-q", "-b", "side")
    _write(r7 / "backend/side.py", "y = 1\n")
    _commit_all(r7, "SIDE")
    _git(r7, "checkout", "-q", "main")
    _write(r7 / _RESULT, "# RESULT\nmain2\n")
    main2 = _commit_all(r7, "MAIN2")
    _git(r7, "merge", "-q", "--no-ff", "-m", "MERGE", "side")
    merge = _git(r7, "rev-parse", "HEAD")
    cases.append(_record(7, "handoff_multi_parent", "build",
                         _run("build", _build_argv(fx, repo=r7, src=main2, handoff=merge,
                                                   out=outdir / "c7.json"))))

    # 8 SRC..HANDOFF 出现 RESULT 以外文件
    r8 = _init_repo(root, "repo_extraf")
    _write(r8 / _RESULT, "# RESULT\ninitial\n")
    _write(r8 / _SRC_FILE, "x = 1\n")
    _commit_all(r8, "BASE")
    _write(r8 / _SRC_FILE, "x = 2\n")
    src8 = _commit_all(r8, "SRC")
    _write(r8 / _RESULT, "# RESULT\nfinal\n")
    _write(r8 / "backend/extra.py", "z = 9\n")
    handoff8 = _commit_all(r8, "HANDOFF-extra")
    cases.append(_record(8, "src_to_handoff_extra_file", "build",
                         _run("build", _build_argv(fx, repo=r8, src=src8, handoff=handoff8,
                                                   out=outdir / "c8.json"))))

    # 11 缺少 --repo
    cases.append(_record(11, "missing_repo", "build",
                         _run("build", [
                             "--expected-src", fx["src"], "--expected-handoff", fx["handoff"],
                             "--exe-sha", fx["exe_sha"], "--bundle", _BUNDLE,
                             "--package-dir", str(fx["pkg"]), "--evidence-dir", str(fx["ev"]),
                             "--gates-meta", str(fx["ev"] / "gates_run.json"),
                             "--out", str(outdir / "c11.json")])))

    # 12 repo 无效 / 非 Git repo
    notgit = root / "not_a_repo"
    notgit.mkdir(exist_ok=True)
    cases.append(_record(12, "invalid_repo", "build",
                         _run("build", _build_argv(fx, repo=notgit, out=outdir / "c12.json"))))

    # 13 build 时 repo HEAD 不等于 HANDOFF
    r13 = _init_repo(root, "repo_head_ne")
    _write(r13 / _RESULT, "# RESULT\ninitial\n")
    _write(r13 / _SRC_FILE, "x = 1\n")
    _commit_all(r13, "BASE")
    _write(r13 / _SRC_FILE, "x = 2\n")
    src13 = _commit_all(r13, "SRC")
    _write(r13 / _RESULT, "# RESULT\nfinal\n")
    handoff13 = _commit_all(r13, "HANDOFF")
    _git(r13, "checkout", "-q", src13)          # HEAD 回退到 SRC(≠HANDOFF)
    cases.append(_record(13, "head_not_equal_handoff", "build",
                         _run("build", _build_argv(fx, repo=r13, src=src13, handoff=handoff13,
                                                   out=outdir / "c13.json"))))

    # 14 build 时 tracked/index dirty
    r14 = _init_repo(root, "repo_dirty")
    _write(r14 / _RESULT, "# RESULT\ninitial\n")
    _write(r14 / _SRC_FILE, "x = 1\n")
    _commit_all(r14, "BASE")
    _write(r14 / _SRC_FILE, "x = 2\n")
    src14 = _commit_all(r14, "SRC")
    _write(r14 / _RESULT, "# RESULT\nfinal\n")
    handoff14 = _commit_all(r14, "HANDOFF")
    _write(r14 / _RESULT, "# RESULT\nfinal\nUNCOMMITTED-DIRTY\n")   # 污染 tracked 文件
    cases.append(_record(14, "tracked_index_dirty", "build",
                         _run("build", _build_argv(fx, repo=r14, src=src14, handoff=handoff14,
                                                   out=outdir / "c14.json"))))

    # ---------- verify 侧 ---------- #
    valid = pos_manifest

    # 1v/2v/3v/4v/5v/15v：错误 / 缺失 / 非 commit / 错误 expected
    cases.append(_record(1, "wrong_src", "verify",
                         _run("verify", _verify_argv(fx, out=valid, src=fx["base"]))))
    cases.append(_record(2, "wrong_handoff", "verify",
                         _run("verify", _verify_argv(fx, out=valid, handoff=fx["base"]))))
    cases.append(_record(3, "src_object_missing", "verify",
                         _run("verify", _verify_argv(fx, out=valid, src="0" * 40))))
    cases.append(_record(4, "handoff_object_missing", "verify",
                         _run("verify", _verify_argv(fx, out=valid, handoff="1" * 40))))
    cases.append(_record(5, "non_commit_object_blob", "verify",
                         _run("verify", _verify_argv(fx, out=valid, handoff=blob))))
    cases.append(_record(15, "verify_wrong_expected", "verify",
                         _run("verify", _verify_argv(fx, out=valid, handoff=fx["src"]))))

    # 9 tree SHA 被篡改
    m9 = _load_manifest(valid)
    m9["git_identity"]["actual"]["src"]["tree"] = "f" * 40
    p9 = outdir / "c9_tamper_tree.json"
    p9.write_text(json.dumps(m9, ensure_ascii=False, indent=2), encoding="utf-8")
    cases.append(_record(9, "tree_sha_tampered", "verify",
                         _run("verify", _verify_argv(fx, out=p9))))

    # 10 manifest parent / diff 被篡改
    m10a = _load_manifest(valid)
    m10a["git_identity"]["actual"]["handoff"]["parents"] = [fx["base"]]
    p10a = outdir / "c10a_tamper_parent.json"
    p10a.write_text(json.dumps(m10a, ensure_ascii=False, indent=2), encoding="utf-8")
    cases.append(_record(10, "manifest_parent_tampered", "verify",
                         _run("verify", _verify_argv(fx, out=p10a))))

    m10b = _load_manifest(valid)
    m10b["git_identity"]["actual"]["src_to_handoff_name_status"] = [
        {"status": "M", "path": _RESULT}, {"status": "A", "path": "backend/hidden.py"}]
    p10b = outdir / "c10b_tamper_diff.json"
    p10b.write_text(json.dumps(m10b, ensure_ascii=False, indent=2), encoding="utf-8")
    cases.append(_record(10, "manifest_diff_tampered", "verify",
                         _run("verify", _verify_argv(fx, out=p10b))))

    # 11v 缺少 --repo
    cases.append(_record(11, "missing_repo", "verify",
                         _run("verify", ["--out", str(valid),
                                         "--expected-src", fx["src"],
                                         "--expected-handoff", fx["handoff"]])))

    # 12v repo 无效
    cases.append(_record(12, "invalid_repo", "verify",
                         _run("verify", _verify_argv(fx, out=valid, repo=notgit))))

    failures = [f"{c['id']}:{c['case']}:{c['mode']}" for c in cases if not c["ok"]]
    return {
        "_meta": {
            "generator": "scripts/h8_r3_git_identity_negtest.py",
            "plan_blob": "7d8a249a5ec3e607855f20d794bb7ed9cda351ee",
            "manifest": "scripts/h8_r3_manifest.py",
            "note": "在一次性临时 Git repo 中独立覆盖 build/verify 双模式；不触碰正式历史。",
        },
        "positive_control": positive,
        "cases": cases,
        "case_ids": sorted({c["id"] for c in cases}),
        "all_ok": (not failures),
        "failures": failures,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    if not _MANIFEST.is_file():
        print(f"NEGTEST_FATAL manifest_missing: {_MANIFEST}")
        return 2

    root = Path(tempfile.mkdtemp(prefix="h8_gitid_neg_"))
    try:
        result = run_matrix(root)
    except Exception as e:  # noqa: BLE001
        print(f"NEGTEST_FATAL fixture_error: {e}")
        return 2
    finally:
        if not args.keep:
            shutil.rmtree(root, ignore_errors=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    for c in result["cases"]:
        print(f"[gitid-neg] #{c['id']:<2} {c['case']:<32} {c['mode']:<6} "
              f"rc={c['exit_code']} verdict_false={c['verdict_false']} ok={c['ok']}")
    print(json.dumps({"positive_ok": result["positive_control"]["ok"],
                      "cases": len(result["cases"]), "all_ok": result["all_ok"],
                      "failures": result["failures"]}, ensure_ascii=False))
    return 0 if result["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
