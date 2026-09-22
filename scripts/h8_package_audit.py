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

# ResumeAssistant 项目树身份判别。
#
# H4 独立回测发现：仅凭「绝对路径中出现 current/canonical/review 目录元素」无法证明路径属于
# ResumeAssistant 项目树（普通文档/工作/媒体/网络共享同名目录也会被阻断），且用固定回看窗口
# 提取嵌入文本中的完整路径条目会产生对齐依赖（键值前导、引号、长前缀漏检）。
#
# 因此这里使用**稳定项目标识**作为项目树身份真源：`resume-assistant`（仓库名，环境无关，
# 非用户名/本机用户目录/本机项目绝对路径）。只有当某个绝对路径（盘符 `X:\\`/`X:/` 或 UNC
# `\\\\`/`//` 开头）内含该标识作为**路径段**（前后被 `\\` 或 `/` 包围，或处于条目边界）时，
# 才判定为「属于 ResumeAssistant 项目树的绝对路径」。
#
# 路径条目解析不依赖固定窗口或前置字符对齐：命中标识作为路径段后，向其两侧逐字节行走至
# 条目边界（空白/引号/容器符号/`=` 等非路径字符），还原完整绝对路径条目，再校验绝对路径开头。
# 因此 `path=`/`root=` 键值、单/双引号、JSON 字符串、正反斜杠以及路径元素距条目起点超过
# 260 字节的长上下文均可稳定还原，不产生对齐依赖。
#
# 命中只回「脱敏类别」（项目标识之后的下一路径段），不回显完整路径，不落用户名/本机目录/本机
# 项目绝对路径。用户目录/临时目录/fixture/测试注入/禁止目录/旧 bundle 检测由其余逻辑保留。
_PROJECT_TREE_IDENT = "resume-assistant"
_IDENT_B = _PROJECT_TREE_IDENT.encode("utf-8")
# 路径条目终止/边界字符（不会出现在合法 Windows 路径条目内部的定界符）。
# 注意：space（0x20）**故意不在** 边界集内——真实 Windows 路径的路径段可含空格
# （如 `D:\\work dir\\resume-assistant\\current`），空格应作为路径字符保留，不能截断条目。
_PATH_EXIT = frozenset(map(ord, "\t\r\n\x00\x0b\x0c\"'\"`,;()[]{}<>|=!"))
# URI scheme 归一化：`scheme://`（如 http/https/ftp/s3/file 等）在字节流中被整体中性化为
# 等长空格。目的是让 URL 的 `X:/`/`://` **绝不**被误判为盘符/UNC 头，从根上消除 URL 误报；
# URL 是否带 `.git`、`/blob/`、查询串、片段或业务路径都不影响其「非文件系统路径」判定。
_URI_SCHEME_RE = re.compile(rb"[A-Za-z][A-Za-z0-9+\-.]*://")
# 驱动器头：`X:\\` 或 `X:/`（单字母 + 冒号 + 单个分隔符）。驱动器头可在条目内任意位置出现
# （支持长前缀淹没），因为 URL 已被中性化，剩余 `X:` 极低概率为误匹配。
_DRIVE_HEAD_RE = re.compile(rb"[A-Za-z]:[\\/]")


def _neutralize_uris(data: bytes) -> bytes:
    """把 URI scheme（`scheme://`）替换为等长空格，返回归一化后的字节流。

    保持字节长度不变，以便标识偏移计算与后续无窗口行走仍成立。
    """
    return _URI_SCHEME_RE.sub(lambda m: b" " * len(m.group(0)), data)


def _path_char(byte: int) -> bool:
    """该字节是否为路径条目可含字符（可打印，且非条目终止/边界定界符，含空格）。"""
    return 32 <= byte <= 126 and byte not in _PATH_EXIT


def _governing_head(entry: bytes, ident_off: int) -> int:
    """返回 `entry` 中**严格位于标识之后句前**（偏移<ident_off）且**最近**的有效文件系统头偏移；
    不存在返回 -1。

    有效 FS 头：
      - 驱动器头 `[A-Za-z]:[\\/]`：可在条目内任意位置（长前缀/多路径场景仍可定位）；
      - UNC 头 `\\`/`//`：仅当处于条目**起点**（token 起点）时有效——因此 JSON 双反斜杠
        `E:\\w\\...` 内部的 `\\`（前方是驱动器）不会被误当 UNC 头，杜绝了 H5 时代
        「取最后一个头选中路径中部 `\\` 导致负偏移 IndexError」的崩溃。

    取「最近」（=最大的严格小于 ident_off 的有效头偏移），使分类总以**该标识自身**的路径段为准；
    任何命中都在标识左侧，`_next_segment` 不会出现负偏移。
    """
    best = -1
    # 驱动器头（任意位置）
    for m in _DRIVE_HEAD_RE.finditer(entry):
        if m.start() < ident_off and m.start() > best:
            best = m.start()
    # UNC 头（仅条目起点；起点天然 < ident_off，只要标识在起点之后）
    if (entry.startswith(b"\\\\") or entry.startswith(b"//")) and 0 < ident_off:
        if 0 > best:
            best = 0
    return best


