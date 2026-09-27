#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 R3-26 返工：Gate runner `--only` fail-closed 的**离线正反向矩阵**。

对应 RESULT §R3-26 §26.5-2。本矩阵不依赖任何真实模型 / 浏览器 / 付费 Gate：
它在一次性临时“迷你仓库”里放置**逐字节复制的真实 runner**（`scripts/h8_r3_run_gates.py`）
与按 runner 自身 `gate_specs()` 契约生成的 fake Gate 脚本，然后**真实启动 runner 子进程**，
读取其真实退出码与 `gates_run.json`。

覆盖用例（逐例断言：进程退出码、逐 Gate 记录、汇总字段、manifest 判定一致）：
  P00_complete_positive   完整 17 门正向控制（全部 Gate exit 0）→ 必须 PASS
  N01_single_failure      单个已选 Gate 失败 → 失败记录必须保留、顶层非绿
  N02_mixed               成功/失败混合 → 成功与失败记录都在
  N03_all_failure         全部已选 Gate 失败 → 逐项非零、顶层非绿
  N04_unknown_gate        `--only` 含未知 Gate → fail-closed（不写记录）
  N05_empty_only          `--only` 为空选择（空串 / 纯逗号）→ fail-closed
  N06_missing_evidence    已选 Gate exit 0 但证据缺失 → fail-closed
  N07_partial_all_pass    子集全部成功 → partial 显式标记且顶层非绿（不得假绿）
  N08_partial_to_manifest 把 N07 的 partial `gates_run.json` 送 manifest → manifest 必须拒绝
  P01_manifest_positive   与 runner 合同一致的全通过夹具送 manifest → 必须接受

§R3-28 §28.7-4：runner 负向矩阵被 manifest 消费时的反向用例（每例必须非零退出 + final_verdict=false）：
  N09_aux_missing          矩阵证据缺失
  N10_aux_truncated        矩阵 JSON 截断/损坏
  N11_aux_runner_sha_mismatch  矩阵记录 runner_sha256 与现场 runner 不符
  N12_aux_missing_case     矩阵缺少必需 case ID
  N13_aux_exit_code_escape 矩阵中任一 case 真实退出码逃逸（非整数）
  N14_aux_all_ok_false     矩阵 all_ok 非 true
  N15_aux_failures_nonempty 矩阵 failures 非空

退出码 0 = 全部用例成立；非 0 = 存在逃逸（并写明 failures）。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNNER = HERE / "h8_r3_run_gates.py"
_MANIFEST = HERE / "h8_r3_manifest.py"

sys.path.insert(0, str(HERE))
import h8_r3_run_gates as RUN  # noqa: E402
import h8_r3_gate_verdict_negtest as GV  # noqa: E402
import h8_r3_gate_fixtures as FX  # noqa: E402


