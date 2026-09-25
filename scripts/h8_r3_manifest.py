"""V2.2.0 R3 §R3-15 返工：总证据 manifest 生成器 / 一致性校验（Git 身份锚点版）。

背景：§R3-15 独立验收判定旧实现 `ACCEPTANCE_FAIL`——build 只把 `--src/--handoff` 原样写入 JSON，
verify 只检查字段非空，未与真实 Git object、父链、tree 和 diff 比较，导致传入错误 SRC/HANDOFF 时
仍 rc 0、`final_verdict=true`。本版按 §R3-15 §15.4-A 建立**可独立校验的 Git 身份锚点**。

设计要求（PLAN §7、工作流 §3.2/§8.3/§8.4、RESULT §R3-15 §15.4-A）：

- build 立即从**明确 Git repo 的现场**解析并独立校验：
  `git rev-parse HEAD`、HEAD 完整 parent 列表、HEAD^、SRC/HANDOFF 的 object type、各自 tree SHA、
  `SRC..HANDOFF` 的 name-status/diff 文件集合、tracked/index clean 状态；
  实际 HEAD 必须精确等于 `--expected-handoff`；HANDOFF 必须是 commit、只有一个 parent 且等于
  `--expected-src`；SRC 必须是 commit；`SRC..HANDOFF` 只允许修改 RESULT 收口文件；调用参数、
  现场解析值与写入 manifest 的值三者完全一致。
- verify 接收来自验收任务的**可信** `--repo/--expected-src/--expected-handoff`，并同时校验：
  manifest 记录值 == 期望值；期望对象在指定 repo 中真实存在且均为 commit；HANDOFF 唯一 parent
  为 SRC；tree SHA 与现场 object 一致；`SRC..HANDOFF` 仅为 RESULT；manifest 记录的 diff 与现场
  一致；PLAN blob、包身份、Gate hash、负向自测仍成立。verify **不要求**当前 repo HEAD 等于
  HANDOFF（文档 Agent 会在 HANDOFF 之上形成 docs-only Acceptance 对象）。
- 任一 Git 命令失败、对象缺失、解析异常或身份不一致：写入明确 `problems`、`final_verdict=false`、
  非零退出，且**不输出可被误认为 PASS 的摘要**。

用法：
  python h8_r3_manifest.py build --repo <git-repo> --expected-src <SRC_SHA> --expected-handoff <HANDOFF_SHA> \\
      --exe-sha <EXE_SHA256> --bundle <bundle.js> \\
      --package-dir <dist/ResumeAssistant> --evidence-dir <path> \\
      [--gates-meta <gates_run.json>] --out <manifest.json>
  python h8_r3_manifest.py verify --out <manifest.json> --repo <git-repo> \\
      --expected-src <SRC_SHA> --expected-handoff <HANDOFF_SHA> [--evidence-dir <path>]

退出码 0 = 生成/校验通过；非 0 = 身份或证据不一致。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PLAN_BLOB = "7d8a249a5ec3e607855f20d794bb7ed9cda351ee"
# HANDOFF 相对 SRC 只允许修改的唯一收口文件。
RESULT_PATH = "docs/versions/v2.2.0/RESULT.md"
IDENTITY_SCHEMA = "resume-assistant/git-identity"
IDENTITY_VERSION = 1

_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# 参与绑定的 Gate 证据文件名（相对 evidence-dir）。
_GATE_EVIDENCE_FILES = [
    "package_audit.json",
    "pyz_check.json",
    "failure_matrix.json",
    "content_real_model.json",
    "real_model_e2e.json",
    "design_fidelity.json",
    "six_grid_aggregate.json",
]

# Git 身份 build/verify 正反向矩阵证据（不绑定 EXE，但纳入最终判定）。
_IDENTITY_MATRIX_FILE = "git_identity_matrix.json"
_IDENTITY_MATRIX_MIN_CASES = 15

# 各证据里应含的最终 EXE SHA-256 的 jsonpath（点分）。
_EXE_SHA_PATH = {
    "package_audit.json": "exe_sha256",
    "pyz_check.json": "exe",              # dict → .get("sha256")；str 可为 64-hex 或指向 EXE 的路径
    "failure_matrix.json": "exe_sha256",
    "content_real_model.json": "exe.sha256",
    "real_model_e2e.json": "exe.sha256",
    "design_fidelity.json": "exe_sha256",
    "six_grid_aggregate.json": "exe.sha256",
}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_by_path(obj, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


# ─────────────────────────── Git 现场解析 ─────────────────────────── #

def _git(repo, *args: str) -> tuple[int, str, str]:
    """在 repo 上运行 git 子命令，返回 (rc, stdout, stderr)。任何异常都折叠为非零 rc。"""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=120,
        )
    except Exception as e:  # noqa: BLE001
        return 1, "", f"git-spawn-error:{e}"
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _is_git_repo(repo) -> bool:
    rc, out, _ = _git(repo, "rev-parse", "--is-inside-work-tree")
    return rc == 0 and out.strip() == "true"


def _commit_identity(repo, ref: str) -> tuple[dict | None, str | None]:
    """把 ref 解析为不可混淆的 commit 身份。

    返回 ({sha,type,tree,parents}, None) 或 (None/l部分, error)。非 commit object、缺失、
    解析异常都返回 error（调用方据此 fail-closed）。
    """
    if not ref:
        return None, "空对象引用"
    rc, typ, _ = _git(repo, "cat-file", "-t", ref)
    if rc != 0:
        return None, f"Git object 不存在或不可读: {ref}"
    typ = typ.strip()
    if typ != "commit":
        return {"sha": ref, "type": typ, "tree": None, "parents": None}, \
            f"Git object 类型非 commit: {ref} -> {typ}"
    rc, tree, _ = _git(repo, "rev-parse", f"{ref}^{{tree}}")
    if rc != 0 or not tree:
        return {"sha": ref, "type": typ, "tree": None, "parents": None}, \
            f"无法解析 commit tree SHA: {ref}"
    rc, parents_out, err = _git(repo, "rev-list", "--parents", "-n", "1", ref)
    if rc != 0 or not parents_out:
        return {"sha": ref, "type": typ, "tree": tree, "parents": None}, \
            f"无法解析 commit parent 列表: {ref} ({err})"
    parts = parents_out.split()
    return {"sha": parts[0], "type": "commit", "tree": tree, "parents": parts[1:]}, None


def _name_status(repo, src: str, handoff: str) -> tuple[list[dict] | None, str | None]:
    rc, out, err = _git(repo, "diff", "--name-status", src, handoff)
    if rc != 0:
        return None, f"无法解析 SRC..HANDOFF diff: {src}..{handoff} ({err})"
    rows: list[dict] = []
    for line in out.splitlines():
        line = line.rstrip("\n")
        if not line.strip():
            continue
        cols = line.split("\t")
        status = cols[0]
        if status.startswith("R") or status.startswith("C"):
            rows.append({"status": status, "path": cols[2] if len(cols) > 2 else cols[-1],
                         "from": cols[1] if len(cols) > 1 else None})
        else:
            rows.append({"status": status, "path": cols[-1]})
    return rows, None


def _tracked_index_clean(repo) -> tuple[bool | None, str | None]:
    """仅看 tracked/index（忽略 untracked），空输出即 clean。"""
    rc, out, err = _git(repo, "status", "--porcelain", "--untracked-files=no")
    if rc != 0:
        return None, f"无法读取 tracked/index 状态: {err}"
    return (out.strip() == ""), None


def _resolve_git_identity(repo, expected_src: str, expected_handoff: str) -> dict:
    """从 repo 现场解析身份并与期望值机械比对。返回完整 git_identity 段（含 checks/verdict）。"""
    checks: dict[str, bool] = {}
    problems: list[str] = []
    actual: dict = {
        "repo_head": None,
        "head_parents": None,
        "head_first_parent": None,
        "src": None,
        "handoff": None,
        "src_to_handoff_name_status": None,
        "src_to_handoff_paths": None,
    }
    expected = {"src": expected_src or None, "handoff": expected_handoff or None}

    checks["repo_provided"] = bool(repo)
    if not repo:
        problems.append("缺少 --repo，无法从 Git 现场解析身份")
        checks.update({
            "repo_is_git": False, "head_equals_expected_handoff": False,
            "handoff_is_commit": False, "handoff_single_parent": False,
            "handoff_parent_equals_src": False, "src_is_commit": False,
            "src_to_handoff_only_result": False, "tracked_index_clean": False,
        })
        return {"schema": IDENTITY_SCHEMA, "version": IDENTITY_VERSION,
                "repo": None, "expected": expected, "actual": actual,
                "checks": checks, "verdict": False, "problems": problems}

    checks["repo_is_git"] = _is_git_repo(repo)
    if not checks["repo_is_git"]:
        problems.append(f"路径不是有效 Git repo: {Path(str(repo)).name}")
        checks.update({
            "head_equals_expected_handoff": False, "handoff_is_commit": False,
            "handoff_single_parent": False, "handoff_parent_equals_src": False,
            "src_is_commit": False, "src_to_handoff_only_result": False,
            "tracked_index_clean": False,
        })
        return {"schema": IDENTITY_SCHEMA, "version": IDENTITY_VERSION,
                "repo": Path(str(repo)).name, "expected": expected, "actual": actual,
                "checks": checks, "verdict": False, "problems": problems}

    checks["expected_full_sha"] = bool(
        expected_src and _FULL_SHA_RE.match(expected_src)
        and expected_handoff and _FULL_SHA_RE.match(expected_handoff))
    if not checks["expected_full_sha"]:
        problems.append("--expected-src/--expected-handoff 必须是完整 40 位小写 SHA")

    # HEAD 与 HEAD 完整 parent 列表。
    rc, head, err = _git(repo, "rev-parse", "HEAD")
    actual["repo_head"] = head if rc == 0 and head else None
    if rc != 0 or not head:
        problems.append(f"无法解析 git rev-parse HEAD: {err}")

    rc, head_parents_out, err = _git(repo, "rev-list", "--parents", "-n", "1", "HEAD")
    if rc == 0 and head_parents_out:
        hp = head_parents_out.split()
        actual["head_parents"] = hp[1:]
        actual["head_first_parent"] = hp[1] if len(hp) > 1 else None
    else:
        problems.append(f"无法解析 HEAD parent 列表: {err}")

    src_id, src_err = _commit_identity(repo, expected_src)
    actual["src"] = src_id
    if src_err:
        problems.append(src_err)

    handoff_id, handoff_err = _commit_identity(repo, expected_handoff)
    actual["handoff"] = handoff_id
    if handoff_err:
        problems.append(handoff_err)

    # SRC..HANDOFF diff 作用域（两边都已是可用 commit 时）。
    ns = None
    if src_id and src_id.get("type") == "commit" and handoff_id and handoff_id.get("type") == "commit":
        ns, ns_err = _name_status(repo, expected_src, expected_handoff)
        if ns_err:
            problems.append(ns_err)
    actual["src_to_handoff_name_status"] = ns
    actual["src_to_handoff_paths"] = sorted(r["path"] for r in ns) if ns is not None else None

    clean, clean_err = _tracked_index_clean(repo)
    if clean_err:
        problems.append(clean_err)

    checks["head_equals_expected_handoff"] = bool(
        actual["repo_head"] and expected_handoff and actual["repo_head"] == expected_handoff)
    if not checks["head_equals_expected_handoff"]:
        problems.append("现场 HEAD 不等于 --expected-handoff")

    checks["handoff_is_commit"] = bool(handoff_id and handoff_id.get("type") == "commit")
    if not checks["handoff_is_commit"]:
        problems.append("HANDOFF 不是 commit object")

    checks["handoff_single_parent"] = bool(
        handoff_id and handoff_id.get("type") == "commit"
        and handoff_id.get("parents") is not None and len(handoff_id["parents"]) == 1)
    if not checks["handoff_single_parent"]:
        problems.append("HANDOFF 不是单 parent commit")

    checks["handoff_parent_equals_src"] = bool(
        checks["handoff_single_parent"] and expected_src
        and handoff_id["parents"][0] == expected_src)
    if not checks["handoff_parent_equals_src"]:
        problems.append("HANDOFF 唯一 parent 不等于 --expected-src")

    checks["src_is_commit"] = bool(src_id and src_id.get("type") == "commit")
    if not checks["src_is_commit"]:
        problems.append("SRC 不是 commit object")

    checks["args_match_live"] = bool(
        actual["src"] and actual["src"].get("sha") == expected_src
        and actual["handoff"] and actual["handoff"].get("sha") == expected_handoff)
    if not checks["args_match_live"]:
        problems.append("调用参数与现场解析值不一致")

    checks["src_to_handoff_only_result"] = bool(
        ns is not None and len(ns) >= 1
        and all(r["path"] == RESULT_PATH for r in ns))
    if not checks["src_to_handoff_only_result"]:
        bad = [r["path"] for r in (ns or []) if r["path"] != RESULT_PATH]
        problems.append(f"SRC..HANDOFF 出现 RESULT 以外文件: {bad if bad else '（diff 不可用或为空）'}")

    checks["tracked_index_clean"] = bool(clean)
    if not checks["tracked_index_clean"]:
        problems.append("tracked/index 工作树不 clean")

    verdict = all(checks.values())
    return {"schema": IDENTITY_SCHEMA, "version": IDENTITY_VERSION,
            "repo": Path(str(repo)).name, "expected": expected, "actual": actual,
            "checks": checks, "verdict": verdict, "problems": problems}


# ─────────────────────────── 包 / 证据 ─────────────────────────── #

def _evidence_exe_sha(ev_dir: Path, fname: str, path: str | None):
    p = ev_dir / fname
    if not p.exists():
        return None, f"missing:{fname}"
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        return None, f"unreadable:{fname}:{e}"
    if path:
        val = _get_by_path(data, path)
        if isinstance(val, dict):
            val = val.get("sha256")
        if isinstance(val, str):
            val = val.lower()
            if not re.fullmatch(r"[0-9a-f]{64}", val):
                fp = Path(val)
                if fp.is_file():
                    try:
                        return sha256_file(fp), None
                    except Exception as e:  # noqa: BLE001
                        return None, f"hash-failed:{fname}:{e}"
                return None, f"exe-path-missing:{fname}:{val}"
        return (val if isinstance(val, str) else val), None
    return None, f"no-sha-path:{fname}"


def _package_identity(pkg_dir: Path) -> dict:
    exe = pkg_dir / "ResumeAssistant.exe"
    files = [p for p in pkg_dir.rglob("*") if p.is_file()]
    total_bytes = sum(p.stat().st_size for p in files)
    exe_sha = sha256_file(exe) if exe.is_file() else None
    assets = sorted(pkg_dir.glob("_internal/frontend/dist/assets/index-*.js"))
    # 脱敏：绝不在证据中写入本机绝对路径；绝对入参折叠为末段目录名。
    rel = pkg_dir.name if pkg_dir.is_absolute() else str(pkg_dir)
    exe_rel = f"{rel}/ResumeAssistant.exe"
    return {
        "path": rel,
        "files": len(files),
        "total_bytes": total_bytes,
        "exe_path": exe_rel,
        "exe_bytes": exe.stat().st_size if exe.is_file() else 0,
        "exe_sha256": exe_sha,
        "bundle": assets[0].name if assets else None,
    }


def _negative_selftest(ev_dir: Path) -> tuple[dict, list[str]]:
    """负向自测必须满足：>=7 类注入、每类 `fail_closed=true`、且每类**非零退出码**（门禁语义）。"""
    problems: list[str] = []
    p = ev_dir / "six_grid_negative_selftest.json"
    if not p.exists():
        return {"present": False}, ["缺负向自测证据: six_grid_negative_selftest.json"]
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        return {"present": True, "ok": False}, [f"负向自测证据不可读: {e}"]
    cases = data.get("cases") or []
    all_fc = bool(cases) and all(c.get("fail_closed") is True for c in cases)
    bad_exit = [c.get("case") for c in cases
                if not (isinstance(c.get("exit_code"), int) and c["exit_code"] != 0)]
    all_nonzero = bool(cases) and not bad_exit
    ok = all_fc and all_nonzero and len(cases) >= 7
    rec = {
        "present": True,
        "sha256": sha256_file(p),
        "bytes": p.stat().st_size,
        "cases": len(cases),
        "all_fail_closed": all_fc,
        "all_exit_codes_nonzero": all_nonzero,
        "nonzero_exit_failures": bad_exit,
        "ok": ok,
    }
    if not all_fc:
        problems.append("负向自测存在非 fail-closed 用例")
    if not all_nonzero:
        problems.append(f"负向自测存在零退出码用例（未按门禁语义非零退出）: {bad_exit}")
    if len(cases) < 7:
        problems.append(f"负向自测用例数 {len(cases)} < 7")
    return rec, problems


def _gate_evidence_checks(ev_dir: Path, exe_sha: str) -> tuple[dict, list[str]]:
    gates: dict = {}
    problems: list[str] = []
    for fn in _GATE_EVIDENCE_FILES:
        fpath = ev_dir / fn
        if not fpath.exists():
            gates[fn] = {"present": False, "exe_sha_match_target": False}
            problems.append(f"证据缺失: {fn}")
            continue
        val, err = _evidence_exe_sha(ev_dir, fn, _EXE_SHA_PATH.get(fn))
        match = (val is not None and val == exe_sha)
        gates[fn] = {
            "present": True,
            "sha256": sha256_file(fpath),
            "bytes": fpath.stat().st_size,
            "exe_sha256": val,
            "exe_sha_match_target": match,
            "error": err,
        }
        if not match:
            problems.append(f"{fn}: exe sha {val} 与目标 {exe_sha[:16]}… 不一致")
    return gates, problems


def _identity_matrix_check(ev_dir: Path) -> tuple[dict, list[str]]:
    """Git 身份 build/verify 正反向矩阵证据：>=15 用例、逐例 ok、正向对照通过。"""
    problems: list[str] = []
    p = ev_dir / _IDENTITY_MATRIX_FILE
    if not p.exists():
        return {"present": False}, [f"缺 Git 身份矩阵证据: {_IDENTITY_MATRIX_FILE}"]
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        return {"present": True, "ok": False}, [f"Git 身份矩阵证据不可读: {e}"]
    cases = data.get("cases") or []
    case_ids = data.get("case_ids") or sorted({c.get("id") for c in cases})
    positive_ok = bool((data.get("positive_control") or {}).get("ok"))
    all_cases_ok = bool(cases) and all(c.get("ok") is True for c in cases)
    ok = (positive_ok and all_cases_ok and data.get("all_ok") is True
          and len(case_ids) >= _IDENTITY_MATRIX_MIN_CASES)
    rec = {
        "present": True,
        "sha256": sha256_file(p),
        "bytes": p.stat().st_size,
        "cases": len(cases),
        "case_ids": case_ids,
        "positive_control_ok": positive_ok,
        "all_cases_ok": all_cases_ok,
        "all_ok": data.get("all_ok"),
        "failures": data.get("failures") or [],
        "ok": ok,
    }
    if not positive_ok:
        problems.append("Git 身份矩阵正向对照未通过")
    if not all_cases_ok:
        problems.append("Git 身份矩阵存在逃逸用例")
    if len(case_ids) < _IDENTITY_MATRIX_MIN_CASES:
        problems.append(f"Git 身份矩阵用例数 {len(case_ids)} < {_IDENTITY_MATRIX_MIN_CASES}")
    return rec, problems


def _cleanup_verdict(gate_runs) -> tuple[dict | None, bool | None, list[str]]:
    """从 gates-meta 抽取 cleanup 判定并折算 cleanup_ok。"""
    problems: list[str] = []
    if not isinstance(gate_runs, dict):
        return None, None, problems
    cleanup = gate_runs.get("cleanup")
    if not isinstance(cleanup, dict):
        return None, None, ["gates-meta 缺少 cleanup 判定"]
    ok = True
    for k, v in cleanup.items():
        if k == "winword_leaked":
            if v:
                ok = False
        elif isinstance(v, bool) and not v:
            ok = False
    if not ok:
        problems.append("cleanup 判定未全部通过")
    return cleanup, ok, problems


def _emit(mode: str, verdict: bool, problems: list[str]) -> None:
    # 单行机器可读摘要（便于受控自测解析）；失败时 final_verdict=false，不构成 PASS 摘要。
    print(json.dumps({"mode": mode, "final_verdict": bool(verdict), "problems": problems},
                     ensure_ascii=False))


# ─────────────────────────── build ─────────────────────────── #

def _build(args) -> int:
    problems: list[str] = []
    ev_dir = Path(args.evidence_dir)
    if not ev_dir.is_dir():
        print(f"[manifest] evidence dir 不存在: {ev_dir}")
        _emit("build", False, ["evidence dir 不存在"])
        return 2

    exe_sha = (args.exe_sha or "").lower()

    repo = args.repo or ""
    expected_src = (args.expected_src or "").strip().lower()
    expected_handoff = (args.expected_handoff or "").strip().lower()

    # 1) Git 身份锚点（现场解析 + 机械比对）。
    git_identity = _resolve_git_identity(repo, expected_src, expected_handoff)
    problems.extend(git_identity.get("problems") or [])

    # 2) 包身份。
    pkg = _package_identity(Path(args.package_dir)) if args.package_dir else None
    if pkg is None:
        problems.append("缺少 --package-dir，无法记录最终包文件数/总字节")
    else:
        if pkg["exe_sha256"] != exe_sha:
            problems.append(
                f"包内 EXE sha {str(pkg['exe_sha256'])[:16]}… 与目标 {exe_sha[:16]}… 不一致")
        if args.bundle and pkg["bundle"] != args.bundle:
            problems.append(f"包内前端 bundle {pkg['bundle']} 与目标 {args.bundle} 不一致")

    # 3) Gate 证据绑定。
    gates, gate_problems = _gate_evidence_checks(ev_dir, exe_sha)
    problems.extend(gate_problems)

    # 4) 负向自测。
    neg_rec, neg_problems = _negative_selftest(ev_dir)
    problems.extend(neg_problems)

    # 4b) Git 身份正反向矩阵。
    idm_rec, idm_problems = _identity_matrix_check(ev_dir)
    problems.extend(idm_problems)

    # 5) Gate 运行汇总与 cleanup 判定。
    gate_runs = None
    gates_meta_ok = False
    if args.gates_meta:
        gmp = Path(args.gates_meta)
        if gmp.is_file():
            try:
                gate_runs = json.loads(gmp.read_text(encoding="utf-8-sig"))
            except Exception as e:  # noqa: BLE001
                problems.append(f"gates-meta 不可读: {e}")
        else:
            problems.append(f"gates-meta 缺失: {gmp}")
    else:
        problems.append("缺少 --gates-meta，无法记录 Gate 命令/退出码/cleanup 判定")
    if isinstance(gate_runs, dict):
        gates_meta_ok = bool(gate_runs.get("all_exit_zero")) and bool(gate_runs.get("final_verdict"))
        if not gates_meta_ok:
            problems.append("gates-meta 未全部退出 0 或 final_verdict 非 true")

    cleanup, cleanup_ok, cleanup_problems = _cleanup_verdict(gate_runs)
    problems.extend(cleanup_problems)

    manifest = {
        "_meta": {
            "generator": "scripts/h8_r3_manifest.py",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "plan_blob": PLAN_BLOB,
            "identity_schema": IDENTITY_SCHEMA,
            "identity_version": IDENTITY_VERSION,
        },
        "identity": {
            "src": expected_src,
            "handoff": expected_handoff,
            "plan_blob": PLAN_BLOB,
            "exe_sha256": exe_sha,
            "bundle": args.bundle,
            "package": pkg,
        },
        "git_identity": git_identity,
        "gates": gates,
        "negative_selftest": neg_rec,
        "identity_matrix": idm_rec,
        "gate_runs": gate_runs,
        "cleanup": cleanup,
        "verdicts": {
            "plan_blob_ok": True,
            "git_identity_ok": git_identity["verdict"],
            "package_ok": bool(pkg and pkg["exe_sha256"] == exe_sha
                               and (not args.bundle or pkg["bundle"] == args.bundle)),
            "gates_ok": all(g.get("present") and g.get("exe_sha_match_target")
                            for g in gates.values()) and len(gates) == len(_GATE_EVIDENCE_FILES),
            "negative_selftest_ok": bool(neg_rec.get("ok")),
            "identity_matrix_ok": bool(idm_rec.get("ok")),
            "gates_meta_ok": gates_meta_ok,
            "cleanup_ok": cleanup_ok,
        },
        "final_verdict": (not problems),
        "problems": problems,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _emit("build", manifest["final_verdict"], problems)
    return 0 if not problems else 1


# ─────────────────────────── verify ─────────────────────────── #

def _verify(args) -> int:
    problems: list[str] = []
    out = Path(args.out)
    if not out.exists():
        print(f"[manifest] manifest 不存在: {out}")
        _emit("verify", False, ["manifest 不存在"])
        return 2
    try:
        m = json.loads(out.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        _emit("verify", False, [f"manifest 不可读: {e}"])
        return 2

    if not m.get("final_verdict"):
        problems.append("manifest 自身 final_verdict=false")
    problems.extend(m.get("problems") or [])

    if (m.get("_meta") or {}).get("plan_blob") != PLAN_BLOB:
        problems.append("PLAN blob 不一致")
    if (m.get("_meta") or {}).get("identity_schema") != IDENTITY_SCHEMA:
        problems.append("identity schema 不一致")

    ident = m.get("identity") or {}
    gi = m.get("git_identity") or {}
    expected_src = (args.expected_src or "").strip().lower()
    expected_handoff = (args.expected_handoff or "").strip().lower()
    repo = args.repo or ""

    # A) manifest 内记录值 == 期望值（双层：identity 与 git_identity.expected）。
    if ident.get("src") != expected_src:
        problems.append("manifest identity.src 不等于 --expected-src")
    if ident.get("handoff") != expected_handoff:
        problems.append("manifest identity.handoff 不等于 --expected-handoff")
    if (gi.get("expected") or {}).get("src") != expected_src:
        problems.append("manifest git_identity.expected.src 不等于 --expected-src")
    if (gi.get("expected") or {}).get("handoff") != expected_handoff:
        problems.append("manifest git_identity.expected.handoff 不等于 --expected-handoff")

    # B) repo 现场机械验证。
    if not repo:
        problems.append("缺少 --repo")
    elif not _is_git_repo(repo):
        problems.append(f"路径不是有效 Git repo: {Path(str(repo)).name}")
    else:
        checks = gi.get("checks") or {}
        if not checks.get("repo_provided", True):
            problems.append("manifest 记录的 Git 身份未在有效 repo 上建立")
        if not gi.get("verdict"):
            problems.append("manifest git_identity.verdict=false")

        src_id, src_err = _commit_identity(repo, expected_src)
        if src_err:
            problems.append(f"verify SRC: {src_err}")
        handoff_id, handoff_err = _commit_identity(repo, expected_handoff)
        if handoff_err:
            problems.append(f"verify HANDOFF: {handoff_err}")

        actual = gi.get("actual") or {}
        rec_src = actual.get("src") or {}
        rec_handoff = actual.get("handoff") or {}

        # tree SHA 与现场一致。
        if src_id and src_id.get("type") == "commit":
            if rec_src.get("tree") != src_id.get("tree"):
                problems.append("manifest 记录 SRC tree SHA 与现场不一致")
            if rec_src.get("parents") != src_id.get("parents"):
                problems.append("manifest 记录 SRC parent 与现场不一致")
        if handoff_id and handoff_id.get("type") == "commit":
            if rec_handoff.get("tree") != handoff_id.get("tree"):
                problems.append("manifest 记录 HANDOFF tree SHA 与现场不一致")
            if rec_handoff.get("parents") != handoff_id.get("parents"):
                problems.append("manifest 记录 HANDOFF parent 与现场不一致")

        # HANDOFF 唯一 parent == SRC。
        if handoff_id and handoff_id.get("type") == "commit":
            parents = handoff_id.get("parents") or []
            if len(parents) != 1:
                problems.append("现场 HANDOFF 不是单 parent commit")
            elif parents[0] != expected_src:
                problems.append("现场 HANDOFF 唯一 parent 不等于 SRC")

        # SRC..HANDOFF 作用域与记录值。
        if (src_id and src_id.get("type") == "commit"
                and handoff_id and handoff_id.get("type") == "commit"):
            ns, ns_err = _name_status(repo, expected_src, expected_handoff)
            if ns_err:
                problems.append(ns_err)
            else:
                if any(r["path"] != RESULT_PATH for r in ns):
                    problems.append("现场 SRC..HANDOFF 出现 RESULT 以外文件")
                if len(ns) < 1:
                    problems.append("现场 SRC..HANDOFF 为空（无 RESULT 收口）")
                rec_ns = actual.get("src_to_handoff_name_status")
                if rec_ns != ns:
                    problems.append("manifest 记录的 SRC..HANDOFF diff 与现场不一致")

    # C) 包身份自洽 + 可选重算。
    pkg = ident.get("package")
    exe_sha = (ident.get("exe_sha256") or "").lower()
    if not pkg:
        problems.append("identity.package 缺失")
    else:
        rec_hash = (pkg.get("exe_sha256") or "").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", rec_hash):
            problems.append("identity.package.exe_sha256 非法")
        if rec_hash != exe_sha:
            problems.append("identity.package.exe_sha256 与 identity.exe_sha256 不一致")
        if not pkg.get("exe_bytes"):
            problems.append("identity.package.exe_bytes 为空")

    # D) Gate 证据绑定 + 可选重算 evidence hash。
    for name, g in (m.get("gates") or {}).items():
        if not g.get("present") or not g.get("exe_sha_match_target"):
            problems.append(f"{name} 未绑定目标 EXE")
    if not m.get("gates"):
        problems.append("gates 段缺失")

    ev_dir = None
    if args.evidence_dir:
        cand = Path(args.evidence_dir)
        if cand.is_dir():
            ev_dir = cand
        else:
            problems.append("--evidence-dir 不存在")
    if ev_dir is not None:
        for name, g in (m.get("gates") or {}).items():
            fp = ev_dir / name
            if not fp.exists():
                problems.append(f"evidence 缺失: {name}")
            elif g.get("sha256") and sha256_file(fp) != g.get("sha256"):
                problems.append(f"evidence hash 与现场不一致: {name}")
        neg = m.get("negative_selftest") or {}
        nfp = ev_dir / "six_grid_negative_selftest.json"
        if neg.get("present"):
            if not nfp.exists():
                problems.append("evidence 缺失: six_grid_negative_selftest.json")
            elif neg.get("sha256") and sha256_file(nfp) != neg.get("sha256"):
                problems.append("negative selftest evidence hash 与现场不一致")
        idm = m.get("identity_matrix") or {}
        ifp = ev_dir / _IDENTITY_MATRIX_FILE
        if idm.get("present"):
            if not ifp.exists():
                problems.append(f"evidence 缺失: {_IDENTITY_MATRIX_FILE}")
            elif idm.get("sha256") and sha256_file(ifp) != idm.get("sha256"):
                problems.append("Git 身份矩阵 evidence hash 与现场不一致")

    # E) 负向自测判定。
    neg = m.get("negative_selftest") or {}
    if not neg.get("present"):
        problems.append("negative_selftest 缺失")
    elif not neg.get("ok"):
        problems.append("negative_selftest 未通过（需 >=7 用例、全部 fail_closed=true 且非零退出码）")

    # E2) Git 身份正反向矩阵判定。
    idm = m.get("identity_matrix") or {}
    if not idm.get("present"):
        problems.append("identity_matrix 缺失")
    elif not idm.get("ok"):
        problems.append("identity_matrix 未通过（需正向对照通过、>=15 用例且逐例 fail-closed）")
    if m.get("verdicts", {}).get("identity_matrix_ok") is not True:
        problems.append("verdicts.identity_matrix_ok 非 true")

    # F) 顶层判定一致性。
    if m.get("verdicts", {}).get("git_identity_ok") is not True:
        problems.append("verdicts.git_identity_ok 非 true")

    ok = not problems
    print(f"[verify] final_verdict={m.get('final_verdict')} "
          f"exe_sha256={str(ident.get('exe_sha256'))[:16]}… problems={len(problems)}")
    for p in problems:
        print(f"  - {p}")
    _emit("verify", ok, problems)
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--repo", default="")
    b.add_argument("--expected-src", default="")
    b.add_argument("--expected-handoff", default="")
    b.add_argument("--exe-sha", required=True)
    b.add_argument("--bundle", default="")
    b.add_argument("--package-dir", default="")
    b.add_argument("--gates-meta", default="")
    b.add_argument("--evidence-dir", required=True)
    b.add_argument("--out", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--out", required=True)
    v.add_argument("--repo", default="")
    v.add_argument("--expected-src", default="")
    v.add_argument("--expected-handoff", default="")
    v.add_argument("--evidence-dir", default="")
    args = ap.parse_args()
    return (_build(args) if args.cmd == "build" else _verify(args))


if __name__ == "__main__":
    sys.exit(main())