def _next_segment(entry: bytes, ident_off: int) -> str:
    """返回条目中位于项目标识之后的下一路径段（脱敏类别）。

    驱动式边界：保证 ident_off 在有效范围内才读取，越界/负偏移一律返回 unknown，绝不崩溃。
    段内容保留空格（空格为路径段合法字符，如 `my docs`），只在遇到下一个 `\\`/`/` 分隔符处结束。
    """
    i = ident_off + len(_IDENT_B)
    n = len(entry)
    if not (0 <= ident_off < n):
        return "unknown"
    while i < n and entry[i] in (ord("\\"), ord("/")):
        i += 1
    seg_start = i
    while i < n and entry[i] not in (ord("\\"), ord("/")):
        i += 1
    seg = entry[seg_start:i].decode("ascii", errors="replace")
    return seg if seg else "unknown"


def _find_project_tree_abs(data: bytes) -> list[str]:
    """扫描字节流，返回命中的项目树路径条目类别（去重保序）。

    步骤：
      1. 归一化：把 URI scheme 中性化为空格外来区分 URL 与文件系统；
      2. 以项目标识 `resume-assistant` 作路径段为锚点逐次扫描；
      3. 每次命中向其两侧**无窗口**行走还原条目（空格为路径段合法字符）；
      4. 在条目内取**严格位于标识左侧最近**的有效 FS 头（盘符任意位置 / UNC 仅起点）；
      5. 分类取标识之后下一路径段；只回类别，不回显完整路径/用户名/机器路径。

    仅当「属于 ResumeAssistant 项目树 + 绝对路径」成立才判命中。返回类别保序去重。
    """
    data = _neutralize_uris(data)
    n = len(data)
    pos = 0
    categories: list[str] = []
    seen: set[str] = set()
    while True:
        k = data.find(_IDENT_B, pos)
        if k == -1:
            break
        last = k + len(_IDENT_B)
        # 路径段边界：前/后须为分隔符（或恰为起始/终止边界）
        before = data[k - 1:k] if k > 0 else b""
        after = data[last:last + 1] if last < n else b""
        is_sep_before = before in (b"\\", b"/")
        is_sep_after = after in (b"\\", b"/")
        is_start_boundary = k == 0 or before in (b"", b"\t", b"\r", b"\n", b"\"", b"'", b"=")
        is_end_boundary = last >= n or after in (b"", b"\t", b"\r", b"\n", b"\"", b"'", b"=")
        if not ( (is_sep_before or is_sep_after)
                 and (is_start_boundary or is_sep_before)
                 and (is_end_boundary or is_sep_after) ):
            pos = last
            continue
        # 无窗口行走：向两侧逐字节扩展至条目边界（空格为路径字符，不截断）。
        s = k
        while s > 0 and _path_char(data[s - 1]):
            s -= 1
        e = last
        while e < n and _path_char(data[e]):
            e += 1
        entry = data[s:e]
        # 取严格位于标识左侧最近的有效 FS 头；不存在则跳过（相对路径/纯文本文本）
        head_off = _governing_head(entry, k - s)
        if head_off < 0:
            pos = last
            continue
        cat = _next_segment(entry[head_off:], k - s - head_off)
        if cat not in seen:
            seen.add(cat)
            categories.append(cat)
        # pos=last 而非 pos=e：同一文本含多个绝对路径时可逐个独立判定；分类按各自标识取段。
        pos = last
    return categories


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
            # 异常封闭：项目树路径扫描绝不因任意输入（含 malformed/binary/畸形转义）抛出未捕获
            # 异常导致审计中断。防御式解析已保证不崩溃，此处再做一层兜底，命中记录为可判定的
            # scan_error 类别，审计仍产出结构化结果（pass 依 hits 判定）。
            try:
                fams = _find_project_tree_abs(low)
            except Exception as e:  # noqa: BLE001
                fams = []
                hits.append({"file": str(rel), "marker": f"scan_error:{type(e).__name__}"})
            for fam in fams:
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
