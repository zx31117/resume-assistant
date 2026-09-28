#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 R3：按 **runner 同一条 stdout 捕获路径** 刷新指定 Gate 的离线证据（最小返工）。

背景（独立验收发现）：
  §32.4 离线重跑负向矩阵时，直接以 `--out` 在证据目录里重写了 `<gate>.json`，但**没有经过**
  `h8_r3_run_gates.py` 的 stdout 捕获路径，于是：
    * `<gate>.log`（runner 捕获的 stdout）停留在更早一次运行，与 `<gate>.json` 不同版本；
    * `gates_run.json` 中该 Gate 记录的 `evidence_sha256` 被后续重算回填，但 `started_at_local`
      / `ended_at_local` / `runtime_s` 仍是上一次运行的值。
  结果：封存证据内部不自洽（`.log` 与 `.json` 矛盾、记录并非该次运行的产物）。

本工具以 `gate_specs()` 的**同一 argv / cwd / target** 重新运行指定 Gate **一次**，从而：
    * 把同一次运行的 stdout(+stderr) 写入 `<gate>.log`；
    * 由 Gate 自身经 `--out` 写入其 `target` 证据文件（`.json`）；
    * 按 runner **完全相同**的字段重写该 Gate 在 `gates_run.json` 中的记录（真实 command /
      exit_code / 时间戳 / runtime / hash / bytes）。
  其它 Gate 记录、`_meta` 原有字段一律不动；**不**设置 `partial`（结果仍是完整多 Gate 运行的代表）。
  仅新增 `_meta.refresh` 作为“本轮刷新了哪些 Gate”的显式披露。

fail-closed：`--gates` 为空 / 含未知 Gate 名 → 非零退出且**不写任何文件**。

用法：
  python scripts/h8_r3_refresh_gate_evidence.py --evidence-dir <ev> \\
      --gates gate_verdict_negtest,seal_manifest_negtest
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from h8_r3_run_gates import gate_specs, _env, sha256_file, _collect_cleanup  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-dir", required=True)
    ap.add_argument("--gates", required=True)
    ap.add_argument("--gates-meta", default="")
    ap.add_argument("--exe", default="")
    args = ap.parse_args()

    ev = Path(args.evidence_dir).resolve()
    meta_path = Path(args.gates_meta).resolve() if args.gates_meta \
        else ev / "gates_run.json"
    if not meta_path.is_file():
        print(f"[refresh] FAIL-CLOSED: gates_run.json 不存在: {meta_path}")
        return 2
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        print(f"[refresh] FAIL-CLOSED: gates_run.json 不可解析: {type(e).__name__}")
        return 2

    exe = Path(args.exe).resolve() if args.exe \
        else ROOT / "dist" / "ResumeAssistant" / "ResumeAssistant.exe"
    specs = {s["name"]: s for s in gate_specs(str(exe), ev)}

    selected = [s.strip() for s in args.gates.split(",") if s.strip()]
    if not selected:
        print(f"[refresh] FAIL-CLOSED: --gates 为空选择: {args.gates!r}")
        return 2
    unknown = sorted(set(selected) - set(specs))
    if unknown:
        print(f"[refresh] FAIL-CLOSED: --gates 含未知 Gate: {unknown}")
        return 2

    records: list[dict] = list(meta.get("gates") or [])
    index = {str(r.get("gate")): i for i, r in enumerate(records)}

    for name in selected:
        spec = specs[name]
        t0 = time.time()
        logf = ev / f"{name}.log"
        with open(logf, "w", encoding="utf-8", errors="replace") as fh:
            proc = subprocess.run(spec["argv"], cwd=str(spec["cwd"]),
                                  env=_env(), stdout=fh, stderr=subprocess.STDOUT,
                                  timeout=3600)
        rc = proc.returncode
        dt = time.time() - t0
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
            "package_exe_sha256": (meta.get("package") or {}).get("exe_sha256"),
            "verdict": rc == 0,
            "cleanup_required": spec["cleanup"],
        }
        if name in index:
            records[index[name]] = rec
        else:
            index[name] = len(records)
            records.append(rec)
        print(f"[refresh] {name}: rc={rc} runtime={dt:.1f}s "
              f"evidence={'OK' if present else 'MISSING'}", flush=True)

    # ── 汇总（与 runner 同口径；不设 partial）───────────────────────────────
    missing_evidence = [r["gate"] for r in records
                        if not (ev / str(r.get("evidence") or "")).is_file()]
    failed = [r["gate"] for r in records if r["exit_code"] != 0]
    problems: list[str] = []
    problems += [f"{g}: 退出码非 0" for g in failed]
    problems += [f"{g}: 证据缺失" for g in missing_evidence]
    executed_all_exit_zero = bool(records) and not failed and not missing_evidence

    meta["gates"] = records
    meta["executed_all_exit_zero"] = executed_all_exit_zero
    meta["all_exit_zero"] = executed_all_exit_zero
    meta["cleanup"] = _collect_cleanup(ev)
    meta["problems"] = problems
    meta["final_verdict"] = executed_all_exit_zero
    _m = meta.setdefault("_meta", {})
    # 累积披露：分批刷新时保留此前已刷新的 Gate，避免 `_meta.refresh.gates` 与实际被刷新记录的
    # 时间戳不一致（后续单独调用不得覆盖先前批次的披露）。
    _prev = _m.get("refresh") or {}
    _prev_gates = [g for g in (_prev.get("gates") or []) if isinstance(g, str)]
    _all_gates = _prev_gates + [g for g in selected if g not in _prev_gates]
    _m["refresh"] = {
        "generator": "scripts/h8_r3_refresh_gate_evidence.py",
        "gates": _all_gates,
        "at_local": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "note": "以 runner 同一捕获路径重跑上述 Gate，使 .log/.json/记录同版本；其余记录未改。",
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[refresh] wrote {meta_path} gates={len(records)} "
          f"all_exit_zero={executed_all_exit_zero} problems={problems}")
    return 0 if executed_all_exit_zero else 1


if __name__ == "__main__":
    sys.exit(main())