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
