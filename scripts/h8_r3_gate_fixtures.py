"""V2.2.0 R3 返工：受控 Gate 负向矩阵的**夹具构造器**（仅测试用，不参与产品运行时）。

本模块为 `h8_r3_git_identity_negtest.py` 与 `h8_r3_gate_verdict_negtest.py` 提供一份
与 `scripts/h8_r3_manifest.py` 逐 Gate 合同完全一致的“可判定为通过”的证据集合，
以及按字段/文件粒度的篡改原语。篡改后的夹具必须让 manifest 以非零退出且
`final_verdict=false` 失败——这是 §R3-18 A 的 fail-closed 要求。

纪律：本模块只写一次性临时目录，不读取或修改任何真实 runtime / 仓库文件。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

# 与 manifest 的 Gate 合同保持同序
GATE_ORDER = [
    "precheck",
    "package_audit",
    "pyz_check",
    "failure_matrix",
    "content_e2e",
    "mainchain_e2e",
    "design_fidelity",
    "six_grid",
    "six_grid_negative_selftest",
    "git_identity_negtest",
    "artifact_auth_matrix",
    "atomic_publish_matrix",
    "gate_verdict_negtest",
    "seal_manifest_negtest",
    # §R3-32 §32.4-1：runner 注册并真实运行的另外三项关键交互门，必须与 manifest 合同一致。
    "frontend_test",
    "docreturned_anchor",
    "docreturned_ui",
]

EVIDENCE_BY_GATE = {
    "precheck": "precheck.log",
    "package_audit": "package_audit.json",
    "pyz_check": "pyz_check.json",
    "failure_matrix": "failure_matrix.json",
    "content_e2e": "content_real_model.json",
    "mainchain_e2e": "real_model_e2e.json",
    "design_fidelity": "design_fidelity.json",
    "six_grid": "six_grid_aggregate.json",
    "six_grid_negative_selftest": "six_grid_negative_selftest.json",
    "git_identity_negtest": "git_identity_matrix.json",
    "artifact_auth_matrix": "artifact_auth_matrix.json",
    "atomic_publish_matrix": "atomic_publish_matrix.json",
    "gate_verdict_negtest": "gate_verdict_negtest.json",
    "seal_manifest_negtest": "seal_manifest_negtest.json",
    "frontend_test": "frontend_test.log",
    "docreturned_anchor": "docreturned_anchor.log",
    "docreturned_ui": "docreturned_ui_summary.json",
}

AUTH_IDS = ["A1", "A2", "A3", "B1", "B2", "B3", "B4", "B5", "C1", "C2", "C3",
            "C4", "C5", "D1", "D2", "D3", "E1", "E2", "F1", "F2", "F3"]
PUBLISH_IDS = ["P1a", "P1b", "P1c", "P1d", "P1e", "P2", "P3", "P4", "P5", "P6",
               "P7", "P8", "P9", "P10", "P11", "P12", "P13", "P14", "P15"]
VERDICT_NEG_IDS = [
    "N01_ok", "N02_generation_failed", "N03_upstream_4xx", "N04_upstream_5xx",
    "N05_timeout", "N06_uncaught_exception", "N07_json_missing", "N08_json_truncated",
    "N09_exit0_json_false", "N10_exit_nonzero_json_true", "N11_cleanup_false",
    "N12_ui_not_p4", "N13_artifact_missing", "N14_summary_tampered",
]


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ── §R3-32 §32.4-2：三项关键交互门的“全通过”夹具常量 ──────────────────────────
# 必须与 `h8_r3_manifest.py` 的 `_UI_ASSERTION_LABELS` 完全一致（正向对照会立刻暴露分歧）。
UI_ASSERTION_LABELS = [
    "u0.retired-files-gone", "u0.no-appshell", "u0.no-resultpaper",
    "u0.pdfpreview-single-definer", "u0.pdfpreview-single-importer",
    "u0.selkey-single-consumer", "u0.hotspot-class-single-source",
    "u0.section-class-single-source", "u0.data-fact-single-source",
    "u0.data-section-single-source", "u0.selkey-single-definer",
    "u0.selection-single-owner", "u0.selection-consumers",
    "u0.pdfpreview-no-local-selection", "u0.shell-single", "u0.brandlink-single",
    "u1.topbar.draft", "u1.topbar.running",
    "u2.p4-reached", "u2.hotspot-kinds", "u2.fact-geometry-distinct",
    "u2.mouse-fact-click", "u2.mouse-fact-select", "u2.fact-detail",
    "u2.mouse-fact-toggle-off", "u2.keyboard-enter-select",
    "u2.keyboard-space-toggle-off", "u2.focus-visible",
    "u2.mouse-section-select", "u2.section-detail", "u2.mutual-exclusion",
    "u2.skills-select", "u2.skills-keyboard-toggle", "u2.canvas-click-clears",
    "u2.no-console-errors",
    "u3.geometry@1920x1080", "u3.geometry@1686x1076", "u3.geometry@1440x900",
    "u3.scale-proportional", "u3.after-scroll",
    "u4.empty-no-hotspots", "u4.empty-no-console-errors",
    "u4.mismatch-no-hotspots", "u4.mismatch-no-console-errors",
    "u4.restore-hotspots",
    "u5.baseline",
    "u5./experiences.topbar", "u5./experiences.no-start-new-task",
    "u5./experiences.returned", "u5./experiences.task-unchanged",
    "u5./experiences.no-model-request", "u5./experiences.no-new-task-or-generate",
    "u5./experiences.task-id-stable",
    "u5./records.topbar", "u5./records.no-start-new-task", "u5./records.returned",
    "u5./records.task-unchanged", "u5./records.no-model-request",
    "u5./records.no-new-task-or-generate", "u5./records.task-id-stable",
    "u5./privacy.topbar", "u5./privacy.no-start-new-task", "u5./privacy.returned",
    "u5./privacy.task-unchanged", "u5./privacy.no-model-request",
    "u5./privacy.no-new-task-or-generate", "u5./privacy.task-id-stable",
    "u6.brandlink-single-flight", "u6.hotspot-dblclick-net-off",
    "u7.single-fact-count", "u7.single-fact-select", "u7.single-fact-toggle-off",
]

# anchor 必需分组与 29 项 PASS 的分布（与真实 docreturned_anchor.log 同构）。
ANCHOR_GROUPS = [("A1)", 6), ("A2)", 7), ("A2b)", 2), ("A3)", 4),
                 ("A4)", 3), ("A5/A6)", 5), ("A7)", 2)]


def frontend_log_payload() -> str:
    """与真实 `frontend_test.log` 同构（含 ANSI 色码）：2 files / 25 tests 全通过。"""
    return (
        "\x1b[1m\x1b[7m\x1b[36m RUN \x1b[39m\x1b[27m\x1b[22m \x1b[36mv2.1.9 \x1b[39m\n\n"
        " \x1b[32m✓\x1b[39m tests/workbenchShell.test.tsx \x1b[2m(\x1b[22m"
        "\x1b[2m9 tests\x1b[22m\x1b[2m)\x1b[22m\n"
        " \x1b[32m✓\x1b[39m tests/pdfPreview.test.tsx \x1b[2m(\x1b[22m"
        "\x1b[2m16 tests\x1b[22m\x1b[2m)\x1b[22m\n\n"
        "\x1b[2m Test Files \x1b[22m \x1b[1m\x1b[32m2 passed\x1b[39m\x1b[22m"
        "\x1b[90m (2)\x1b[39m\x1b[90m\n"
        "\x1b[2m      Tests \x1b[22m \x1b[1m\x1b[32m25 passed\x1b[39m\x1b[22m"
        "\x1b[90m (25)\x1b[39m\x1b[90m\n"
    )


def anchor_log_payload() -> str:
    """与真实 `docreturned_anchor.log` 同构：A1～A7 分组 + 29 项 PASS + 终态 FAIL=0。"""
    lines: list[str] = []
    for head, n in ANCHOR_GROUPS:
        lines.append(f"=== {head} 分组 fixture ===")
        for i in range(n):
            lines.append(f"[PASS] {head}-{i} fixture 断言成立")
    lines.append("V2.2.0 DOC_RETURNED anchor 离线门：FAIL=0")
    return "\n".join(lines) + "\n"


def ui_summary_payload(exe_sha: str | None = None) -> dict:
    """与真实 `docreturned_ui_summary.json` 同构：72 个精确 label、全部 ok、pass=72。

    `exe_sha` 提供时附带冻结包身份（`exe.sha256`）——与该门合同的 `exe_sha_path` 对齐，
    使正向夹具通过 manifest 的包身份交叉核验；负向用例可省略以构造身份缺失。
    """
    payload = {
        "assertions": [{"label": lbl, "ok": True, "extra": ""}
                       for lbl in UI_ASSERTION_LABELS],
        "pass": len(UI_ASSERTION_LABELS),
        "fails": [],
        "cleanup": {"runtime_removed": True},
    }
    if exe_sha:
        payload["exe"] = {"path": "pkg/ResumeAssistant.exe", "sha256": exe_sha,
                          "size": 16833361}
    return payload


# ── §R3-28 §28.7-3 / §R3-30 §30.5-1：runner 负向矩阵（辅助判定段一）的“全通过”夹具 ──
AUX_MATRIX_FILE = "run_gates_negtest.json"
AUX_SCHEMA = "resume-assistant/r3-run-gates-negtest"
AUX_POSITIVE_CASE_IDS = ["P00_complete_positive", "P01_manifest_positive"]
AUX_NEGATIVE_CASE_IDS = [
    "N01_single_failure", "N02_mixed", "N03_all_failure", "N04_unknown_gate",
    "N05_empty_only", "N06_missing_evidence", "N07_partial_all_pass",
    "N08_partial_to_manifest", "N09_aux_missing", "N10_aux_truncated",
    "N11_aux_runner_sha_mismatch", "N12_aux_missing_case",
    "N13_aux_exit_code_escape", "N14_aux_all_ok_false", "N15_aux_failures_nonempty",
    "N16_aux_negative_exit_zero", "N17_aux_n05_subcases_missing",
    "N18_aux_n05_subcase_exit_zero", "N19_aux_n05_gates_run_written",
    "N20_aux_duplicate_case_id", "N21_aux_extra_case_id",
]
# 必须与 h8_r3_manifest.py `_AUX_REQUIRED_CASE_IDS` 完全一致。
AUX_CASE_IDS = AUX_POSITIVE_CASE_IDS + AUX_NEGATIVE_CASE_IDS
_RUNNER_PATH = Path(__file__).resolve().parent / "h8_r3_run_gates.py"

# ── §R3-30 §30.5-4：seal 脱敏/复扫矩阵（辅助判定段二）的“全通过”夹具 ────────────
SEAL_SCAN_FILE = "seal_scan_negtest.json"
SEAL_SCAN_SCHEMA = "resume-assistant/r3-seal-scan-negtest"
SEAL_SCAN_PART_A = [
    ("S1_live_root_forward_slash", 0), ("S2_live_root_json_doubled", 0),
    ("S3_system_data_abs_path", 0), ("S4_unc_path", 0), ("S5_long_context", 0),
    ("S6_public_url_preserved", 0), ("X1_extra_forbidden_hit", 1),
    ("X2_extra_forbidden_absent", 0),
]
SEAL_SCAN_PART_B = [
    ("B1_drive_path_hit", True), ("B2_unc_hit", True), ("B3_unix_home_hit", True),
    ("B4_placeholders_clean", False), ("B5_plain_clean", False),
]
SEAL_SCAN_CASE_IDS = ([c for c, _ in SEAL_SCAN_PART_A]
                      + [c for c, _ in SEAL_SCAN_PART_B]
                      + ["B6_url_masked_roundtrip"])
_SEAL_PATH = Path(__file__).resolve().parent / "h8_r3_seal.py"


def aux_matrix_payload() -> dict:
    """与辅助判定段（一）逐项对齐的 runner 矩阵夹具。

    退出码**极性**必须成立（§R3-30 §30.5-1）：正向 `P00`/`P01` 真实 0 退出，
    负向 `N*` 真实非 0 退出；`N05` 携带两个原始输入的真实非零退出码与
    「未写 gates_run.json」。
    """
    cases: list[dict] = []
    for cid in AUX_CASE_IDS:
        positive = cid in AUX_POSITIVE_CASE_IDS
        rec = {"id": cid, "case": cid, "exit_code": 0 if positive else 2, "ok": True}
        if cid == "N05_empty_only":
            rec["subcases"] = [
                {"input": "", "exit_code": 2, "gates_run_written": False},
                {"input": " , ,", "exit_code": 2, "gates_run_written": False},
            ]
        cases.append(rec)
    return {
        "schema": AUX_SCHEMA, "version": 1,
        "generator": "scripts/h8_r3_run_gates_negtest.py",
        "runner": _RUNNER_PATH.name,
        "runner_sha256": sha256_file(_RUNNER_PATH) if _RUNNER_PATH.is_file() else None,
        "cases": cases, "case_count": len(cases),
        "failures": [], "all_ok": True,
    }


def seal_scan_payload() -> dict:
    """与辅助判定段（二）逐项对齐的 seal 扫描矩阵夹具（14 个精确 case ID）。"""
    cases: list[dict] = []
    for cid, rc in SEAL_SCAN_PART_A:
        cases.append({"id": cid, "case": cid, "part": "A", "stage_rc": rc,
                      "expected_rc": rc, "rescan_zero_hit": True,
                      "text_files": 1, "forbidden_hits": 0,
                      "problems": [], "detail": "", "ok": True})
    for cid, expect_hit in SEAL_SCAN_PART_B:
        cases.append({"id": cid, "case": cid, "part": "B", "expect_hit": expect_hit,
                      "hits": 2 if expect_hit else 0, "problems": [],
                      "detail": "", "ok": True})
    cases.append({"id": "B6_url_masked_roundtrip", "case": "URL 掩蔽零误报且可逆",
                  "part": "B", "masked_hits": 0, "roundtrip_ok": True,
                  "problems": [], "detail": "", "ok": True})
    return {
        "schema": SEAL_SCAN_SCHEMA, "version": 1,
        "generator": "scripts/h8_r3_seal_scan_negtest.py",
        "seal_script": _SEAL_PATH.name,
        "seal_script_sha256": sha256_file(_SEAL_PATH) if _SEAL_PATH.is_file() else None,
        "case_count": len(cases),
        "cases": cases, "failures": [], "all_ok": True,
    }


def _sixgrid_samples() -> list[dict]:
    """合成 18 个通过全部六格后置条件的样本（含 total_s / telemetry）。"""
    _total = {"short": 19.0, "typical": 30.0, "long": 38.0}
    samples = []
    for mode in ("cold", "warm"):
        for size in ("short", "typical", "long"):
            for i in range(3):
                samples.append({
                    "status": "SUCCEEDED", "size": size, "mode": mode, "sample": i + 1,
                    "first_fact_s": 5.5 + i * 0.3, "total_s": _total[size] + i * 0.2,
                    "telemetry": {
                        "logical_calls_eq_1_plus_2F": True,
                        "attempts_all_le_3": True,
                        "no_retry_after_success": True,
                        "embedding_in_0_or_1": True, "embedding_calls": 1,
                        "completion_le_16k": True,
                    },
                })
    return samples


def _valid_payloads(exe_sha: str) -> dict[str, object]:
    """返回每个 Gate 的“全通过”证据 payload（与 manifest 合同逐项对齐）。"""
    return {
        "precheck": (
            "[阻断] Python 编译检查通过\n"
            "[哨兵] 默认 runtime 内容快照一致（未读取/改写；空标准骨架目录新增放行）\n"
            "预检结果：阻断检查全部通过\n"
        ),
        "package_audit": {
            "dir": "pkg", "files": 4044, "total_bytes": 170000000,
            "exe": "pkg/ResumeAssistant.exe", "exe_sha256": exe_sha,
            "block_marker_hits": [], "forbidden_paths": [], "pass": True,
        },
        "pyz_check": {"all_ok": True, "exe": {"sha256": exe_sha}, "modules": {}},
        "failure_matrix": {
            "exe_sha256": exe_sha, "final_pass": True, "cleanup_gate_ok": True,
            "residual_after_rerun": {"leftover": [], "processes": []},
            "cleanup_path": ["iso_runtime"], "first_run_exit": 0, "first_run_failed": False,
            "cleanup": {"ok": True, "runtime_removed": True},
        },
        "content_e2e": {
            "ok": True, "gate_passed": True, "exe": {"sha256": exe_sha},
            "runtime_deleted": True,
            "main_terminal": {"status": "SUCCEEDED", "terminal_error": None},
            "content_checks": {"owner_scope": True, "sentinel_only_current": True,
                               "no_foreign_owner": True, "field_conservation": True},
            "cleanup": {"ok": True, "runtime_removed": True},
        },
        "mainchain_e2e": {
            "ok": True, "gate_passed": True, "exe": {"sha256": exe_sha},
            "runtime_deleted": True, "ui_p4_reached": True,
            "ui_pdf_viewer": {"viewer_ready": True, "viewer_pages": 1},
            "pdf_viewer_same_source_final": {"same_source": True, "viewer_ready": True},
            "artifact_checks": {"word_download_eq_disk_docx": True,
                                "pdf_download_eq_disk_pdf": True, "no_4xx_5xx": True},
            "cleanup": {"ok": True, "runtime_removed": True, "winword_leaked": []},
        },
        "design_fidelity": {
            "exe_sha256": exe_sha,
            "summary": {"pass": 120, "fail": 0, "exit": 0},
            "cleanup": {"ok": True, "runtime_removed": True},
            "keyboard_matrix": {"pages": {
                "/": {"ok": True}, "/experiences": {"ok": True},
                "/records": {"ok": True}, "/privacy": {"ok": True}}},
            "review_1686x1076": {"ok": True, "scrollHeight": 100, "clientHeight": 100},
        },
        "six_grid": {
            "gate_passed": True, "pass": True, "exe": {"sha256": exe_sha},
            "n_samples": 18, "first_fact_median_s": 5.9, "first_fact_max_s": 7.1,
            "first_fact_limit_s": 15, "fail_messages": [],
            # §R3-20：结构化六格样本/格分布/四格降幅/retry ledger（供 manifest 逐项重算）。
            "samples": _sixgrid_samples(),
            "cells": {f"{m}/{s}": 3 for m in ("cold", "warm")
                      for s in ("short", "typical", "long")},
            "four_grid": {c: {"baseline": b, "total_median": round(b * 0.6, 2),
                              "n": 3, "reduction": 0.4, "ok": True}
                          for c, b in {"cold/typical": 89.49, "cold/long": 94.32,
                                       "warm/typical": 84.48, "warm/long": 97.92}.items()},
            "retry_ledger": [{"attempt": 1, "rc": 0, "valid_rows": 3,
                              "discarded_valid_rows": False}],
        },
        "six_grid_negative_selftest": {
            "cases": [{"case": c, "fail_closed": True, "exit_code": 1}
                      for c in ("missing_sample", "dup_sample", "missing_grid", "embedding_2",
                                "false_check", "truncated_evidence", "cleanup_failed")],
            "all_fail_closed": True, "all_exit_codes_nonzero": True,
            "nonzero_exit_failures": [],
        },
        "git_identity_negtest": {
            "positive_control": {"ok": True},
            "cases": [{"id": f"id{i}", "case": f"fixture_{i}", "mode": "build",
                       "exit_code": 1, "ok": True} for i in range(1, 16)],
            "case_ids": [f"id{i}" for i in range(1, 16)],
            "all_ok": True, "failures": [],
        },
        "artifact_auth_matrix": {
            "all_ok": True, "exe": {"sha256": exe_sha},
            "case_ids": AUTH_IDS,
            "cases": [{"id": i, "case": f"fixture_{i}", "ok": True} for i in AUTH_IDS],
            "cleanup": {"ok": True, "runtime_removed": True},
        },
        "atomic_publish_matrix": {
            "all_ok": True, "case_ids": PUBLISH_IDS,
            "cases": [{"id": i, "case": f"fixture_{i}", "ok": True} for i in PUBLISH_IDS],
            "cleanup": {"ok": True, "runtime_removed": True},
        },
        "gate_verdict_negtest": {
            "all_ok": True, "case_ids": VERDICT_NEG_IDS,
            "cases": [{"id": i, "case": f"fixture_{i}", "ok": True} for i in VERDICT_NEG_IDS],
            "positive_control": {"ok": True},
            "cleanup": {"ok": True, "runtime_removed": True},
        },
        "seal_manifest_negtest": {
            "all_ok": True, "ok": True,
            "cases": [{"id": f"N{i}", "case": f"fixture_{i}", "ok": True}
                      for i in range(9)],
            "problems": [],
        },
        # §R3-32 §32.4-2：三项关键交互门的“全通过”夹具。
        "frontend_test": frontend_log_payload(),
        "docreturned_anchor": anchor_log_payload(),
        "docreturned_ui": ui_summary_payload(exe_sha),
    }


def write_valid_evidence(ev_dir: Path, exe_sha: str,
                         *, mutate: dict | None = None) -> dict:
    """写出“全通过”的证据集合 + gates_run.json，返回 gates_run 结构。

    `mutate` 支持按 Gate 替换/删除 payload，或直接覆盖 gates_run 字段（供负向用例使用）：
      {"payload": {gate: {...}}, "drop_payload": [gate], "truncate": [gate],
       "gates_run": {...}, "drop_gate": [gate], "override_exit": {gate: int},
       "override_evidence_sha": {gate: str}}
    """
    mutate = mutate or {}
    ev_dir.mkdir(parents=True, exist_ok=True)
    payloads = _valid_payloads(exe_sha)
    for g, over in (mutate.get("payload") or {}).items():
        payloads[g] = over
    for g in (mutate.get("drop_payload") or []):
        payloads.pop(g, None)

    for g in GATE_ORDER:
        if g not in payloads:
            continue
        fname = EVIDENCE_BY_GATE[g]
        data = payloads[g]
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2)
        if g in (mutate.get("truncate") or []):
            text = text[: max(4, len(text) // 3)]
        (ev_dir / fname).write_text(text, encoding="utf-8")

    # runner 负向矩阵（辅助判定段一）的“全通过”夹具。
    aux = mutate["aux_matrix"] if mutate.get("aux_matrix") is not None else aux_matrix_payload()
    (ev_dir / AUX_MATRIX_FILE).write_text(
        json.dumps(aux, ensure_ascii=False, indent=2), encoding="utf-8")

    # seal 脱敏/复扫矩阵（辅助判定段二）的“全通过”夹具（§R3-30 §30.5-4）。
    sea = (mutate["seal_scan"] if mutate.get("seal_scan") is not None
           else seal_scan_payload())
    (ev_dir / SEAL_SCAN_FILE).write_text(
        json.dumps(sea, ensure_ascii=False, indent=2), encoding="utf-8")

    ended = time.strftime("%Y-%m-%dT%H:%M:%S")
    started = ended
    gates = []
    for g in GATE_ORDER:
        if g in (mutate.get("drop_gate") or []):
            continue
        fname = EVIDENCE_BY_GATE[g]
        fp = ev_dir / fname
        rec = {
            "gate": g,
            "command": f"<fixture> {g}",
            "exit_code": (mutate.get("override_exit") or {}).get(g, 0),
            "started_at_local": started,
            "ended_at_local": ended,
            "evidence": fname,
            "evidence_sha256": sha256_file(fp) if fp.exists() else None,
            "evidence_bytes": fp.stat().st_size if fp.exists() else 0,
            "package_exe_sha256": exe_sha,
            "verdict": True,
            "cleanup_verdict": True,
        }
        for gg, sh in (mutate.get("override_evidence_sha") or {}).items():
            if gg == g:
                rec["evidence_sha256"] = sh
        gates.append(rec)

    # §R3-32 §32.4-1：Gate ID 集合必须唯一且精确——支持注入重复 / 额外记录（供反向用例）。
    for g in (mutate.get("duplicate_gate") or []):
        base = next((r for r in gates if r["gate"] == g), None)
        if base is not None:
            gates.append(dict(base))
    for extra_rec in (mutate.get("extra_gate_records") or []):
        gates.append(dict(extra_rec))

    runs = {
        "_meta": {"generator": "gate_fixtures", "plan_blob": "fixture",
                  "src": "fixture", "package_exe_sha256": exe_sha,
                  "collected_at_local": ended},
        "package": {"files": 4044, "total_bytes": 170000000, "exe_bytes": 16833361,
                    "exe_sha256": exe_sha},
        "gates": gates,
        "all_exit_zero": all(r["exit_code"] == 0 for r in gates),
        "cleanup": {"winword_leaked": [], "residual": []},
        "verdicts": {"fixture": True},
        "problems": [],
        "final_verdict": all(r["exit_code"] == 0 for r in gates),
    }
    for k, v in (mutate.get("gates_run") or {}).items():
        runs[k] = v
    return runs
