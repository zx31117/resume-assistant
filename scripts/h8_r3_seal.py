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


# 现场根路径（**动态**解析，禁止写入用户名/用户目录/项目绝对路径字面量）。
HERE = Path(__file__).resolve().parent
LIVE_ROOT = HERE.parent
LIVE_REPO_PARENT = LIVE_ROOT.parent
try:
    HOME = Path.home()
except Exception:  # noqa: BLE001
    HOME = None


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


# §R3-28 §28.7-2：文本判定改为**二进制嗅探**（前 8KB 无 NUL 且可 UTF-8 解码），
# 从而天然覆盖 `.diff` 等无扩展名白名单的文本类证据（旧版按扩展名白名单会把 `.diff`
# 当二进制原样复制，导致本机绝对路径直接进入封存）。
_SNIFF_BYTES = 8192


def _looks_text(head: bytes) -> bool:
    """前 8KB 无 NUL 且可严格 UTF-8 解码（增量解码，容忍末尾被截断的多字节序列）。"""
    if b"\x00" in head:
        return False
    import codecs
    dec = codecs.getincrementaldecoder("utf-8")()
    try:
        dec.decode(head)
    except UnicodeDecodeError:
        return False
    return True


def _path_regex(p: Path) -> str:
    """把绝对路径编译为**分隔符不敏感**的正则（`\\` 与 `/` 均可，大小写不敏感）。"""
    parts = [x for x in re.split(r"[\\/]+", str(p)) if x]
    return r"[\\/]+".join(re.escape(x) for x in parts)


def _dynamic_redactions() -> list[tuple[str, str]]:
    """由**动态现场根**生成脱敏规则（最长优先，避免父目录先吃掉子目录前缀）。"""
    roots: list[tuple[Path, str]] = [
        (LIVE_ROOT, "<current-workspace>"),
        (LIVE_REPO_PARENT, "<repo-parent>"),
    ]
    if HOME is not None:
        roots.append((HOME, "<home>"))
    out: list[tuple[str, str]] = []
    for p, rep in sorted(roots, key=lambda t: len(str(t[0])), reverse=True):
        if str(p):
            out.append((_path_regex(p), rep))
    return out


# 通用路径词法（在动态现场根之后应用）：盘符路径 / UNC（含 JSON 双反斜杠）/ 类 Unix 用户目录。
GENERIC_REDACTIONS: list[tuple[str, str]] = [
    (r"[A-Za-z]:[\\/]+[^\s\"'<>|*?\r\n]+", "<local-path>"),
    (r"\\{2,}[A-Za-z0-9_.\-]+(?:[\\/]+[^\s\"'<>|*?\r\n]*)?", "<unc-path>"),
    (r"/(?:home|Users)/[^\s\"'<>|*?]+", "<home>"),
    (r"%TEMP%", "<temp>"),
]

# 公开 HTTP(S) URL：先掩蔽、脱敏后复扫、最后还原——**不得**被误报为 UNC/本地路径。
_URL_RE = re.compile(r"https?://[^\s\"'<>\\]+")

# 脱敏后 fail-closed 复扫的本地路径词法。
_LOCAL_PATH_RESCAN: list[tuple[str, str]] = [
    (r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]+[^\s\"'<>|*?\r\n]+", "盘符绝对路径"),
    (r"\\{2,}[A-Za-z0-9_.\-]+(?:[\\/]+[^\s\"'<>|*?\r\n]*)", "UNC/双反斜杠路径"),
    (r"/(?:home|Users)/[^\s\"'<>|*?]+", "类 Unix 用户目录"),
]


def _live_literals() -> list[str]:
    """现场绝对路径字面量（工作区 / 仓库父目录 / 家目录 / 临时目录），复扫零命中依据。"""
    import tempfile
    lits: list[str] = []
    for p in (LIVE_ROOT, LIVE_REPO_PARENT, HOME):
        if p is not None and str(p):
            lits.append(str(p))
    try:
        lits.append(tempfile.gettempdir())
    except Exception:  # noqa: BLE001
        pass
    return [x for x in lits if x]

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
        text, n = re.subn(pat, rep, text, flags=re.IGNORECASE)
        if n:
            mapping[rep] = mapping.get(rep, 0) + n
    return text


def _mask_urls(text: str, store: dict[str, str]) -> str:
    """把公开 HTTP(S) URL 掩蔽为不可命中路径词法的占位符（脱敏后还原）。"""
    def _repl(m: re.Match) -> str:
        token = f"\x00URL{len(store)}\x00"
        store[token] = m.group(0)
        return token
    return _URL_RE.sub(_repl, text)


def _restore_urls(text: str, store: dict[str, str]) -> str:
    for token, url in store.items():
        text = text.replace(token, url)
    return text


def _scan_forbidden(text: str, where: str, problems: list[str],
                    forbidden: list[str]) -> int:
    """按**实际传入**的 forbidden 列表 + PII 形态扫描（返回命中数）。

    §R3-28 §28.7-2：旧版忽略传入列表、只遍历全局常量，导致 `--extra-forbidden`
    只写进报告、实际未参与扫描（fail-open）。本版以参数为准。
    """
    hits = 0
    low = text.lower()
    for s in forbidden:
        if s and s in low:
            problems.append(f"{where}: 命中禁止子串 {s[:16]}…")
            hits += 1
    for pat, label in PII_PATTERNS:
        if re.search(pat, text):
            problems.append(f"{where}: 命中疑似 {label}")
            hits += 1
    return hits


