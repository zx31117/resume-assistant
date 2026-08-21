"""V1.4+ C2/C3 修正专用脚本：
1. C2：修正文档中对 docs/versions/*/T8_manifest.json 的陈旧引用（统一指向 <delivery-root>/.t8-manifest.json）
2. C3：把 V1.0–V1.4.x 文档（.md / .json）中真实本机路径替换为通用占位符，保留语义。

占位符约定：
  <repo-root>       — 开发 worktree 根目录
  <delivery-root>   — T8 交付验收 worktree 根
  <worktrees-root>  — .trae-cn worktrees 集合目录
  <user-profile>    — 用户主目录
  <old-dev-root>    — 旧盘符开发根（V1.0–V1.3 历史文档中的 d:\\V1 / E:\\V1 等）
  <temp-dir>        — 系统临时目录

安全设计（§九-3）：
  本脚本不硬编码任何真实用户名、API Key 前缀或本机绝对路径。
  路径匹配使用通配符正则（\\d+ 匹配数字用户名，ark-[a-f0-9]+ 匹配 Key 前缀），
  可适配任意开发者的本机环境，而非仅限当前机器。

注：%LOCALAPPDATA%、RESUME_DATA_DIR 等环境变量或配置常量名称保留原样，
    它们本身就是通用占位符，不是硬编码本机路径。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs"
assert DOCS_ROOT.is_dir(), f"docs not found: {DOCS_ROOT}"

# ============== 通配符模式（不硬编码真实用户名/路径）============== #
# \d+          — 匹配数字用户名（如 Windows 默认风格）
# [^\s\\/]+    — 匹配任意路径段（更宽泛的用户名/目录名兜底）
# ark-[a-f0-9]+ — 匹配火山方舟 API Key 前缀（hex 段）
_UN = r"\d+"                         # 数字用户名通配符
_UN_G = r"[^\s\\/]+"                 # 通用用户名通配符（兜底）

# ============== 替换规则：按优先级从「更具体」到「更通用」排序 ============== #
# 顺序重要：先匹配更长、更具体的路径，避免短路径提前吃掉前缀。
REPLACEMENTS: list[tuple[str, str]] = [
    # —— 1) file:// 链接 —— #
    (
        rf"file:///[cC]:/Users/{_UN}/\.trae-cn/worktrees/V1/feat-generate-code-wiki-qOQiu7",
        r"file:///<repo-root>",
    ),
    (
        rf"file:///[cC]:/Users/{_UN}/\.trae-cn/worktrees/V1/feat-generate-code-wiki-qOQiu7/",
        r"file:///<repo-root>/",
    ),

    # —— 2) 开发 worktree 根（最长的具体路径）—— #
    (
        rf"[cC]:\\Users\\{_UN}\\\.trae-cn\\worktrees\\V1\\feat-generate-code-wiki-qOQiu7",
        r"<repo-root>",
    ),
    (
        rf"[cC]:/Users/{_UN}/\.trae-cn/worktrees/V1/feat-generate-code-wiki-qOQiu7",
        r"<repo-root>",
    ),
    #   JSON 编码变体（双反斜杠）
    (
        rf"[cC]:\\\\Users\\\\{_UN}\\\\\.trae-cn\\\\worktrees\\\\V1\\\\feat-generate-code-wiki-qOQiu7",
        r"<repo-root>",
    ),

    # —— 3) 验收 worktree 根 —— #
    (
        rf"[cC]:\\Users\\{_UN}\\\.trae-cn\\worktrees\\V1高性能验收agent",
        r"<delivery-root>",
    ),
    (
        rf"[cC]:/Users/{_UN}/\.trae-cn/worktrees/V1高性能验收agent",
        r"<delivery-root>",
    ),
    #   验收 worktree 纯名称
    (
        r"V1高性能验收agent",
        r"<delivery-root-name>",
    ),

    # —— 4) 临时目录路径 —— #
    (
        rf"[cC]:\\Users\\{_UN}\\AppData\\Local\\Temp",
        r"<temp-dir>",
    ),
    (
        rf"[cC]:/Users/{_UN}/AppData/Local/Temp",
        r"<temp-dir>",
    ),
    #   JSON 编码变体
    (
        rf"[cC]:\\\\Users\\\\{_UN}\\\\AppData\\\\Local\\\\Temp",
        r"<temp-dir>",
    ),

    # —— 5) 开发 worktrees 集合目录 —— #
    (
        rf"[cC]:\\Users\\{_UN}\\\.trae-cn\\worktrees\\V1",
        r"<worktrees-root>/V1",
    ),
    (
        rf"[cC]:/Users/{_UN}/\.trae-cn/worktrees/V1",
        r"<worktrees-root>/V1",
    ),
    (
        rf"[cC]:\\Users\\{_UN}\\\.trae-cn\\worktrees",
        r"<worktrees-root>",
    ),
    (
        rf"[cC]:/Users/{_UN}/\.trae-cn/worktrees",
        r"<worktrees-root>",
    ),
    #   JSON 编码变体
    (
        rf"[cC]:\\\\Users\\\\{_UN}\\\\\.trae-cn\\\\worktrees\\\\V1",
        r"<worktrees-root>/V1",
    ),

    # —— 5.5) 旧盘符开发根路径（V1.0–V1.3 历史文档）—— #
    (
        r"[dD]:\\V1",
        r"<old-dev-root>",
    ),
    (
        r"[dD]:/V1",
        r"<old-dev-root>",
    ),
    (
        r"[eE]:\\V1",
        r"<old-dev-root>",
    ),
    (
        r"[eE]:/V1",
        r"<old-dev-root>",
    ),

    # —— 6) 用户主目录（兜底）—— #
    (
        rf"[cC]:\\Users\\{_UN}",
        r"<user-profile>",
    ),
    (
        rf"[cC]:/Users/{_UN}",
        r"<user-profile>",
    ),
    #   JSON 编码变体
    (
        rf"[cC]:\\\\Users\\\\{_UN}",
        r"<user-profile>",
    ),
    #   通用兜底：非数字用户名
    (
        rf"[cC]:\\Users\\{_UN_G}",
        r"<user-profile>",
    ),
    (
        rf"[cC]:/Users/{_UN_G}",
        r"<user-profile>",
    ),
]

# ============== API Key 前缀脱敏（§九-3 / L1）============== #
# 至少 8 位 hex 才匹配，避免误伤 ark-api-key 等占位符中的短 hex 段
_ARK_PATTERN = r"ark-[a-f0-9]{8,}"
_ARK_REPLACEMENT = "ark-********"


def _replace_c2_references(text: str) -> str:
    """C2：删除/替换对陈旧 docs/versions/<version>/T8_manifest.json 的引用。"""
    text = re.sub(
        r"\[(?:docs/versions/v1\.\d+(?:\.\d+)?/)?T8_manifest\.json\]\([^)]*T8_manifest\.json\)",
        "`<delivery-root>/.t8-manifest.json`（交付验收 worktree 根唯一 manifest 真源）",
        text,
    )
    text = text.replace(
        "（包括本文件与 T8_manifest.json）",
        "（本文件与版本文档；manifest 真源为交付根 <delivery-root>/.t8-manifest.json）",
    )
    text = re.sub(
        r"`?docs/versions/v1\.\d+(?:\.\d+)?/T8_manifest\.json`?",
        "`<delivery-root>/.t8-manifest.json`",
        text,
    )
    text = re.sub(
        r"(?<!\.t8-)T8_manifest\.json",
        "<delivery-root>/.t8-manifest.json（唯一 manifest 真源）",
        text,
    )
    return text


def _replace_c3_paths(text: str) -> str:
    """C3：把真实本机绝对路径和 API Key 前缀替换为通用占位符。"""
    for pattern, repl in REPLACEMENTS:
        text = re.sub(pattern, repl, text)
    # L1：API Key 前缀脱敏
    text = re.sub(_ARK_PATTERN, _ARK_REPLACEMENT, text)
    return text


def _process_file(f: Path) -> tuple[int, int]:
    """处理单个文件；返回 (c2_hits, c3_hits)。"""
    raw_bytes = f.read_bytes()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw_bytes.decode("utf-8", errors="replace")

    original = text

    text = _replace_c2_references(text)
    text = _replace_c3_paths(text)

    if text == original:
        return 0, 0

    c2_changes = original.count("T8_manifest.json") - text.count("T8_manifest.json") + \
                 (0 if "T8_manifest" in original else 0)
    c3_changes = 0
    for pattern, _ in REPLACEMENTS:
        c3_changes += len(re.findall(pattern, original))
    c3_changes += len(re.findall(_ARK_PATTERN, original))

    f.write_text(text, encoding="utf-8")
    return max(c2_changes, 1), max(c3_changes, 1)


def main() -> int:
    targets = sorted(
        p for p in DOCS_ROOT.rglob("*")
        if p.is_file() and p.suffix.lower() in {".md", ".json"}
    )
    print(f"[C2/C3] 扫描 {len(targets)} 个文档（.md / .json）...\n")

    total_c2 = 0
    total_c3 = 0
    changed_files: list[str] = []

    for f in targets:
        rel = f.relative_to(DOCS_ROOT)
        c2, c3 = _process_file(f)
        if c2 or c3:
            changed_files.append(str(rel))
            total_c2 += c2
            total_c3 += c3
            print(f"  ✏️  {rel}  (C2≈{c2}, C3≈{c3})")

    print(f"\n[C2/C3] Done. {len(changed_files)} files changed.")
    print(f"  C2 manifest 引用修正: ~{total_c2} 处")
    print(f"  C3 绝对路径占位符化: ~{total_c3} 处")

    # 残留检查：使用通配符模式，不硬编码真实字符串
    print("\n[C2/C3] 残留检查...")
    leftovers: list[tuple[str, int, str]] = []
    BAD_PATTERNS = [
        (rf"[cC]:\\Users\\{_UN}\\", "Win drive + username path"),
        (rf"[cC]:/Users/{_UN}/", "URI drive + username path"),
        (r"V1高性能验收agent", "验收 worktree 中文名 (应替换为 <delivery-root>)"),
        (r"T8_manifest\.json", "陈旧 manifest 文件名 (应替换为 <delivery-root>/.t8-manifest.json)"),
        (r"[dDeE]:\\V1", "旧盘符开发根路径 (应替换为 <old-dev-root>)"),
        (r"[dDeE]:/V1", "旧盘符 URI 路径 (应替换为 <old-dev-root>)"),
        (_ARK_PATTERN, "API key 前缀 (应替换为 ark-********)"),
    ]
    for f in targets:
        rel = str(f.relative_to(DOCS_ROOT))
        text = f.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            for pat, label in BAD_PATTERNS:
                if re.search(pat, line):
                    leftovers.append((rel, i, f"{label}: {line.strip()[:120]}"))
    if leftovers:
        print(f"  ⚠️  发现 {len(leftovers)} 处残留（下面列出前 10 条）：")
        for rel, ln, ctx in leftovers[:10]:
            print(f"    - {rel}:{ln}  {ctx}")
        if len(leftovers) > 10:
            print(f"    ... 其余 {len(leftovers)-10} 条省略")
        return 1
    else:
        print("  ✅ 0 残留：未发现硬编码本机路径 / 陈旧 manifest 引用。")
        return 0


if __name__ == "__main__":
    sys.exit(main())
