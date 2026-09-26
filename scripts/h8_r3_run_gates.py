#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 R3：全量 Gate 运行器 + 证据收集器（产出 gates_run.json，逐 Gate 真实退出码）。

职责：
- 以真实子进程顺序运行全部受控 Gate，记录命令 / 真实退出码 / 开始-结束时间；
- 把每个 Gate 的产物证据归集到最终证据目录并计算 SHA-256；
- 汇总 cleanup 判定（只包含成立项；任一失败项以空列表/False 呈现，供 manifest 逐 Gate 核验）；
- 重算 `all_exit_zero` 与 `final_verdict`（不自我宣称通过；manifest 会再逐 Gate 交叉复核）。

用法：
  python scripts/h8_r3_run_gates.py --exe dist/ResumeAssistant/ResumeAssistant.exe \\
      --evidence-dir <final-evidence-dir> [--only precheck,package_audit,...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BACKEND = ROOT / "backend"
VA = ROOT / "validation-artifacts" / "h8"

PY = "C:/Users/31117/AppData/Local/Programs/Python/Python310/python.exe"

PLAN_BLOB = "7d8a249a5ec3e607855f20d794bb7ed9cda351ee"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _env() -> dict:
    import os
    e = dict(os.environ)
    for k in ("PYTHONPATH", "NODE_OPTIONS", "HTTP_PROXY", "HTTPS_PROXY",
              "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        e.pop(k, None)
    return e


# ── Gate 定义：name → (cwd, argv, evidence_target, evidence_source_rel) ──
# evidence_source_rel 为 None 表示该 Gate 直接把 evidence_target 写到目标目录。
def gate_specs(exe: str, ev: Path) -> list[dict]:
    exe_abs = str(Path(exe).resolve())
    return [
        dict(name="precheck", cwd=ROOT, argv=[PY, "scripts/precheck.py"],
             target="precheck.log", src=None, cleanup=False),
        dict(name="package_audit", cwd=ROOT,
             argv=[PY, "scripts/h8_package_audit.py", "--dir", "dist/ResumeAssistant",
                   "--json", str(ev / "package_audit.json")],
             target="package_audit.json", src=None, cleanup=False),
        dict(name="pyz_check", cwd=ROOT,
             argv=[PY, "scripts/h8_r2_pyz_check.py", "--exe", exe_abs,
                   "--out", str(ev / "pyz_check.json")],
             target="pyz_check.json", src=None, cleanup=False),
        dict(name="failure_matrix", cwd=ROOT,
             argv=[PY, "scripts/h8_r2_failure_matrix.py", "--exe", exe_abs,
                   "--out", str(ev / "failure_matrix.json")],
             target="failure_matrix.json", src=None, cleanup=True),
        dict(name="content_e2e", cwd=ROOT,
             argv=[PY, "scripts/h8_r3_real_model_content.py", "--exe", exe_abs],
             target="content_real_model.json",
             src=VA / "r3" / "content_real_model.json", cleanup=True),
        dict(name="mainchain_e2e", cwd=ROOT,
             argv=[PY, "scripts/h8_real_model_e2e.py", "--exe", exe_abs],
             target="real_model_e2e.json",
             src=VA / "e2e" / "real_model_e2e.json", cleanup=True),
        dict(name="design_fidelity", cwd=ROOT,
             argv=[PY, "scripts/h8_design_fidelity.py", "--exe", exe_abs],
             target="design_fidelity.json",
             src=VA / "fidelity" / "design_fidelity.json", cleanup=True),
        dict(name="six_grid", cwd=BACKEND,
             argv=[PY, "_e2e_v22_aggregate.py", "--exe", exe_abs,
                   "--out", str(ev / "six_grid_aggregate.json")],
             target="six_grid_aggregate.json", src=None, cleanup=False),
        dict(name="six_grid_negative_selftest", cwd=ROOT,
             argv=[PY, "scripts/h8_r3_sixgrid_negative_selftest.py",
                   "--out", str(ev / "six_grid_negative_selftest.json")],
             target="six_grid_negative_selftest.json", src=None, cleanup=False),
        dict(name="git_identity_negtest", cwd=ROOT,
             argv=[PY, "scripts/h8_r3_git_identity_negtest.py",
                   "--out", str(ev / "git_identity_matrix.json")],
             target="git_identity_matrix.json", src=None, cleanup=False),
        dict(name="artifact_auth_matrix", cwd=ROOT,
             argv=[PY, "scripts/h8_r3_artifact_auth_matrix.py", "--exe", exe_abs,
                   "--out", str(ev / "artifact_auth_matrix.json")],
             target="artifact_auth_matrix.json", src=None, cleanup=True),
        dict(name="atomic_publish_matrix", cwd=ROOT,
             argv=[PY, "scripts/h8_r3_atomic_publish_matrix.py",
                   "--out", str(ev / "atomic_publish_matrix.json")],
             target="atomic_publish_matrix.json", src=None, cleanup=True),
        dict(name="gate_verdict_negtest", cwd=ROOT,
             argv=[PY, "scripts/h8_r3_gate_verdict_negtest.py",
                   "--out", str(ev / "gate_verdict_negtest.json")],
             target="gate_verdict_negtest.json", src=None, cleanup=True),
    ]


def _load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _collect_cleanup(ev: Path) -> dict:
    content = _load_json(ev / "content_real_model.json")
    e2e = _load_json(ev / "real_model_e2e.json")
    fidelity = _load_json(ev / "design_fidelity.json")
    fm = _load_json(ev / "failure_matrix.json")
    auth = _load_json(ev / "artifact_auth_matrix.json")
    atomic = _load_json(ev / "atomic_publish_matrix.json")
    verdict = _load_json(ev / "gate_verdict_negtest.json")

    winword = []
    for d in (e2e, fm):
        wl = (d.get("cleanup") or {}).get("winword_leaked") or d.get("winword_leaked") or []
        winword += list(wl)

    cleanup: dict = {"winword_leaked": sorted(set(winword))}
    def put(k, v):
        if isinstance(v, bool):
            cleanup[k] = bool(v)
    put("content_runtime_deleted", content.get("runtime_deleted"))
    put("e2e_runtime_deleted", e2e.get("runtime_deleted"))
    put("fidelity_runtime_removed", (fidelity.get("cleanup") or {}).get("runtime_removed"))
    put("failure_matrix_cleanup_ok", (fm.get("cleanup") or {}).get("ok"))
    put("artifact_auth_runtime_deleted", auth.get("runtime_deleted"))
    put("atomic_publish_runtime_removed", (atomic.get("cleanup") or {}).get("runtime_removed"))
    put("gate_verdict_runtime_removed", (verdict.get("cleanup") or {}).get("runtime_removed"))
    return cleanup


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--evidence-dir", required=True)
    ap.add_argument("--src", default="")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    exe = Path(args.exe).resolve()
    if not exe.is_file():
        print(f"[runner] exe 不存在: {exe}")
        return 2
    exe_sha = sha256_file(exe)
    # 证据目录一律解析为**绝对路径**：部分 Gate 以 `cwd=BACKEND` 运行，相对路径会被
    # 误解析到 backend/ 下，导致证据落错位置（cwd 与 --evidence-dir 不一致）。
    ev = Path(args.evidence_dir).resolve()
    ev.mkdir(parents=True, exist_ok=True)
    only = {s.strip() for s in (args.only or "").split(",") if s.strip()}

    specs = gate_specs(str(exe), ev)
    if only:
        specs = [s for s in specs if s["name"] in only]

    # ── 增量合并：同一证据目录下、同一包身份已记录且证据在场的 Gate 不再重跑 ──
    existing: dict[str, dict] = {}
    existing_meta = ev / "gates_run.json"
    if existing_meta.is_file():
        try:
            prev = json.loads(existing_meta.read_text(encoding="utf-8-sig"))
        except Exception:
            prev = {}
        if (prev.get("package") or {}).get("exe_sha256") == exe_sha:
            for rec in (prev.get("gates") or []):
                if isinstance(rec, dict) and rec.get("gate"):
                    existing[str(rec["gate"])] = rec

    records = [existing[n] for n in [s["name"] for s in specs]
               if n in existing and existing[n].get("exit_code") == 0
               and (ev / existing[n]["evidence"]).is_file()]
    for name in list(existing):
        if name not in {s["name"] for s in specs} \
                and existing[name].get("exit_code") == 0 \
                and (ev / existing[name]["evidence"]).is_file():
            records.append(existing[name])

    started_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    for spec in specs:
        name = spec["name"]
        if name in existing and existing[name].get("exit_code") == 0 \
                and (ev / spec["target"]).is_file():
            print(f"[runner] {name}: reuse (same package, prior exit 0, evidence present)",
                  flush=True)
            continue
        t0 = time.time()
        logf = ev / f"{name}.log"
        with open(logf, "w", encoding="utf-8", errors="replace") as fh:
            proc = subprocess.run(spec["argv"], cwd=str(spec["cwd"]),
                                  env=_env(), stdout=fh, stderr=subprocess.STDOUT,
                                  timeout=3600)
        rc = proc.returncode
        dt = time.time() - t0
        # 收集证据
        target = ev / spec["target"]
        if spec["src"] is not None and Path(spec["src"]).is_file():
            shutil.copy2(spec["src"], target)
        present = target.is_file()
        rec = {
            "gate": name,
            "command": " ".join(a for a in spec["argv"]),
            "exit_code": rc,
            "started_at_local": datetime.fromtimestamp(t0).strftime("%Y-%m-%dT%H:%M:%S"),
            "ended_at_local": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "runtime_s": round(dt, 2),
            "evidence": spec["target"],
            "evidence_sha256": sha256_file(target) if present else None,
            "evidence_bytes": target.stat().st_size if present else 0,
            "package_exe_sha256": exe_sha,
            "verdict": rc == 0,
            "cleanup_required": spec["cleanup"],
        }
        records.append(rec)
        print(f"[runner] {name}: rc={rc} runtime={dt:.1f}s evidence={'OK' if present else 'MISSING'}",
              flush=True)

    cleanup = _collect_cleanup(ev)
    gates_meta = {
        "_meta": {
            "generator": "scripts/h8_r3_run_gates.py",
            "plan_blob": PLAN_BLOB,
            "src": args.src or None,
            "package_exe_sha256": exe_sha,
            "round_start_local": started_ts,
            "collected_at_local": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "package": {
            "exe_sha256": exe_sha,
            "exe_bytes": exe.stat().st_size,
        },
        "gates": records,
        "all_exit_zero": bool(records) and all(r["exit_code"] == 0 for r in records),
        "cleanup": cleanup,
        "problems": [r["gate"] for r in records if r["exit_code"] != 0],
        "final_verdict": bool(records) and all(r["exit_code"] == 0 for r in records),
    }
    (ev / "gates_run.json").write_text(json.dumps(gates_meta, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    print(f"[runner] wrote {ev / 'gates_run.json'} all_exit_zero={gates_meta['all_exit_zero']}")
    return 0 if gates_meta["all_exit_zero"] else 1


if __name__ == "__main__":
    sys.exit(main())
