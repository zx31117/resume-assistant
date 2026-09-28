#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 R3 返工：Gate verdict 判定链负向矩阵（真实子进程 + 真实退出码）。

对应 RESULT §R3-18 A 与 PLAN §7 / 工作流 §8.4。每一例都：
  1) 在一次性临时目录里构造一份与 manifest 逐 Gate 合同一致的“全通过”证据集合；
  2) 按用例注入**真实故障**（生成失败 / 上游 4xx/5xx / 超时 / 未捕获异常 / JSON 缺失或截断 /
     exit 0 但 JSON 失败 / exit 非零但 JSON 成功 / cleanup 失败 / UI 未到 P4 / artifact 缺失 /
     单项失败但汇总被篡改成成功 / 包身份不符 / 证据 hash 不符 / Gate 记录缺失 / 矩阵用例失败）；
  3) **真实启动 manifest 子进程**并读取其真实退出码、stdout 判定与 `problems`；
  4) 断言：rc != 0、`final_verdict=false`、`problems` 可定位、且没有输出可被误认为 PASS 的摘要。

退出码 0 = 全部负向用例 fail-closed 且正向对照通过；非 0 = 存在逃逸（并写明 failures）。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EVID = ROOT / "validation-artifacts" / "h8" / "r3rework4"
_MANIFEST = HERE / "h8_r3_manifest.py"
sys.path.insert(0, str(HERE))
import h8_r3_gate_fixtures as FX  # noqa: E402


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


_BUNDLE = "index-Fixture.js"
_RESULT = "docs/versions/v2.2.0/RESULT.md"
_SRC_FILE = "backend/services/placeholder.py"


def _sh(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=180)


def _git(repo: Path, *args: str) -> str:
    p = _sh(["git", "-C", str(repo), *args])
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout.strip()


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


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
    return {"rc": p.returncode, "stdout": p.stdout, "stderr": p.stderr,
            "payload": _parse_payload(p.stdout)}


class Fixture:
    """一次性夹具：repo(SRC→HANDOFF only RESULT) + 包内 EXE + 证据集合。"""

    def __init__(self, root: Path):
        self.root = root
        repo = _init_repo(root)
        _write(repo / _RESULT, "# RESULT\ninitial\n")
        _write(repo / _SRC_FILE, "x = 1\n")
        _commit_all(repo, "BASE")
        _write(repo / _SRC_FILE, "x = 2\n")
        self.src = _commit_all(repo, "SRC")
        _write(repo / _RESULT, "# RESULT\nfinal\n")
        self.handoff = _commit_all(repo, "HANDOFF")
        self.repo = repo

        pkg = root / "pkg" / "ResumeAssistant"
        exe = pkg / "ResumeAssistant.exe"
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_bytes(b"FIXTURE-EXE" * 64)
        asset = pkg / "_internal" / "frontend" / "dist" / "assets" / _BUNDLE
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_text("// fixture bundle\n", encoding="utf-8")
        self.pkg = pkg
        self.exe_sha = FX.sha256_file(exe)
        self.outdir = root / "out"
        self.outdir.mkdir(exist_ok=True)

    def evidence(self, name: str, mutate: dict | None = None) -> Path:
        ev = self.root / f"ev_{name}"
        if ev.exists():
            _rmtree_force(ev)
        runs = FX.write_valid_evidence(ev, self.exe_sha, mutate=mutate)
        _write(ev / "gates_run.json", json.dumps(runs, ensure_ascii=False, indent=2))
        return ev

    def argv(self, ev: Path, out: Path, *, exe_sha: str | None = None) -> list[str]:
        return [
            "--repo", str(self.repo),
            "--expected-src", self.src,
            "--expected-handoff", self.handoff,
            "--exe-sha", exe_sha if exe_sha is not None else self.exe_sha,
            "--bundle", _BUNDLE,
            "--package-dir", str(self.pkg),
            "--evidence-dir", str(ev),
            "--gates-meta", str(ev / "gates_run.json"),
            "--out", str(out),
        ]