def _rescan_local_paths(text: str, where: str, problems: list[str]) -> int:
    """脱敏后的 fail-closed 复扫：盘符/UNC/用户目录/现场字面量/PII 任一命中即计入。

    传入口为**已掩蔽 URL** 的文本，因此公开 HTTP(S) URL 不会误报为本地路径。
    """
    hits = 0
    for pat, label in _LOCAL_PATH_RESCAN:
        n = len(re.findall(pat, text))
        if n:
            problems.append(f"{where}: 脱敏后仍残留{label}（{n} 处）")
            hits += n
    low = text.lower()
    for lit in _live_literals():
        if lit.lower() in low:
            problems.append(f"{where}: 脱敏后仍残留现场绝对路径字面量")
            hits += 1
    for pat, label in PII_PATTERNS:
        if re.search(pat, text):
            problems.append(f"{where}: 脱敏后仍命中疑似 {label}")
            hits += 1
    return hits


def _desensitize_tree(src: Path, dst: Path, forbidden: list[str],
                      redactions: list[tuple[str, str]],
                      redact_map: dict[str, int], problems: list[str]) -> dict:
    """把 src 目录脱敏复制到 dst（文本按二进制嗅探判定）。返回统计。"""
    stats = {"text_files": 0, "binary_files": 0,
             "forbidden_hits": 0, "path_rescan_hits": 0}
    dst.mkdir(parents=True, exist_ok=True)
    for src_f in sorted(src.rglob("*")):
        if not src_f.is_file():
            continue
        rel = src_f.relative_to(src)
        out_f = dst / rel
        out_f.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = src_f.read_bytes()
        except Exception as e:  # noqa: BLE001
            problems.append(f"{rel}: 读取失败 {type(e).__name__}")
            continue
        if not _looks_text(data[:_SNIFF_BYTES]):
            stats["binary_files"] += 1
            out_f.write_bytes(data)
            continue
        try:
            raw = data.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"{rel}: 文本嗅探通过但整体非 UTF-8（fail-closed）")
            out_f.write_bytes(data)
            continue
        stats["text_files"] += 1
        store: dict[str, str] = {}
        masked = _mask_urls(raw, store)
        clean = _redact(masked, redactions, redact_map)
        stats["forbidden_hits"] += _scan_forbidden(clean, str(rel), problems, forbidden)
        stats["path_rescan_hits"] += _rescan_local_paths(clean, str(rel), problems)
        # 写回必须禁用换行翻译，避免 Windows CRLF 翻译改变字节。
        with open(out_f, "w", encoding="utf-8", newline="") as fh:
            fh.write(_restore_urls(clean, store))
    return stats


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
    with open(gm, "w", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(meta, ensure_ascii=False, indent=2))
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

    redactions = _dynamic_redactions() + GENERIC_REDACTIONS
    redact_map: dict[str, int] = {}
    problems: list[str] = []
    stats = _desensitize_tree(ev, staged, forbidden, redactions, redact_map, problems)

    # 重算 gates_run.json evidence_sha256（脱敏后字节）
    meta = _recompute_gates_hashes(staged)

    report = {
        "generator": "scripts/h8_r3_seal.py stage",
        "staged_at_local": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "source_evidence_dir": ev.name,
        "staged_evidence_dir": staged.name,
        "text_detection": f"binary-sniff({_SNIFF_BYTES}B, no-NUL + strict utf-8)",
        "redaction_placeholders": sorted({rep for _, rep in redactions}),
        "redaction_map": {k: v for k, v in sorted(redact_map.items())},
        "forbidden_substrings_checked": forbidden,
        "counts": stats,
        "local_path_rescan_fail_closed": True,
        "local_path_rescan_zero_hit": stats["path_rescan_hits"] == 0,
        "gates_recorded": [g.get("gate") for g in (meta.get("gates") or [])],
        "problems": problems,
        "ok": not problems,
    }
    with open(staged / "STAGE_REPORT.json", "w", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(report, ensure_ascii=False, indent=2))

    if problems:
        print("[seal:stage] FAIL-CLOSED：")
        for p in problems[:40]:
            print("  -", p)
        return 1
    n = len([p for p in staged.rglob("*") if p.is_file()])
    print(f"[seal:stage] OK staged={staged} files={n} text={stats['text_files']} "
          f"binary={stats['binary_files']} redactions={sum(redact_map.values())} "
          f"path_rescan_hits={stats['path_rescan_hits']}")
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

    # §R3-28 §28.7-5：封存前必须确认 staging 自身已 fail-closed（无未解决 problems）。
    stage_ok = None
    srep = staged / "STAGE_REPORT.json"
    if srep.is_file():
        try:
            stage_ok = json.loads(srep.read_text(encoding="utf-8-sig")).get("ok")
        except Exception:  # noqa: BLE001
            print("[seal] FAIL-CLOSED: STAGE_REPORT.json 不可解析")
            return 2
        if stage_ok is not True:
            print("[seal] FAIL-CLOSED: staging STAGE_REPORT.ok 非 true，拒绝封存")
            return 1

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
            "stage_report_ok": stage_ok,
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