def sha256_file(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── fake Gate 脚本模板（只在一次性临时目录里生成，不参与产品运行时）──
_FAKE_PY = '''# -*- coding: utf-8 -*-
"""负向矩阵一次性 fake Gate：{gate}（不参与产品运行时）。"""
import json
import os
import sys

CFG = {cfg}
GATE = {gate}
WRITE_SRC = {write}


def _target(argv):
    # src 型 Gate：fake 先把证据写到 runner 会 copy 的源路径（与 evidence-dir 无关）；
    # 其余带 --out/--json 的 Gate：从本次 argv 现场取目标，避免耦合具体 evidence-dir。
    if WRITE_SRC:
        return WRITE_SRC
    for i, a in enumerate(argv):
        if a in ("--out", "--json") and i + 1 < len(argv):
            return argv[i + 1]
    return None


def main() -> int:
    try:
        cfg = json.load(open(CFG, encoding="utf-8"))
    except Exception:
        cfg = {{}}
    rc = int((cfg.get("rc") or {{}}).get(GATE, 0))
    target = _target(sys.argv[1:])
    if target and GATE not in (cfg.get("no_evidence") or []):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            json.dump({{"fake_gate": GATE, "ok": True}}, fh, ensure_ascii=False)
    print("[fake] " + GATE + " rc=" + str(rc))
    return rc


if __name__ == "__main__":
    sys.exit(main())
'''

_FAKE_MJS = '''// 负向矩阵一次性 fake frontend Gate（不参与产品运行时）。
import fs from 'node:fs';

const CFG = {cfg};
const GATE = {gate};

let cfg = {{}};
try {{ cfg = JSON.parse(fs.readFileSync(CFG, 'utf8')); }} catch (e) {{}}
const rc = Number(((cfg.rc || {{}})[GATE]) ?? 0);
console.log('[fake] ' + GATE + ' rc=' + rc);
process.exit(rc);
'''


def _src_write_path(spec: dict, src_map: dict) -> str | None:
    """仅 src 型 Gate 需要固定写出路径（runner 会把它 copy 到 evidence-dir）；
    其余 Gate 的 fake 在运行时从 argv 的 `--out/--json` 现场取目标。"""
    if spec["src"] is not None:
        return str(src_map[spec["name"]])
    return None


def _build_mini_repo(root: Path) -> dict:
    """与真实仓库同构的最小目录：逐字节复制真实 runner + 按 gate_specs 生成 fake Gate。"""
    mini_scripts = root / "scripts"
    (root / "backend").mkdir(parents=True, exist_ok=True)
    (root / "frontend").mkdir(parents=True, exist_ok=True)
    mini_scripts.mkdir(parents=True, exist_ok=True)
    exe = root / "dist" / "ResumeAssistant" / "ResumeAssistant.exe"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_bytes(b"FAKE-EXE" * 64)
    shutil.copy2(RUNNER, mini_scripts / "h8_r3_run_gates.py")

    ev = root / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    cfg_path = root / "fake_config.json"
    cfg_path.write_text("{}", encoding="utf-8")

    specs = RUN.gate_specs(str(exe), ev)
    mini_va = root / "validation-artifacts" / "h8"
    src_map = {s["name"]: mini_va / s["src"].relative_to(RUN.VA)
               for s in specs if s["src"] is not None}

    generated: list[dict] = []
    for spec in specs:
        # spec["cwd"] 来自真实仓库（ROOT/BACKEND/FRONTEND 常量）；fake 必须落在**迷你仓库**
        # 的同名相对目录里，否则会污染真实仓库、且 mini runner 也找不到脚本。
        rel_cwd = Path(spec["cwd"]).resolve().relative_to(ROOT)
        script_rel = Path(spec["argv"][1])
        script_abs = root / rel_cwd / script_rel
        script_abs.parent.mkdir(parents=True, exist_ok=True)
        write = _src_write_path(spec, src_map)
        if spec["argv"][0] == "node":
            body = _FAKE_MJS.format(cfg=json.dumps(str(cfg_path)),
                                    gate=json.dumps(spec["name"]))
        else:
            body = _FAKE_PY.format(cfg=json.dumps(str(cfg_path)),
                                   gate=json.dumps(spec["name"]),
                                   write=repr(write))
        script_abs.write_text(body, encoding="utf-8")
        generated.append({"gate": spec["name"], "script": str(script_rel),
                          "writer": write})

    return {"root": root, "exe": exe, "ev": ev, "cfg": cfg_path,
            "runner": mini_scripts / "h8_r3_run_gates.py",
            "names": [s["name"] for s in specs], "generated": generated}


def _run_runner(mini: dict, *, only: str | None, ev_dir: Path,
                rc: dict | None = None, no_evidence: list | None = None) -> dict:
    mini["cfg"].write_text(json.dumps({"rc": rc or {}, "no_evidence": no_evidence or []}),
                           encoding="utf-8")
    argv = [sys.executable, str(mini["runner"]),
            "--exe", str(mini["exe"]), "--evidence-dir", str(ev_dir)]
    if only is not None:
        argv += ["--only", only]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=900)
    meta = None
    gm = ev_dir / "gates_run.json"
    if gm.is_file():
        try:
            meta = json.loads(gm.read_text(encoding="utf-8-sig"))
        except Exception:
            meta = None
    return {"rc": p.returncode, "stdout": p.stdout, "stderr": p.stderr,
            "gates_run_path": gm, "meta": meta,
            "meta_written": gm.is_file()}


