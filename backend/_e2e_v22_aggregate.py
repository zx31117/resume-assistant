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

同时支持失败注入负向自测（--inject <case>）：向聚合器注入一类缺陷，验证它作为门禁必须 fail-closed。
**注入模式与被测门禁同语义**：检出注入缺陷 → 非零退出且不输出 PASS 摘要；未检出（缺陷逃逸）→ 退出 0。
因此外部自测运行器断言"7 类注入全部得到非零退出码"，即可证明聚合器对缺陷类 fail-closed。

用法（在 backend 下，PYTHONPATH=backend）：
  python _e2e_v22_aggregate.py                         # 全 6 格 x n=3 汇总判定
  python _e2e_v22_aggregate.py --inject <case>          # 注入一类缺陷（不跑真实 6 格）；检出即非零退出
  python _e2e_v22_aggregate.py --n 1 --sizes short      # 限定子集（供调试/局部验证，不用于门禁）

退出码 0 = 全部条件成立且 pass=true；任一失败非 0 且 pass=false。
"""
from __future__ import annotations

import hashlib
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

# V2.1.0 同格总时长中位（s）—— PLAN §5.5「typical/long 总时长相对 V2.1.0 同格中位数
# 降低 ≥25%」的硬门禁基线。值取自 V2.1.0 六格实测（RESULT §R2 表），为固定参照常量，
# 不随本轮运行变化。short 两格无基线，不参与降幅判定。
V21_BASELINE_TOTAL_MEDIAN_S = {
    "cold/typical": 89.49,
    "cold/long": 94.32,
    "warm/typical": 84.48,
    "warm/long": 97.92,
}
REDUCTION_MIN = 0.25  # 降幅 ≥25%（等价于 total 中位 ≤ 0.75×基线）


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_cell_process(size: str, mode: str, n: int) -> tuple[list[dict], int, str]:
    """在独立 OS 进程中运行单格矩阵 cell，解析其 JSON 输出行。"""
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
    tail = (proc.stdout or "")[-300:]
    return cell_meta, proc.returncode, tail


def _run_cell_with_retry(size: str, mode: str, n: int,
                         attempts: int = 3) -> tuple[list[dict], int, str, int, list[dict]]:
    """收集单格，**仅对无有效 JSON 的明确基础设施失败**做有限重试。

    §R3-20 返工关键约束：完成样本（含超限慢样本、业务失败样本、合同失败样本）一旦产出
    有效 JSON，**必须保留并压低本轮 Gate，不得丢弃后重跑**。只有进程被外部信号杀 / 无输出 /
    JSON 全不可解析这类"无有效样本"的基础设施失败才允许有限重试。返回
    (rows, rc, tail, used_attempts, retry_ledger)。
    """
    import time as _time
    ledger: list[dict] = []
    for a in range(max(1, attempts)):
        got, rc, tail = _run_cell_process(size, mode, n)
        ledger.append({
            "attempt": a + 1, "rc": rc, "valid_rows": len(got),
            "discarded_valid_rows": False,
        })
        if got:
            # 有有效 JSON 样本 = 完成样本，必须保留；即使 rc!=0（业务/合同失败）也不重跑。
            return got, rc, tail, a + 1, ledger
        if a + 1 < attempts:
            _time.sleep(2.0 * (a + 1))
    # 重试耗尽仍无有效样本：返回空 + 非零 rc，最终由 _evaluate 判 CELL_FAILED。
    return [], 1, "", max(1, attempts), ledger


def _collect(size: str, mode: str, n: int) -> tuple[list[dict], list[dict]]:
    """收集单格样本，返回 (rows, retry_ledger)。

    冷启动格（cold）必须"每样本独立全新 OS 进程 + 新 DB + 新 runtime 目录"（矩阵进程内的
    module-global 引擎会跨样本复用，导致第 2/3 个样本崩溃或复用旧库）。因此 cold 逐样本以
    `--n 1` 独立进程采样并重新编号，保证 (size, mode, sample) 身份唯一且互相隔离；
    warm 保持同进程复用（先 warmup 再计数）。两者均**仅对无有效样本的基础设施失败**做有限重试，
    完成样本一律保留。
    """
    ledger: list[dict] = []
    if mode == "cold":
        rows: list[dict] = []
        for i in range(n):
            got, rc, tail, tries, led = _run_cell_with_retry(size, mode, 1)
            ledger.extend(led)
            if rc != 0 or not got:
                return [{"status": "CELL_FAILED", "size": size, "mode": mode,
                         "sample": i + 1, "first_fact_s": None,
                         "reason": f"cold sample {i + 1} returncode={rc} "
                                   f"valid_rows={len(got)} attempts={tries} "
                                   f"stdout_tail={tail}"}], ledger
            for x in got:
                x = dict(x)
                x["sample"] = i + 1
                rows.append(x)
        return rows, ledger

    cell_meta, rc, tail, tries, led = _run_cell_with_retry(size, mode, n)
    ledger.extend(led)
    if rc != 0 or not cell_meta:
        return [{"status": "CELL_FAILED", "size": size, "mode": mode,
                 "sample": -1, "first_fact_s": None,
                 "reason": f"cell returncode={rc} valid_rows={len(cell_meta)} "
                           f"attempts={tries} "
                           f"stdout_tail={tail}"}], ledger
    return cell_meta, ledger


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
    elif case == "sample_failed":
        # 某样本状态非 SUCCEEDED（业务失败/超时/取消）
        for x in d:
            if x.get("status") == "SUCCEEDED":
                x["status"] = "FAILED"
                x["reason"] = "simulated business failure"
                break
    elif case == "first_fact_over_limit":
        # 首 Fact 超 15s（完成慢样本必须压低 Gate，不得丢弃）
        for x in d:
            if x.get("status") == "SUCCEEDED":
                x["first_fact_s"] = 16.5
                break
    elif case == "four_grid_shortfall":
        # 四格任一降幅不足：把 typical/long 格 total 中位抬到基线附近（降幅 <25%）
        for x in d:
            if x.get("size") in ("typical", "long") and x.get("status") == "SUCCEEDED":
                x["total_s"] = 85.0
    elif case == "attempts_gt_3":
        for x in d:
            if x.get("telemetry") is not None:
                x["telemetry"]["attempts_all_le_3"] = False
    elif case == "retry_after_success":
        for x in d:
            if x.get("telemetry") is not None:
                x["telemetry"]["no_retry_after_success"] = False
    elif case == "completion_gt_16k":
        for x in d:
            if x.get("telemetry") is not None:
                x["telemetry"]["completion_le_16k"] = False
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

    # 5b) 四格有基线格（typical/long × cold/warm）总时长中位降幅 ≥25% —— PLAN §5.5 硬门禁。
    #     必须从样本 total_s 独立重算，不信任顶层 pass；short 两格无基线不参与。
    four_grid: dict[str, dict] = {}
    totals_by_cell: dict[str, list[float]] = {}
    for x in ok_samples:
        ts = x.get("total_s")
        if isinstance(ts, (int, float)):
            totals_by_cell.setdefault(f"{x.get('mode')}/{x.get('size')}", []).append(float(ts))
    for cell, base in V21_BASELINE_TOTAL_MEDIAN_S.items():
        vals = sorted(totals_by_cell.get(cell, []))
        if len(vals) < 3:
            four_grid[cell] = {"baseline": base, "total_median": None, "n": len(vals),
                               "reduction": None, "ok": False}
            pass_all = _record(pass_all, ctx,
                               f"有基线格 {cell} 样本数 {len(vals)} < 3，无法判定降幅")
            continue
        med = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
        reduction = 1.0 - med / base
        ok = reduction >= REDUCTION_MIN
        four_grid[cell] = {"baseline": base, "total_median": round(med, 2), "n": len(vals),
                           "reduction": round(reduction, 4), "ok": ok}
        if not ok:
            pass_all = _record(pass_all, ctx,
                               f"有基线格 {cell} 降幅 {reduction:.2%} < {REDUCTION_MIN:.0%}（{med:.2f}s / {base}s）")
    ctx["four_grid"] = four_grid

    # 5c) retry ledger 丢弃完成样本的防御性不变量：任何一次尝试已有有效样本却仍继续重试
    #     （discarded_valid_rows）即为违规，fail-closed。正常固定逻辑绝不可能触发。
    ledger = ctx.get("retry_ledger") or []
    for e in ledger:
        if e.get("discarded_valid_rows") or (e.get("attempt", 1) > 1 and e.get("valid_rows", 0) > 0):
            pass_all = _record(pass_all, ctx, "retry ledger 记录到完成样本被丢弃（attempt 后续仍重试）")
            break
    return pass_all


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    n = 3
    sizes = list(_ALL_SIZES)
    inject = None
    exe_path = None
    out = None
    if "--n" in args:
        n = int(args[args.index("--n") + 1])
    if "--sizes" in args:
        sizes = [s.strip() for s in args[args.index("--sizes") + 1].split(",")]
    if "--inject" in args:
        inject = args[args.index("--inject") + 1]
    if "--exe" in args:
        exe_path = Path(args[args.index("--exe") + 1])
    if "--out" in args:
        out = Path(args[args.index("--out") + 1])

    ctx: dict = {"fails": [], "cells": {}, "first_fact_median": None, "first_fact_max": None}

    if inject is not None:
        # 负向自测（§R3-10 B-3）：向聚合器注入一类缺陷，验证它作为"门禁"必须 fail-closed——
        # 即**非零退出**且不输出 PASS 摘要。退出码语义与真实门禁完全一致：检出缺陷 → 非零。
        # 外部自测运行器据此断言"7 类注入全部得到非零退出码"。
        good: list[dict] = []
        # 合成基线样本的 total_s：typical/long 取远低于 V2.1 基线（降幅 ~60%），short 取绝对值，
        # 确保"理想基线"在四格降幅硬门禁上也通过，注入缺陷才是唯一失败源。
        _total_s_for = {"short": 19.0, "typical": 30.0, "long": 38.0}
        for mode in _ALL_MODES:
            for size in _ALL_SIZES:
                for i in range(n):
                    good.append({
                        "status": "SUCCEEDED", "size": size, "mode": mode, "sample": i + 1,
                        "first_fact_s": 7.0 + (i * 0.5),
                        "total_s": _total_s_for[size] + (i * 0.3),
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
        if inject == "discarded_valid_rows":
            # 完成样本被丢弃：retry ledger 记录到某次尝试已有有效样本却仍继续重试。
            bad_ctx["retry_ledger"] = [{"attempt": 2, "rc": 0, "valid_rows": 3,
                                        "discarded_valid_rows": True}]
        result = _evaluate(broken, bad_ctx)      # True = 未检出注入缺陷（门禁会放行）
        fail_closed = not result
        exit_code = 0 if result else 1           # 检出缺陷 → 非零退出
        verdict = "FAIL-CLOSED" if fail_closed else "NOT_FAIL_CLOSED"
        print(f"INJECT_CASE={inject} verdict={verdict} exit={exit_code}")
        print(json.dumps({"case": inject, "fail_closed": fail_closed, "exit_code": exit_code,
                          "fail_messages": bad_ctx["fails"]}, ensure_ascii=False))
        return exit_code

    # 正常门禁模式：跑真实 6 格 x n
    print(f"[sixgrid] 开始收集 {len(sizes)}x{len(_ALL_MODES)} 格 x n={n}（真实模型，较慢）...", flush=True)
    dataset: list[dict] = []
    retry_ledger: list[dict] = []
    for mode in _ALL_MODES:
        for size in sizes:
            print(f"[sixgrid]  {mode}/{size} n={n} ...", flush=True)
            rows, led = _collect(size, mode, n)
            dataset.extend(rows)
            retry_ledger.extend(led)
            print(f"[sixgrid]    -> {len(rows)} 样本", flush=True)

    ctx["cells"] = {}
    for mode in _ALL_MODES:
        for size in sizes:
            key = f"{mode}/{size}"
            ctx["cells"][key] = sum(1 for x in dataset
                                    if x.get("status") == "SUCCEEDED"
                                    and x.get("mode") == mode and x.get("size") == size)
    ctx["retry_ledger"] = retry_ledger

    pass_all = _evaluate(dataset, ctx)
    summary = {
        "gate": "V2.2.0 R3 six-grid performance (fail-closed)",
        "pass": pass_all,
        "n_samples": len(dataset),
        "cells": ctx["cells"],
        "first_fact_median_s": ctx["first_fact_median"],
        "first_fact_max_s": ctx["first_fact_max"],
        "first_fact_limit_s": FIRST_FACT_LIMIT_S,
        # §R3-20：结构化输出四格基线与降幅（供 manifest 独立重算，不信任顶层 pass）。
        "four_grid": ctx.get("four_grid", {}),
        "four_grid_all_ok": all(v.get("ok") is True for v in ctx.get("four_grid", {}).values()),
        # §R3-20：逐 cell/整轮尝试的 retry ledger；只有无有效 JSON 的基础设施失败可重试。
        "retry_ledger": retry_ledger,
        "retry_ledger_any_discard": any(
            e.get("discarded_valid_rows")
            or (e.get("attempt", 1) > 1 and e.get("valid_rows", 0) > 0)
            for e in retry_ledger),
        "fail_messages": ctx["fails"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if out is not None:
        exe_sha = None
        exe_bytes = 0
        if exe_path is not None:
            p = Path(exe_path)
            exe_bytes = p.stat().st_size if p.is_file() else 0
            if p.is_file():
                exe_sha = _sha256_file(p)
        evidence = {
            "_meta": {
                "generator": "backend/_e2e_v22_aggregate.py",
                "plan_blob": "7d8a249a5ec3e607855f20d794bb7ed9cda351ee",
            },
            "exe": {"path": str(exe_path) if exe_path is not None else None,
                    "sha256": exe_sha, "size": exe_bytes},
            "gate_passed": bool(pass_all),
            "pass": bool(pass_all),
            # 逐样本原始数据：供 Acceptance 复算中位数/最大值、样本身份唯一性与调用契约。
            "samples": dataset,
            **summary,
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if pass_all else 1


if __name__ == "__main__":
    sys.exit(main())