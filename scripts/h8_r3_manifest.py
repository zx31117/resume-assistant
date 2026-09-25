"""V2.2.0 R3 §R3-10 C：总证据 manifest 生成器 / 一致性校验。

文档要求（RESULT §R3-10 C-1/C-2）：总 manifest 必须记录 PLAN blob、SRC/HANDOFF 身份、最终包路径、
文件数、总字节、EXE 字节、EXE SHA-256、前端 bundle、每个 Gate 的命令/退出码/证据 hash、运行时间、
cleanup 与最终总判定；各 Gate 证据必须各自记录最终 EXE SHA，或通过不可变 hash 引用同一总 manifest，
使全部证据绑定同一 EXE。任一身份或证据不一致即 final_verdict=false 且非零退出。

用法：
  python h8_r3_manifest.py build --src <SRC_SHA> --handoff <HANDOFF_SHA> \
      --exe-sha <EXE_SHA256> --bundle <bundle.js> \
      --package-dir <dist/ResumeAssistant> --evidence-dir <path> \
      [--gates-meta <gates_run.json>] --out <manifest.json>
  python h8_r3_manifest.py verify --out <manifest.json>

退出码 0 = 生成/校验通过；非 0 = 身份或证据不一致。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PLAN_BLOB = "7d8a249a5ec3e607855f20d794bb7ed9cda351ee"

# 参与绑定的 Gate 证据文件名（相对 evidence-dir）。
_GATE_EVIDENCE_FILES = [
    "package_audit.json",
    "pyz_check.json",
    "failure_matrix.json",
    "content_real_model.json",
    "real_model_e2e.json",
    "design_fidelity.json",
    "six_grid_aggregate.json",
]

# 各证据里应含的最终 EXE SHA-256 的 jsonpath（点分）。
_EXE_SHA_PATH = {
    "package_audit.json": "exe_sha256",
    "pyz_check.json": "exe",              # dict → .get("sha256")；str 可为 64-hex 或指向 EXE 的路径
    "failure_matrix.json": "exe_sha256",
    "content_real_model.json": "exe.sha256",
    "real_model_e2e.json": "exe.sha256",
    "design_fidelity.json": "exe_sha256",
    "six_grid_aggregate.json": "exe.sha256",
}


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


def _evidence_exe_sha(ev_dir: Path, fname: str, path: str | None):
    p = ev_dir / fname
    if not p.exists():
        return None, f"missing:{fname}"
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        return None, f"unreadable:{fname}:{e}"
    if path:
        val = _get_by_path(data, path)
        if isinstance(val, dict):
            val = val.get("sha256")
        if isinstance(val, str):
            val = val.lower()
            if not re.fullmatch(r"[0-9a-f]{64}", val):
                # 视为指向最终 EXE 的本地路径：hash 该文件绑定到目标 EXE SHA。
                fp = Path(val)
                if fp.is_file():
                    try:
                        return sha256_file(fp), None
                    except Exception as e:  # noqa: BLE001
                        return None, f"hash-failed:{fname}:{e}"
                return None, f"exe-path-missing:{fname}:{val}"
        return (val if isinstance(val, str) else val), None
    return None, f"no-sha-path:{fname}"


def _package_identity(pkg_dir: Path) -> dict:
    exe = pkg_dir / "ResumeAssistant.exe"
    files = [p for p in pkg_dir.rglob("*") if p.is_file()]
    total_bytes = sum(p.stat().st_size for p in files)
    exe_sha = sha256_file(exe) if exe.is_file() else None
    assets = sorted(pkg_dir.glob("_internal/frontend/dist/assets/index-*.js"))
    return {
        "path": str(pkg_dir),
        "files": len(files),
        "total_bytes": total_bytes,
        "exe_path": str(exe),
        "exe_bytes": exe.stat().st_size if exe.is_file() else 0,
        "exe_sha256": exe_sha,
        "bundle": assets[0].name if assets else None,
    }


def _negative_selftest(ev_dir: Path) -> tuple[dict, list[str]]:
    """负向自测必须满足：>=7 类注入、每类 `fail_closed=true`、且每类**非零退出码**（门禁语义）。

    返回 (记录, problems)。任一不满足都进入 problems，从而压低 final_verdict。
    """
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
    rec = {
        "present": True,
        "sha256": sha256_file(p),
        "bytes": p.stat().st_size,
        "cases": len(cases),
        "all_fail_closed": all_fc,
        "all_exit_codes_nonzero": all_nonzero,
        "nonzero_exit_failures": bad_exit,
        "ok": ok,
    }
    if not all_fc:
        problems.append("负向自测存在非 fail-closed 用例")
    if not all_nonzero:
        problems.append(f"负向自测存在零退出码用例（未按门禁语义非零退出）: {bad_exit}")
    if len(cases) < 7:
        problems.append(f"负向自测用例数 {len(cases)} < 7")
    return rec, problems


def _build(args) -> int:
    exe_sha = args.exe_sha.lower()
    ev_dir = Path(args.evidence_dir)
    if not ev_dir.is_dir():
        print(f"[manifest] evidence dir 不存在: {ev_dir}")
        return 2

    problems: list[str] = []

    pkg = _package_identity(Path(args.package_dir)) if args.package_dir else None
    if pkg is None:
        problems.append("缺少 --package-dir，无法记录最终包文件数/总字节")
    else:
        if pkg["exe_sha256"] != exe_sha:
            problems.append(
                f"包内 EXE sha {str(pkg['exe_sha256'])[:16]}… 与目标 {exe_sha[:16]}… 不一致")
        if args.bundle and pkg["bundle"] != args.bundle:
            problems.append(f"包内前端 bundle {pkg['bundle']} 与目标 {args.bundle} 不一致")

    gates: dict = {}
    for fn in _GATE_EVIDENCE_FILES:
        fpath = ev_dir / fn
        if not fpath.exists():
            gates[fn] = {"present": False}
            problems.append(f"证据缺失: {fn}")
            continue
        val, err = _evidence_exe_sha(ev_dir, fn, _EXE_SHA_PATH.get(fn))
        match = (val is not None and val == exe_sha)
        gates[fn] = {
            "present": True,
            "sha256": sha256_file(fpath),
            "bytes": fpath.stat().st_size,
            "exe_sha256": val,
            "exe_sha_match_target": match,
            "error": err,
        }
        if not match:
            problems.append(f"{fn}: exe sha {val} 与目标 {exe_sha[:16]}… 不一致")

    neg_rec, neg_problems = _negative_selftest(ev_dir)
    problems.extend(neg_problems)

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

    manifest = {
        "_meta": {
            "generator": "scripts/h8_r3_manifest.py",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "plan_blob": PLAN_BLOB,
        },
        "identity": {
            "src": args.src,
            "handoff": args.handoff,
            "plan_blob": PLAN_BLOB,
            "exe_sha256": exe_sha,
            "bundle": args.bundle,
            "package": pkg,
        },
        "gates": gates,
        "negative_selftest": neg_rec,
        "gate_runs": gate_runs,
        "final_verdict": (not problems),
        "problems": problems,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"final_verdict": manifest["final_verdict"], "problems": problems},
                     ensure_ascii=False, indent=2))
    return 0 if not problems else 1


def _verify(args) -> int:
    out = Path(args.out)
    if not out.exists():
        print(f"[manifest] manifest 不存在: {out}")
        return 2
    m = json.loads(out.read_text(encoding="utf-8-sig"))
    problems = list(m.get("problems") or [])
    if (m.get("_meta") or {}).get("plan_blob") != PLAN_BLOB:
        problems.append("PLAN blob 不一致")
    ident = m.get("identity") or {}
    for k in ("src", "handoff", "exe_sha256"):
        if not ident.get(k):
            problems.append(f"identity.{k} 缺失")
    if not ident.get("package"):
        problems.append("identity.package 缺失")
    for name, g in (m.get("gates") or {}).items():
        if not g.get("present") or not g.get("exe_sha_match_target"):
            problems.append(f"{name} 未绑定目标 EXE")
    neg = m.get("negative_selftest") or {}
    if not neg.get("present"):
        problems.append("negative_selftest 缺失")
    elif not neg.get("ok"):
        problems.append(
            "negative_selftest 未通过（需 >=7 用例、全部 fail_closed=true 且非零退出码）")
    ok = bool(m.get("final_verdict")) and not problems
    print(f"[verify] final_verdict={m.get('final_verdict')} exe_sha256={str(ident.get('exe_sha256'))[:16]}… "
          f"problems={len(problems)}")
    for p in problems:
        print(f"  - {p}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--src", required=True)
    b.add_argument("--handoff", required=True)
    b.add_argument("--exe-sha", required=True)
    b.add_argument("--bundle", default="")
    b.add_argument("--package-dir", default="")
    b.add_argument("--gates-meta", default="")
    b.add_argument("--evidence-dir", required=True)
    b.add_argument("--out", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--out", required=True)
    v.add_argument("--evidence-dir")   # 保留占位，兼容调用
    args = ap.parse_args()
    return (_build(args) if args.cmd == "build" else _verify(args))


if __name__ == "__main__":
    sys.exit(main())
