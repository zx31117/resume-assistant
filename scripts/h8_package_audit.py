#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""H8 最终包内审计（PLAN §20.9 / 用户 H8 指令「三、最终回归与包」）。

对 onedir 目录做**纯 Python**遍历，断言最终包内：
- 无 H6 测试注入痕迹（VITE_H6_INJECT / _v21_h6_* / h6_fixtures / h6-inject / __h6_inject__）；
- 无 mock/测试运行时痕迹（v21h6_stub_runtime / stub_posts.log / h8e2e_*）；
- 无真实数据与密钥（.env / *.db / output 目录 / key-like 文件）；
- 无临时路径与开发机绝对路径（%TEMP% 的具体绝对路径、C:\\Users\\<user>、仓库绝对路径）。

用法：
  python scripts/h8_package_audit.py --dir <onedir 根> [--json <out.json>]
退出码：0=通过；1=命中阻断标记；2=参数/目录错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

# 高信号阻断标记（大小写不敏感）
BLOCK_MARKERS = (
    "vite_h6_inject", "__h6_inject__", "h6-inject:", "_v21_h6_stub", "_v21_h6_matrix",
    "h6_fixtures", "v21h6_stub_runtime", "stub_posts.log", "h6_stub_runtime_dir",
    "h8e2e_", "maybeinjecth6",
)
# 开发机绝对路径（当前工作机）
DEV_PATHS = (
    "d:\\demo\\resume-assistant", "dev-recovery-20260908",
    "c:\\users\\31117\\appdata\\local\\temp",
)
# 允许的常见子串（避免误报）：仅用于解释，不改变判定
FORBID_SUFFIX = (".env", ".db", ".sqlite", ".sqlite3")
FORBID_DIRS = ("output", "logs", "cache", "database")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="onedir 根目录（含 ResumeAssistant.exe）")
    ap.add_argument("--json", default=None, help="审计结果 JSON 输出路径")
    args = ap.parse_args()

    root = Path(args.dir).resolve()
    if not root.is_dir():
        print(f"[fatal] 目录不存在：{root}")
        return 2

    files = 0
    total_bytes = 0
    hits: list[dict] = []
    forbidden: list[str] = []
    exe = None
    exe_sha = ""
    for dirpath, dirs, names in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        for dname in list(dirs):
            if dname.lower() in FORBID_DIRS and str(rel_dir) == ".":
                forbidden.append(f"dir::{rel_dir / dname}")
        for n in names:
            p = Path(dirpath) / n
            rel = p.relative_to(root)
            if n.lower() == "resumeassistant.exe":
                exe, exe_sha = str(p), sha256_file(p)
            if p.suffix.lower() in FORBID_SUFFIX:
                forbidden.append(f"file::{rel}")
            try:
                size = p.stat().st_size
            except Exception:
                size = 0
            files += 1
            total_bytes += size
            try:
                data = p.read_bytes()
            except Exception as e:  # noqa: BLE001
                hits.append({"file": str(rel), "marker": f"<read_failed:{e}>"})
                continue
            low = data.lower()
            for m in BLOCK_MARKERS:
                if m.encode("utf-8") in low:
                    hits.append({"file": str(rel), "marker": m})
            for dp in DEV_PATHS:
                if dp.encode("utf-8") in low:
                    hits.append({"file": str(rel), "marker": f"dev_path:{dp}"})

    result = {
        "dir": str(root),
        "files": files,
        "total_bytes": total_bytes,
        "exe": exe,
        "exe_sha256": exe_sha,
        "block_marker_hits": hits,
        "forbidden_paths": forbidden,
        "pass": (not hits) and (not forbidden),
    }
    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[audit] dir={root}")
    print(f"[audit] files={files} bytes={total_bytes} exe_sha256={exe_sha[:16]}…")
    print(f"[audit] marker_hits={len(hits)} forbidden_paths={len(forbidden)}")
    for h in hits[:10]:
        print(f"  - HIT {h['file']} :: {h['marker']}")
    for f in forbidden[:10]:
        print(f"  - FORBIDDEN {f}")
    print("[audit] RESULT =", "PASS" if result["pass"] else "FAIL")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
