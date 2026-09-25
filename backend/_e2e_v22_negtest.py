"""V2.2.0 R3 §R3-10 B-3：六格聚合器 fail-closed 负向自测运行器。

对 7 类注入缺陷，分别以**独立子进程**调用 `backend/_e2e_v22_aggregate.py --inject <case>`，采集其
**真实退出码**。门禁语义要求：检出注入缺陷即**非零退出**且不输出 PASS 摘要。本运行器断言 7/7 均为
非零退出且 JSON 输出 `fail_closed=true`；任一缺陷逃逸（退出 0 或 `fail_closed=false`）即非零退出。

产出证据 JSON：逐类 `(case, fail_closed, exit_code, fail_messages)` + `all_fail_closed` +
`all_exit_codes_nonzero`，并记录目标 EXE 身份供总 manifest 引用。

用法：
  python _e2e_v22_negtest.py --out <evidence.json> [--exe <ResumeAssistant.exe>]
退出码：0 = 7 类全部 fail-closed 且非零退出；1 = 存在逃逸；2 = 环境错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_AGG = _THIS_DIR / "_e2e_v22_aggregate.py"

CASES = (
    "missing_sample",
    "dup_sample",
    "missing_grid",
    "embedding_2",
    "false_check",
    "truncated_evidence",
    "cleanup_failed",
)


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--exe", default="")
    args = ap.parse_args()

    if not _AGG.is_file():
        print(f"NEGTEST_FATAL aggregate_missing: {_AGG}")
        return 2

    exe_sha = None
    if args.exe and Path(args.exe).is_file():
        exe_sha = _sha256_file(Path(args.exe))

    results: list[dict] = []
    escaped: list[str] = []
    for case in CASES:
        proc = subprocess.run(
            [sys.executable, str(_AGG), "--inject", case],
            cwd=str(_THIS_DIR), capture_output=True, text=True, timeout=300,
        )
        rc = proc.returncode
        payload = None
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    payload = None
        fail_closed = bool(rc != 0 and payload is not None and payload.get("fail_closed") is True)
        rec = {
            "case": case,
            "fail_closed": fail_closed,
            "exit_code": rc,
            "fail_messages": (payload or {}).get("fail_messages", []),
            "stdout_tail": proc.stdout[-160:],
        }
        results.append(rec)
        if not fail_closed:
            escaped.append(case)
        print(f"[negtest] {case} exit_code={rc} fail_closed={fail_closed}")

    all_fc = all(r["fail_closed"] for r in results)
    all_nonzero = all(isinstance(r["exit_code"], int) and r["exit_code"] != 0 for r in results)
    evidence = {
        "_meta": {
            "generator": "backend/_e2e_v22_negtest.py",
            "plan_blob": "7d8a249a5ec3e607855f20d794bb7ed9cda351ee",
            "target_exe_sha256": exe_sha,
            "note": "注入模式与被测门禁同语义：检出注入缺陷即非零退出。",
        },
        "cases": results,
        "all_fail_closed": all_fc,
        "all_exit_codes_nonzero": all_nonzero,
        "nonzero_exit_failures": escaped,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"all_fail_closed": all_fc, "all_exit_codes_nonzero": all_nonzero,
                      "escaped": escaped}, ensure_ascii=False))
    return 0 if (all_fc and all_nonzero) else 1


if __name__ == "__main__":
    sys.exit(main())
