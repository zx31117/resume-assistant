"""V2.2.0 R3 返工：总证据 manifest 生成器 / 一致性校验（Git 身份锚点 + 逐 Gate 判定链）。

背景（继承 §R3-15）：旧实现只把 `--src/--handoff` 原样写入 JSON、verify 只检查字段非空，
未与真实 Git object/父链/tree/diff 比较。本版按 §R3-15 §15.4-A 建立**可独立校验的 Git 身份锚点**。

§R3-18 A 追加要求（本版核心变化）：
- **不得只信任顶层汇总布尔值**（`all_exit_zero` / `final_verdict`）。build/verify 必须逐 Gate：
  1) 该 Gate 在 `gates_run.json` 中的记录存在，命令非空，`exit_code` 为整数；
  2) 证据文件存在且 SHA-256 与记录一致；
  3) 证据**内部** verdict 为真（按 Gate 合同从证据 JSON/日志中重新解析）；
  4) 证据记录的包身份等于目标 EXE SHA-256；
  5) 该 Gate 的必需后置条件全部成立（例如主链必须 UI 到达 P4、viewer ready、同源、cleanup）；
  6) cleanup 判定为真。
- **矛盾识别（fail-closed）**：exit 非零但结论成功；exit 为零但结论失败；主链无生成/无 artifact
  但声称成功；UI 未到 P4 却写成主链成功；cleanup 失败但 Gate 成功；单项失败但 `all_exit_zero=true`；
  单项失败但 `final_verdict=true`；字段缺失、JSON 截断、解析失败、证据假成功、包不匹配、必需断言缺失。
- 任一问题：`problems` 可定位、`final_verdict=false`、非零退出，且不输出可被误认为 PASS 的摘要。

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
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

# §R3-20：六格硬门禁的 V2.1.0 同格总时长中位基线（s）。PLAN §5.5「typical/long 总时长
# 相对 V2.1.0 同格中位数降低 ≥25%」的固定参照常量，与 `backend/_e2e_v22_aggregate.py` 同源。
_V21_BASELINE_TOTAL_MEDIAN_S = {
    "cold/typical": 89.49,
    "cold/long": 94.32,
    "warm/typical": 84.48,
    "warm/long": 97.92,
}
_REDUCTION_MIN = 0.25

# ── 逐 Gate 证据合同 ──────────────────────────────────────────── #
# kind: "json" | "log"
#   verdict: 证据内 verdict 的判定表达式（见 _eval_verdict）
#   exe_sha_path: 证据内目标 EXE SHA-256 的取法（json 专用）
#   postconditions: 该 Gate 必须成立的后置条件（见 _eval_postcondition）
#   min_cases / required_case_ids: 矩阵类 Gate 的最低覆盖要求
_GATE_CONTRACTS: dict[str, dict] = {
    "precheck": {
        "evidence": "precheck.log",
        "kind": "log",
        "verdict": ("log_regex", r"预检结果：阻断检查全部通过"),
        "forbid": [r"预检结果：阻断检查 FAILED", r"\[阻断\] 失败"],
        "postconditions": ["log_sentinel_unchanged"],
        "cleanup_required": False,
    },
    "package_audit": {
        "evidence": "package_audit.json",
        "kind": "json",
        "verdict": ("path_true", "pass"),
        "exe_sha_path": "exe_sha256",
        "postconditions": ["no_block_marker_hits", "no_forbidden_paths"],
        "cleanup_required": False,
    },
    "pyz_check": {
        "evidence": "pyz_check.json",
        "kind": "json",
        "verdict": ("path_true", "all_ok"),
        "exe_sha_path": "exe.sha256",
        "postconditions": [],
        "cleanup_required": False,
    },
    "failure_matrix": {
        "evidence": "failure_matrix.json",
        "kind": "json",
        "verdict": ("path_true", "final_pass"),
        "exe_sha_path": "exe_sha256",
        "postconditions": ["cleanup_gate_ok", "no_residual_after_rerun"],
        "cleanup_required": True,
    },
    "content_e2e": {
        "evidence": "content_real_model.json",
        "kind": "json",
        "verdict": ("all_true", ["ok", "gate_passed"]),
        "exe_sha_path": "exe.sha256",
        "postconditions": ["main_terminal_succeeded", "runtime_deleted",
                           "content_checks_all_true"],
        "cleanup_required": True,
    },
    "mainchain_e2e": {
        "evidence": "real_model_e2e.json",
        "kind": "json",
        "verdict": ("all_true", ["ok", "gate_passed"]),
        "exe_sha_path": "exe.sha256",
        "postconditions": ["ui_p4_reached", "viewer_ready", "viewer_same_source",
                           "artifact_checks_all_true", "runtime_deleted",
                           "cleanup_ok"],
        "cleanup_required": True,
    },
    "design_fidelity": {
        "evidence": "design_fidelity.json",
        "kind": "json",
        "verdict": ("fidelity_summary_clean", None),
        "exe_sha_path": "exe_sha256",
        "postconditions": ["cleanup_ok", "keyboard_matrix_all_true",
                           "review_1686x1076_present"],
        "cleanup_required": True,
    },
    "six_grid": {
        "evidence": "six_grid_aggregate.json",
        "kind": "json",
        "verdict": ("all_true", ["gate_passed", "pass"]),
        "exe_sha_path": "exe.sha256",
        "postconditions": [
            # §R3-20：六格必要后置条件必须全部机械重算，不能只信顶层 pass。
            "six_grid_samples_ge_18",
            "six_grid_first_fact_within_limit",
            "six_grid_grid_distribution",
            "six_grid_all_succeeded",
            "six_grid_four_grid_reduction_ge_25",
            "six_grid_embedding_0_or_1",
            "six_grid_logical_calls_1_plus_2F",
            "six_grid_attempts_le_3",
            "six_grid_no_retry_after_success",
            "six_grid_completion_le_16k",
            "six_grid_no_discard",
        ],
        "cleanup_required": False,
    },
    "six_grid_negative_selftest": {
        "evidence": "six_grid_negative_selftest.json",
        "kind": "json",
        "verdict": ("neg_selftest_ok", None),
        "exe_sha_path": None,
        "postconditions": [],
        "cleanup_required": False,
    },
    "git_identity_negtest": {
        "evidence": "git_identity_matrix.json",
        "kind": "json",
        "verdict": ("identity_matrix_ok", None),
        "exe_sha_path": None,
        "postconditions": [],
        "cleanup_required": False,
    },
    "artifact_auth_matrix": {
        "evidence": "artifact_auth_matrix.json",
        "kind": "json",
        "verdict": ("all_true", ["all_ok"]),
        "exe_sha_path": "exe.sha256",
        "postconditions": ["auth_matrix_cases"],
        "required_case_ids": ["A1", "A2", "B1", "B3", "B5", "C1", "C3", "C4",
                              "D1", "E1", "E2", "F1", "F3"],
        "cleanup_required": True,
    },
    "atomic_publish_matrix": {
        "evidence": "atomic_publish_matrix.json",
        "kind": "json",
        "verdict": ("all_true", ["all_ok"]),
        "exe_sha_path": None,
        "postconditions": ["publish_matrix_cases", "cleanup_ok"],
        "required_case_ids": ["P1a", "P1b", "P2", "P3", "P4", "P5", "P6", "P7",
                              "P8", "P9", "P10", "P11", "P12", "P13", "P14", "P15"],
        "cleanup_required": True,
    },
    "gate_verdict_negtest": {
        "evidence": "gate_verdict_negtest.json",
        "kind": "json",
        "verdict": ("all_true", ["all_ok"]),
        "exe_sha_path": None,
        "postconditions": ["verdict_negtest_cases"],
        "min_cases": 13,
        "cleanup_required": False,
    },
    "seal_manifest_negtest": {
        "evidence": "seal_manifest_negtest.json",
        "kind": "json",
        "verdict": ("all_true", ["all_ok", "ok"]),
        "exe_sha_path": None,
        "postconditions": ["seal_manifest_negtest_cases"],
        "cleanup_required": False,
    },
    # ── §R3-32 §32.4：runner 注册并真实运行的 17 门中，此前漏入合同的三项关键交互门 ──
    # 它们承载人工打回的 P4 点击、非工作台返回与组件正反向行为；证据失败必须使总 manifest
    # fail-closed，不得只以「有一条 rc=0 记录」代替逐门语义核验。
    "frontend_test": {
        "evidence": "frontend_test.log",
        "kind": "log",
        "verdict": ("frontend_summary", None),
        "postconditions": [],
        "cleanup_required": False,
    },
    "docreturned_anchor": {
        "evidence": "docreturned_anchor.log",
        "kind": "log",
        "verdict": ("anchor_summary", None),
        "postconditions": [],
        "cleanup_required": False,
    },
    "docreturned_ui": {
        "evidence": "docreturned_ui_summary.json",
        "kind": "json",
        "verdict": ("ui_summary", None),
        "exe_sha_path": None,
        "postconditions": ["ui_required_interactions"],
        "cleanup_required": True,
    },
}

# 每次 build/verify 必须存在的 Gate（缺一即失败）。
_REQUIRED_GATES = list(_GATE_CONTRACTS.keys())

# ── §R3-32 §32.4-2：三项关键交互门的**精确语义常量** ──────────────────────────
# frontend_test：至少 2 个 test files、25 tests 全通过、且不得出现失败摘要。
_FRONTEND_TEST_FILE_COUNT = 2
_FRONTEND_TEST_TOTAL = 25

# docreturned_anchor：29 项 PASS、0 FAIL、终态 `FAIL=0`，且 A1～A7 必需分组在场。
_ANCHOR_PASS_COUNT = 29
_ANCHOR_REQUIRED_GROUPS = ["A1)", "A2)", "A2b)", "A3)", "A4)", "A5/A6)", "A7)"]

# docreturned_ui：72 个**唯一且精确**的 assertion label、逐项 ok=true、pass=72、fails=[]。
_UI_ASSERTION_LABELS = [
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

# §32.4-2：`docreturned_ui` 必须至少覆盖的交互语义（逐项须真实 ok=true）。
_UI_REQUIRED_LABELS = [
    # P4 fact / section / skills 真实鼠标与键盘交互
    "u2.mouse-fact-click", "u2.mouse-fact-select", "u2.mouse-fact-toggle-off",
    "u2.keyboard-enter-select", "u2.keyboard-space-toggle-off",
    "u2.mouse-section-select", "u2.skills-select", "u2.skills-keyboard-toggle",
    "u2.canvas-click-clears", "u2.mutual-exclusion",
    # empty / mismatch 诚实退出（无幽灵热区、无异常）
    "u4.empty-no-hotspots", "u4.empty-no-console-errors",
    "u4.mismatch-no-hotspots", "u4.mismatch-no-console-errors",
    "u4.restore-hotspots",
    # 三条非工作台路由返回工作台，且 Task 不变、零生成 / 零模型请求
    "u5./experiences.returned", "u5./records.returned", "u5./privacy.returned",
    "u5./experiences.task-unchanged", "u5./records.task-unchanged",
    "u5./privacy.task-unchanged",
    "u5./experiences.no-model-request", "u5./records.no-model-request",
    "u5./privacy.no-model-request",
    "u5./experiences.no-new-task-or-generate", "u5./records.no-new-task-or-generate",
    "u5./privacy.no-new-task-or-generate",
    # 单飞语义
    "u6.brandlink-single-flight", "u6.hotspot-dblclick-net-off",
]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _strip_ansi(text: str) -> str:
    """剥离 ANSI 色码后按终端可见文本匹配（vitest 摘要带转义序列）。"""
    return _ANSI_RE.sub("", text)

_IDENTITY_MATRIX_FILE = "git_identity_matrix.json"
_IDENTITY_MATRIX_MIN_CASES = 15

# ── §R3-28 §28.7-3 / §R3-30 §30.5-1：runner 负向矩阵的**离线辅助判定段（一）** ──────
# 它**不是**第 18 个原始 Gate（不写入 `_GATE_CONTRACTS`），但必须进入 manifest 的独立
# 辅助判定：文件 hash、runner SHA、必需 case ID（**唯一且精确集合**）、退出码**极性**
# （正向必须 0、负向必须非 0）、`N05` 逐子例真实退出码与「未写 gates_run.json」、
# `all_ok=true` 且 `failures=[]`。任一缺失/不一致 ⇒ `final_verdict=false` 且非零退出。
#
# §R3-30 §30.2：只校验「退出码是整数」不足以 fail-closed——负向用例被改成 0、N05 子例
# 被删除或被改成 0，都必须在 build 与 verify 两处独立失败。
_AUX_MATRIX_FILE = "run_gates_negtest.json"
_AUX_SCHEMA = "resume-assistant/r3-run-gates-negtest"
_AUX_VERSION = 1
_AUX_POSITIVE_CASE_IDS = ["P00_complete_positive", "P01_manifest_positive"]
_AUX_NEGATIVE_CASE_IDS = [
    "N01_single_failure", "N02_mixed", "N03_all_failure", "N04_unknown_gate",
    "N05_empty_only", "N06_missing_evidence", "N07_partial_all_pass",
    "N08_partial_to_manifest", "N09_aux_missing", "N10_aux_truncated",
    "N11_aux_runner_sha_mismatch", "N12_aux_missing_case",
    "N13_aux_exit_code_escape", "N14_aux_all_ok_false", "N15_aux_failures_nonempty",
    # §R3-30 §30.5-2：负向用例退出码被改为 0 / N05 子例缺失或被改 0 /
    # `gates_run_written=true` / 重复与额外 case ID 的离线反例也必须全部在场。
    "N16_aux_negative_exit_zero", "N17_aux_n05_subcases_missing",
    "N18_aux_n05_subcase_exit_zero", "N19_aux_n05_gates_run_written",
    "N20_aux_duplicate_case_id", "N21_aux_extra_case_id",
]
_AUX_REQUIRED_CASE_IDS = _AUX_POSITIVE_CASE_IDS + _AUX_NEGATIVE_CASE_IDS
_AUX_N05_ID = "N05_empty_only"
# §R3-30 §30.5-1：N05 必须精确包含「空串」与「纯逗号」两个原始输入子例。
_AUX_N05_REQUIRED_INPUTS = ["", " , ,"]
_RUNNER_PATH = Path(__file__).resolve().parent / "h8_r3_run_gates.py"

# ── §R3-30 §30.5-4：seal 脱敏/复扫矩阵的**离线辅助判定段（二）** ──────────────────
# 与 runner 矩阵同理，它也不是原始产品 Gate；checksum 只能证明「字节没变」，
# 不能证明这份矩阵表达的 seal 语义成立，因此必须进入 manifest 最终判定。
_AUX_SEAL_FILE = "seal_scan_negtest.json"
_AUX_SEAL_SCHEMA = "resume-assistant/r3-seal-scan-negtest"
_AUX_SEAL_VERSION = 1
_AUX_SEAL_REQUIRED_CASE_IDS = [
    "S1_live_root_forward_slash", "S2_live_root_json_doubled",
    "S3_system_data_abs_path", "S4_unc_path", "S5_long_context",
    "S6_public_url_preserved", "X1_extra_forbidden_hit",
    "X2_extra_forbidden_absent",
    "B1_drive_path_hit", "B2_unc_hit", "B3_unix_home_hit",
    "B4_placeholders_clean", "B5_plain_clean", "B6_url_masked_roundtrip",
]
_AUX_SEAL_SCRIPT_PATH = Path(__file__).resolve().parent / "h8_r3_seal.py"


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
    """把 ref 解析为不可混淆的 commit 身份。"""
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
    rc, out, err = _git(repo, "status", "--porcelain", "--untracked-files=no")
    if rc != 0:
        return None, f"无法读取 tracked/index 状态: {err}"
    return (out.strip() == ""), None


def _resolve_git_identity(repo, expected_src: str, expected_handoff: str) -> dict:
    """从 repo 现场解析身份并与期望值机械比对。返回完整 git_identity 段（含 checks/verdict）。"""
    checks: dict[str, bool] = {}
    problems: list[str] = []
    actual: dict = {
        "repo_head": None, "head_parents": None, "head_first_parent": None,
        "src": None, "handoff": None,
        "src_to_handoff_name_status": None, "src_to_handoff_paths": None,
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


# ─────────────────── 证据 verdict / 后置条件求值 ─────────────────── #

def _read_evidence(ev_dir: Path, fname: str) -> tuple[object | None, str | None, str | None]:
    """返回 (parsed_or_text, error, raw_text)。JSON 截断/不可解析必须显式报错。"""
    p = ev_dir / fname
    if not p.exists():
        return None, f"missing:{fname}", None
    try:
        raw = p.read_text(encoding="utf-8-sig")
    except Exception as e:  # noqa: BLE001
        return None, f"unreadable:{fname}:{type(e).__name__}", None
    if fname.endswith(".json"):
        try:
            return json.loads(raw), None, raw
        except Exception as e:  # noqa: BLE001
            return None, f"json-parse-failed:{fname}:{type(e).__name__}", raw
    return raw, None, raw


def _eval_verdict(spec, data, raw: str | None, problems: list[str], label: str) -> bool | None:
    """按合同求值证据内部 verdict。返回 True/False；None 表示无法判定（计为失败）。"""
    kind = spec[0]
    if kind == "log_regex":
        if raw is None:
            problems.append(f"{label}: 证据无文本内容")
            return None
        return re.search(spec[1], raw) is not None
    if kind == "path_true":
        val = _get_by_path(data, spec[1])
        if val is None:
            problems.append(f"{label}: 证据缺少 verdict 字段 {spec[1]}")
            return None
        return val is True
    if kind == "all_true":
        out = True
        for pth in spec[1]:
            val = _get_by_path(data, pth)
            if val is None:
                problems.append(f"{label}: 证据缺少 verdict 字段 {pth}")
                out = None
            elif val is not True:
                out = False
        return out
    if kind == "fidelity_summary_clean":
        summary = _get_by_path(data, "summary") or {}
        if not isinstance(summary, dict) or "fail" not in summary:
            problems.append(f"{label}: 证据缺少 summary.fail")
            return None
        return summary.get("fail") == 0 and int(summary.get("exit", 1) or 0) == 0
    if kind == "neg_selftest_ok":
        cases = data.get("cases") or []
        if not cases:
            problems.append(f"{label}: 负向自测无用例")
            return None
        all_fc = all(c.get("fail_closed") is True for c in cases)
        bad_exit = [c.get("case") for c in cases
                    if not (isinstance(c.get("exit_code"), int) and c["exit_code"] != 0)]
        if len(cases) < 7:
            problems.append(f"{label}: 负向自测用例数 {len(cases)} < 7")
        if not all_fc:
            problems.append(f"{label}: 存在非 fail-closed 用例")
        if bad_exit:
            problems.append(f"{label}: 存在零退出码用例 {bad_exit}")
        return bool(all_fc and not bad_exit and len(cases) >= 7)
    if kind == "identity_matrix_ok":
        cases = data.get("cases") or []
        ids = data.get("case_ids") or sorted({c.get("id") for c in cases})
        positive_ok = bool((data.get("positive_control") or {}).get("ok"))
        all_cases_ok = bool(cases) and all(c.get("ok") is True for c in cases)
        if not positive_ok:
            problems.append(f"{label}: 正向对照未通过")
        if not all_cases_ok:
            problems.append(f"{label}: 存在逃逸用例")
        if len(ids) < _IDENTITY_MATRIX_MIN_CASES:
            problems.append(f"{label}: 用例数 {len(ids)} < {_IDENTITY_MATRIX_MIN_CASES}")
        return bool(positive_ok and all_cases_ok
                    and data.get("all_ok") is True
                    and len(ids) >= _IDENTITY_MATRIX_MIN_CASES)
    # ── §R3-32 §32.4-2：三门关键交互门的语义 verdict ──
    if kind == "frontend_summary":
        if raw is None:
            problems.append(f"{label}: 证据无文本内容")
            return None
        text = _strip_ansi(raw)
        files = re.search(r"Test Files\s+(\d+) passed\s*\((\d+)\)", text)
        tests = re.search(r"Tests\s+(\d+) passed\s*\((\d+)\)", text)
        ok = True
        if not files or files.group(1) != str(_FRONTEND_TEST_FILE_COUNT) \
                or files.group(2) != str(_FRONTEND_TEST_FILE_COUNT):
            problems.append(f"{label}: 未确认 {_FRONTEND_TEST_FILE_COUNT} 个 test files 全部通过")
            ok = False
        if not tests or tests.group(1) != str(_FRONTEND_TEST_TOTAL) \
                or tests.group(2) != str(_FRONTEND_TEST_TOTAL):
            problems.append(f"{label}: 未确认 {_FRONTEND_TEST_TOTAL} 个 tests 全部通过")
            ok = False
        if re.search(r"\bfailed\b", text, re.IGNORECASE):
            problems.append(f"{label}: 摘要出现失败记录（failed）")
            ok = False
        return ok
    if kind == "anchor_summary":
        if raw is None:
            problems.append(f"{label}: 证据无文本内容")
            return None
        text = _strip_ansi(raw)
        n_pass = len(re.findall(r"\[PASS\]", text))
        n_fail = len(re.findall(r"\[FAIL\]", text))
        terminal = re.search(r"FAIL\s*=\s*(\d+)", text)
        missing = [g for g in _ANCHOR_REQUIRED_GROUPS if g not in text]
        ok = True
        if n_pass != _ANCHOR_PASS_COUNT:
            problems.append(f"{label}: PASS 项 {n_pass} != {_ANCHOR_PASS_COUNT}")
            ok = False
        if n_fail:
            problems.append(f"{label}: 存在 {n_fail} 项 [FAIL]")
            ok = False
        if not terminal or terminal.group(1) != "0":
            problems.append(f"{label}: 终态未确认 FAIL=0")
            ok = False
        if missing:
            problems.append(f"{label}: 缺少 A1～A7 必需分组 {missing}")
            ok = False
        return ok
    if kind == "ui_summary":
        if not isinstance(data, dict):
            problems.append(f"{label}: 证据不是 JSON 对象")
            return None
        assertions = data.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            problems.append(f"{label}: 证据缺少 assertions")
            return None
        labels = [a.get("label") for a in assertions if isinstance(a, dict)]
        have = set(labels)
        want = set(_UI_ASSERTION_LABELS)
        ok = True
        if len(labels) != len(have):
            problems.append(f"{label}: assertion label 存在重复")
            ok = False
        missing = sorted(want - have)
        extra = sorted(have - want)
        if missing:
            problems.append(f"{label}: 缺少必需 assertion label {missing}")
            ok = False
        if extra:
            problems.append(f"{label}: 存在额外/未知 assertion label {extra}")
            ok = False
        bad = sorted(str(a.get("label")) for a in assertions
                     if isinstance(a, dict) and a.get("ok") is not True)
        if bad:
            problems.append(f"{label}: assertion 未通过 {bad}")
            ok = False
        if data.get("pass") != len(_UI_ASSERTION_LABELS):
            problems.append(f"{label}: pass={data.get('pass')} != {len(_UI_ASSERTION_LABELS)}")
            ok = False
        if data.get("fails") != []:
            problems.append(f"{label}: fails 非空 {data.get('fails')}")
            ok = False
        return ok
    problems.append(f"{label}: 未知 verdict 规格 {kind}")
    return None


def _eval_postcondition(name: str, data, raw: str | None, label: str) -> bool | None:
    """求值 Gate 必需后置条件；None/False 都视为未成立（fail-closed）。"""
    if name == "runtime_deleted":
        return data.get("runtime_deleted") is True
    if name == "cleanup_ok":
        cl = data.get("cleanup") or {}
        if isinstance(cl, dict) and "ok" in cl:
            return cl.get("ok") is True
        if "cleanup_ok" in data:
            return data.get("cleanup_ok") is True
        if isinstance(cl, dict) and "runtime_removed" in cl:
            return cl.get("runtime_removed") is True
        return None
    if name == "main_terminal_succeeded":
        return (_get_by_path(data, "main_terminal.status") == "SUCCEEDED")
    if name == "content_checks_all_true":
        checks = data.get("content_checks")
        if not isinstance(checks, dict) or not checks:
            return None
        return all(v is True for v in checks.values())
    if name == "ui_p4_reached":
        return data.get("ui_p4_reached") is True
    if name == "viewer_ready":
        return _get_by_path(data, "ui_pdf_viewer.viewer_ready") is True
    if name == "viewer_same_source":
        v = _get_by_path(data, "pdf_viewer_same_source_final.same_source")
        return v is True
    if name == "artifact_checks_all_true":
        checks = data.get("artifact_checks")
        if not isinstance(checks, dict) or not checks:
            return None
        return all(v is True for v in checks.values())
    if name == "keyboard_matrix_all_true":
        km = data.get("keyboard_matrix")
        if not isinstance(km, dict) or not km:
            return None
        pages = km.get("pages")
        if not isinstance(pages, dict) or not pages:
            return None
        return all(
            isinstance(v, dict) and v.get("ok") is True
            for v in pages.values()
        )
    if name == "review_1686x1076_present":
        rv = data.get("review_1686x1076")
        return isinstance(rv, dict) and rv.get("ok") is True
    if name == "six_grid_samples_ge_18":
        n = data.get("n_samples")
        return isinstance(n, int) and n >= 18
    if name == "six_grid_first_fact_within_limit":
        med = data.get("first_fact_median_s")
        mx = data.get("first_fact_max_s")
        lim = data.get("first_fact_limit_s") or 15
        return (isinstance(med, (int, float)) and isinstance(mx, (int, float))
                and med <= lim and mx <= lim)
    if name == "six_grid_grid_distribution":
        # 6 格（short/typical/long × cold/warm）每格 n>=3，且恰好 6 格。
        cells = data.get("cells")
        if not isinstance(cells, dict) or len(cells) != 6:
            return None
        return all(isinstance(v, int) and v >= 3 for v in cells.values())
    if name == "six_grid_all_succeeded":
        samples = data.get("samples")
        if not isinstance(samples, list) or not samples:
            return None
        return all(s.get("status") == "SUCCEEDED" for s in samples)
    if name == "six_grid_four_grid_reduction_ge_25":
        # 从逐样本 total_s 独立重算四格（typical/long × cold/warm）降幅，不信任顶层 four_grid。
        samples = data.get("samples")
        if not isinstance(samples, list) or not samples:
            return None
        totals: dict[str, list[float]] = {}
        for s in samples:
            ts = s.get("total_s")
            if s.get("status") == "SUCCEEDED" and isinstance(ts, (int, float)):
                totals.setdefault(f"{s.get('mode')}/{s.get('size')}", []).append(float(ts))
        for cell, base in _V21_BASELINE_TOTAL_MEDIAN_S.items():
            vals = sorted(totals.get(cell, []))
            if len(vals) < 3:
                return False
            med = vals[len(vals) // 2] if len(vals) % 2 else \
                (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
            if (1.0 - med / base) < _REDUCTION_MIN:
                return False
        return True
    if name == "six_grid_embedding_0_or_1":
        samples = data.get("samples")
        if not isinstance(samples, list) or not samples:
            return None
        for s in samples:
            tel = s.get("telemetry")
            if not isinstance(tel, dict):
                return None
            if tel.get("embedding_in_0_or_1") is not True:
                return False
            ec = tel.get("embedding_calls")
            if not (ec == 0 or ec == 1):
                return False
        return True
    if name == "six_grid_logical_calls_1_plus_2F":
        samples = data.get("samples")
        if not isinstance(samples, list) or not samples:
            return None
        for s in samples:
            tel = s.get("telemetry")
            if not isinstance(tel, dict):
                return None
            if tel.get("logical_calls_eq_1_plus_2F") is not True:
                return False
        return True
    if name == "six_grid_attempts_le_3":
        samples = data.get("samples")
        if not isinstance(samples, list) or not samples:
            return None
        for s in samples:
            tel = s.get("telemetry")
            if not isinstance(tel, dict):
                return None
            if tel.get("attempts_all_le_3") is not True:
                return False
        return True
    if name == "six_grid_no_retry_after_success":
        samples = data.get("samples")
        if not isinstance(samples, list) or not samples:
            return None
        for s in samples:
            tel = s.get("telemetry")
            if not isinstance(tel, dict):
                return None
            if tel.get("no_retry_after_success") is not True:
                return False
        return True
    if name == "six_grid_completion_le_16k":
        samples = data.get("samples")
        if not isinstance(samples, list) or not samples:
            return None
        for s in samples:
            tel = s.get("telemetry")
            if not isinstance(tel, dict):
                return None
            if tel.get("completion_le_16k") is not True:
                return False
        return True
    if name == "six_grid_no_discard":
        ledger = data.get("retry_ledger")
        if ledger is None:
            return None
        if not isinstance(ledger, list):
            return None
        for e in ledger:
            if e.get("discarded_valid_rows") or \
                    (e.get("attempt", 1) > 1 and e.get("valid_rows", 0) > 0):
                return False
        return True
    if name == "cleanup_gate_ok":
        return data.get("cleanup_gate_ok") is True
    if name == "no_residual_after_rerun":
        res = data.get("residual_after_rerun")
        if res is None:
            return None
        if isinstance(res, dict):
            return all((not v) for v in res.values())
        return bool(res) is False
    if name == "no_block_marker_hits":
        v = data.get("block_marker_hits")
        return isinstance(v, list) and len(v) == 0
    if name == "no_forbidden_paths":
        v = data.get("forbidden_paths")
        return isinstance(v, list) and len(v) == 0
    if name == "auth_matrix_cases":
        ids = data.get("case_ids") or []
        cases = data.get("cases") or []
        if not cases:
            return None
        return all(c.get("ok") is True for c in cases) and bool(ids)
    if name == "publish_matrix_cases":
        cases = data.get("cases") or []
        if not cases:
            return None
        return all(c.get("ok") is True for c in cases)
    if name == "verdict_negtest_cases":
        cases = data.get("cases") or []
        if not cases:
            return None
        return all(c.get("ok") is True for c in cases)
    if name == "seal_manifest_negtest_cases":
        cases = data.get("cases") or []
        if not cases:
            return None
        return all(c.get("ok") is True for c in cases) and len(cases) >= 8
    if name == "ui_required_interactions":
        # §R3-32 §32.4-2：docreturned_ui 必须真实覆盖 P4 鼠标/键盘、empty/mismatch 诚实退出、
        # 三条非工作台路由返回、Task 不变、零生成/零模型请求与单飞语义（逐项 ok=true）。
        assertions = data.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            return None
        by_label = {a.get("label"): a.get("ok")
                    for a in assertions if isinstance(a, dict)}
        return all(by_label.get(lbl) is True for lbl in _UI_REQUIRED_LABELS)
    if name == "log_sentinel_unchanged":
        if raw is None:
            return None
        return ("默认 runtime 内容快照一致" in raw) and ("FAILED" not in raw)
    return None


def _evidence_exe_sha(data, path: str | None):
    if not path:
        return None, None
    val = _get_by_path(data, path)
    if isinstance(val, dict):
        val = val.get("sha256")
    if isinstance(val, str):
        v = val.lower()
        if _HEX64_RE.match(v):
            return v, None
        fp = Path(val)
        if fp.is_file():
            try:
                return sha256_file(fp), None
            except Exception as e:  # noqa: BLE001
                return None, f"hash-failed:{e}"
        return None, f"exe-path-missing:{val}"
    return None, "exe-sha-not-a-string"


def _gate_evidence_checks(ev_dir: Path, exe_sha: str,
                          gate_runs: dict | None) -> tuple[dict, list[str]]:
    """逐 Gate 交叉核验（本版核心）。返回 (gates_record, problems)。"""
    gates: dict[str, dict] = {}
    problems: list[str] = []

    run_index: dict[str, dict] = {}
    if isinstance(gate_runs, dict):
        for gr in (gate_runs.get("gates") or []):
            if isinstance(gr, dict) and gr.get("gate"):
                run_index[str(gr["gate"])] = gr

    for name, spec in _GATE_CONTRACTS.items():
        label = name
        rec: dict = {"evidence": spec["evidence"], "problems": []}
        fname = spec["evidence"]
        fpath = ev_dir / fname

        # 1) 证据文件存在 + hash
        if not fpath.exists():
            rec.update({"present": False})
            rec["problems"].append("evidence-missing")
            problems.append(f"{label}: 证据缺失 {fname}")
            gates[name] = rec
            continue
        rec["present"] = True
        rec["sha256"] = sha256_file(fpath)
        rec["bytes"] = fpath.stat().st_size

        data, err, raw = _read_evidence(ev_dir, fname)
        if err:
            rec["problems"].append(err)
            problems.append(f"{label}: {err}")
            gates[name] = rec
            continue

        # 2) gates_run 记录存在 + 命令 + 真实退出码
        run = run_index.get(name)
        if run is None:
            rec["problems"].append("gates-run-record-missing")
            problems.append(f"{label}: gates_run.json 缺少该 Gate 的运行记录")
        else:
            rec["exit_code"] = run.get("exit_code")
            rec["command"] = run.get("command")
            rec["started_at_local"] = run.get("started_at_local")
            rec["ended_at_local"] = run.get("ended_at_local")
            rec["recorded_evidence_sha256"] = run.get("evidence_sha256")
            rec["recorded_package_exe_sha256"] = run.get("package_exe_sha256")
            if not isinstance(run.get("exit_code"), int):
                rec["problems"].append("exit-code-not-int")
                problems.append(f"{label}: exit_code 非整数（字段缺失或类型错误）")
            if not (run.get("command") or "").strip():
                rec["problems"].append("command-missing")
                problems.append(f"{label}: 缺少命令记录")
            if run.get("evidence") and run.get("evidence") != fname:
                rec["problems"].append("evidence-name-mismatch")
                problems.append(f"{label}: gates_run 记录的证据名 {run.get('evidence')} != {fname}")
            if run.get("evidence_sha256") and \
                    run.get("evidence_sha256") != rec["sha256"]:
                rec["problems"].append("evidence-hash-mismatch")
                problems.append(f"{label}: 证据 hash 与 gates_run 记录不一致")
            if run.get("package_exe_sha256") and \
                    str(run.get("package_exe_sha256")).lower() != exe_sha:
                rec["problems"].append("package-sha-mismatch")
                problems.append(f"{label}: gates_run 记录的包身份与目标 EXE 不一致")

        # 3) 证据内部 verdict
        verdict = _eval_verdict(spec["verdict"], data, raw, problems, label)
        rec["verdict"] = verdict

        # 4) 证据内包身份
        if spec.get("exe_sha_path"):
            val, verr = _evidence_exe_sha(data, spec["exe_sha_path"])
            rec["exe_sha256"] = val
            rec["exe_sha_match_target"] = (val is not None and val == exe_sha)
            if not rec["exe_sha_match_target"]:
                problems.append(
                    f"{label}: 证据内包身份 {str(val)[:16]}… 与目标 {exe_sha[:16]}… 不一致"
                    f"{(' (' + verr + ')') if verr else ''}")
        else:
            rec["exe_sha_match_target"] = True

        # 5) 必需后置条件
        post: dict[str, object] = {}
        for pc in spec.get("postconditions", []):
            post[pc] = _eval_postcondition(pc, data, raw, label)
            if post[pc] is not True:
                problems.append(f"{label}: 后置条件未成立 {pc}={post[pc]}")
        rec["postconditions"] = post

        # 6) 矩阵最低覆盖
        req_ids = spec.get("required_case_ids")
        if req_ids:
            have = set(data.get("case_ids") or [])
            missing = [c for c in req_ids if c not in have]
            rec["missing_case_ids"] = missing
            if missing:
                problems.append(f"{label}: 缺少必需用例 {missing}")
        min_cases = spec.get("min_cases")
        if min_cases:
            n = len(data.get("case_ids") or data.get("cases") or [])
            rec["cases"] = n
            if n < min_cases:
                problems.append(f"{label}: 用例数 {n} < {min_cases}")

        # 7) 禁止模式（日志类）
        if raw is not None and spec.get("forbid"):
            for pat in spec["forbid"]:
                if re.search(pat, raw):
                    rec["problems"].append(f"forbidden-pattern:{pat}")
                    problems.append(f"{label}: 证据命中禁止模式 {pat}")

        # 8) 矛盾识别
        exit_code = rec.get("exit_code")
        if isinstance(exit_code, int) and verdict is not None:
            if exit_code != 0 and verdict is True:
                rec["problems"].append("contradiction-exit-nonzero-but-verdict-true")
                problems.append(f"{label}: exit={exit_code} 非零但证据结论为成功（矛盾，fail-closed）")
            if exit_code == 0 and verdict is False:
                rec["problems"].append("contradiction-exit-zero-but-verdict-false")
                problems.append(f"{label}: exit=0 但证据结论为失败（矛盾，fail-closed）")

        # 9) 该 Gate 的 cleanup 判定（复用 cleanup_ok 后置条件求值器，保证口径一致：
        #    同时兼容 `cleanup.ok` / 顶层 `cleanup_ok` / `cleanup.runtime_removed` 三种证据形态）
        cleanup_required = spec.get("cleanup_required", False)
        if cleanup_required:
            ok = _eval_postcondition("cleanup_ok", data, raw, label)
            rec["cleanup_verdict"] = ok
            if ok is not True:
                problems.append(f"{label}: cleanup 判定未通过（{ok}）")
                if verdict is True:
                    rec["problems"].append("contradiction-cleanup-failed-but-gate-success")
                    problems.append(f"{label}: cleanup 失败却把 Gate 判为成功（矛盾）")
        else:
            rec["cleanup_verdict"] = None

        gates[name] = rec

    return gates, problems


def _negative_selftest(ev_dir: Path) -> tuple[dict, list[str]]:
    """向后兼容的独立负向自测段（six_grid_negative_selftest.json）。"""
    return _legacy_neg(ev_dir)


def _legacy_neg(ev_dir: Path) -> tuple[dict, list[str]]:
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
    rec = {"present": True, "sha256": sha256_file(p), "bytes": p.stat().st_size,
           "cases": len(cases), "all_fail_closed": all_fc,
           "all_exit_codes_nonzero": all_nonzero,
           "nonzero_exit_failures": bad_exit, "ok": ok}
    if not all_fc:
        problems.append("负向自测存在非 fail-closed 用例")
    if not all_nonzero:
        problems.append(f"负向自测存在零退出码用例: {bad_exit}")
    if len(cases) < 7:
        problems.append(f"负向自测用例数 {len(cases)} < 7")
    return rec, problems


def _identity_matrix_check(ev_dir: Path) -> tuple[dict, list[str]]:
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
    rec = {"present": True, "sha256": sha256_file(p), "bytes": p.stat().st_size,
           "cases": len(cases), "case_ids": case_ids,
           "positive_control_ok": positive_ok, "all_cases_ok": all_cases_ok,
           "all_ok": data.get("all_ok"), "failures": data.get("failures") or [],
           "ok": ok}
    if not positive_ok:
        problems.append("Git 身份矩阵正向对照未通过")
    if not all_cases_ok:
        problems.append("Git 身份矩阵存在逃逸用例")
    if len(case_ids) < _IDENTITY_MATRIX_MIN_CASES:
        problems.append(f"Git 身份矩阵用例数 {len(case_ids)} < {_IDENTITY_MATRIX_MIN_CASES}")
    return rec, problems


def _aux_matrix_check(ev_dir: Path) -> tuple[dict, list[str]]:
    """独立辅助判定段：逐项机械校验 runner 负向矩阵（`run_gates_negtest.json`）。"""
    problems: list[str] = []
    p = ev_dir / _AUX_MATRIX_FILE
    if not p.exists():
        return {"present": False}, [f"缺 runner 负向矩阵证据: {_AUX_MATRIX_FILE}"]
    file_sha = sha256_file(p)
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        return ({"present": True, "sha256": file_sha, "ok": False},
                [f"runner 负向矩阵 JSON 不可解析（截断/损坏）: {type(e).__name__}"])
    if not isinstance(data, dict):
        return ({"present": True, "sha256": file_sha, "ok": False},
                ["runner 负向矩阵顶层不是 JSON 对象"])

    cases = data.get("cases") or []
    case_ids = [c.get("id") for c in cases if isinstance(c, dict)]
    missing = [c for c in _AUX_REQUIRED_CASE_IDS if c not in case_ids]
    duplicate_ids = sorted({i for i in case_ids
                            if isinstance(i, str) and case_ids.count(i) > 1})
    extra_ids = sorted({i for i in case_ids
                        if isinstance(i, str) and i not in _AUX_REQUIRED_CASE_IDS})
    runner_live = sha256_file(_RUNNER_PATH) if _RUNNER_PATH.is_file() else None

    bad_exit: list[str] = []
    not_ok: list[str] = []
    bad_polarity: list[str] = []
    n05_problems: list[str] = []
    for c in cases:
        if not isinstance(c, dict):
            problems.append("runner 负向矩阵存在非对象用例")
            continue
        cid = c.get("id")
        if not isinstance(c.get("exit_code"), int):
            bad_exit.append(str(cid))
        # §R3-30 §30.5-1：正向用例必须真实 0 退出，负向用例必须真实非 0 退出。
        if isinstance(cid, str) and isinstance(c.get("exit_code"), int):
            if cid in _AUX_POSITIVE_CASE_IDS and c.get("exit_code") != 0:
                bad_polarity.append(f"{cid}=正向应为0实际{c.get('exit_code')}")
            if cid in _AUX_NEGATIVE_CASE_IDS and c.get("exit_code") == 0:
                bad_polarity.append(f"{cid}=负向应为非0实际0")
        # §R3-30 §30.5-1：N05 必须精确包含两个原始输入子例，且各子例为真实非零退出
        # 且明确记录「未写 gates_run.json」。
        if cid == _AUX_N05_ID:
            subs = c.get("subcases")
            if not isinstance(subs, list):
                n05_problems.append("N05 缺少 subcases 列表")
            else:
                got = [s.get("input") for s in subs if isinstance(s, dict)]
                if sorted(map(repr, got)) != sorted(map(repr, _AUX_N05_REQUIRED_INPUTS)):
                    n05_problems.append(
                        f"N05 subcases 输入集合必须为 {_AUX_N05_REQUIRED_INPUTS}")
                for s in subs:
                    if not isinstance(s, dict):
                        n05_problems.append("N05 subcase 非对象")
                        continue
                    sc = s.get("exit_code")
                    if not isinstance(sc, int) or sc == 0:
                        n05_problems.append(
                            f"N05 subcase({s.get('input')!r}) 退出码必须为真实非零整数")
                    if s.get("gates_run_written") is not False:
                        n05_problems.append(
                            f"N05 subcase({s.get('input')!r}) 必须记录 gates_run_written=false")
        else:
            for sub in (c.get("subcases") or []):
                if not isinstance(sub, dict) or not isinstance(sub.get("exit_code"), int):
                    bad_exit.append(f"{cid}#subcase")
        if c.get("ok") is not True:
            not_ok.append(str(cid))

    rec = {
        "present": True, "sha256": file_sha, "bytes": p.stat().st_size,
        "schema": data.get("schema"), "version": data.get("version"),
        "generator": data.get("generator"), "runner": data.get("runner"),
        "runner_sha256_recorded": data.get("runner_sha256"),
        "runner_sha256_live": runner_live,
        "case_count_recorded": data.get("case_count"), "case_count_actual": len(cases),
        "case_ids": case_ids, "missing_case_ids": missing,
        "duplicate_case_ids": duplicate_ids, "extra_case_ids": extra_ids,
        "case_id_set_exact": not missing and not duplicate_ids and not extra_ids,
        "all_ok": data.get("all_ok"), "failures": data.get("failures"),
        "bad_exit_codes": bad_exit, "not_ok_cases": not_ok,
        "bad_polarity": bad_polarity, "n05_problems": n05_problems,
    }

    if data.get("schema") != _AUX_SCHEMA:
        problems.append(f"runner 负向矩阵 schema 非 {_AUX_SCHEMA}")
    if data.get("version") != _AUX_VERSION:
        problems.append(f"runner 负向矩阵 version 非 {_AUX_VERSION}")
    if not runner_live:
        problems.append("现场 scripts/h8_r3_run_gates.py 缺失，无法比对 runner SHA")
    elif data.get("runner_sha256") != runner_live:
        problems.append("runner 负向矩阵记录的 runner_sha256 与现场 runner 不一致")
    if not cases:
        problems.append("runner 负向矩阵无用例")
    if missing:
        problems.append(f"runner 负向矩阵缺少必需 case ID: {missing}")
    if duplicate_ids:
        problems.append(f"runner 负向矩阵存在重复 case ID: {duplicate_ids}")
    if extra_ids:
        problems.append(f"runner 负向矩阵存在额外/未知 case ID: {extra_ids}")
    if data.get("case_count") != len(cases):
        problems.append("runner 负向矩阵 case_count 与实际用例数不一致")
    if bad_exit:
        problems.append(f"runner 负向矩阵存在非整数真实退出码: {bad_exit}")
    if bad_polarity:
        problems.append(f"runner 负向矩阵退出码极性错误: {bad_polarity}")
    if n05_problems:
        problems.append(f"runner 负向矩阵 N05 子例证据不满足要求: {n05_problems}")
    if not_ok:
        problems.append(f"runner 负向矩阵存在未通过用例: {not_ok}")
    if data.get("all_ok") is not True:
        problems.append("runner 负向矩阵 all_ok 非 true")
    if data.get("failures") != []:
        problems.append(f"runner 负向矩阵 failures 非空: {data.get('failures')}")

    rec["ok"] = not problems
    return rec, problems


def _aux_seal_matrix_check(ev_dir: Path) -> tuple[dict, list[str]]:
    """离线辅助判定段（二）：逐项机械校验 seal 脱敏/复扫矩阵（`seal_scan_negtest.json`）。

    §R3-30 §30.5-4：校验文件 hash、现场 `h8_r3_seal.py` SHA、schema/version、
    14 个唯一且精确 case ID、逐 case（含子例）预期退出码/结果、`all_ok=true`、
    `failures=[]`。任一缺失/篡改/逃逸/脚本 SHA 不一致都必须压低最终 verdict。
    """
    problems: list[str] = []
    p = ev_dir / _AUX_SEAL_FILE
    if not p.exists():
        return {"present": False}, [f"缺 seal 扫描矩阵证据: {_AUX_SEAL_FILE}"]
    file_sha = sha256_file(p)
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        return ({"present": True, "sha256": file_sha, "ok": False},
                [f"seal 扫描矩阵 JSON 不可解析（截断/损坏）: {type(e).__name__}"])
    if not isinstance(data, dict):
        return ({"present": True, "sha256": file_sha, "ok": False},
                ["seal 扫描矩阵顶层不是 JSON 对象"])

    cases = data.get("cases") or []
    case_ids = [c.get("id") for c in cases if isinstance(c, dict)]
    missing = [c for c in _AUX_SEAL_REQUIRED_CASE_IDS if c not in case_ids]
    duplicate_ids = sorted({i for i in case_ids
                            if isinstance(i, str) and case_ids.count(i) > 1})
    extra_ids = sorted({i for i in case_ids
                        if isinstance(i, str) and i not in _AUX_SEAL_REQUIRED_CASE_IDS})
    script_live = (sha256_file(_AUX_SEAL_SCRIPT_PATH)
                   if _AUX_SEAL_SCRIPT_PATH.is_file() else None)

    bad_result: list[str] = []
    not_ok: list[str] = []
    for c in cases:
        if not isinstance(c, dict):
            problems.append("seal 扫描矩阵存在非对象用例")
            continue
        cid = str(c.get("id"))
        if cid == "B6_url_masked_roundtrip":
            if c.get("masked_hits") != 0 or c.get("roundtrip_ok") is not True:
                bad_result.append(f"{cid}(掩蔽后仍命中或还原不可逆)")
        elif cid.startswith("B"):
            if not isinstance(c.get("hits"), int):
                bad_result.append(f"{cid}(hits 非整数)")
            elif bool(c.get("expect_hit")) != (c.get("hits") > 0):
                bad_result.append(f"{cid}(hits 与 expect_hit 不符)")
        else:  # Part A：真实 stage 子进程退出码必须等于预期
            if not isinstance(c.get("stage_rc"), int) or \
                    not isinstance(c.get("expected_rc"), int):
                bad_result.append(f"{cid}(stage_rc/expected_rc 非整数)")
            elif c.get("stage_rc") != c.get("expected_rc"):
                bad_result.append(f"{cid}(stage_rc={c.get('stage_rc')}"
                                  f"≠expected_rc={c.get('expected_rc')})")
        if c.get("ok") is not True:
            not_ok.append(cid)

    rec = {
        "present": True, "sha256": file_sha, "bytes": p.stat().st_size,
        "schema": data.get("schema"), "version": data.get("version"),
        "generator": data.get("generator"),
        "script_sha256_recorded": data.get("seal_script_sha256"),
        "script_sha256_live": script_live,
        "case_count_recorded": data.get("case_count"), "case_count_actual": len(cases),
        "case_ids": case_ids, "missing_case_ids": missing,
        "duplicate_case_ids": duplicate_ids, "extra_case_ids": extra_ids,
        "case_id_set_exact": not missing and not duplicate_ids and not extra_ids,
        "all_ok": data.get("all_ok"), "failures": data.get("failures"),
        "bad_results": bad_result, "not_ok_cases": not_ok,
    }

    if data.get("schema") != _AUX_SEAL_SCHEMA:
        problems.append(f"seal 扫描矩阵 schema 非 {_AUX_SEAL_SCHEMA}")
    if data.get("version") != _AUX_SEAL_VERSION:
        problems.append(f"seal 扫描矩阵 version 非 {_AUX_SEAL_VERSION}")
    if not script_live:
        problems.append("现场 scripts/h8_r3_seal.py 缺失，无法比对 seal 脚本 SHA")
    elif data.get("seal_script_sha256") != script_live:
        problems.append("seal 扫描矩阵记录的 seal 脚本 SHA 与现场不一致")
    if not cases:
        problems.append("seal 扫描矩阵无用例")
    if missing:
        problems.append(f"seal 扫描矩阵缺少必需 case ID: {missing}")
    if duplicate_ids:
        problems.append(f"seal 扫描矩阵存在重复 case ID: {duplicate_ids}")
    if extra_ids:
        problems.append(f"seal 扫描矩阵存在额外/未知 case ID: {extra_ids}")
    if data.get("case_count") != len(cases):
        problems.append("seal 扫描矩阵 case_count 与实际用例数不一致")
    if bad_result:
        problems.append(f"seal 扫描矩阵退出码/结果不符: {bad_result}")
    if not_ok:
        problems.append(f"seal 扫描矩阵存在未通过用例: {not_ok}")
    if data.get("all_ok") is not True:
        problems.append("seal 扫描矩阵 all_ok 非 true")
    if data.get("failures") != []:
        problems.append(f"seal 扫描矩阵 failures 非空: {data.get('failures')}")

    rec["ok"] = not problems
    return rec, problems


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
        "path": rel, "files": len(files), "total_bytes": total_bytes,
        "exe_path": exe_rel, "exe_bytes": exe.stat().st_size if exe.is_file() else 0,
        "exe_sha256": exe_sha, "bundle": assets[0].name if assets else None,
    }


def _gates_meta_consistency(gate_runs, gates: dict) -> tuple[dict, list[str]]:
    """重算汇总判定并与 gates-meta 自报值比对（不得只信自报字段）。"""
    problems: list[str] = []
    rec: dict = {}
    if not isinstance(gate_runs, dict):
        return {"present": False}, ["gates-meta 缺失或不可解析"]
    runs = [g for g in (gate_runs.get("gates") or []) if isinstance(g, dict)]
    by_name = {str(g.get("gate")): g for g in runs}
    rec["present"] = True
    rec["gate_count"] = len(runs)
    rec["gate_names"] = sorted(by_name)
    names_all = [str(g.get("gate")) for g in runs]
    duplicate = sorted({n for n in names_all if names_all.count(n) > 1})
    extra = sorted({n for n in names_all if n not in _REQUIRED_GATES})
    missing = [n for n in _REQUIRED_GATES if n not in by_name]
    rec["duplicate_gates"] = duplicate
    rec["extra_gates"] = extra
    rec["missing_gates"] = missing
    # §R3-32 §32.4-1：runner 注册集合 / fixture 集合 / `_REQUIRED_GATES` 必须是**唯一且精确的
    # 同一 17 门**；缺失、重复或额外 Gate ID 都必须 fail-closed。
    rec["gate_name_set_exact"] = bool(
        not missing and not duplicate and not extra
        and len(names_all) == len(_REQUIRED_GATES))
    if missing:
        problems.append(f"gates-meta 缺少必需 Gate 记录: {missing}")
    if duplicate:
        problems.append(f"gates-meta 存在重复 Gate 记录: {duplicate}")
    if extra:
        problems.append(f"gates-meta 存在额外/未知 Gate 记录: {extra}")

    exits = [g.get("exit_code") for g in runs]
    rec["exit_codes"] = {str(g.get("gate")): g.get("exit_code") for g in runs}
    recomputed_all_zero = bool(runs) and all(isinstance(e, int) and e == 0 for e in exits)
    rec["recomputed_all_exit_zero"] = recomputed_all_zero
    rec["reported_all_exit_zero"] = gate_runs.get("all_exit_zero")
    if bool(gate_runs.get("all_exit_zero")) != recomputed_all_zero:
        problems.append("all_exit_zero 自报值与逐 Gate 退出码重算结果不一致")
        if any(isinstance(e, int) and e != 0 for e in exits):
            problems.append("存在单项非零退出但 all_exit_zero=true（矛盾）")

    # 逐 Gate 结论一致性（自报 verdicts 不得覆盖实际证据结论）
    gate_ok = all(
        (g.get("verdict") is True)
        and (g.get("exit_code") == 0)
        and (g.get("exe_sha_match_target", True) is True)
        and all(v is True for v in (g.get("postconditions") or {}).values())
        and (g.get("cleanup_verdict") in (None, True))
        for g in gates.values()
    ) and len(gates) == len(_GATE_CONTRACTS)
    rec["recomputed_gates_ok"] = gate_ok
    rec["reported_final_verdict"] = gate_runs.get("final_verdict")
    if bool(gate_runs.get("final_verdict")) and not gate_ok:
        problems.append("final_verdict=true 但逐 Gate 交叉核验未全部通过（矛盾）")

    cleanup = gate_runs.get("cleanup")
    rec["reported_cleanup"] = cleanup
    if isinstance(cleanup, dict):
        bad = [k for k, v in cleanup.items()
               if (k == "winword_leaked" and v) or (isinstance(v, bool) and not v)]
        rec["cleanup_bad_keys"] = bad
        if bad:
            problems.append(f"gates-meta cleanup 判定存在失败项: {bad}")
    else:
        problems.append("gates-meta 缺少 cleanup 判定")
    return rec, problems


def _emit(mode: str, verdict: bool, problems: list[str]) -> None:
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
    if not _HEX64_RE.match(exe_sha):
        problems.append("--exe-sha 必须是完整 64 位小写 SHA-256")

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

    # 3) gates_run 汇总。
    gate_runs = None
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
        problems.append("缺少 --gates-meta，无法逐 Gate 核对命令/退出码/cleanup")

    # 4) 逐 Gate 交叉核验（核心）。
    gates, gate_problems = _gate_evidence_checks(ev_dir, exe_sha, gate_runs)
    problems.extend(gate_problems)

    # 5) 汇总一致性（不得只信自报布尔值）。
    meta_rec, meta_problems = _gates_meta_consistency(gate_runs, gates)
    problems.extend(meta_problems)

    # 6) 负向自测 + Git 身份矩阵（独立段，兼容既有合同）。
    neg_rec, neg_problems = _negative_selftest(ev_dir)
    problems.extend(neg_problems)
    idm_rec, idm_problems = _identity_matrix_check(ev_dir)
    problems.extend(idm_problems)
    aux_rec, aux_problems = _aux_matrix_check(ev_dir)
    problems.extend(aux_problems)
    aux_seal_rec, aux_seal_problems = _aux_seal_matrix_check(ev_dir)
    problems.extend(aux_seal_problems)

    cleanup = (gate_runs or {}).get("cleanup") if isinstance(gate_runs, dict) else None
    cleanup_ok = None
    if isinstance(cleanup, dict):
        cleanup_ok = not [k for k, v in cleanup.items()
                          if (k == "winword_leaked" and v) or (isinstance(v, bool) and not v)]

    manifest = {
        "_meta": {
            "generator": "scripts/h8_r3_manifest.py",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "plan_blob": PLAN_BLOB,
            "identity_schema": IDENTITY_SCHEMA,
            "identity_version": IDENTITY_VERSION,
        },
        "identity": {
            "src": expected_src, "handoff": expected_handoff, "plan_blob": PLAN_BLOB,
            "exe_sha256": exe_sha, "bundle": args.bundle, "package": pkg,
        },
        "git_identity": git_identity,
        "gates": gates,
        "gates_meta": meta_rec,
        "negative_selftest": neg_rec,
        "identity_matrix": idm_rec,
        "aux_matrix": aux_rec,
        "aux_seal_matrix": aux_seal_rec,
        "gate_runs": gate_runs,
        "cleanup": cleanup,
        "verdicts": {
            "plan_blob_ok": True,
            "git_identity_ok": git_identity["verdict"],
            "package_ok": bool(pkg and pkg["exe_sha256"] == exe_sha
                               and (not args.bundle or pkg["bundle"] == args.bundle)),
            "gates_ok": all(
                (g.get("present") is True)
                and (g.get("verdict") is True)
                and (g.get("exit_code") == 0)
                and (g.get("exe_sha_match_target") is True)
                and all(v is True for v in (g.get("postconditions") or {}).values())
                and (g.get("cleanup_verdict") in (None, True))
                and not (g.get("problems") or [])
                for g in gates.values()
            ) and len(gates) == len(_GATE_CONTRACTS),
            "negative_selftest_ok": bool(neg_rec.get("ok")),
            "identity_matrix_ok": bool(idm_rec.get("ok")),
            "aux_matrix_ok": bool(aux_rec.get("ok")),
            "aux_seal_matrix_ok": bool(aux_seal_rec.get("ok")),
            "gates_meta_ok": bool(meta_rec.get("recomputed_gates_ok")),
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

    if m.get("final_verdict") is not True:
        problems.append("manifest 自身 final_verdict 非 true")
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

    # A) manifest 内记录值 == 期望值。
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

        if handoff_id and handoff_id.get("type") == "commit":
            parents = handoff_id.get("parents") or []
            if len(parents) != 1:
                problems.append("现场 HANDOFF 不是单 parent commit")
            elif parents[0] != expected_src:
                problems.append("现场 HANDOFF 唯一 parent 不等于 SRC")

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
                if actual.get("src_to_handoff_name_status") != ns:
                    problems.append("manifest 记录的 SRC..HANDOFF diff 与现场不一致")

    # C) 包身份自洽 + 可选重算。
    pkg = ident.get("package")
    exe_sha = (ident.get("exe_sha256") or "").lower()
    if not pkg:
        problems.append("identity.package 缺失")
    else:
        rec_hash = (pkg.get("exe_sha256") or "").lower()
        if not _HEX64_RE.match(rec_hash):
            problems.append("identity.package.exe_sha256 非法")
        if rec_hash != exe_sha:
            problems.append("identity.package.exe_sha256 与 identity.exe_sha256 不一致")
        if not pkg.get("exe_bytes"):
            problems.append("identity.package.exe_bytes 为空")

    # D) 逐 Gate 字段级复检（不依赖 build 时的结论）。
    gates = m.get("gates") or {}
    missing_gates = [n for n in _REQUIRED_GATES if n not in gates]
    if missing_gates:
        problems.append(f"gates 段缺少必需 Gate: {missing_gates}")
    extra_gates = [n for n in gates if n not in _REQUIRED_GATES]
    if extra_gates:
        problems.append(f"gates 段存在额外/未知 Gate: {extra_gates}")
    if len(gates) != len(_REQUIRED_GATES):
        problems.append(f"gates 段数量 {len(gates)} != {len(_REQUIRED_GATES)}")
    for name, g in gates.items():
        if g.get("present") is not True:
            problems.append(f"{name}: 证据不存在")
            continue
        if g.get("verdict") is not True:
            problems.append(f"{name}: 证据 verdict 非 true")
        if g.get("exit_code") != 0:
            problems.append(f"{name}: 真实退出码 {g.get('exit_code')} 非 0")
        if g.get("exe_sha_match_target") is not True:
            problems.append(f"{name}: 证据内包身份与目标 EXE 不一致")
        for pc, val in (g.get("postconditions") or {}).items():
            if val is not True:
                problems.append(f"{name}: 后置条件 {pc} 未成立（{val}）")
        if g.get("cleanup_verdict") is False:
            problems.append(f"{name}: cleanup 判定失败")
        if g.get("problems"):
            problems.append(f"{name}: 交叉核验问题 {g['problems']}")

    # E) 现场重算证据 hash。
    ev_dir = None
    if args.evidence_dir:
        cand = Path(args.evidence_dir)
        if cand.is_dir():
            ev_dir = cand
        else:
            problems.append("--evidence-dir 不存在")
    if ev_dir is not None:
        for name, g in gates.items():
            fname = g.get("evidence")
            if not fname:
                continue
            fp = ev_dir / fname
            if not fp.exists():
                problems.append(f"evidence 缺失: {fname}")
            elif g.get("sha256") and sha256_file(fp) != g.get("sha256"):
                problems.append(f"evidence hash 与现场不一致: {fname}")
        for seg, fname, key in (
            ("negative_selftest", "six_grid_negative_selftest.json", "negative_selftest"),
            ("identity_matrix", _IDENTITY_MATRIX_FILE, "identity_matrix"),
            ("aux_matrix", _AUX_MATRIX_FILE, "aux_matrix"),
            ("aux_seal_matrix", _AUX_SEAL_FILE, "aux_seal_matrix"),
        ):
            rec = m.get(key) or {}
            if rec.get("present"):
                fp = ev_dir / fname
                if not fp.exists():
                    problems.append(f"evidence 缺失: {fname}")
                elif rec.get("sha256") and sha256_file(fp) != rec.get("sha256"):
                    problems.append(f"{seg} evidence hash 与现场不一致")

    # F) 顶层判定一致性。
    v = m.get("verdicts") or {}
    for k in ("git_identity_ok", "package_ok", "gates_ok", "negative_selftest_ok",
              "identity_matrix_ok", "aux_matrix_ok", "aux_seal_matrix_ok",
              "gates_meta_ok"):
        if v.get(k) is not True:
            problems.append(f"verdicts.{k} 非 true")

    # G) runner 负向矩阵辅助判定段的独立复核（不依赖 build 时的结论）。
    aux = m.get("aux_matrix") or {}
    if aux.get("present") is not True:
        problems.append("manifest 缺少 runner 负向矩阵辅助判定段")
    else:
        if aux.get("all_ok") is not True:
            problems.append("aux_matrix all_ok 非 true")
        if aux.get("failures") != []:
            problems.append("aux_matrix failures 非空")
        if aux.get("missing_case_ids"):
            problems.append(f"aux_matrix 缺少必需 case ID: {aux.get('missing_case_ids')}")
        if aux.get("duplicate_case_ids"):
            problems.append(f"aux_matrix 存在重复 case ID: {aux.get('duplicate_case_ids')}")
        if aux.get("extra_case_ids"):
            problems.append(f"aux_matrix 存在额外/未知 case ID: {aux.get('extra_case_ids')}")
        if aux.get("case_id_set_exact") is not True:
            problems.append("aux_matrix case ID 非唯一且精确集合")
        if aux.get("bad_exit_codes"):
            problems.append("aux_matrix 存在非整数真实退出码")
        if aux.get("bad_polarity"):
            problems.append(f"aux_matrix 退出码极性错误: {aux.get('bad_polarity')}")
        if aux.get("n05_problems"):
            problems.append(f"aux_matrix N05 子例证据不满足要求: {aux.get('n05_problems')}")
        if aux.get("not_ok_cases"):
            problems.append("aux_matrix 存在未通过用例")
        if aux.get("case_count_recorded") != aux.get("case_count_actual"):
            problems.append("aux_matrix case_count 与实际用例数不一致")
        live_now = sha256_file(_RUNNER_PATH) if _RUNNER_PATH.is_file() else None
        if not aux.get("runner_sha256_live") or \
                aux.get("runner_sha256_recorded") != aux.get("runner_sha256_live"):
            problems.append("aux_matrix runner SHA 记录与现场不一致")
        if live_now != aux.get("runner_sha256_live"):
            problems.append("aux_matrix runner SHA 现场值已变化")

    # H) seal 扫描矩阵辅助判定段的独立复核（不依赖 build 时的结论）。
    auxs = m.get("aux_seal_matrix") or {}
    if auxs.get("present") is not True:
        problems.append("manifest 缺少 seal 扫描矩阵辅助判定段")
    else:
        if auxs.get("all_ok") is not True:
            problems.append("aux_seal_matrix all_ok 非 true")
        if auxs.get("failures") != []:
            problems.append("aux_seal_matrix failures 非空")
        if auxs.get("missing_case_ids"):
            problems.append(f"aux_seal_matrix 缺少必需 case ID: {auxs.get('missing_case_ids')}")
        if auxs.get("duplicate_case_ids"):
            problems.append(f"aux_seal_matrix 存在重复 case ID: {auxs.get('duplicate_case_ids')}")
        if auxs.get("extra_case_ids"):
            problems.append(f"aux_seal_matrix 存在额外/未知 case ID: {auxs.get('extra_case_ids')}")
        if auxs.get("case_id_set_exact") is not True:
            problems.append("aux_seal_matrix case ID 非唯一且精确集合")
        if auxs.get("bad_results"):
            problems.append(f"aux_seal_matrix 退出码/结果不符: {auxs.get('bad_results')}")
        if auxs.get("not_ok_cases"):
            problems.append("aux_seal_matrix 存在未通过用例")
        if auxs.get("case_count_recorded") != auxs.get("case_count_actual"):
            problems.append("aux_seal_matrix case_count 与实际用例数不一致")
        seal_live_now = (sha256_file(_AUX_SEAL_SCRIPT_PATH)
                         if _AUX_SEAL_SCRIPT_PATH.is_file() else None)
        if not auxs.get("script_sha256_live") or \
                auxs.get("script_sha256_recorded") != auxs.get("script_sha256_live"):
            problems.append("aux_seal_matrix seal 脚本 SHA 记录与现场不一致")
        if seal_live_now != auxs.get("script_sha256_live"):
            problems.append("aux_seal_matrix seal 脚本 SHA 现场值已变化")
    if v.get("cleanup_ok") is not True:
        problems.append("verdicts.cleanup_ok 非 true")
    meta = m.get("gates_meta") or {}
    if meta.get("recomputed_all_exit_zero") is not True:
        problems.append("逐 Gate 退出码重算结果非全 0")
    if meta.get("recomputed_gates_ok") is not True:
        problems.append("逐 Gate 交叉核验重算结论非通过")
    if meta.get("gate_name_set_exact") is not True:
        problems.append("gates_meta 记录集合非唯一且精确 17 门")
    if meta.get("missing_gates"):
        problems.append(f"gates_meta 缺少必需 Gate 记录: {meta.get('missing_gates')}")
    if meta.get("duplicate_gates"):
        problems.append(f"gates_meta 存在重复 Gate 记录: {meta.get('duplicate_gates')}")
    if meta.get("extra_gates"):
        problems.append(f"gates_meta 存在额外/未知 Gate 记录: {meta.get('extra_gates')}")
    if meta.get("gate_count") != len(_REQUIRED_GATES):
        problems.append(f"gates_meta.gate_count={meta.get('gate_count')} != {len(_REQUIRED_GATES)}")

    ok = not problems
    # §R3-20：控制台摘要必须使用**本次 verify 重新计算**的 verdict，不得打印存量 manifest 的
    # true（否则失败时摘要仍显示 final_verdict=True，与 JSON/退出码冲突）。
    print(f"[verify] final_verdict={bool(ok)} "
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
