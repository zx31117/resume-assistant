#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 R3：中央封存（包 + 证据）+ 脱敏 + CHECKSUMS + SEAL_REPORT。

§R3-20 返工：拆成两个子命令，使 **manifest 只以脱敏后字节为唯一输入**，并在中央副本上二次 verify：

  1. `stage`   把原始证据目录脱敏复制到全新的 final staging 证据目录，并**重算** `gates_run.json`
               里每项 evidence_sha256（因为脱敏会改变字节）。该 staging 目录即 manifest 的唯一输入。
  2. `seal`    把包逐字节复制到中央 `<src>/`，把 final staging 证据目录逐字节复制到中央
               `<src>-evidence/`，随后写 `SEAL_REPORT.json` 与 `CHECKSUMS.sha256`（覆盖全部文件、
               不覆盖自身）。生成 checksum 后任何文件变化都使封存失败。

用法：
  python scripts/h8_r3_seal.py stage --evidence-dir <raw> --staged-dir <final> [--extra-forbidden ...]
  python scripts/h8_r3_seal.py seal  --pkg-dir dist/ResumeAssistant --staged-dir <final> \
      --staging-root <acceptance-staging> --src <short> [--force]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


def _rmtree_force(path, attempts: int = 8) -> bool:
    """删除目录树，兼容**只读文件**（产品迁移备份 `*.db.bak` 被 `os.chmod(bak, 0o444)`）。"""
    import inspect as _inspect
    import os
    import stat as _stat
    import time as _time

    def _fix(func, p, exc=None):
        try:
            os.chmod(p, _stat.S_IWRITE)
            func(p)
        except Exception:  # noqa: BLE001
            pass

    _params = _inspect.signature(shutil.rmtree).parameters
    _kw = {"onexc": _fix} if "onexc" in _params else {"onerror": _fix}
    for _ in range(attempts):
        try:
            shutil.rmtree(path, **_kw)
        except Exception:  # noqa: BLE001
            pass
        if not os.path.exists(path):
            return True
        _time.sleep(0.4)
    return not os.path.exists(path)


# 文本类扩展名（需要脱敏/扫描）；其余按二进制逐字节复制。
TEXT_EXT = {".json", ".log", ".txt", ".md", ".sha256", ".csv", ".jsonl", ".html", ".xml", ".yaml", ".yml"}

# 占位符映射（顺序敏感：先长后短，避免子串误替换）。
DEFAULT_REDACTIONS: list[tuple[str, str]] = [
    (r"D:[\\/]+demo[\\/]+resume-assistant[\\/]+current", "<current-workspace>"),
    (r"D:[\\/]+demo[\\/]+resume-assistant[\\/]+review", "<canonical-repo>"),
    (r"D:[\\/]+demo[\\/]+resume-assistant", "<repo-parent>"),
    (r"C:[\\/]+Users[\\/]+31117", "<home>"),
    (r"C:[\\/]+Users[\\/]+[A-Za-z0-9_.\-]+", "<home>"),
    (r"%TEMP%", "<temp>"),
    (r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s\"']+[\\/]+AppData[\\/]+Local[\\/]+Temp[\\/]+[^\\/\s\"']*", "<temp>"),
    (r"[A-Za-z]:[\\/]+[^\\/\s\"']*[\\/]+Temp[\\/]+[^\\/\s\"']*", "<temp>"),
]

# 禁止出现的旧对象 SHA / 旧 bundle（仅供追溯，不得进入新封存证据）。
FORBIDDEN_SUBSTRINGS = [
    "32388b7d63a08c8cf6e194d771fb46d9371490ca".lower(),
    "221a12bc917e3ef6128d40b258f602feb8f55c0db42b88049ad7d2d49c589e97".lower(),
    "eed6513ab93826f52a25a1135f30265302349e5c".lower(),
    "c37270c",
    "b7bf632",
    "f8289de",
    "e960f3a0d7acd65d4efd099dc46a1a8c75492bd1".lower(),
    "index-DWWBklCp.js",
    "7450efb0",
]

