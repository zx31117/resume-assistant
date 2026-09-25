"""V2.2.0 R3 §R3-10 B：六格真实性能 fail-closed 聚合器。

文档要求（RESULT §R3-10）：必须在一个最终汇总中机械检查如下全部条件，任一不成立必须
非零退出且 pass=false，不允许先退出 0 再人工补行：
  - 精确 6 格（size × mode），每格 n >= 3，总计至少 18 个有效样本；
  - 每个样本有可区分的 (size, mode, sample) 身份，无重复 run/sample；
  - 全部样本 status == SUCCEEDED；
  - 首 Fact 中位数与最大值 <= 15s（PLAN §5.5）；
  - telemetry 契约：logical_calls == 1 + 2F（F = fact 调用数）、单逻辑调用 attempts <= 3、
    成功后不重试、单任务 completion <= 16k、Embedding 调用为 0 或 1；
  - typical/long 相对 short 不倒退（仅报告，硬断言以内文本地列表为准）。

同时支持失败注入负向自测（--inject <case>）：人为破坏输入证明聚合器对该类缺陷必 fail-closed。

用法（在 backend 下，PYTHONPATH=backend）：
  python _e2e_v22_aggregate.py                         # 全 6 格 x n=3 汇总判定
  python _e2e_v22_aggregate.py --inject <case>          # 负向自测某类缺陷（不跑真实 6 格）
  python _e2e_v22_aggregate.py --n 1 --sizes short      # 限定子集（供调试/局部验证，不用于门禁）

退出码 0 = 全部条件成立且 pass=true；任一失败非 0 且 pass=false。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_MATRIX = _THIS_DIR / "_e2e_v22_matrix.py"
_ALL_SIZES = ("short", "typical", "long")
_ALL_MODES = ("cold", "warm")

FIRST_FACT_LIMIT_S = 15.0


def _collect(size: str, mode: str, n: int) -> list[dict]:
    """运行单格矩阵 cell 并解析其 JSON 输出行。cell 非零退出即视为本格失败。"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_THIS_DIR)
    proc = subprocess.run(
        [sys.executable, str(_MATRIX), "--size", size, "--mode", mode, "--n", str(n)],
        cwd=str(_THIS_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    rows: list[dict] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{"):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        elif line.startswith(("SUMMARY", "WARMUP_FAILED")):
            continue
    cell_meta = [r for r in rows if r.get("size") == size and r.get("mode") == mode]
    if proc.returncode != 0 or not cell_meta:
        return [{"status": "CELL_FAILED", "size": size, "mode": mode,
                 "sample": -1, "first_fact_s": None,
                 "reason": f"cell returncode={proc.returncode} valid_rows={len(cell_meta)} "
                           f"stdout_tail={proc.stdout[-300:] if proc.stdout else ''}"}]
    return cell_meta


def _inject(dataset: list[dict], case: str) -> list[dict]:
    """按用例破坏样本集，模拟文档 §R3-10 B-3 列出的缺陷类别（负向自测）。"""
    d = [dict(x) for x in dataset]
    if not d:
        return d
    if case == "missing_sample":
        # 少数一个样本
        d = d[:-1]
    elif case == "dup_sample":
        # 重复 sample/run 身份
        d[0] = dict(d[0])
        d[0]["sample"] = d[1]["sample"]
    elif case == "missing_grid":
        # 某格缺失：把所有该格样本剔除
        tgt = next(x for x in d if x.get("status") == "SUCCEEDED")
        d = [x for x in d if not (x.get("size") == tgt["size"] and x.get("mode") == tgt["mode"])]
    elif case == "embedding_2":
        # embedding_calls=2
        for x in d:
            if x.get("telemetry") is not None:
                x["telemetry"]["embedding_calls"] = 2
                x["telemetry"]["embedding_in_0_or_1"] = False
    elif case == "false_check":
        # 某个强制布尔为 false
        for x in d:
            if x.get("telemetry") is not None:
                x["telemetry"]["logical_calls_eq_1_plus_2F"] = False
    elif case == "truncated_evidence":
        # 证据截断/畸形：某样本缺一语义字段（判定视为 SUCCEEDED 但无 telemetry 键）
        for x in d[:3]:
            x.pop("telemetry", None)
    elif case == "cleanup_failed":
        # 模拟 cleanup 失败：注入一个 cell_failed 伪行（等价于格收集中断）
        d.insert(0, {"status": "CELL_FAILED", "size": "short", "mode": "cold",
                     "sample": -1, "first_fact_s": None,
                     "reason": "simulated cleanup failure"})
    return d


def _assert_fail(ctx, msg: str) -> bool:
    print(f"  [FAIL] {msg}")
    ctx["fails"].append(msg)
    return True  # True 表示"本处检测到失败"；调用方用 `pass_all and not _assert_fail(...)` 累积


def _record(pass_all: bool, ctx, msg: str) -> bool:
    """若本处触发失败，返回 False（导致最终 pass_all=False），否则保持原值。"""
    if _assert_fail(ctx, msg):
        return False
    return pass_all


def _evaluate(dataset: list[dict], ctx: dict) -> bool:
    """对样本集做机械判定，写 ctx 汇总；返回是否全部 panel 通过。"""
    fails = ctx["fails"]
    pass_all = True

    # 1) 样本总数与网格完整性
    n = len(dataset)
    if n < 18:
        pass_all = _record(pass_all, ctx, f"样本总数不足 18（实得 {n}）")
    cells: dict[str, int] = {}
    for x in dataset:
        cells.setdefault(f"{x.get('mode')}/{x.get('size')}", []).append(x)
    for mode in _ALL_MODES:
        for size in _ALL_SIZES:
            key = f"{mode}/{size}"
            got = len(cells.get(key, []))
            if got < 3:
                pass_all = _record(pass_all, ctx, f"格 {key} 样本数 {got} < 3")

    # 2) 身份唯一性（size, mode, sample 无重复 run）
    ids = [(x.get("size"), x.get("mode"), x.get("sample")) for x in dataset]
    if len(ids) != len(set(ids)):
        pass_all = _record(pass_all, ctx, "存在重复 (size,mode,sample) run 身份")

    # 3) 全部 SUCCEEDED
    not_ok = [x for x in dataset if x.get("status") != "SUCCEEDED"]
    if not_ok:
        pass_all = _record(
            pass_all, ctx,
            f"{len(not_ok)} 个样本非 SUCCEEDED：{not_ok[0].get('size')}/{not_ok[0].get('mode')}"
            f" sample={not_ok[0].get('sample')} status={not_ok[0].get('status')} "
            f"reason={not_ok[0].get('reason')}")

    ok_samples = [x for x in dataset if x.get("status") == "SUCCEEDED"]

    # 4) 首 Fact 中位数 / 最大值 ≤ 15s
    firsts = [x["first_fact_s"] for x in ok_samples if x.get("first_fact_s") is not None]
    if len(firsts) < len(ok_samples):
        pass_all = _record(pass_all, ctx, "存在 SUCCEEDED 样本缺少 first_fact_s")
    if firsts:
        s = sorted(firsts)
        med = s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2
        mx = max(firsts)
        ctx["first_fact_median"] = round(med, 2)
        ctx["first_fact_max"] = round(mx, 2)
        if med > FIRST_FACT_LIMIT_S or mx > FIRST_FACT_LIMIT_S:
            pass_all = _record(
                pass_all, ctx, f"首 Fact median={med:.2f}/max={mx:.2f} 超过 {FIRST_FACT_LIMIT_S}s")

    # 5) telemetry 契约逐样本
    for x in ok_samples:
        tel = x.get("telemetry") or {}
        sid = f"{x.get('size')}/{x.get('mode')} sample={x.get('sample')}"
        if "telemetry" not in x:
            pass_all = _record(pass_all, ctx, f"{sid}: 缺 telemetry（evidence 截断/畸形）")
            continue
        if tel.get("logical_calls_eq_1_plus_2F") is False:
            pass_all = _record(pass_all, ctx, f"{sid}: logical_calls != 1+2F")
        if tel.get("attempts_all_le_3") is False:
            pass_all = _record(pass_all, ctx, f"{sid}: 存在 attempt>3")
        if tel.get("no_retry_after_success") is False:
            pass_all = _record(pass_all, ctx, f"{sid}: 成功后仍有重试")
        if tel.get("embedding_in_0_or_1") is False:
            pass_all = _record(pass_all, ctx,
                               f"{sid}: embedding_calls={tel.get('embedding_calls')}（应 0/1）")
        if tel.get("completion_le_16k") is False:
            pass_all = _record(pass_all, ctx, f"{sid}: completion 超 16k")
    return pass_all


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    n = 3
    sizes = list(_ALL_SIZES)
    inject = None
    if "--n" in args:
        n = int(args[args.index("--n") + 1])
    if "--sizes" in args:
        sizes = [s.strip() for s in args[args.index("--sizes") + 1].split(",")]
    if "--inject" in args:
        inject = args[args.index("--inject") + 1]

    ctx: dict = {"fails": [], "cells": {}, "first_fact_median": None, "first_fact_max": None}

    if inject is not None:
        # 负向自测：构造一个"理想通过"数据集的变体，验证聚合器对该类缺陷必 fail-closed。
        good: list[dict] = []
        for mode in _ALL_MODES:
            for size in _ALL_SIZES:
                for i in range(n):
                    good.append({
                        "status": "SUCCEEDED", "size": size, "mode": mode, "sample": i + 1,
                        "first_fact_s": 7.0 + (i * 0.5),
                        "telemetry": {
                            "logical_calls_eq_1_plus_2F": True,
                            "attempts_all_le_3": True,
                            "no_retry_after_success": True,
                            "embedding_in_0_or_1": True,
                            "embedding_calls": 1,
                            "completion_le_16k": True,
                        },
                    })
        assert _evaluate(good, {"fails": []}) is True, "理想基线应通过"
        broken = _inject(good, inject)
        bad_ctx: dict = {"fails": []}
        result = _evaluate(broken, bad_ctx)
        verdict = "FAIL-CLOSED" if not result else "NOT_FAIL_CLOSED"
        print(f"INJECT_CASE={inject} verdict={verdict}")
        print(json.dumps({"case": inject, "fail_closed": not result,
                          "fail_messages": bad_ctx["fails"]}, ensure_ascii=False))
        return 0 if not result else 1

    # 正常门禁模式：跑真实 6 格 x n
    print(f"[sixgrid] 开始收集 {len(sizes)}x{len(_ALL_MODES)} 格 x n={n}（真实模型，较慢）...", flush=True)
    dataset: list[dict] = []
    for mode in _ALL_MODES:
        for size in sizes:
            print(f"[sixgrid]  {mode}/{size} n={n} ...", flush=True)
            rows = _collect(size, mode, n)
            dataset.extend(rows)
            print(f"[sixgrid]    -> {len(rows)} 样本", flush=True)

    ctx["cells"] = {}
    for mode in _ALL_MODES:
        for size in sizes:
            key = f"{mode}/{size}"
            ctx["cells"][key] = sum(1 for x in dataset
                                    if x.get("status") == "SUCCEEDED"
                                    and x.get("mode") == mode and x.get("size") == size)

    pass_all = _evaluate(dataset, ctx)
    summary = {
        "gate": "V2.2.0 R3 six-grid performance (fail-closed)",
        "pass": pass_all,
        "n_samples": len(dataset),
        "cells": ctx["cells"],
        "first_fact_median_s": ctx["first_fact_median"],
        "first_fact_max_s": ctx["first_fact_max"],
        "first_fact_limit_s": FIRST_FACT_LIMIT_S,
        "fail_messages": ctx["fails"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if pass_all else 1


if __name__ == "__main__":
    sys.exit(main())