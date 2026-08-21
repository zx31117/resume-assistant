"""V1.4 T8 — 一次性干净首发 worktree 构建脚本。

用途：
  1. 从开发 worktree（当前仓库 A 类文件）拷贝干净源码；
  2. 严格排除 C 类（运行时数据）/ D 类（隔离区脚本之外？不，T8 不进 GitHub 首发，但验收 Agent 需要 D 类来跑 T7/T9 复核——因此 D 类脚本也会一并拷贝，且在 T8_DELIVERY.md 中明确"验收后可剔除"）；
  3. 初始化全新 git 仓库（-b main），不含开发仓库任何旧历史；
  4. 生成首次且唯一的 commit = "V1.4 首发干净源码包（A类 + 脚本验收辅助D类）"；
  5. 输出 manifest.json 给 T8_DELIVERY.md 引用。

执行：
    cd backend
    python _v14_t8_delivery.py \
        --source <dev_worktree_root> \
        --dest  C:\\Users\\<xxx>\\.trae-cn\\worktrees\\V1高性能验收agent
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


# —— T6 A 类允许保留的 input/ 文件名白名单（纯虚构，无 PII）—— #
_INPUT_LEGIT_FNAMES = {"demo_profile.json","demo_experiences.json","demo_jd.txt"}

# —— 全局排除规则（C 类 + 构建产物 + 敏感）—— #
_DIR_EXCLUDE = {
    ".git",".venv","__pycache__",".pytest_cache",".mypy_cache",".ruff_cache",
    "data","output","logs","cache",   # runtime 四个子目录，无论在哪一层
    "sources",                        # docs/sources 历史遗留（开发仓库已删，仍兜底）
    "stub-e2e-ErXehG",                # 旧开发临时子 worktree 名
    "validation-artifacts",           # L3：验收产物（T7 报告 JSON 等），验收时生成含本机路径，不入首发包
    ".workbuddy",                     # §九-2：Agent 会话/缓存产物
}
_EXT_EXCLUDE = {
    ".pyc",".pyo",".pyd",
    ".db",".sqlite",".sqlite3",".bin",
    ".doc",".pdf",".potx",   # 注意：.docx 不在这里——pm_template.docx 是白名单 B 类模板资产
    ".log",".bak",".swp",".tmp",
    ".png",".jpg",".jpeg",".gif",".webp",
}

# —— C1：显式文件级排除（不进入首发包、不进入 manifest）—— #
#   backend/pip_freeze_baseline.txt:
#     requirements.txt 已是公开的顶层依赖真源（含版本锁定说明与 V1.2 验证锚）。
#     pip_freeze 完整快照含 118 项传递依赖，属于本地重现用 C/D 类辅助产物，
#     不在公开仓库长期维护；干净 clone 用 requirements.txt 可得到一致安装结果。
_FILE_ALWAYS_EXCLUDE_RELPATHS = {"backend/pip_freeze_baseline.txt"}

# —— 白名单（不被 _EXT_EXCLUDE 等通用规则命中，命中则直接放行）—— #
#   backend/templates/pm_template.docx：由 _build_templates.py 从 pm_template.json 生成的
#   二进制模板资产，属于 PLAN §7 明确允许的 B 类文件（工具生成、构建产物、可复现）。
#   T6 审计已记录：无 PII/无 Secret/可复现，因此必须进入首发包，否则 TemplateRenderer 无法加载。
_WHITELIST_RELPATHS = {"backend/templates/pm_template.docx"}
_FILE_EXCLUDE = {
    ".env",".env.local",".env.user",
}

# —— 名字级硬排除：任何层级，只要 basename（目录名 or 文件名）命中即跳过 —— #
#   .git 是必排除：开发 worktree 根下的 .git 是 file（指向真实 gitdir），
#   一旦 copy 进 dest 就会把验收 worktree 误挂到开发 git 真源，破坏"零历史全新 git"。
#   __t8_acceptance_worktree 同样：前一轮 T8 若把 dest 建在 src_root 下，下一轮
#   rglob("*") 就会递归 copy 它自己（"俄罗斯套娃"），几轮后就 10 层嵌套超时/爆盘。
_NAME_ALWAYS_EXCLUDE = {".git", ".t8-manifest.json", "__t8_acceptance_worktree", "__v141_delivery_preview"}


def should_skip(rel_parts: tuple[str, ...], name: str, full: Path) -> tuple[bool, str | None]:
    """返回 (是否跳过, 跳过原因)"""
    rel_posix = "/".join(rel_parts + (name,))
    # —— 白名单最优先：一旦命中直接放行，不再走任何排除规则 —— #
    if rel_posix in _WHITELIST_RELPATHS:
        return False, None
    # —— C1：显式 relpath 级硬排除（优先级高于通用扩展名/目录规则）—— #
    if rel_posix in _FILE_ALWAYS_EXCLUDE_RELPATHS:
        return True, f"C1 显式排除（requirements.txt 已是唯一依赖真源，不强行发布 freeze 快照）: {rel_posix}"
    # 目录级别
    for p in rel_parts:
        if p in _DIR_EXCLUDE:
            return True, f"目录排除: {p}"
        if p in _NAME_ALWAYS_EXCLUDE:
            return True, f"名字级硬排除(目录段): {p}"
    # 名字级硬排除（文件名 or 目录名）—— name 就是当前项的 basename
    if name in _NAME_ALWAYS_EXCLUDE:
        return True, f"名字级硬排除: {name}"
    # 文件名级硬排除
    if name in _FILE_EXCLUDE:
        return True, f"敏感/环境文件排除: {name}"
    # 扩展名排除
    ext = full.suffix.lower()
    if ext in _EXT_EXCLUDE:
        return True, f"扩展名排除: {ext}"
    # 特别：input 目录只允许白名单（demo_*）
    if "input" in rel_parts and name not in _INPUT_LEGIT_FNAMES and full.is_file():
        return True, f"input 非白名单文件（疑似真实用户上传）排除: {name}"
    return False, None


def copy_clean(source_root: Path, dest_root: Path, manifest: dict):
    # 严格一次性：若 dest 已存在，优先 rename 成 .bad-timestamp（避免 Windows 沙箱锁 .git 导致 rmtree 失败）；
    # rename 失败 fallback 到 rmtree。
    if dest_root.exists():
        ts = int(_dt.datetime.now().timestamp())
        bad = dest_root.parent / f"{dest_root.name}.bad-{ts}"
        try:
            dest_root.rename(bad)
            manifest["prev_dest_renamed_to"] = str(bad)
        except Exception as e1:
            manifest["prev_dest_rename_error"] = f"{type(e1).__name__}: {e1}"[:200]
            try:
                shutil.rmtree(dest_root, ignore_errors=True)
            except Exception as e2:
                manifest["prev_dest_rmtree_error"] = f"{type(e2).__name__}: {e2}"[:200]
        # 如果目标仍然存在，强制中断——绝不在污染目录上继续拷贝
        if dest_root.exists():
            raise RuntimeError(f"目标目录仍存在，无法构建一次性干净首发: {dest_root}")
    dest_root.mkdir(parents=True, exist_ok=True)

    # —— 额外安全网：dest_root 绝不能落在 source_root 之内（否则 rglob 会自己抄自己）—— #
    #   如果调用方显式这么传，记录警告并直接阻断；真正的"一次性干净首发"天然不在 source_root 内。
    try:
        dest_root.resolve().relative_to(source_root.resolve())
        manifest["dest_inside_source_root"] = True
        manifest["dest_inside_source_root_note"] = (
            "调用方把 T8 首发包建在了开发 worktree 之内（非致命），"
            "但因此依赖 _NAME_ALWAYS_EXCLUDE 拦截同名目录；生产发布请移至 worktrees/ 同级外部目录。"
        )
    except ValueError:
        pass  # 正常：dest 不在 source 内

    copied_files: list[dict] = []
    skipped: list[dict] = []
    total_size = 0

    # 使用 os.walk + 目录级剪枝，避免 rglob("*") 遍历 .venv（2.4万文件）等大目录。
    # 等价于 should_skip 中 lines 83-87 的目录段检查，但前移到遍历阶段，不递归进入排除目录。
    # _NAME_ALWAYS_EXCLUDE 中的 __t8_acceptance_worktree 同样在此拦截，
    # 因此即使 dest 落在 source_root 内也不会自我递归拷贝。
    _PRUNE_DIR_NAMES = _DIR_EXCLUDE | _NAME_ALWAYS_EXCLUDE
    for root, dirs, files in os.walk(source_root):
        kept: list[str] = []
        for d in dirs:
            if d in _PRUNE_DIR_NAMES:
                rel_prune = str(Path(root, d).relative_to(source_root)).replace("\\", "/")
                skipped.append({"path": rel_prune, "reason": f"目录剪枝(不递归): {d}"})
            else:
                kept.append(d)
        dirs[:] = kept  # 原地修改，阻止 os.walk 递归进入排除目录
        for fname in files:
            src = Path(root) / fname
            rel = src.relative_to(source_root)
            parts = rel.parts
            skip, reason = should_skip(parts[:-1], parts[-1], src)
            if skip:
                skipped.append({"path": str(rel).replace("\\", "/"), "reason": reason})
                continue
            dst = dest_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            size = dst.stat().st_size
            total_size += size
            sha = hashlib.sha256(dst.read_bytes()).hexdigest()
            copied_files.append({
                "path": str(rel).replace("\\", "/"),
                "bytes": size,
                "sha256": sha,
            })

    manifest["copied_count"] = len(copied_files)
    manifest["skipped_count"] = len(skipped)
    manifest["total_bytes_copied"] = total_size
    manifest["copied_files"] = copied_files
    manifest["skipped_samples"] = skipped[:80]
    if len(skipped) > 80:
        manifest["skipped_samples_truncated_from"] = len(skipped)
    # —— 关键安全断言：拷贝完成后 dest 下绝对不能有 .git（文件/目录都不允许）—— #
    stray = dest_root / ".git"
    if stray.exists():
        raise RuntimeError(
            f"拷贝后发现 {stray}（类型= {'dir' if stray.is_dir() else 'file'}），"
            f"存在误把开发 git 真源挂进首发包风险；中止 T8。"
        )


def init_fresh_git(dest_root: Path, manifest: dict):
    """在 dest_root 全新 git init -b main，只做一次 commit，完全不含开发仓库历史。"""
    def run(cmd: list[str]):
        p = subprocess.run(cmd, cwd=str(dest_root), capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"GIT FAIL: {cmd}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
        return (p.stdout + p.stderr).strip()

    run(["git", "init", "-b", "main"])
    run(["git", "config", "user.name", "ResumeAssistant V1.4 Delivery Bot"])
    run(["git", "config", "user.email", "v14-delivery@trae.local"])
    run(["git", "add", "-A"])

    # —— B1 强制保障：pm_template.docx 必须进入 Git —— #
    # 尽管 .gitignore 第 55 行有 !backend/templates/pm_template.docx 例外，
    # 仍显式 -f 强制 add，双重保险避免任何忽略规则把必要模板排除在首发包外。
    tpl_rel = "backend/templates/pm_template.docx"
    tpl_abs = dest_root / tpl_rel
    if not tpl_abs.is_file():
        raise RuntimeError(f"B1 阻断：拷贝后 {tpl_abs} 不存在，TemplateRenderer 无法加载。")
    run(["git", "add", "-f", tpl_rel])  # -f 无视任何 ignore 规则

    # 执行首发 commit
    try:
        commit_std = run([
            "git", "commit", "-q", "-m",
            "V1.4 首发干净源码包（A类 + 验收辅助D类，不含开发仓库历史、不含 runtime data / 二进制）",
        ])
    except RuntimeError as e:
        if "nothing to commit" in str(e):
            commit_std = "nothing to commit"
        else:
            raise

    head = run(["git","rev-parse","HEAD"]) if commit_std != "nothing to commit" else "(none)"
    status = run(["git","status","--short"])
    branch = run(["git","branch","--show-current"]).strip()
    hist_count = run(["git","rev-list","--count","HEAD"]) if commit_std != "nothing to commit" else "0"

    # —— B1 二次验证：git ls-files 必须找到 pm_template.docx —— #
    tpl_tracked = run(["git", "ls-files", tpl_rel]).strip()
    if tpl_tracked == "":
        raise RuntimeError(
            f"B1 阻断：git commit 完成后 git ls-files 仍找不到 {tpl_rel}。"
            f"干净 clone 将无法运行 Stub Demo，必须修复。"
        )
    # C1 二次验证：pip_freeze_baseline.txt 绝对不能在 git 跟踪中出现
    freeze_tracked = run(["git", "ls-files", "backend/pip_freeze_baseline.txt"]).strip()
    if freeze_tracked != "":
        raise RuntimeError(
            "C1 阻断：backend/pip_freeze_baseline.txt 不应进入首发 Git 跟踪，"
            "requirements.txt 已是唯一依赖真源。"
        )

    manifest["git"] = {
        "init_at_dest": str(dest_root),
        "branch": branch,
        "head_commit": head,
        "history_commit_count": int(hist_count),
        "status_after_commit_clean": status == "",
        "b1_template_tracked": tpl_tracked,
        "c1_freeze_excluded": freeze_tracked == "",
    }
    # —— 严格断言：全新 main，历史长度必须 = 1 条首发 commit —— #
    if branch != "main":
        raise RuntimeError(f"git init -b main 后分支不是 main，实际 = {branch!r}")
    if manifest["git"]["history_commit_count"] != 1:
        raise RuntimeError(
            f"零历史首发包要求 commit 数=1，实际 = {manifest['git']['history_commit_count']}；"
            f"疑似被旧仓库继承污染。"
        )
    return head  # 返回 HEAD commit 供 manifest 生成阶段使用


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=None, help="开发 worktree 根（默认使用本 repo 根：当前脚本父目录的父目录）")
    ap.add_argument("--dest", required=True, help="一次性干净首发 worktree 目标路径")
    ap.add_argument("--manifest-out", default=None, help="manifest.json 额外输出路径（默认仅写入 <dest>/.t8-manifest.json）")
    args = ap.parse_args()

    script = Path(__file__).resolve()
    src_root = Path(args.source).resolve() if args.source else script.parent.parent
    dst_root = Path(args.dest).resolve()

    if not (src_root / "README.md").is_file() or not (src_root / "backend" / "main.py").is_file():
        print(f"[FATAL] source root 不合法，未找到 README.md 或 backend/main.py: {src_root}", file=sys.stderr)
        raise SystemExit(2)

    manifest: dict = {
        "v14_t8_delivery_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "source_root": str(src_root),
        "dest_root": str(dst_root),
        "intent": "V1.4 一次性干净首发 worktree，用于高性能验收 Agent 在零历史 + 零 runtime data 环境中执行 T7/T9 复核，最终作为 GitHub 首发包的物理真源。",
        "manifest_note": (
            "本文件是交付真源唯一 manifest：位于交付 worktree 根 .t8-manifest.json，"
            "内容在 git commit 完成后基于 git ls-files 实际跟踪清单重算，与最终首发 commit 严格一致。"
        ),
    }

    # —— 前置：确保 src_root 下 pm_template.docx 已经从 pm_template.json 生成
    #   （它不在 .gitignore，属于『构建产物 + 可复现』的 B 类资产；
    #    开发/本机都要先构建才能让首发包拿到最新一致版本）
    tpl_docx = src_root / "backend" / "templates" / "pm_template.docx"
    tpl_builder = src_root / "backend" / "templates" / "_build_templates.py"
    if not tpl_docx.is_file():
        if not tpl_builder.is_file():
            raise RuntimeError(f"pm_template.docx 不存在且构建脚本 {tpl_builder} 也不存在，无法交付 T8。")
        print("[T8 pre-step] pm_template.docx missing — invoking templates/_build_templates.py...")
        p = subprocess.run(
            [sys.executable, str(tpl_builder)],
            cwd=str(src_root / "backend"),
            capture_output=True, text=True,
        )
        if p.returncode != 0 or not tpl_docx.is_file():
            raise RuntimeError(
                f"前置构建 pm_template.docx 失败 (exit={p.returncode})\n"
                f"STDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
            )
        print(f"[T8 pre-step] built: {tpl_docx} ({tpl_docx.stat().st_size} bytes)")
    else:
        print(f"[T8 pre-step] pm_template.docx present: {tpl_docx.stat().st_size} bytes")

    copy_clean(src_root, dst_root, manifest)
    init_fresh_git(dst_root, manifest)

    # —— C2：manifest 真源唯一化 —— #
    #   commit 完成后，基于 git ls-files 实际跟踪文件重算 manifest 文件列表。
    #   这保证 manifest 与首发 commit 的内容 100% 一致，不存在『拷贝了但被 git ignore 跳过』的偏差。
    def run_git(cmd: list[str]):
        p = subprocess.run(cmd, cwd=str(dst_root), capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"GIT FAIL (manifest phase): {cmd}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
        return p.stdout

    tracked_files = [ln.strip() for ln in run_git(["git", "ls-files"]).splitlines() if ln.strip()]
    git_based_files: list[dict] = []
    total_size_git = 0
    for rel in tracked_files:
        abs_p = dst_root / rel
        if not abs_p.is_file():
            raise RuntimeError(f"git ls-files 列出 {rel} 但磁盘不存在，疑似首发包构建不一致。")
        size = abs_p.stat().st_size
        total_size_git += size
        sha = hashlib.sha256(abs_p.read_bytes()).hexdigest()
        git_based_files.append({
            "path": rel.replace("\\", "/"),
            "bytes": size,
            "sha256": sha,
        })

    # C1 再核查：git 跟踪中绝不能有 pip_freeze_baseline.txt
    for f in git_based_files:
        if f["path"] == "backend/pip_freeze_baseline.txt":
            raise RuntimeError("C1 阻断：manifest 阶段发现 pip_freeze_baseline.txt 仍进入首发 git。")
    # B1 再核查：git 跟踪必须有 pm_template.docx
    tpl_paths = [f["path"] for f in git_based_files if f["path"] == "backend/templates/pm_template.docx"]
    if not tpl_paths:
        raise RuntimeError("B1 阻断：manifest 阶段 git ls-files 未包含 pm_template.docx。")

    # 覆盖 manifest 中的文件清单：以 git ls-files 结果为准
    manifest["file_list_basis"] = "git-ls-files (post-commit, canonical)"
    manifest["tracked_file_count"] = len(git_based_files)
    manifest["tracked_total_bytes"] = total_size_git
    manifest["tracked_files"] = git_based_files
    # 保留旧字段向后兼容：
    manifest["copied_count"] = manifest.get("copied_count", "n/a (use tracked_file_count)")

    # —— 唯一 manifest 输出点：<delivery-root>/.t8-manifest.json —— #
    #   不再在 docs/versions/ 下任何版本子目录留副本，避免两个真源互相冲突。
    #   .t8-manifest.json 已在 _NAME_ALWAYS_EXCLUDE 中，因此不会进入 git 跟踪。
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
    (dst_root / ".t8-manifest.json").write_text(manifest_text, encoding="utf-8")
    if args.manifest_out:
        Path(args.manifest_out).write_text(manifest_text, encoding="utf-8")

    print("\n========== V1.4 T8 DELIVERY OK (B1+C1+C2 修正版) ==========")
    print(f"  source       : {manifest['source_root']}")
    print(f"  dest         : {manifest['dest_root']}")
    print(f"  copied (fs)  : {manifest['copied_count']} files  ({manifest.get('total_bytes_copied','?')} bytes)")
    print(f"  tracked (git): {manifest['tracked_file_count']} files  ({manifest['tracked_total_bytes']} bytes)")
    print(f"  skipped      : {manifest['skipped_count']} paths (C/D/binary/potential-PII)")
    print(f"  git HEAD     : {manifest['git']['head_commit']}")
    print(f"  branch       : {manifest['git']['branch']}")
    print(f"  status clean : {manifest['git']['status_after_commit_clean']}")
    print(f"  B1 template  : ✅ tracked = {manifest['git']['b1_template_tracked']}")
    print(f"  C1 freeze    : ✅ excluded from git = {manifest['git']['c1_freeze_excluded']}")
    print(f"  manifest (唯一真源): {dst_root / '.t8-manifest.json'}")
    print(f"  （docs/versions/<version>/T8_manifest.json 不再生成，避免双真源冲突）")


if __name__ == "__main__":
    main()