def _rec(case_id: str, name: str, mode: str, run: dict, *, expect_fail: bool = True) -> dict:
    rc = run["rc"]
    payload = run["payload"] or {}
    problems = payload.get("problems") or []
    if not problems:
        blob = (run["stdout"] or "") + (run["stderr"] or "")
        problems = [ln.strip()[2:].strip() for ln in blob.splitlines()
                    if ln.strip().startswith("- ")]
    final_verdict = payload.get("final_verdict")
    if expect_fail:
        ok = (rc != 0) and (final_verdict is False) and bool(problems)
    else:
        ok = (rc == 0) and (final_verdict is True)
    return {"id": case_id, "case": name, "mode": mode, "exit_code": rc,
            "final_verdict": final_verdict, "problems_nonempty": bool(problems),
            "problems": problems[:6], "ok": bool(ok)}


def run_matrix(root: Path) -> dict:
    fx = Fixture(root)
    cases: list[dict] = []

    # ── 正向对照：全通过证据集必须 build rc 0 / final_verdict true ──
    ev_ok = fx.evidence("ok")
    pos = _run("build", fx.argv(ev_ok, fx.outdir / "pos.json"))
    positive = _rec("P00_positive_control", "全通过证据集", "build", pos, expect_fail=False)
    if not positive["ok"]:
        return {"_meta": {"generator": "scripts/h8_r3_gate_verdict_negtest.py"},
                "positive_control": positive, "cases": [], "all_ok": False,
                "failures": ["positive_control_failed"],
                "positive_stdout": (pos["stdout"] or "")[-2000:]}

    def case(cid: str, name: str, mutate: dict, *, exe_sha: str | None = None,
             mode: str = "build") -> None:
        ev = fx.evidence(cid)
        # mutate 已用于生成；这里重放同样 mutate（evidence() 已按 mutate 生成）
        run = _run(mode, fx.argv(ev, fx.outdir / f"{cid}.json", exe_sha=exe_sha))
        cases.append(_rec(cid, name, mode, run))

    def case_with(cid: str, name: str, mutate: dict, *, exe_sha: str | None = None) -> None:
        ev = fx.evidence(cid, mutate)
        run = _run("build", fx.argv(ev, fx.outdir / f"{cid}.json", exe_sha=exe_sha))
        cases.append(_rec(cid, name, "build", run))

    # N01 生成失败：content_e2e 结论失败 + 真实非零退出
    case_with("N01_generation_failed", "生成失败（content_e2e 失败 + exit=8）", {
        "payload": {"content_e2e": {
            "ok": False, "gate_passed": False, "exe": {"sha256": fx.exe_sha},
            "runtime_deleted": True,
            "main_terminal": {"status": "FAILED", "terminal_error": "GENERATION_FAILED"},
            "content_checks": {"owner_scope": True}, "cleanup": {"ok": True}}},
        "override_exit": {"content_e2e": 8},
    })

    # N02 上游 4xx：主链 artifact 断言失败但 Gate 自报成功（exit 0 → 矛盾）
    case_with("N02_upstream_4xx", "上游 4xx（claim 成功但 artifact 断言失败，exit=0 矛盾）", {
        "payload": {"mainchain_e2e": {
            "ok": True, "gate_passed": True, "exe": {"sha256": fx.exe_sha},
            "runtime_deleted": True, "ui_p4_reached": True,
            "ui_pdf_viewer": {"viewer_ready": True},
            "pdf_viewer_same_source_final": {"same_source": True},
            "artifact_checks": {"word_download_eq_disk_docx": False, "no_4xx_5xx": False},
            "cleanup": {"ok": True}}},
    })

    # N03 上游 5xx：viewer 未 ready（真实失败）
    case_with("N03_upstream_5xx", "上游 5xx（viewer 未 ready 却声称成功）", {
        "payload": {"mainchain_e2e": {
            "ok": True, "gate_passed": True, "exe": {"sha256": fx.exe_sha},
            "runtime_deleted": True, "ui_p4_reached": True,
            "ui_pdf_viewer": {"viewer_ready": False},
            "pdf_viewer_same_source_final": {"same_source": False},
            "artifact_checks": {"no_4xx_5xx": False},
            "cleanup": {"ok": True}}},
    })

    # N04 timeout：exit=124 且结论失败
    case_with("N04_timeout", "timeout（exit=124 + 结论失败）", {
        "payload": {"content_e2e": {
            "ok": False, "gate_passed": False, "exe": {"sha256": fx.exe_sha},
            "runtime_deleted": False, "main_terminal": {"status": "RUNNING"},
            "content_checks": {}, "cleanup": {"ok": False}}},
        "override_exit": {"content_e2e": 124},
    })

    # N05 未捕获异常：证据显式带 exception 且结论失败
    case_with("N05_uncaught_exception", "未捕获异常（exception 在场 + 结论失败）", {
        "payload": {"mainchain_e2e": {
            "ok": False, "gate_passed": False, "exe": {"sha256": fx.exe_sha},
            "exception": "RuntimeError('boom')", "runtime_deleted": True,
            "ui_p4_reached": False, "artifact_checks": {}, "cleanup": {"ok": True}}},
        "override_exit": {"mainchain_e2e": 2},
    })

    # N06 JSON 缺失
    case_with("N06_json_missing", "证据 JSON 缺失（real_model_e2e.json 不存在）", {
        "drop_payload": ["mainchain_e2e"],
    })

    # N07 JSON 截断
    case_with("N07_json_truncated", "证据 JSON 被截断（design_fidelity.json）", {
        "truncate": ["design_fidelity"],
    })

    # N08 exit 0 但 JSON 失败
    case_with("N08_exit0_json_false", "exit=0 但证据结论失败（六格）", {
        "payload": {"six_grid": {
            "gate_passed": False, "pass": False, "exe": {"sha256": fx.exe_sha},
            "n_samples": 18, "first_fact_median_s": 5.9, "first_fact_max_s": 7.1,
            "fail_messages": ["injected"]}},
        "override_exit": {"six_grid": 0},
    })

    # N09 exit 非零但 JSON 成功
    case_with("N09_exit_nonzero_json_true", "exit=7 但证据结论成功（failure_matrix）", {
        "override_exit": {"failure_matrix": 7},
    })

    # N10 cleanup 失败但 Gate 成功
    case_with("N10_cleanup_false", "cleanup 失败却把 Gate 判为成功", {
        "payload": {"mainchain_e2e": {
            "ok": True, "gate_passed": True, "exe": {"sha256": fx.exe_sha},
            "runtime_deleted": True, "ui_p4_reached": True,
            "ui_pdf_viewer": {"viewer_ready": True},
            "pdf_viewer_same_source_final": {"same_source": True},
            "artifact_checks": {"no_4xx_5xx": True},
            "cleanup": {"ok": False, "runtime_removed": False}}},
    })

    # N11 UI 未到 P4
    case_with("N11_ui_not_p4", "UI 未到 P4 却写成主链成功", {
        "payload": {"mainchain_e2e": {
            "ok": True, "gate_passed": True, "exe": {"sha256": fx.exe_sha},
            "runtime_deleted": True, "ui_p4_reached": False,
            "ui_pdf_viewer": {"viewer_ready": True},
            "pdf_viewer_same_source_final": {"same_source": True},
            "artifact_checks": {"no_4xx_5xx": True},
            "cleanup": {"ok": True}}},
    })

    # N12 artifact 缺失
    case_with("N12_artifact_missing", "artifact 缺失却写成主链成功", {
        "payload": {"mainchain_e2e": {
            "ok": True, "gate_passed": True, "exe": {"sha256": fx.exe_sha},
            "runtime_deleted": True, "ui_p4_reached": True,
            "ui_pdf_viewer": {"viewer_ready": True},
            "pdf_viewer_same_source_final": {"same_source": True},
            "artifact_checks": {"pdf_download_eq_disk_pdf": False},
            "cleanup": {"ok": True}}},
    })

    # N13 单项失败但汇总被篡改成功
    case_with("N13_summary_tampered", "单项失败但 all_exit_zero/final_verdict 被篡改为 true", {
        "override_exit": {"atomic_publish_matrix": 1},
        "gates_run": {"all_exit_zero": True, "final_verdict": True, "problems": []},
    })

    # N14 包身份不符
    case_with("N14_package_sha_mismatch", "证据内包身份与目标 EXE 不一致", {},
              exe_sha="a" * 64)

    # N15 证据 hash 不符
    case_with("N15_evidence_hash_mismatch", "gates_run 记录的证据 hash 与现场不一致", {
        "override_evidence_sha": {"pyz_check": "b" * 64},
    })

    # N16 Gate 运行记录缺失
    case_with("N16_gate_record_missing", "gates_run 缺少某项 Gate 运行记录", {
        "drop_gate": ["gate_verdict_negtest"],
    })

    # N17 授权矩阵用例失败
    case_with("N17_auth_matrix_case_failed", "授权矩阵存在失败用例", {
        "payload": {"artifact_auth_matrix": {
            "all_ok": True, "exe": {"sha256": fx.exe_sha},
            "case_ids": FX.AUTH_IDS,
            "cases": [{"id": i, "case": f"c{i}", "ok": i != "B3"} for i in FX.AUTH_IDS],
            "cleanup": {"ok": True}}},
    })

    # N18 原子发布矩阵用例失败
    case_with("N18_publish_matrix_case_failed", "原子发布矩阵存在失败用例", {
        "payload": {"atomic_publish_matrix": {
            "all_ok": True, "case_ids": FX.PUBLISH_IDS,
            "cases": [{"id": i, "case": f"c{i}", "ok": i != "P11"} for i in FX.PUBLISH_IDS],
            "cleanup": {"ok": True}}},
    })

    # N19 键盘矩阵缺失（Design Fidelity 后置条件）
    case_with("N19_keyboard_matrix_missing", "Design Fidelity 缺少键盘矩阵后置条件", {
        "payload": {"design_fidelity": {
            "exe_sha256": fx.exe_sha, "summary": {"pass": 120, "fail": 0, "exit": 0},
            "cleanup": {"ok": True},
            "review_1686x1076": {"ok": True}}},
    })

    # N20 verify 侧：篡改 gate 退出码后 verify 必须失败
    ev_ok2 = fx.evidence("ok2")
    ok_manifest = fx.outdir / "ok2.json"
    _ = _run("build", fx.argv(ev_ok2, ok_manifest))
    try:
        m = json.loads(ok_manifest.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001
        m = None
    if isinstance(m, dict):
        m["gates"]["precheck"]["exit_code"] = 3
        tampered = fx.outdir / "tampered_exit.json"
        tampered.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        run = _run("verify", ["--out", str(tampered), "--repo", str(fx.repo),
                              "--expected-src", fx.src, "--expected-handoff", fx.handoff,
                              "--evidence-dir", str(ev_ok2)])
        cases.append(_rec("N20_verify_exit_tampered", "verify 侧篡改 gate 退出码", "verify", run))
    else:
        cases.append({"id": "N20_verify_exit_tampered", "case": "verify 侧篡改 gate 退出码",
                      "mode": "verify", "exit_code": None, "final_verdict": None,
                      "problems_nonempty": False, "problems": [], "ok": False})

    # ── §R3-32 §32.4-4：三项关键交互门（frontend_test / docreturned_anchor / docreturned_ui）
    #    的离线反向矩阵。每例同时要求 build 与 verify 非零、final_verdict=false，
    #    且 problems 定位到具体 Gate。证据 hash 由夹具按**现场重算**写入（等价于篡改后同步
    #    更新证据 hash），以证明 manifest 不靠 hash 相等来判定语义。 ──
    def case_bv(cid: str, name: str, mutate: dict) -> None:
        ev = fx.evidence(cid, mutate)
        out = fx.outdir / f"{cid}.json"
        rb = _run("build", fx.argv(ev, out))
        rv = _run("verify", ["--out", str(out), "--repo", str(fx.repo),
                             "--expected-src", fx.src, "--expected-handoff", fx.handoff,
                             "--evidence-dir", str(ev)])
        rec = _rec(cid, name, "build+verify", rb)
        v_payload = rv["payload"] or {}
        v_ok = (rv["rc"] != 0) and (v_payload.get("final_verdict") is False)
        rec["verify_rc"] = rv["rc"]
        rec["verify_final_verdict"] = v_payload.get("final_verdict")
        rec["ok"] = bool(rec["ok"] and v_ok)
        if not v_ok:
            rec["problems"] = (rec["problems"] or []) + [
                f"verify 未 fail-closed rc={rv['rc']} "
                f"final_verdict={v_payload.get('final_verdict')}"]
        cases.append(rec)

    # T01：frontend_test 摘要显示失败，但 gates_run 记录仍为 exit 0
    case_bv("T01_frontend_failed_exit0", "frontend_test 证据失败但 runner 记录 0", {
        "payload": {"frontend_test":
                    " \x1b[32m×\x1b[39m tests/pdfPreview.test.tsx\n"
                    "\x1b[2m Test Files \x1b[22m \x1b[1m\x1b[31m1 failed\x1b[39m"
                    "\x1b[22m\x1b[90m (2)\x1b[39m\n"
                    "\x1b[2m      Tests \x1b[22m \x1b[1m\x1b[31m3 failed\x1b[39m"
                    "\x1b[22m\x1b[90m | 22 passed (25)\x1b[39m\n"},
    })

    # T02：frontend_test 摘要缺失（只剩 RUN 行），未确认 2 files / 25 tests
    case_bv("T02_frontend_summary_missing", "frontend_test 摘要缺失", {
        "payload": {"frontend_test": "\x1b[36m RUN \x1b[39m v2.1.9\n"},
    })

    # T03：frontend_test 证据被截断
    case_bv("T03_frontend_evidence_truncated", "frontend_test 证据截断",
            {"truncate": ["frontend_test"]})

    # T04：frontend_test 证据缺失
    case_bv("T04_frontend_evidence_missing", "frontend_test 证据缺失",
            {"drop_payload": ["frontend_test"]})

    # T05：docreturned_anchor 出现 [FAIL] 且终态 FAIL=1
    case_bv("T05_anchor_fail_terminal", "anchor 出现 FAIL 且终态 FAIL=1", {
        "payload": {"docreturned_anchor":
                    FX.anchor_log_payload()
                    .replace("[PASS] A7)-1 fixture 断言成立",
                             "[FAIL] A7)-1 fixture 断言失败")
                    .replace("FAIL=0", "FAIL=1")},
    })

    # T06：docreturned_anchor 缺少 A4 必需分组（29 项 PASS 仍在场，隔离分组检查）
    case_bv("T06_anchor_group_missing", "anchor 缺少 A4 必需分组", {
        "payload": {"docreturned_anchor": "\n".join(
            [f"=== {h} 分组 fixture ===" for h, _ in
             [("A1)", 6), ("A2)", 7), ("A2b)", 2), ("A3)", 4), ("A5/A6)", 8), ("A7)", 2)]]
            + [f"[PASS] g{i} fixture 断言成立" for i in range(29)]
            + ["V2.2.0 DOC_RETURNED anchor 离线门：FAIL=0"]) + "\n"},
    })

    # T07：docreturned_anchor 证据缺失
    case_bv("T07_anchor_evidence_missing", "anchor 证据缺失",
            {"drop_payload": ["docreturned_anchor"]})

    # T08：docreturned_anchor 证据被截断
    case_bv("T08_anchor_evidence_truncated", "anchor 证据截断",
            {"truncate": ["docreturned_anchor"]})

    # T09：docreturned_ui pass=0 / fails 非空 / 首个 assertion ok=false
    t09_ui = FX.ui_summary_payload()
    t09_ui["assertions"][0] = {"label": t09_ui["assertions"][0]["label"], "ok": False}
    t09_ui["pass"] = 0
    t09_ui["fails"] = [t09_ui["assertions"][0]["label"]]
    case_bv("T09_ui_pass_zero", "ui summary pass=0 / 存在失败 assertion",
            {"payload": {"docreturned_ui": t09_ui}})

    # T10：docreturned_ui 缺少必需 assertion label（71 个）与 pass 不一致
    t10_ui = FX.ui_summary_payload()
    t10_ui["assertions"] = [a for a in t10_ui["assertions"]
                            if a["label"] != "u2.mouse-fact-click"]
    t10_ui["pass"] = len(t10_ui["assertions"])
    case_bv("T10_ui_label_missing", "ui summary 缺少必需 assertion label",
            {"payload": {"docreturned_ui": t10_ui}})

    # T11：docreturned_ui 出现额外/未知 assertion label
    t11_ui = FX.ui_summary_payload()
    t11_ui["assertions"].append({"label": "u9.unknown-assertion", "ok": True})
    t11_ui["pass"] = len(t11_ui["assertions"])
    case_bv("T11_ui_label_extra", "ui summary 存在额外 assertion label",
            {"payload": {"docreturned_ui": t11_ui}})

    # T12：docreturned_ui 证据被截断（JSON 不可解析）
    case_bv("T12_ui_evidence_truncated", "ui summary 证据截断",
            {"truncate": ["docreturned_ui"]})

    # T13：docreturned_ui 证据缺失
    case_bv("T13_ui_evidence_missing", "ui summary 证据缺失",
            {"drop_payload": ["docreturned_ui"]})

    # T14：三门证据全部失败，且 gates_run 里的 evidence_sha256/evidence_bytes **同步重算**
    #      —— 证明「篡改证据 + 更新记录 hash」不能把总 manifest 洗绿。
    t14_ui = FX.ui_summary_payload()
    t14_ui["pass"] = 0
    t14_ui["fails"] = ["u2.mouse-fact-click"]
    t14_ui["assertions"] = [dict(a, ok=False) for a in t14_ui["assertions"]]
    ev14 = fx.evidence("T14_three_gates_hash_resynced", {
        "payload": {
            "frontend_test": " \x1b[31m×\x1b[39m tests/pdfPreview.test.tsx\n"
                             "\x1b[2m Test Files \x1b[22m 2 failed (2)\n"
                             "\x1b[2m      Tests \x1b[22m 25 failed (25)\n",
            "docreturned_anchor": FX.anchor_log_payload().replace("FAIL=0", "FAIL=3"),
            "docreturned_ui": t14_ui,
        },
    })
    gm_path = ev14 / "gates_run.json"
    gm14 = json.loads(gm_path.read_text(encoding="utf-8-sig"))
    for g in gm14.get("gates") or []:
        fname = g.get("evidence")
        if not fname:
            continue
        fp = ev14 / fname
        if fp.is_file():
            g["evidence_sha256"] = FX.sha256_file(fp)
            g["evidence_bytes"] = fp.stat().st_size
    gm_path.write_text(json.dumps(gm14, ensure_ascii=False, indent=2), encoding="utf-8")
    out14 = fx.outdir / "T14_three_gates_hash_resynced.json"
    rb14 = _run("build", fx.argv(ev14, out14))
    rv14 = _run("verify", ["--out", str(out14), "--repo", str(fx.repo),
                           "--expected-src", fx.src, "--expected-handoff", fx.handoff,
                           "--evidence-dir", str(ev14)])
    rec14 = _rec("T14_three_gates_hash_resynced",
                 "三门证据失败且记录 hash 同步重算", "build+verify", rb14)
    vp14 = rv14["payload"] or {}
    v14_ok = (rv14["rc"] != 0) and (vp14.get("final_verdict") is False)
    rec14["verify_rc"] = rv14["rc"]
    rec14["verify_final_verdict"] = vp14.get("final_verdict")
    rec14["ok"] = bool(rec14["ok"] and v14_ok)
    if not v14_ok:
        rec14["problems"] = (rec14["problems"] or []) + [
            f"verify 未 fail-closed rc={rv14['rc']} "
            f"final_verdict={vp14.get('final_verdict')}"]
    cases.append(rec14)

    # T15：Gate ID 重复（同一 Gate 在 gates_run 中出现两次）⇒ 集合非唯一必须 fail-closed
    case_bv("T15_gate_id_duplicate", "gates_run 出现重复 Gate ID",
            {"duplicate_gate": ["frontend_test"]})

    # T16：Gate ID 额外/未知（gates_run 出现合同外的 Gate 记录）⇒ 集合非精确必须 fail-closed
    case_bv("T16_gate_id_extra", "gates_run 出现额外/未知 Gate ID", {
        "extra_gate_records": [{
            "gate": "unknown_gate_zz", "command": "<fixture> unknown_gate_zz",
            "exit_code": 0, "started_at_local": "2026-01-01T00:00:00",
            "ended_at_local": "2026-01-01T00:00:00", "evidence": None,
            "evidence_sha256": None, "evidence_bytes": 0,
            "package_exe_sha256": fx.exe_sha, "verdict": True,
        }],
    })

    # T17：docreturned_ui 证据内包身份（exe.sha256）与目标 EXE 不一致 ⇒ 必须 fail-closed。
    #      这是新增 `exe_sha_path="exe.sha256"` 绑定的精确反例：其余断言全部通过，仅包身份错配。
    case_bv("T17_ui_exe_sha_mismatch", "ui summary 包身份与目标 EXE 不一致",
            {"payload": {"docreturned_ui": FX.ui_summary_payload("f" * 64)}})

    failures = [f"{c['id']}:{c['case']}:{c['mode']}" for c in cases if not c["ok"]]
    return {
        "_meta": {
            "generator": "scripts/h8_r3_gate_verdict_negtest.py",
            "plan_blob": "7d8a249a5ec3e607855f20d794bb7ed9cda351ee",
            "manifest": "scripts/h8_r3_manifest.py",
            "note": "逐例真实启动 manifest 子进程并读取真实退出码；不在测试中硬编码预期退出码。",
        },
        "positive_control": positive,
        "cases": cases,
        "case_ids": [c["id"] for c in cases],
        "all_ok": (not failures),
        "failures": failures,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(EVID / "gate_verdict_negtest.json"))
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    if not _MANIFEST.is_file():
        print(f"NEGTEST_FATAL manifest_missing: {_MANIFEST}")
        return 2

    root = Path(tempfile.mkdtemp(prefix="h8verdict_"))
    try:
        result = run_matrix(root)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        result = {"_meta": {"generator": "scripts/h8_r3_gate_verdict_negtest.py"},
                  "cases": [], "case_ids": [], "all_ok": False,
                  "failures": [f"exception:{type(e).__name__}"]}
    finally:
        if not args.keep:
            _rmtree_force(root)
    result["cleanup"] = {"ok": not root.exists(), "runtime_removed": not root.exists()}

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for c in result.get("cases", []):
        print(f"[verdict-neg] {c['id']:<28} {c['mode']:6} rc={c['exit_code']} "
              f"verdict={c['final_verdict']} ok={c['ok']}")
    print(json.dumps({"positive_ok": (result.get("positive_control") or {}).get("ok"),
                      "cases": len(result.get("cases", [])),
                      "all_ok": result.get("all_ok"),
                      "failures": result.get("failures")}, ensure_ascii=False))
    return 0 if result.get("all_ok") else 1


if __name__ == "__main__":
    sys.exit(main())