def _summary(meta: dict | None) -> dict:
    if not isinstance(meta, dict):
        return {}
    return {"partial": meta.get("partial"),
            "unexecuted_gates": meta.get("unexecuted_gates"),
            "all_exit_zero": meta.get("all_exit_zero"),
            "final_verdict": meta.get("final_verdict"),
            "executed_all_exit_zero": meta.get("executed_all_exit_zero"),
            "gate_count": len(meta.get("gates") or []),
            "exit_codes": {str(g.get("gate")): g.get("exit_code")
                           for g in (meta.get("gates") or [])}}


def _records(meta: dict | None) -> dict:
    if not isinstance(meta, dict):
        return {}
    return {str(g.get("gate")): {"exit_code": g.get("exit_code"),
                                 "evidence": g.get("evidence"),
                                 "evidence_present": bool(g.get("evidence_sha256"))}
            for g in (meta.get("gates") or [])}


def _manifest(mode: str, argv: list[str]) -> dict:
    p = subprocess.run([sys.executable, str(_MANIFEST), mode, *argv],
                       capture_output=True, text=True, timeout=300)
    payload = None
    for line in reversed((p.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                payload = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    return {"rc": p.returncode, "payload": payload or {},
            "stdout": p.stdout, "stderr": p.stderr}


def _case(case_id: str, name: str, run: dict, *, expect_rc_nonzero: bool,
          partial: bool, expect_gate_count: int, expected_exits: dict | None = None,
          detail: str = "", extra_ok: bool = True,
          expect_meta_written: bool = True) -> dict:
    problems: list[str] = []
    meta = run["meta"]
    summ = _summary(meta)
    if expect_rc_nonzero and run["rc"] == 0:
        problems.append(f"进程退出码应为非零，实际 {run['rc']}")
    if not expect_rc_nonzero and run["rc"] != 0:
        problems.append(f"进程退出码应为 0，实际 {run['rc']}: {(run['stderr'] or '')[-300:]}")
    if not expect_meta_written:
        if run["meta_written"]:
            problems.append("非法输入（未知 Gate / 空选择）时不应写出 gates_run.json")
    elif not run["meta_written"]:
        problems.append("未写出 gates_run.json")
    elif meta is None:
        problems.append("gates_run.json 不可解析")
    else:
        if summ["gate_count"] != expect_gate_count:
            problems.append(f"逐 Gate 记录数应为 {expect_gate_count}，实际 {summ['gate_count']}")
        if summ["partial"] is not partial:
            problems.append(f"partial 应为 {partial}，实际 {summ['partial']}")
        if partial and not summ["unexecuted_gates"]:
            problems.append("partial run 未显式列出未执行 Gate")
        if bool(summ["all_exit_zero"]) is not (not expect_rc_nonzero):
            problems.append(f"all_exit_zero 应为 {not expect_rc_nonzero}，实际 {summ['all_exit_zero']}")
        if bool(summ["final_verdict"]) is not (not expect_rc_nonzero):
            problems.append(f"final_verdict 应为 {not expect_rc_nonzero}，实际 {summ['final_verdict']}")
        for g, want in (expected_exits or {}).items():
            got = summ["exit_codes"].get(g, "<missing>")
            if got != want:
                problems.append(f"{g} 记录退出码应为 {want}，实际 {got}（失败记录不得被剔除）")
    return {"id": case_id, "case": name, "exit_code": run["rc"],
            "problems": problems + ([] if extra_ok else ["外部断言失败"]),
            "detail": detail, "summary": summ, "records": _records(meta),
            "ok": (not problems) and extra_ok}


def run_matrix(root: Path) -> dict:
    mini = _build_mini_repo(root)
    all_names = list(mini["names"])
    subset = ["precheck", "package_audit", "pyz_check"]
    unexecuted_for_subset = [n for n in all_names if n not in subset]

    cases: list[dict] = []

    # P00：完整 17 门正向控制（不传 --only）
    ev = root / "ev_p00"
    run = _run_runner(mini, only=None, ev_dir=ev, rc={})
    p00 = _case("P00_complete_positive", "完整 17 门正向控制", run, expect_rc_nonzero=False,
                partial=False, expect_gate_count=len(all_names),
                detail=f"全部 {len(all_names)} 门 fake Gate exit 0 时必须完整 PASS",
                extra_ok=bool(run["meta"]) and not (run["meta"].get("unexecuted_gates")))
    cases.append(p00)

    # N01：单个已选 Gate 失败
    ev = root / "ev_n01"
    run = _run_runner(mini, only=",".join(subset), ev_dir=ev, rc={"precheck": 1})
    n01 = _case("N01_single_failure", "单个已选 Gate 失败", run, expect_rc_nonzero=True,
                partial=True, expect_gate_count=3, expected_exits={"precheck": 1},
                detail="失败的 precheck 记录必须保留且 exit_code=1")
    n01["unexecuted_ok"] = bool(run["meta"]) and \
        run["meta"].get("unexecuted_gates") == unexecuted_for_subset
    if not n01["unexecuted_ok"]:
        n01["ok"] = False
        n01["problems"].append("unexecuted_gates 与预期未执行集合不一致")
    cases.append(n01)

    # N02：成功/失败混合
    ev = root / "ev_n02"
    run = _run_runner(mini, only=",".join(subset), ev_dir=ev, rc={"package_audit": 1})
    n02 = _case("N02_mixed", "成功/失败混合", run, expect_rc_nonzero=True,
                partial=True, expect_gate_count=3,
                expected_exits={"precheck": 0, "package_audit": 1, "pyz_check": 0},
                detail="成功与失败记录必须同时存在，且顶层非绿")
    cases.append(n02)

    # N03：全部已选 Gate 失败
    ev = root / "ev_n03"
    run = _run_runner(mini, only=",".join(subset), ev_dir=ev,
                      rc={g: 2 for g in subset})
    n03 = _case("N03_all_failure", "全部已选 Gate 失败", run, expect_rc_nonzero=True,
                partial=True, expect_gate_count=3,
                expected_exits={g: 2 for g in subset},
                detail="逐项非零退出，顶层必须非绿")
    cases.append(n03)

    # N04：未知 Gate
    ev = root / "ev_n04"
    run = _run_runner(mini, only="precheck,no_such_gate", ev_dir=ev, rc={})
    n04 = _case("N04_unknown_gate", "--only 含未知 Gate", run, expect_rc_nonzero=True,
                partial=True, expect_gate_count=0, expect_meta_written=False,
                detail="未知 Gate 必须 fail-closed：不执行、不写 gates_run.json")
    cases.append(n04)

    # N05：空 --only（空串 / 纯逗号）——**逐子例持久化真实退出码**与「未写 gates_run.json」
    # （§R3-28 §28.7-4：旧版只留 `exit_code=null`，封存字节不足以让后续角色逐例机械复核）。
    n05_ok, n05_detail, n05_subs = True, [], []
    for raw in ("", " , ,"):
        ev = root / f"ev_n05_{abs(hash(raw)) % 1000}"
        run = _run_runner(mini, only=raw, ev_dir=ev, rc={})
        n05_subs.append({"input": raw, "exit_code": run["rc"],
                         "gates_run_written": run["meta_written"]})
        if run["rc"] == 0 or run["meta_written"]:
            n05_ok = False
            n05_detail.append(f"--only={raw!r} 未 fail-closed（rc={run['rc']}, "
                              f"written={run['meta_written']}）")
    n05_exits = [s["exit_code"] for s in n05_subs if isinstance(s["exit_code"], int)]
    cases.append({"id": "N05_empty_only", "case": "空 --only",
                  "exit_code": max(n05_exits) if n05_exits else None,
                  "subcases": n05_subs,
                  "summary": {}, "records": {}, "problems": n05_detail,
                  "detail": "空串 / 纯逗号都必须 fail-closed、不写 gates_run.json，"
                            "并逐子例记录真实退出码",
                  "ok": n05_ok})

    # N06：证据缺失（exit 0 但证据不在场）
    ev = root / "ev_n06"
    run = _run_runner(mini, only="package_audit", ev_dir=ev, rc={},
                      no_evidence=["package_audit"])
    n06 = _case("N06_missing_evidence", "exit 0 但证据缺失", run, expect_rc_nonzero=True,
                partial=True, expect_gate_count=1, expected_exits={"package_audit": 0},
                detail="证据缺失必须 fail-closed（顶层非绿）")
    rec = (run["meta"] or {}).get("gates") or [{}]
    if rec and rec[0].get("evidence_sha256") is not None:
        n06["ok"] = False
        n06["problems"].append("证据缺失时 evidence_sha256 应为 null")
    cases.append(n06)

    # N07：partial 子集全部成功 —— 必须显式标记 partial 且顶层非绿
    ev_n07 = root / "ev_n07"
    run = _run_runner(mini, only=",".join(subset), ev_dir=ev_n07, rc={})
    n07 = _case("N07_partial_all_pass", "partial 子集全部成功", run, expect_rc_nonzero=True,
                partial=True, expect_gate_count=3,
                expected_exits={g: 0 for g in subset},
                detail="全部已选 Gate 成功也必须 partial=true / final_verdict=false（不得假绿）")
    cases.append(n07)

    # N08：把 N07 的 partial gates_run.json 送 manifest —— manifest 必须拒绝
    fxroot = root / "fx_n08"
    fxroot.mkdir(parents=True, exist_ok=True)
    fixture = GV.Fixture(fxroot)
    ev_fx = fixture.evidence("n08")
    # 用 N07 的 partial gates_run.json 覆盖夹具里的权威记录
    shutil.copy2(ev_n07 / "gates_run.json", ev_fx / "gates_run.json")
    run_m = _manifest("build", fixture.argv(ev_fx, root / "fx_n08" / "out.json"))
    payload = run_m["payload"] or {}
    problems = payload.get("problems") or []
    missing_hit = any("缺少必需 Gate" in p for p in problems)
    n08 = {"id": "N08_partial_to_manifest", "case": "partial 结果送 manifest",
           "exit_code": run_m["rc"], "summary": {}, "records": {},
           "final_verdict": payload.get("final_verdict"),
           "problems": problems[:6],
           "detail": "partial gates_run 必须使 manifest 非零退出、final_verdict=false 且指出缺门",
           "ok": (run_m["rc"] != 0) and (payload.get("final_verdict") is False)
                 and missing_hit}
    if not missing_hit:
        n08["problems"] = (n08["problems"] or []) + ["manifest 未指出缺少必需 Gate"]
    cases.append(n08)

    # P01：与 runner 合同一致的全通过夹具送 manifest —— 必须接受（正向对照）
    fxroot = root / "fx_p01"
    fxroot.mkdir(parents=True, exist_ok=True)
    fixture = GV.Fixture(fxroot)
    ev_fx = fixture.evidence("p01")
    run_m = _manifest("build", fixture.argv(ev_fx, root / "fx_p01" / "out.json"))
    payload = run_m["payload"] or {}
    p01 = {"id": "P01_manifest_positive", "case": "manifest 全通过正向对照",
           "exit_code": run_m["rc"], "summary": {}, "records": {},
           "final_verdict": payload.get("final_verdict"),
           "problems": (payload.get("problems") or [])[:6],
           "detail": "完整且逐 Gate 合同成立的证据集必须被 manifest 接受",
           "ok": (run_m["rc"] == 0) and (payload.get("final_verdict") is True)}
    cases.append(p01)

    # ── §R3-28 §28.7-4：runner 负向矩阵被 manifest 消费时的反向用例（N09–N15）──
    # 每一例都必须让 manifest 非零退出、final_verdict=false，且 problems 明确指出矩阵问题。
    def aux_case(cid: str, name: str, mutate: dict | None, *, after=None,
                 detail: str = "") -> None:
        ev_aux = fixture.evidence(cid, mutate)
        if after is not None:
            after(ev_aux)
        run_a = _manifest("build", fixture.argv(ev_aux, root / f"fx_{cid}" / "out.json"))
        payload_a = run_a["payload"] or {}
        probs = payload_a.get("problems") or []
        hit = any("负向矩阵" in p for p in probs)
        problems = list(probs[:8])
        if not hit:
            problems.append("manifest problems 未指出 runner 负向矩阵")
        cases.append({"id": cid, "case": name, "exit_code": run_a["rc"],
                      "final_verdict": payload_a.get("final_verdict"),
                      "problems": problems, "summary": {}, "records": {},
                      "detail": detail,
                      "ok": (run_a["rc"] != 0)
                            and (payload_a.get("final_verdict") is False) and hit})

    base_aux = FX.aux_matrix_payload()

    def _aux_variant(**over) -> dict:
        a = json.loads(json.dumps(base_aux))
        a.update(over)
        return a

    # N09：矩阵证据缺失
    aux_case("N09_aux_missing", "负向矩阵证据缺失", None,
             after=lambda ev_d: (ev_d / FX.AUX_MATRIX_FILE).unlink(),
             detail=f"{FX.AUX_MATRIX_FILE} 缺失时 manifest 必须 fail-closed")

    # N10：矩阵 JSON 截断/损坏
    def _truncate(ev_d: Path) -> None:
        fp = ev_d / FX.AUX_MATRIX_FILE
        fp.write_text(fp.read_text(encoding="utf-8")[:40], encoding="utf-8")

    aux_case("N10_aux_truncated", "负向矩阵 JSON 截断", None, after=_truncate,
             detail="JSON 截断/损坏时 manifest 必须 fail-closed")

    # N11：runner SHA 记录与现场不符
    aux_case("N11_aux_runner_sha_mismatch", "runner SHA 不符",
             {"aux_matrix": _aux_variant(runner_sha256="0" * 64)},
             detail="记录的 runner_sha256 与现场不一致时必须 fail-closed")

    # N12：缺少必需 case ID（case_count 同步修正，隔离出「少 case」单一故障）
    n12 = _aux_variant()
    n12["cases"] = [c for c in n12["cases"] if c["id"] != "P01_manifest_positive"]
    n12["case_count"] = len(n12["cases"])
    aux_case("N12_aux_missing_case", "缺少必需 case ID", {"aux_matrix": n12},
             detail="缺少必需 case ID 时必须 fail-closed")

    # N13：某一用例真实退出码逃逸（非整数）
    n13 = _aux_variant()
    for c in n13["cases"]:
        if c["id"] == "N01_single_failure":
            c["exit_code"] = None
    aux_case("N13_aux_exit_code_escape", "退出码逃逸（非整数）", {"aux_matrix": n13},
             detail="任一用例退出码非真实整数时必须 fail-closed")

    # N14：all_ok 被置 false
    aux_case("N14_aux_all_ok_false", "all_ok=false",
             {"aux_matrix": _aux_variant(all_ok=False)},
             detail="矩阵 all_ok 非 true 时必须 fail-closed")

    # N15：failures 非空
    aux_case("N15_aux_failures_nonempty", "failures 非空",
             {"aux_matrix": _aux_variant(failures=["P00_complete_positive"])},
             detail="矩阵 failures 非空时必须 fail-closed")

    # ── §R3-30 §30.2/§30.5-2：只校验「退出码是整数」不够，必须校验极性、N05 子例、
    #    case ID 唯一且精确集合，否则负向用例逃逸仍会被判绿。 ──

    # N16：负向用例退出码被改为 0（结构合法、语义错误）
    n16 = _aux_variant()
    for c in n16["cases"]:
        if c["id"] == "N01_single_failure":
            c["exit_code"] = 0
    aux_case("N16_aux_negative_exit_zero", "负向用例退出码改为 0", {"aux_matrix": n16},
             detail="负向用例退出码为 0 时必须 fail-closed（不得只校验整数类型）")

    # N17：N05 逐子例证据被删除
    n17 = _aux_variant()
    for c in n17["cases"]:
        if c["id"] == "N05_empty_only":
            c.pop("subcases", None)
    aux_case("N17_aux_n05_subcases_missing", "N05 子例缺失", {"aux_matrix": n17},
             detail="N05 缺少 subcases 时必须 fail-closed")

    # N18：N05 任一子例退出码被改为 0
    n18 = _aux_variant()
    for c in n18["cases"]:
        if c["id"] == "N05_empty_only":
            c["subcases"][0]["exit_code"] = 0
    aux_case("N18_aux_n05_subcase_exit_zero", "N05 子例退出码为 0", {"aux_matrix": n18},
             detail="N05 任一子例退出码为 0 时必须 fail-closed")

    # N19：N05 子例被写成「已写 gates_run.json」
    n19 = _aux_variant()
    for c in n19["cases"]:
        if c["id"] == "N05_empty_only":
            c["subcases"][0]["gates_run_written"] = True
    aux_case("N19_aux_n05_gates_run_written", "N05 子例写了 gates_run.json",
             {"aux_matrix": n19},
             detail="N05 子例 gates_run_written 非 false 时必须 fail-closed")

    # N20：重复 case ID
    n20 = _aux_variant()
    n20["cases"].append(dict(n20["cases"][0]))
    n20["case_count"] = len(n20["cases"])
    aux_case("N20_aux_duplicate_case_id", "重复 case ID", {"aux_matrix": n20},
             detail="case ID 非唯一时必须 fail-closed")

    # N21：额外/未知 case ID
    n21 = _aux_variant()
    n21["cases"].append({"id": "N99_aux_unknown_case", "case": "unknown",
                         "exit_code": 1, "ok": True})
    n21["case_count"] = len(n21["cases"])
    aux_case("N21_aux_extra_case_id", "额外/未知 case ID", {"aux_matrix": n21},
             detail="出现额外/未知 case ID 时必须 fail-closed")

    failures = [c["id"] for c in cases if not c["ok"]]
    return {
        "schema": "resume-assistant/r3-run-gates-negtest",
        "version": 1,
        "generated_at_local": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "generator": "scripts/h8_r3_run_gates_negtest.py",
        "runner": RUNNER.name,
        "runner_sha256": sha256_file(RUNNER),
        "gate_set": {"count": len(all_names), "names": all_names},
        "fake_gates": mini["generated"],
        "case_count": len(cases),
        "cases": cases,
        "failures": failures,
        "all_ok": not failures,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="h8_r3_runner_negtest_"))
    t0 = time.time()
    try:
        result = run_matrix(tmp)
    finally:
        GV._rmtree_force(tmp)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[runner-negtest] cases={result['case_count']} failures={result['failures']} "
          f"all_ok={result['all_ok']} runtime={time.time() - t0:.1f}s")
    for c in result["cases"]:
        flag = "OK " if c["ok"] else "FAIL"
        print(f"  [{flag}] {c['id']} rc={c['exit_code']} {c['detail']}")
        for p in c["problems"]:
            print(f"         - {p}")
    return 0 if result["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())