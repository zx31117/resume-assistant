#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 R3 返工：真实 runtime 只读哨兵（rel/size/mtime/hash）。

用途：本轮所有测试/demo 均使用仓库外隔离 `RESUME_DATA_DIR`；真实用户 runtime
（默认 `%LOCALAPPDATA%/ResumeAssistant`）全程只读。本工具在轮次开始与结束各采集一次
**逐文件**相对路径、字节数、mtime(ns) 与 SHA-256，并做集合/内容差分。

纪律：
- 只读：仅 `os.scandir` + `open('rb')`；不创建、不删除、不重命名任何真实 runtime 对象。
- 脱敏：输出中只保留 **相对路径**（相对 runtime 根），不写本机绝对路径与用户名。
- 差分口径：新增 / 删除 / 内容变化（size 或 mtime 或 sha 变化）；目录本身的 mtime 不计。

用法：
  python scripts/h8_r3_runtime_sentinel.py capture --out <snapshot.json>
  python scripts/h8_r3_runtime_sentinel.py diff --before <a.json> --after <b.json> --out <diff.json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKIP_DIR_NAMES = {".instance"}


def _default_runtime_root() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "ResumeAssistant"
        return Path.home() / "AppData" / "Local" / "ResumeAssistant"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ResumeAssistant"
    return Path.home() / ".local" / "share" / "resume-assistant"


def sha256_file(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def capture(root: Path) -> dict:
    files: dict[str, dict] = {}
    skipped: list[str] = []
    if not root.is_dir():
        return {"root_exists": False, "files": {}, "skipped": [], "count": 0, "total_bytes": 0}
    for dirpath, dirnames, filenames in os.walk(root):
        # 不进入 .instance（运行时锁目录，含频繁变化的 pid/lock 文件；不属用户数据）
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            fp = Path(dirpath) / name
            rel = str(fp.relative_to(root)).replace("\\", "/")
            try:
                st = fp.stat()
            except OSError:
                skipped.append(rel)
                continue
            rec = {"size": int(st.st_size), "mtime_ns": int(st.st_mtime_ns)}
            try:
                rec["sha256"] = sha256_file(fp)
            except OSError:
                rec["sha256"] = None
                skipped.append(rel)
            files[rel] = rec
    return {
        "root_exists": True,
        "files": files,
        "skipped": sorted(skipped),
        "count": len(files),
        "total_bytes": sum(v["size"] for v in files.values()),
    }


def diff(before: dict, after: dict) -> dict:
    bf = before.get("files") or {}
    af = after.get("files") or {}
    added = sorted(set(af) - set(bf))
    removed = sorted(set(bf) - set(af))
    changed = sorted(
        k for k in (set(bf) & set(af))
        if (bf[k]["size"] != af[k]["size"]
            or bf[k]["mtime_ns"] != af[k]["mtime_ns"]
            or bf[k].get("sha256") != af[k].get("sha256"))
    )
    return {
        "before_count": len(bf),
        "after_count": len(af),
        "before_total_bytes": before.get("total_bytes"),
        "after_total_bytes": after.get("total_bytes"),
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": len(bf) - len(changed) - len(removed),
        "identical": (not added and not removed and not changed),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--root", default="")
    c.add_argument("--out", required=True)
    d = sub.add_parser("diff")
    d.add_argument("--before", required=True)
    d.add_argument("--after", required=True)
    d.add_argument("--out", default="")
    args = ap.parse_args()

    if args.cmd == "capture":
        root = Path(args.root) if args.root else _default_runtime_root()
        snap = capture(root)
        snap["root_label"] = root.name  # 脱敏：只留末段名
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"mode": "capture", "count": snap["count"],
                          "total_bytes": snap["total_bytes"],
                          "root_exists": snap["root_exists"]}, ensure_ascii=False))
        return 0

    before = json.loads(Path(args.before).read_text(encoding="utf-8-sig"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8-sig"))
    dd = diff(before, after)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(dd, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"mode": "diff", "identical": dd["identical"],
                      "added": len(dd["added"]), "removed": len(dd["removed"]),
                      "changed": len(dd["changed"])}, ensure_ascii=False))
    return 0 if dd["identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
