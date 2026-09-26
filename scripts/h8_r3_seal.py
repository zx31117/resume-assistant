#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 R3：中央封存（包 + 证据）+ 脱敏 + CHECKSUMS + SEAL_REPORT。

职责（对照 RESULT §R3-18 §八）：
- 新建 `<acceptance-staging>/<src>/`（包逐字节副本）与 `<acceptance-staging>/<src>-evidence/`；
- 不覆盖或删除既有封存目录（存在则拒绝，除非显式 --force）；
- 证据目录文本类文件脱敏：本机绝对路径 / 用户名 / 临时目录 → 占位符；
- 封存前扫描拒绝：旧包 SHA、旧 bundle、真实 Key 形态、真实联系方式/履历正文、缺失或 hash 不一致；
- 生成 `CHECKSUMS.sha256`（覆盖证据目录全部文件，逐行 `<sha256>  <relpath>`）与 `SEAL_REPORT.json`；
- 输出脱敏映射与统计，供 RESULT 引用。

用法：
  python scripts/h8_r3_seal.py --src 32388b7 --pkg-dir dist/ResumeAssistant \\
      --evidence-dir <ev> --staging-root <acceptance-staging> [--force]
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
    """删除目录树，兼容**只读文件**（产品迁移备份 `*.db.bak` 被 `os.chmod(bak, 0o444)`）。

    Windows 上 `shutil.rmtree(..., ignore_errors=True)` 遇到只读文件会**静默失败**，
    导致隔离 runtime 残留、Gate cleanup 误判失败（已在 mainchain/design_fidelity/
    atomic_publish 复现）。这里在出错回调里清除只读位后重试，并做有限次整体重试以
    吸收句柄释放延迟。
    """
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
    # 本机绝对路径（正/反斜杠）
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
# 疑似真实凭据 / PII 形态（正则）。命中即 fail-closed。
# 注意：手机号必须加**字母数字边界**，否则会误命中 SHA-256 / 统计数字内部的连续数字段
# （已复现：`…a16587404607e…` 被当成手机号）。真实联系方式两侧通常是引号/空格/标点。
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="新 SRC 短名（封存目录名）")
    ap.add_argument("--pkg-dir", required=True)
    ap.add_argument("--evidence-dir", required=True)
    ap.add_argument("--staging-root", required=True)
    ap.add_argument("--extra-forbidden", default="", help="额外禁止子串，逗号分隔")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    pkg = Path(args.pkg_dir).resolve()
    ev = Path(args.evidence_dir).resolve()
    root = Path(args.staging_root).resolve()
    if not pkg.is_dir():
        print(f"[seal] 包目录不存在: {pkg}")
        return 2
    if not ev.is_dir():
        print(f"[seal] 证据目录不存在: {ev}")
        return 2

    forbidden = list(FORBIDDEN_SUBSTRINGS)
    for s in (args.extra_forbidden or "").split(","):
        s = s.strip()
        if s:
            forbidden.append(s.lower())
    pii = list(PII_PATTERNS)

    out_pkg = root / args.src
    out_ev = root / f"{args.src}-evidence"
    for d in (out_pkg, out_ev):
        if d.exists():
            if not args.force:
                print(f"[seal] 目标已存在（拒绝覆盖）：{d}")
                return 3
            _rmtree_force(d)

    problems: list[str] = []
    redact_map: dict[str, int] = {}

    # 1) 包：逐字节复制（不改内容，保持可校验一致性）
    shutil.copytree(pkg, out_pkg)
    pkg_files = [p for p in out_pkg.rglob("*") if p.is_file()]

    # 2) 证据：文本脱敏后写；二进制逐字节复制；同时扫描禁止内容
    out_ev.mkdir(parents=True, exist_ok=True)
    for src_f in sorted(ev.rglob("*")):
        if not src_f.is_file():
            continue
        rel = src_f.relative_to(ev)
        dst = out_ev / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src_f.suffix.lower() in TEXT_EXT:
            try:
                raw = src_f.read_text(encoding="utf-8", errors="replace")
            except Exception as e:  # noqa: BLE001
                problems.append(f"{rel}: 读取失败 {e!r}")
                continue
            _scan_forbidden(raw, str(rel), problems)
            clean = _redact(raw, DEFAULT_REDACTIONS, redact_map)
            dst.write_text(clean, encoding="utf-8")
        else:
            shutil.copy2(src_f, dst)

    # 3) 证据内逐 Gate 交叉的记录数（粗略统计，供报告）
    gates_meta = {}
    gm = out_ev / "gates_run.json"
    if gm.is_file():
        try:
            gates_meta = json.loads(gm.read_text(encoding="utf-8-sig"))
        except Exception:
            gates_meta = {}

    # 3.1) 先写 SEAL_REPORT.json，再写 CHECKSUMS —— 这样 CHECKSUMS 能覆盖**全部**封存文件
    #      （含 SEAL_REPORT.json 自身；仅排除 CHECKSUMS.sha256 以避免自引用）。
    #      （前一 accepted 回合 32388b7-evidence 的 CHECKSUMS 同样包含 SEAL_REPORT.json。）
    ev_files = sorted([p for p in out_ev.rglob("*") if p.is_file()])
    seal = {
        "_meta": {
            "generator": "scripts/h8_r3_seal.py",
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
            "files": len(ev_files) + 1,  # + SEAL_REPORT.json 自身
            "checksums_file": "CHECKSUMS.sha256",
        },
        "gates_recorded": [g.get("gate") for g in (gates_meta.get("gates") or [])],
        "gates_all_exit_zero": gates_meta.get("all_exit_zero"),
        "redaction_map": {k: v for k, v in sorted(redact_map.items())},
        "forbidden_substrings_checked": forbidden,
        "problems": problems,
        "ok": not problems,
    }
    (out_ev / "SEAL_REPORT.json").write_text(
        json.dumps(seal, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4) CHECKSUMS.sha256：覆盖封存证据目录**全部文件**（含 SEAL_REPORT.json），
    #    仅排除 CHECKSUMS.sha256 自身以避免自引用。
    all_files = sorted([p for p in out_ev.rglob("*")
                        if p.is_file() and p.name != "CHECKSUMS.sha256"])
    lines = []
    for p in all_files:
        rel = p.relative_to(out_ev).as_posix()
        lines.append(f"{sha256_file(p)}  {rel}")
    (out_ev / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if problems:
        print("[seal] FAIL-CLOSED：")
        for p in problems[:40]:
            print("  -", p)
        return 1
    print(f"[seal] OK pkg={out_pkg} files={len(pkg_files)}  "
          f"ev={out_ev} files={len(all_files)} checksums={len(lines)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
