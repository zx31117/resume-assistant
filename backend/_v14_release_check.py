"""V1.4.2+ 发布前只读清洁验证（不重建 Git 历史，不执行 push）。

V1.4.0/1 的一次性首发重建（_v14_t8_delivery.py）已退出：公开仓库建立后，
后续版本应使用正常增量 Git 流程，不再每次重建 orphan/single-commit 仓库，
也不应把 force push 当作常规发布方式。

本脚本只做只读验证：
  1. Git 跟踪范围是否符合规则（runtime/敏感/验收产物不被跟踪）；
  2. 必要白名单模板是否被跟踪（B1）；
  3. 源码树中是否存在本机绝对路径、用户名、密钥等真实 PII；
  4. 公开信息（仓库 URL / release / tag）不被误报为敏感；
  5. 工作区是否 clean、当前分支与基线 commit 是否符合预期；
  6. 内置正反向自测：确保真实邮箱能检出、虚构域名正确排除。

输出全部使用 GBK 安全的 ASCII 标记（[PASS]/[FAIL]/[WARN]），
在默认 Windows 控制台（GBK/CP936）直接运行不乱码。

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


# ---- A class: input/ filenames whitelist (pure fictional, no PII) ---- #
_INPUT_LEGIT_FNAMES = {"demo_profile.json", "demo_experiences.json", "demo_jd.txt"}

# ---- C/D class: directories that must not be tracked ---- #
_DIR_EXCLUDE_NO_GIT = {
    "data", "output", "logs", "cache",
    "validation-artifacts",
}

# ---- C1: explicit file exclusions ---- #
_FILE_ALWAYS_EXCLUDE_RELPATHS = {"backend/pip_freeze_baseline.txt"}

# ---- B class: templates that MUST be tracked ---- #
_B_TRACKED_RELPATHS = {"backend/templates/pm_template.docx"}

# ---- Environment files ---- #
_FILE_EXCLUDE_NO_GIT = {".env", ".env.local", ".env.user"}

# ---- Public info patterns (not PII) ---- #
_PUBLIC_GITHUB_PATTERNS = [
    re.compile(r"github\.com[/:][A-Za-z0-9_\-]+/[A-Za-z0-9_\-\.]+"),
    re.compile(r"releases?/tag/v?\d+\.\d+"),
    re.compile(r"(?i)mit license"),
]

# ---- RFC 2606 / RFC 6761 reserved domains that must NOT be flagged as real PII ---- #
# Anything ending with these domain suffixes is fictional test data.
_RESERVED_DOMAIN_SUFFIXES = (
    "example.com", "example.org", "example.net", "example.edu",
    "should-not-appear.com",   # legacy test domain (being phased out to example.invalid)
)
_RESERVED_TLDS = (".invalid", ".test", ".example", ".localhost")

# ---- PII patterns (hits on public patterns are auto-exempted) ---- #
_PII_PATTERNS = [
    (re.compile(r"[A-Za-z]:\\Users\\[^\"'\s]+"), "Windows local user path"),
    (re.compile(r"~\.[A-Za-z0-9_\-\.]+\\trae\-cn"), "local Trae private dir"),
    (re.compile(r"[A-Za-z0-9_\-]{8,}\.trae\.local"), "local intranet domain"),
    (re.compile(r"(?i)(ark_api_key|openai_api_key|api[_-]?key|secret)\s*[:=]\s*[\"'][^\"']{8,}[\"']"), "plaintext API key"),
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.(com|cn|net|org|io|edu)\b"), "real email (non-reserved)"),
]


def _is_reserved_email(email: str) -> bool:
    """Return True if the email uses a RFC 2606 / 6761 reserved domain or TLD."""
    lower = email.lower()
    for suffix in _RESERVED_DOMAIN_SUFFIXES:
        if lower.endswith("@" + suffix) or lower.endswith("." + suffix):
            return True
    for tld in _RESERVED_TLDS:
        if lower.endswith(tld):
            return True
    # also catch @example.invalid, @test.invalid etc.
    at_idx = lower.rfind("@")
    if at_idx >= 0:
        domain = lower[at_idx + 1:]
        for tld in _RESERVED_TLDS:
            if domain.endswith(tld):
                return True
    return False


def _is_public_info(text: str) -> bool:
    return any(p.search(text) for p in _PUBLIC_GITHUB_PATTERNS)


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
            findings.append(("B1", f"[PASS] tracked: {rel}"))
        else:
            findings.append(("B1", f"[FAIL] missing tracked: {rel} (TemplateRenderer cannot load template)"))

    for rel in sorted(tracked):
        parts = rel.replace("\\", "/").split("/")
        for seg in parts[:-1]:
            if seg in _DIR_EXCLUDE_NO_GIT:
                findings.append(("B2", f"[FAIL] runtime dir file tracked: {rel} (in {seg}/)"))
                break

    for rel in sorted(_FILE_ALWAYS_EXCLUDE_RELPATHS):
        if rel in tracked_set:
            findings.append(("C1", f"[FAIL] freeze snapshot tracked: {rel} (requirements.txt is the sole dep source)"))
        else:
            findings.append(("C1", f"[PASS] excluded: {rel}"))

    for rel in sorted(_FILE_EXCLUDE_NO_GIT):
        if rel in tracked_set:
            findings.append(("B2-env", f"[FAIL] env file tracked: {rel}"))
        else:
            findings.append(("B2-env", f"[PASS] not tracked: {rel}"))

    for rel in sorted(tracked):
        parts = rel.replace("\\", "/").split("/")
        if "input" in parts[:-1] and parts[-1] not in _INPUT_LEGIT_FNAMES and Path(rel).suffix != "":
            findings.append(("B2-input", f"[FAIL] non-whitelist input file tracked: {rel}"))

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

    # Skip this script itself: it contains positive self-test emails by design
    _self_name = Path(__file__).name

    hits_by_file = {}
    for f in scanned_files:
        if f.name == _self_name:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat, desc in _PII_PATTERNS:
            for m in pat.finditer(text):
                match_text = m.group(0)
                if _is_public_info(match_text):
                    continue
                # Email-specific: skip reserved/fictional domains
                if "email" in desc:
                    if _is_reserved_email(match_text):
                        continue
                rel = f.relative_to(repo_root).as_posix()
                hits_by_file.setdefault(rel, []).append(f"{desc}: {match_text[:80]}")

    if not hits_by_file:
        findings.append(("PII", "[PASS] no local PII, keys, or real user emails found"))
    else:
        for rel in sorted(hits_by_file):
            for hint in hits_by_file[rel][:5]:
                findings.append(("PII", f"[FAIL] {rel}: {hint}"))
    return findings


def check_workspace(repo_root):
    findings = []
    status = _run_git(["status", "--porcelain"], repo_root)
    if status == "":
        findings.append(("Git", "[PASS] working tree clean"))
    else:
        findings.append(("Git", f"[WARN] uncommitted changes:\n{status}"))

    branch = _run_git(["branch", "--show-current"], repo_root)
    findings.append(("Git", f"branch: {branch}"))

    head = _run_git(["rev-parse", "HEAD"], repo_root)
    findings.append(("Git", f"HEAD: {head}"))

    parents_line = _run_git(["rev-list", "--parents", "-n", "1", "HEAD"], repo_root).split()
    parent_count = len(parents_line) - 1
    if parent_count >= 1:
        findings.append(("Git", f"[PASS] incremental history ({parent_count} parent(s); no orphan)"))
    else:
        findings.append(("Git", "[WARN] HEAD has no parent (orphan; only V1.4.0 one-shot allowed)"))

    return findings


def _selftest_email_detection():
    """Positive and negative self-test: verify the email regex and reserved-domain logic.

    Positive (must detect): a real-looking email on a non-reserved domain.
    Negative (must NOT detect): emails on example.com, example.invalid, etc.
    """
    findings = []
    email_pat = _PII_PATTERNS[-1][0]  # last pattern is the email regex

    # --- Positive cases: must be detected as real ---
    positive_cases = [
        "user@gmail.com",
        "someone@company.cn",
        "test@real-domain.org",
        "admin@university.edu",
    ]
    pos_ok = True
    for email in positive_cases:
        m = email_pat.search(email)
        if m and not _is_reserved_email(m.group(0)):
            pass  # detected as real = correct
        else:
            pos_ok = False
            findings.append(("SELFTEST", f"[FAIL] positive case NOT detected: {email}"))

    # --- Negative cases: must NOT be detected (reserved domains) ---
    negative_cases = [
        "user@example.com",
        "user@example.org",
        "user@example.net",
        "user@example.edu",
        "user@test.invalid",
        "user@should-not-appear.com",
        "leaked-fake@example.invalid",
        "demo@example.com",
    ]
    neg_ok = True
    for email in negative_cases:
        m = email_pat.search(email)
        if m and not _is_reserved_email(m.group(0)):
            neg_ok = False
            findings.append(("SELFTEST", f"[FAIL] negative case wrongly detected: {email}"))

    if pos_ok:
        findings.append(("SELFTEST", f"[PASS] positive: {len(positive_cases)} real emails correctly detected"))
    if neg_ok:
        findings.append(("SELFTEST", f"[PASS] negative: {len(negative_cases)} reserved-domain emails correctly excluded"))
    return findings


def run_all(repo_root):
    sections = {
        "Git tracking rules (B1/B2/C1)": check_git_tracking(repo_root),
        "Privacy & PII": check_privacy(repo_root),
        "Workspace & history": check_workspace(repo_root),
        "Self-test: email detection": _selftest_email_detection(),
    }
    exit_code = 0
    for _, rows in sections.items():
        for _, msg in rows:
            if msg.startswith("[FAIL]"):
                exit_code = 2
            elif msg.startswith("[WARN]"):
                if exit_code == 0:
                    exit_code = 1
    return exit_code, sections


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo-root", default="..", help="Git repo root (default: ..)")
    args = ap.parse_args()
    repo_root = Path(args.repo_root).resolve()
    if not (repo_root / ".git").exists():
        print(f"[ERROR] {repo_root} is not a Git repo (.git not found)", file=sys.stderr)
        return 3

    print("=" * 60)
    print("V1.4.2+ Release Check -- read-only clean verification")
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
        print("[PASS] All read-only checks passed. Next: T7 / RESULT update / T9 independent review.")
        print("       This script does NOT create repos, rewrite history, or push main/tag.")
    elif code == 1:
        print("[WARN] Non-blocking warnings found (marked [WARN]). Review before release.")
    else:
        print("[FAIL] Blocking issues found (marked [FAIL]). Fix and re-run.")
    print("=" * 60)
    return code


if __name__ == "__main__":
    raise SystemExit(main())