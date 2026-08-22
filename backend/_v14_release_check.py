"""V1.4.2+ 发布前只读清洁验证（不重建 Git 历史，不执行 push）。

V1.4.0/1 的一次性首发重建（_v14_t8_delivery.py）已退出：公开仓库建立后，
后续版本应使用正常增量 Git 流程，不再每次重建 orphan/single-commit 仓库，
也不应把 force push 当作常规发布方式。

本脚本只做只读验证：
  1. Git 跟踪范围是否符合规则（runtime/敏感/验收产物不被跟踪）；
  2. 必要白名单模板是否被跟踪（B1）；
  3. 源码树中是否存在本机绝对路径、用户名、密钥等真实 PII；
  4. 公开信息（仓库 URL / release / tag）不被误报为敏感；
  5. 工作区是否 clean、当前分支与基线 commit 是否符合预期。

执行：
    cd backend
    python _v14_release_check.py [--repo-root ..]
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


# —— A 类 input/ 文件名白名单（纯虚构，无 PII）—— #
_INPUT_LEGIT_FNAMES = {"demo_profile.json", "demo_experiences.json", "demo_jd.txt"}

# —— C/D 类目录排除（不得进入 Git 跟踪）—— #
_DIR_EXCLUDE_NO_GIT = {
    "data", "output", "logs", "cache",
    "validation-artifacts",
}

# —— C1 显式文件排除（冻结快照不应跟踪，requirements.txt 是唯一依赖真源）—— #
_FILE_ALWAYS_EXCLUDE_RELPATHS = {"backend/pip_freeze_baseline.txt"}

# —— B 类白名单模板：必须被 Git 跟踪 —— #
_B_TRACKED_RELPATHS = {"backend/templates/pm_template.docx"}

# —— 环境文件排除 —— #
_FILE_EXCLUDE_NO_GIT = {".env", ".env.local", ".env.user"}

# —— 公开信息不应被隐私扫描误删的模式（匹配命中视为正常用户入口，不计入 PII）—— #
_PUBLIC_GITHUB_PATTERNS = [
    re.compile(r"github\.com[/:][A-Za-z0-9_\-]+/[A-Za-z0-9_\-\.]+"),
    re.compile(r"releases?/tag/v?\d+\.\d+"),
    re.compile(r"(?i)mit license"),
]

# —— 真正需要扫描的本机 PII 模式（命中公开模式时自动豁免）—— #
_PII_PATTERNS = [
    (re.compile(r"[A-Za-z]:\\Users\\[^\"'\s]+"), "Windows 本机绝对用户路径"),
    (re.compile(r"~\.[A-Za-z0-9_\-\.]+\\trae\-cn"), "本机 Trae 私有目录"),
    (re.compile(r"[A-Za-z0-9_\-]{8,}\.trae\.local"), "本机内网私有域名"),
    (re.compile(r"(?i)(ark_api_key|openai_api_key|api[_-]?key|secret)\s*[:=]\s*[\"'][^\"']{8,}[\"']"), "明文 API Key"),
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.(com|cn|net|org|io|edu)\b"), "真实邮箱（排除 example.com）"),
]


def _run_git(args, repo_root):
    out = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def check_git_tracking(repo_root):
    findings = []
    tracked = _run_git(["ls-files"], repo_root).splitlines()
    tracked_set = set(tracked)

    for rel in sorted(_B_TRACKED_RELPATHS):
        if rel in tracked_set:
            findings.append(("B1", f"✅ 跟踪: {rel}"))
        else:
            findings.append(("B1", f"❌ 缺失跟踪: {rel}（TemplateRenderer 无法加载模板）"))

    for rel in sorted(tracked):
        parts = rel.replace("\\", "/").split("/")
        for seg in parts[:-1]:
            if seg in _DIR_EXCLUDE_NO_GIT:
                findings.append(("B2", f"❌ 运行时目录文件被跟踪: {rel}（位于 {seg}/）"))
                break

    for rel in sorted(_FILE_ALWAYS_EXCLUDE_RELPATHS):
        if rel in tracked_set:
            findings.append(("C1", f"❌ freeze 快照被跟踪: {rel}（requirements.txt 是唯一依赖真源）"))
        else:
            findings.append(("C1", f"✅ 排除: {rel}"))

    for rel in sorted(_FILE_EXCLUDE_NO_GIT):
        if rel in tracked_set:
            findings.append(("B2-env", f"❌ 环境文件被跟踪: {rel}"))
        else:
            findings.append(("B2-env", f"✅ 未跟踪: {rel}"))

    for rel in sorted(tracked):
        parts = rel.replace("\\", "/").split("/")
        if "input" in parts[:-1] and parts[-1] not in _INPUT_LEGIT_FNAMES and Path(rel).suffix != "":
            findings.append(("B2-input", f"❌ input 非白名单文件被跟踪: {rel}"))

    return findings


def check_privacy(repo_root):
    findings = []
    scanned_files = []

    for root, dirs, fnames in os.walk(repo_root):
        prune = []
        for d in dirs:
            if d in {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache",
                    ".ruff_cache", "node_modules", ".workbuddy"}:
                prune.append(d)
        for d in prune:
            dirs.remove(d)
        for fn in fnames:
            p = Path(root) / fn
            if p.suffix.lower() in {".py", ".md", ".json", ".txt", ".yaml", ".yml",
                                    ".cfg", ".ini", ".toml", ".html", ".js", ".ts",
                                    ".css", ".sh", ".ps1", ".bat"}:
                scanned_files.append(p)

    def _is_public_info(t):
        return any(p.search(t) for p in _PUBLIC_GITHUB_PATTERNS)

    hits_by_file = {}
    for f in scanned_files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat, desc in _PII_PATTERNS:
            for m in pat.finditer(text):
                match_text = m.group(0)
                if _is_public_info(match_text):
                    continue
                if desc == "真实邮箱" and match_text.lower().endswith("@example.com"):
                    continue
                rel = f.relative_to(repo_root).as_posix()
                hits_by_file.setdefault(rel, []).append(f"{desc}: {match_text[:80]}")

    if not hits_by_file:
        findings.append(("PII", "✅ 未发现本机 PII、密钥或真实用户邮箱"))
    else:
        for rel in sorted(hits_by_file):
            for hint in hits_by_file[rel][:3]:
                findings.append(("PII", f"❌ {rel}: {hint}"))
    return findings


def check_workspace(repo_root):
    findings = []
    status = _run_git(["status", "--porcelain"], repo_root)
    if status == "":
        findings.append(("Git", "✅ 工作区 clean"))
    else:
        findings.append(("Git", f"⚠️  工作区未提交变更:\n{status}"))

    branch = _run_git(["branch", "--show-current"], repo_root)
    findings.append(("Git", f"当前分支: {branch}"))

    head = _run_git(["rev-parse", "HEAD"], repo_root)
    findings.append(("Git", f"HEAD commit: {head}"))

    parents_line = _run_git(["rev-list", "--parents", "-n", "1", "HEAD"], repo_root).split()
    parent_count = len(parents_line) - 1
    if parent_count >= 1:
        findings.append(("Git", f"✅ 正常增量历史（{parent_count} 个父提交；无 orphan）"))
    else:
        findings.append(("Git", "⚠️  HEAD 无父提交（仅 V1.4.0 一次性首发时允许）"))

    return findings


def run_all(repo_root):
    sections = {
        "Git 跟踪规则 (B1/B2/C1)": check_git_tracking(repo_root),
        "隐私与 PII": check_privacy(repo_root),
        "工作区与历史": check_workspace(repo_root),
    }
    exit_code = 0
    for _, rows in sections.items():
        for _, msg in rows:
            if msg.startswith("❌"):
                exit_code = 2
    return exit_code, sections


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo-root", default="..", help="Git 仓库根（默认：..）")
    args = ap.parse_args()
    repo_root = Path(args.repo_root).resolve()
    if not (repo_root / ".git").exists():
        print(f"[ERROR] {repo_root} 不是 Git 仓库（找不到 .git）", file=sys.stderr)
        return 3

    print("=" * 60)
    print("V1.4.2+ Release Check — 只读清洁验证")
    print(f"repo : {repo_root}")
    print("=" * 60)
    print()
    code, sections = run_all(repo_root)
    for title, rows in sections.items():
        print(f"[{title}]")
        for tag, msg in rows:
            print(f"  {msg}")
        print()

    print("=" * 60)
    if code == 0:
        print("✅ 全部只读检查通过。下一步按工作流转 T7 / RESULT 补录 / T9 独立验收。")
        print("   本脚本不会创建新仓库、不会改写历史、不会推送 main/tag。")
    else:
        print("❌ 存在阻断项（标 ❌ 行）。修复后重新执行本脚本。")
    print("=" * 60)
    return code


if __name__ == "__main__":
    raise SystemExit(main())