# 疑似真实凭据 / PII 形态（正则）。命中即 fail-closed。
# 手机号必须加**字母数字边界**，否则会误命中 SHA-256 / 统计数字内部的连续数字段。
PII_PATTERNS = [
    (r"(?i)ark[_-]?api[_-]?key\s*[:=]\s*[\"']?[A-Za-z0-9\-_]{16,}", "ARK key 赋值"),
    (r"(?<![0-9A-Za-z])sk-[A-Za-z0-9]{16,}(?![0-9A-Za-z])", "OpenAI 风格 key"),
    (r"(?<![0-9A-Za-z])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?![0-9A-Za-z])(?=.*key)",
     "UUID key"),
    (r"(?<![0-9A-Za-z])1[3-9]\d{9}(?![0-9A-Za-z])", "疑似手机号"),
    (r"(?<![0-9A-Za-z._%+\-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}(?![0-9A-Za-z])", "疑似邮箱"),
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _redact(text: str, redactions: list[tuple[str, str]], mapping: dict[str, int]) -> str:
    for pat, rep in redactions:
        text, n = re.subn(pat, rep, text)
        if n:
            mapping[rep] = mapping.get(rep, 0) + n
    return text


def _scan_forbidden(text: str, where: str, problems: list[str]) -> None:
    low = text.lower()
    for s in FORBIDDEN_SUBSTRINGS:
        if s in low:
            problems.append(f"{where}: 命中禁止子串 {s[:16]}…")
    for pat, label in PII_PATTERNS:
        if re.search(pat, text):
            problems.append(f"{where}: 命中疑似 {label}")


def _desensitize_tree(src: Path, dst: Path, forbidden: list[str],
                      redact_map: dict[str, int]) -> list[str]:
    """把 src 目录脱敏复制到 dst。返回 problems。"""
    problems: list[str] = []
    dst.mkdir(parents=True, exist_ok=True)
    for src_f in sorted(src.rglob("*")):
        if not src_f.is_file():
            continue
        rel = src_f.relative_to(src)
        out_f = dst / rel
        out_f.parent.mkdir(parents=True, exist_ok=True)
        if src_f.suffix.lower() in TEXT_EXT:
            try:
                raw = src_f.read_text(encoding="utf-8", errors="replace")
            except Exception as e:  # noqa: BLE001
                problems.append(f"{rel}: 读取失败 {e!r}")
                continue
            _scan_forbidden(raw, str(rel), problems)
            clean = _redact(raw, DEFAULT_REDACTIONS, redact_map)
            out_f.write_text(clean, encoding="utf-8")
        else:
            shutil.copy2(src_f, out_f)
    return problems


def _recompute_gates_hashes(staged: Path) -> dict:
    """在脱敏后的 staging 目录上重算 gates_run.json 每项 evidence_sha256 并写回。

    脱敏会改变文本证据字节，因此 gates_run.json 里记录的 evidence_sha256 必须同步更新，
    否则 manifest build 会报 evidence-hash-mismatch。返回更新后的 gates_run dict。
    """
    gm = staged / "gates_run.json"
    if not gm.is_file():
        return {}
    try:
        meta = json.loads(gm.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    for rec in (meta.get("gates") or []):
        ev = rec.get("evidence")
        if not ev:
            continue
        p = staged / ev
        if p.is_file():
            rec["evidence_sha256"] = sha256_file(p)
            rec["evidence_bytes"] = p.stat().st_size
    gm.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def _stage(args) -> int:
    ev = Path(args.evidence_dir).resolve()
    staged = Path(args.staged_dir).resolve()
    if not ev.is_dir():
        print(f"[seal:stage] 证据目录不存在: {ev}")
        return 2

    forbidden = list(FORBIDDEN_SUBSTRINGS)
    for s in (args.extra_forbidden or "").split(","):
        s = s.strip()
        if s:
            forbidden.append(s.lower())

    if staged.exists():
        _rmtree_force(staged)
    staged.mkdir(parents=True, exist_ok=True)

    redact_map: dict[str, int] = {}
    problems = _desensitize_tree(ev, staged, forbidden, redact_map)

    # 重算 gates_run.json evidence_sha256（脱敏后字节）
    meta = _recompute_gates_hashes(staged)

    report = {
        "generator": "scripts/h8_r3_seal.py stage",
        "staged_at_local": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "source_evidence_dir": ev.name,
        "staged_evidence_dir": staged.name,
        "redaction_map": {k: v for k, v in sorted(redact_map.items())},
        "forbidden_substrings_checked": forbidden,
        "gates_recorded": [g.get("gate") for g in (meta.get("gates") or [])],
        "problems": problems,
        "ok": not problems,
    }
    (staged / "STAGE_REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if problems:
        print("[seal:stage] FAIL-CLOSED：")
        for p in problems[:40]:
            print("  -", p)
        return 1
    n = len([p for p in staged.rglob("*") if p.is_file()])
    print(f"[seal:stage] OK staged={staged} files={n} "
          f"redactions={sum(redact_map.values())}")
    return 0


def _seal(args) -> int:
    pkg = Path(args.pkg_dir).resolve()
    staged = Path(args.staged_dir).resolve()
    root = Path(args.staging_root).resolve()
    if not pkg.is_dir():
        print(f"[seal] 包目录不存在: {pkg}")
        return 2
    if not staged.is_dir():
        print(f"[seal] staging 证据目录不存在: {staged}")
        return 2

    out_pkg = root / args.src
    out_ev = root / f"{args.src}-evidence"
    for d in (out_pkg, out_ev):
        if d.exists():
            if not args.force:
                print(f"[seal] 目标已存在（拒绝覆盖）：{d}")
                return 3
            _rmtree_force(d)

    # 1) 包：逐字节复制（不改内容，保持可校验一致性）
    shutil.copytree(pkg, out_pkg)
    pkg_files = [p for p in out_pkg.rglob("*") if p.is_file()]

    # 2) 证据：final staging 目录逐字节复制（不再次脱敏——staging 已是脱敏后字节）
    shutil.copytree(staged, out_ev)
    ev_files_before = [p for p in out_ev.rglob("*") if p.is_file()]

    # 3) 读 gates_run（staging 已重算 hash）用于报告
    gates_meta = {}
    gm = out_ev / "gates_run.json"
    if gm.is_file():
        try:
            gates_meta = json.loads(gm.read_text(encoding="utf-8-sig"))
        except Exception:
            gates_meta = {}

    # 4) SEAL_REPORT.json（在 CHECKSUMS 之前写，使 CHECKSUMS 能覆盖它）
    seal = {
        "_meta": {
            "generator": "scripts/h8_r3_seal.py seal",
            "sealed_at_local": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "src_short": args.src,
        },
        "package": {
            "archive_dir": out_pkg.name,
            "files": len(pkg_files),
            "total_bytes": sum(p.stat().st_size for p in pkg_files),
        },
        "evidence": {
            "archive_dir": out_ev.name,
            "files": len(ev_files_before) + 1,  # + SEAL_REPORT.json 自身
            "checksums_file": "CHECKSUMS.sha256",
        },
        "gates_recorded": [g.get("gate") for g in (gates_meta.get("gates") or [])],
        "gates_all_exit_zero": gates_meta.get("all_exit_zero"),
        "problems": [],
        "ok": True,
    }
    (out_ev / "SEAL_REPORT.json").write_text(
        json.dumps(seal, ensure_ascii=False, indent=2), encoding="utf-8")

    # 5) CHECKSUMS.sha256：覆盖证据目录**全部文件**（含 SEAL_REPORT.json 与 gate_manifest.json），
    #    仅排除 CHECKSUMS.sha256 自身以避免自引用。
    all_files = sorted([p for p in out_ev.rglob("*")
                        if p.is_file() and p.name != "CHECKSUMS.sha256"])
    lines = []
    for p in all_files:
        rel = p.relative_to(out_ev).as_posix()
        lines.append(f"{sha256_file(p)}  {rel}")
    (out_ev / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[seal] OK pkg={out_pkg} files={len(pkg_files)}  "
          f"ev={out_ev} files={len(all_files)} checksums={len(lines)}")
    return 0


def _verify_checksums(args) -> int:
    """校验 CHECKSUMS.sha256 与证据目录现场一致：逐项 hash、无缺失/额外未登记文件。

    用于中央副本二次 verify（§R3-20）：缺失/额外/不一致一律非零退出。
    """
    ev = Path(args.evidence_dir).resolve()
    ck = ev / "CHECKSUMS.sha256"
    if not ck.is_file():
        print("[seal:verify-checksums] 缺 CHECKSUMS.sha256")
        return 1
    problems: list[str] = []
    listed: dict[str, str] = {}
    for line in ck.read_text(encoding="utf-8").splitlines():
        line = line.rstrip("\n")
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            problems.append(f"checksum 行格式非法: {line[:60]!r}")
            continue
        listed[parts[1]] = parts[0]
    # 缺失 / 不一致
    for rel, want in listed.items():
        p = ev / rel
        if not p.is_file():
            problems.append(f"checksum 登记文件缺失: {rel}")
            continue
        if sha256_file(p) != want:
            problems.append(f"checksum 不一致: {rel}")
    # 额外未登记文件（除 CHECKSUMS.sha256 自身）
    actual = {p.relative_to(ev).as_posix() for p in ev.rglob("*")
              if p.is_file() and p.name != "CHECKSUMS.sha256"}
    extra = sorted(actual - set(listed))
    for rel in extra:
        problems.append(f"未登记文件: {rel}")

    out = {"mode": "verify-checksums", "problems": problems, "ok": not problems,
           "listed": len(listed), "actual": len(actual)}
    print(json.dumps(out, ensure_ascii=False))
    return 0 if not problems else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("stage")
    st.add_argument("--evidence-dir", required=True)
    st.add_argument("--staged-dir", required=True)
    st.add_argument("--extra-forbidden", default="")

    sl = sub.add_parser("seal")
    sl.add_argument("--pkg-dir", required=True)
    sl.add_argument("--staged-dir", required=True)
    sl.add_argument("--staging-root", required=True)
    sl.add_argument("--src", required=True)
    sl.add_argument("--force", action="store_true")

    vc = sub.add_parser("verify-checksums")
    vc.add_argument("--evidence-dir", required=True)

    args = ap.parse_args()
    if args.cmd == "stage":
        return _stage(args)
    if args.cmd == "seal":
        return _seal(args)
    return _verify_checksums(args)


if __name__ == "__main__":
    sys.exit(main())
