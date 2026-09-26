#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 R3：六格聚合器 fail-closed 负向自测运行器。

逐例以**真实子进程**调用 `backend/_e2e_v22_aggregate.py --inject <case>`，读取真实退出码，
断言每一例都非零退出（fail-closed）且不输出 PASS 摘要。结果写入
`six_grid_negative_selftest.json`，供 manifest 逐 Gate 核验。

纪律：不在测试中硬编码预期退出码——退出码一律读取子进程真实返回值。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BACKEND = ROOT / "backend"
AGGREGATE = BACKEND / "_e2e_v22_aggregate.py"

INJECT_CASES = ["missing_sample", "dup_sample", "missing_grid", "embedding_2",
                "false_check", "truncated_evidence", "cleanup_failed",
                # §R3-20 追加：样本失败 / 首 Fact 超限 / 四格降幅不足 / attempts>3 /
                # 成功后重试 / completion>16k / 完成慢样本被丢弃。
                "sample_failed", "first_fact_over_limit", "four_grid_shortfall",
                "attempts_gt_3", "retry_after_success", "completion_gt_16k",
                "discarded_valid_rows"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "validation-artifacts" / "h8" / "r3rework4"
                                        / "six_grid_negative_selftest.json"))
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    cases = []
    for case in INJECT_CASES:
        proc = subprocess.run(
            [args.python, str(AGGREGATE), "--inject", case],
            cwd=str(BACKEND), capture_output=True, text=True, timeout=120,
        )
        rc = proc.returncode
        fail_closed = rc != 0
        cases.append({
            "case": case,
            "fail_closed": fail_closed,
            "exit_code": rc,
            "fail_messages": [],
            "stderr_tail": (proc.stderr or "")[-400:],
        })
        print(f"[neg-selftest] {case}: rc={rc} fail_closed={fail_closed}")

    all_fc = all(c["fail_closed"] for c in cases)
    all_nonzero = all(isinstance(c["exit_code"], int) and c["exit_code"] != 0 for c in cases)
    out = {
        "generator": "scripts/h8_r3_sixgrid_negative_selftest.py",
        "aggregate": "backend/_e2e_v22_aggregate.py",
        "cases": cases,
        "all_fail_closed": all_fc,
        "all_exit_codes_nonzero": all_nonzero,
        "nonzero_exit_failures": [c["case"] for c in cases if not (c["exit_code"] != 0)],
        "ok": bool(all_fc and all_nonzero),
    }
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"all_fail_closed": all_fc, "all_exit_codes_nonzero": all_nonzero,
                      "ok": out["ok"]}, ensure_ascii=False))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
