"""V2.2.0 六格真实模型性能矩阵总入口（short/typical/long × cold/warm，每格 n≥3）。

逐个调用 _e2e_v22_matrix.main()（真实 ARK 模型），汇总 JSON 与中位数，
写 docs/versions/v2.2.0/evidence/r2_real_model_matrix.json。
退出码 0 = 六格全部样本 SUCCEEDED。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

# 真实模型 Key 从 Windows 凭据库读取，并在任何 settings 模块 import 之前注入环境变量
#（settings.ARK_API_KEY 默认在 import 时读取 os.getenv，故须先行设置）。
_cm = None
try:
    from core.credential_manager import get_api_key as _get_api_key
    _cm = _get_api_key()
except Exception:  # noqa: BLE001
    _cm = None
if _cm and not os.environ.get("ARK_API_KEY"):
    os.environ["ARK_API_KEY"] = _cm
    print(f"[sixgrid] injected ARK_API_KEY from credential manager (len={len(_cm)})")

import _e2e_v22_matrix as matrix  # noqa: E402   (仅用于常量/路径约定，不在此进程内跑调用)

_EVID = Path(_THIS_DIR) / ".." / "docs" / "versions" / "v2.2.0" / "evidence"
_EVID.mkdir(parents=True, exist_ok=True)
_OUT = _EVID / "r2_real_model_matrix.json"
_MATRIX = Path(__file__).resolve().parent / "_e2e_v22_matrix.py"

_CELLS = [("short", "cold"), ("short", "warm"), ("typical", "cold"),
          ("typical", "warm"), ("long", "cold"), ("long", "warm")]
N = 3


def _spawn(size: str, mode: str, n: int) -> tuple[int, list[dict], str]:
    """独立子进程运行矩阵 cell（矩阵的 engine 是进程级单例，需以新进程换来新 DB）。"""
    import subprocess
    proc = subprocess.run(
        [sys.executable, str(_MATRIX), "--size", size, "--mode", mode, "--n", str(n)],
        capture_output=True, text=True, encoding="utf-8",
        env=os.environ,  # 继承注入的 ARK_API_KEY
    )
    samples: list[dict] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                samples.append(json.loads(line))
            except Exception:
                pass
    return proc.returncode, samples, proc.stdout + proc.stderr


def _run_cell(size, mode) -> tuple[int, list[dict], str]:
    """cold：每样本一个全新子进程（冷启动、新进程+新 DB，规避 engine 进程级单例的库复用，
    否则同进程第二样本向已 seed 的库重复插入 exp1 而 IntegrityError）。
    warm：单进程内 warmup + n 计数（同库同进程，设计如此）。"""
    rc_sum = 0
    samples: list[dict] = []
    texts: list[str] = []
    if mode == "cold":
        for _ in range(N):
            rc, ss, text = _spawn(size, mode, 1)
            rc_sum += 1 if rc != 0 else 0
            samples.extend(ss)
            texts.append(text)
    else:
        rc, ss, text = _spawn(size, mode, N)
        rc_sum += 1 if rc != 0 else 0
        samples.extend(ss)
        texts.append(text)
    return (1 if rc_sum else 0), samples, "\n".join(texts)


def main() -> int:
    t0 = time.time()
    results: list[dict] = []
    failures = 0
    logs: dict[str, str] = {}
    for size, mode in _CELLS:
        rc, samples, text = _run_cell(size, mode)
        logs[f"{size}/{mode}"] = text
        results.extend(samples)
        if rc != 0:
            failures += 1
            print(f"  [cell FAILED] {size}/{mode}:", flush=True)
            print((text or "")[-2500:], flush=True)
        print(f"[cell pass] {size}/{mode} rc={rc} samples={len(samples)}", flush=True)

    # 汇总：首完整 Fact 中位数/最大值、总耗时中位数
    sizes = ("short", "typical", "long")
    summary: dict[str, dict] = {}
    for size in sizes:
        cells = [r for r in results if r.get("size") == size]
        for mode in ("cold", "warm"):
            xs = [r for r in cells if r.get("mode") == mode and r.get("first_fact_s") is not None]
            ts = [r for r in cells if r.get("mode") == mode and r.get("total_s") is not None]
            def _med(vals):
                sv = sorted(vals)
                n = len(sv)
                return sv[n // 2] if n % 2 else ((sv[n // 2 - 1] + sv[n // 2]) / 2)
            summary[f"{size}/{mode}"] = {
                "n": len([r for r in cells if r.get("mode") == mode]),
                "first_fact_median_s": _med([x["first_fact_s"] for x in xs]) if xs else None,
                "first_fact_max_s": max((x["first_fact_s"] for x in xs), default=None),
                "total_median_s": _med([x["total_s"] for x in ts]) if ts else None,
                "total_max_s": max((x["total_s"] for x in ts), default=None),
                "succeeded": sum(1 for r in cells if r.get("mode") == mode and r.get("status") == "SUCCEEDED"),
            }

    doc = {
        "engine": "real-model deepseek-v4-pro-ga-260813 (credential-manager key)",
        "cells": N,
        "elapsed_s": round(time.time() - t0, 1),
        "samples": results,
        "summary": summary,
        "failures": failures,
    }
    _OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {_OUT}")
    print(f"SIXGRID_EXIT=0 failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())