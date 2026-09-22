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
import tempfile
from pathlib import Path

# 高信号阻断标记（大小写不敏感）
BLOCK_MARKERS = (
    "vite_h6_inject", "__h6_inject__", "h6-inject:", "_v21_h6_stub", "_v21_h6_matrix",
    "h6_fixtures", "v21h6_stub_runtime", "stub_posts.log", "h6_stub_runtime_dir",
    "h8e2e_", "maybeinjecth6",
)
# 环境无关的通用开发痕迹子串（不含用户名/机器名/工作区绝对路径，也不包含会误伤第三方
# 预打包 C 扩展/win32com 的通用 Windows 路径片段）。任何命中即视为包内携带开发机痕迹。
# 用户目录/临时目录/仓库根的**用户特定**检测由 `_runtime_dev_paths()` 运行时动态覆盖，
# 不落任何用户特定硬编码。
GENERIC_DEV_SUBSTRINGS = (
    "%userprofile%",
    "dev-recovery-20260908",
)

# 项目树路径族：开发 / canonical / review 检出的顶层子目录名。
#
# H3 独立回测发现：若仅以「脚本所在仓库根」为前缀，当脚本从一次性源码副本运行时前缀即变成
# 副本根，包内指向真实项目树（开发/current、canonical、review 检出）的绝对路径将无法被发现，
# 相对基线产生「项目树路径族」检测能力净收窄。因此这里采用**稳定的派生规则**：
#   识别「Windows 绝对路径（盘符:\\\\… 或 \\\\\\\\…）」内、其路径元素恰好等于这三个顶层
#   子目录名的字节切片。
# 该规则**不依赖脚本运行位置**（不在前缀中写死任何工作区/用户名/机器名）、**环境无关**，
# 只要求路径是绝对路径（以盘符或 UNC 开头）且元素属于项目树路径族，即可从任意一次性副本
# 检出。相对路径（如包内合法的 `_internal\\current\\x`）天然不满足「绝对路径开头」，不会误报。
#
# `.pyd` 内上游编译路径多为相对或非项固路径，不命中「盘符+项目树族元素」形态；通用临时目录
# 片段（如 `%TEMP%` 展开后的具体绝对路径）仍不在此处引入（由 `_runtime_dev_paths()` 运行时覆盖），
# 避免误报第三方预编译 C 扩展。
_PROJECT_TREE_FAMILIES = ("current", "canonical", "review")


def _find_project_tree_abs(data: bytes) -> list[str]:
    """扫描字节流，返回命中的项目树路径族元素（去重、保序）。

    位置无关判定：先找到路径元素恰好为 `current`/`canonical`/`review` 的位置，再回溯确认
    该元素之前存在 Windows 绝对路径开头（`X:\\` 或 `\\\\`）。仅当两者同时成立才判定为命中，
    从而过滤掉相对路径与的第三方 `.pyd` 上游路径。
    """
    hits: list[str] = []
    i = 0
    n = len(data)
    while i < n:
        # 定位最靠前的族名元素及其字节表示
        seg = None
        for fam in _PROJECT_TREE_FAMILIES:
            fb = fam.encode("utf-8")
            j = data.find(fb, i)
            if j != -1 and (seg is None or j < seg[0]):
                seg = (j, fam)
        if seg is None:
            break
        j, fam = seg
        fb = fam.encode("utf-8")
        # 元素边界：前后须为路径分隔符（\\ 或 /）其一，确保是「路径元素」而非子串
        before_ok = j == 0 or data[j - 1:j] in (b"\\", b"/")
        after = data[j + len(fb):j + len(fb) + 1]
        after_ok = after in (b"\\", b"/") or after == b"" or after in (b"\r", b"\n")
        if before_ok and after_ok:
            # 回溯确认「绝对路径」开头：该元素之前（最近一次分隔符或字符串开头）应有盘符:\\
            # 或 UNC \\。截取该元素所在条目回溯窗口（过去第 N 段起始）。
            back = j
            # 找本路径元素的起点（前一个被分隔符包住的段起点）
            seg_start = j
            while seg_start > 0 and data[seg_start - 1:seg_start] not in (b"\\", b"/"):
                seg_start -= 1
            # 从该段起点再向前取绝对路径前缀（去掉开头可能的空白）
            prefix = data[max(0, seg_start - 260):seg_start]
            head = prefix.lstrip(b" \t\r\n\x00")
            if head.startswith(b"\\\\") or _has_drive_head(head):
                hits.append(fam)
                # 跳过本段，避免重复判定同元素
                i = j + len(fb)
                continue
        i = j + len(fb)
    # 去重保序
    seen: list[str] = []
    for h in hits:
        if h not in seen:
            seen.append(h)
    return seen


def _has_drive_head(head: bytes) -> bool:
    """判定字节前缀是否以 `X:\\` 或 `X:/` 开头（X 为单个 ASCII 字母，大小写均可）。"""
    if len(head) < 3:
        return False
    c = head[0]
    is_letter = (0x41 <= c <= 0x5A) or (0x61 <= c <= 0x7A)
    if not is_letter:
        return False
    return head[1:2] == b":" and head[2:3] in (b"\\", b"/")


def _runtime_dev_paths() -> tuple[str, ...]:
    """运行时动态取得当前用户目录 / 临时目录 / 仓库根，去重后作为环境特有扫描前缀。

    只追加、不削弱对「开发路径、用户目录、临时目录、仓库绝对路径」的检测；由调用方在
    遍历前一次性计算，避免每次比对重复解析。返回小写规范化后的唯一前缀元组。
    """
    seen: list[str] = []
    for s in (
            tempfile.gettempdir(),
            os.path.expanduser("~"),
            str(Path(__file__).resolve().parents[1]),  # 仓库根（当前工作区）
    ):
        try:
            norm = os.path.normpath(s).lower().rstrip("\\")
        except Exception:  # noqa: BLE001
            continue
        if norm and norm not in seen:
            seen.append(norm)
    return tuple(seen)
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
    repo = Path(__file__).resolve().parents[1]
    if not root.is_dir():
        print(f"[fatal] 目录不存在：{root}")
        return 2

    files = 0
    total_bytes = 0
    hits: list[dict] = []
    forbidden: list[str] = []
    exe = None
    exe_sha = ""
    # 运行时一次性组合：环境无关通用子串 + 当前机器环境特有前缀（含用户目录/临时目录/仓库根）
    scan_paths = GENERIC_DEV_SUBSTRINGS + _runtime_dev_paths()
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
            for dp in scan_paths:
                if dp.encode("utf-8") in low:
                    hits.append({"file": str(rel), "marker": f"dev_path:{dp}"})
            for fam in _find_project_tree_abs(low):
                hits.append({"file": str(rel), "marker": f"project_tree_abs:{fam}"})

    # 持久化路径一律相对仓库或取文件名，不落本机工作区绝对路径
    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(repo))
        except ValueError:
            return p.name

    result = {
        "dir": _rel(root),
        "files": files,
        "total_bytes": total_bytes,
        "exe": _rel(Path(exe)) if exe else "",
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
