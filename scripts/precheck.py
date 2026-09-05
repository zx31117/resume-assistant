"""V2.0.2 统一预检入口（Windows 本地与 GitHub CI 共用同一逻辑）。

用途：把「Python 编译」「六个零密钥回归脚本」「前端正式构建」三类阻断检查收敛到一处，
由本地开发与 GitHub workflow 调用同一份代码，避免两边检查逻辑漂移。

阻断检查（任一失败 => 以非零退出，禁止假绿）：
- 编译：python -m compileall 校验 backend 全部源码可编译；
- 固定计数：六个回归脚本必须「退出码 == 0」且「汇总行匹配精确正则」双通过，
  防止少跑、额外 SUSPEND、输出格式消失或静默返回成功；
- 前端：frontend 下 `npm run build`（tsc -b && vite build）成功且 dist/index.html 存在。

非阻断检查（首版仅报告，不影响退出码）：ruff、ESLint、依赖漏洞扫描。T4 建立基线后填入
NON_BLOCKING；此处仅保留框架与明确未配置标记，绝不把「未运行」写成「零问题」。

隔离与清理边界：
- 子进程环境剥离真实 API Key 与 runtime 路径注入，测试只在各自临时 runtime 上运行；
- 本脚本不读取真实 %LOCALAPPDATA% 数据，不在版本目录写入机读报告、数据库、DOCX 或日志；
- 原始扫描/构建产物落在已被 .gitignore 排除的目录（__pycache__、frontend/dist、临时目录）。

前置：Python 3.10+ 已 `pip install -r backend/requirements.txt`；前端已 `npm ci`。
执行：python scripts/precheck.py
退出码：0 = 全部阻断检查通过；1 = 至少一个阻断检查失败。
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
FRONTEND = REPO_ROOT / "frontend"

# 单个回归脚本最长运行时间（秒）。
SCRIPT_TIMEOUT = 900
# 前端构建最长运行时间（秒）。
FRONTEND_TIMEOUT = 600

# 阻断检查需要保留在环境中的变量；其余 Key / runtime 注入一律剥离。
_STRIP_ENV = (
    "ARK_API_KEY", "ARK_BASE_URL", "LLM_MODEL", "EMBEDDING_MODEL",
    "SQLITE_PATH", "CHROMA_PATH", "DOCX_OUTPUT_DIR", "RESUME_DATA_DIR",
    "APP_HOST", "APP_PORT",
)

# Python 编译检查范围：仅覆盖随便携包发布的产品源码（与 packaging/resume_assistant.spec
# 的 hiddenimports 一致），不包含历史验证脚本（`_*.py`）。历史脚本属 V2.0.2 范围外的
# 存档资产，其中 `from __future__` 位置等既有问题不在本版本修正。
COMPILE_TARGETS = (
    "main.py", "manage.py", "run_stub_demo.py", "fill_user_data.py",
    "api", "core", "database", "models", "prompts", "services",
)

# 六个零密钥回归脚本及其「固定汇总计数」精确正则（PLAN §6 R4）。
# 每个脚本必须退出码 0 且其输出中存在匹配该正则的汇总行。
BLOCKING_SCRIPTS = (
    ("_v201_validation.py",    r"PASS=77\s+FAIL=0",             "V2.0.1 可观测性验证"),
    ("_v15_r_rework.py",       r"PASS=48\s+FAIL=0\s+\(total=48\)", "V1.5 R-返工回归"),
    ("_v20_smoke.py",          r"PASS=20\s+FAIL=0",             "V2.0 冒烟"),
    ("_v2_t5_crud_check.py",   r"PASS=15\s+FAIL=0",             "V2.0 T5 CRUD"),
    ("_v2_lifecycle_matrix.py", r"矩阵合计\s+50\s+项，失败\s+0",   "生命周期矩阵"),
    ("_v14_t7_regression.py",  r"total=15\s+PASS=12\s+FAIL=0\s+SUSPEND=3", "V1.4 T7 回归"),
)

# 非阻断检查（PLAN §3.3 / §6 R6）：只报告，绝不参与退出码。
# 工具版本固定在后端 backend/requirements-dev.txt（ruff/pip-audit）与
# 前端 frontend/package.json 的 devDependencies（eslint/typescript-eslint/eslint-plugin-react-hooks）。
# 每条 = (key, 显示名, 工作目录, 命令, 是否走 shell, 摘要正则)。
NON_BLOCKING = (
    (
        "ruff", "Python 静态检查（ruff）",
        BACKEND,
        [sys.executable, "-m", "ruff", "check",
         "api", "core", "database", "models", "prompts", "services",
         "main.py", "manage.py", "run_stub_demo.py", "fill_user_data.py"],
        False,
        r"Found \d+ errors|All checks passed",
    ),
    (
        "pip-audit", "Python 依赖漏洞（pip-audit）",
        BACKEND,
        [sys.executable, "-m", "pip_audit", "-r", "requirements.txt"],
        False,
        r"Found \d+ known vulnerabilit[^\n]*|No known vulnerabilities found",
    ),
    (
        "eslint", "前端静态检查（ESLint）",
        FRONTEND,
        "npm run lint",
        True,
        r"\d+ problems? \([^)]*\)",
    ),
    (
        "npm-audit", "Node 依赖漏洞（npm audit）",
        FRONTEND,
        "npm audit",
        True,
        r"found \d+ vulnerabilit[^\n]*|\d+ vulnerabilit[^\n]*",
    ),
)


class _Failure(Exception):
    """阻断检查失败的统一异常，携带可读诊断。"""


def _strip_env() -> dict[str, str]:
    """返回剥离真实 Key / runtime 注入后的子进程环境。"""
    env = dict(os.environ)
    for k in _STRIP_ENV:
        env.pop(k, None)
    # F4：子进程强制 UTF-8 输出，避免其默认落 GBK（cp936）管道在打印中文/emoji 时
    # 触发二次 UnicodeEncodeError；父进程侧仍以 encoding="utf-8", errors="replace" 读取。
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _tail(text: str, n: int = 20) -> str:
    """取输出末 n 行，用于失败诊断。"""
    lines = [ln.rstrip() for ln in text.splitlines()]
    keep = lines[-n:]
    return "\n".join(keep)


def _run_blocking_script(filename: str, pattern: str, label: str) -> None:
    """运行单个回归脚本并做「退出码 + 固定计数」双断言。"""
    print(f"[阻断] 运行 {label} ({filename}) ...", flush=True)
    try:
        proc = subprocess.run(
            [sys.executable, filename],
            cwd=str(BACKEND),
            env=_strip_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SCRIPT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise _Failure(f"{label} 超时（>{SCRIPT_TIMEOUT}s）")
    except FileNotFoundError as e:
        raise _Failure(f"{label} 无法启动 python：{e}")

    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise _Failure(
            f"{label} 退出码 {proc.returncode}（期望 0）。末尾输出：\n{_tail(output)}"
        )
    if not re.search(pattern, output):
        raise _Failure(
            f"{label} 汇总计数不匹配（期望 `{pattern}`）。末尾输出：\n{_tail(output)}"
        )
    print(f"[阻断] {label} 通过（退出码 0，计数匹配）", flush=True)


def _run_compile_check() -> None:
    print("[阻断] 运行 Python 编译检查 (产品源码) ...", flush=True)
    targets = [str(BACKEND / t) for t in COMPILE_TARGETS]
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", *targets],
            cwd=str(REPO_ROOT),
            env=_strip_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SCRIPT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise _Failure(f"编译检查超时（>{SCRIPT_TIMEOUT}s）")

    if proc.returncode != 0:
        output = (proc.stdout or "") + (proc.stderr or "")
        raise _Failure(f"Python 编译失败。末尾输出：\n{_tail(output)}")
    print("[阻断] Python 编译检查通过", flush=True)


def _run_frontend_build() -> None:
    print("[阻断] 运行前端正式构建 (npm run build) ...", flush=True)
    try:
        # Windows 下 npm 是 npm.cmd，需经 shell 解析；命令为固定常量，无注入风险。
        proc = subprocess.run(
            "npm run build",
            cwd=str(FRONTEND),
            env=_strip_env(),
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=FRONTEND_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise _Failure(f"前端构建超时（>{FRONTEND_TIMEOUT}s）")
    except FileNotFoundError as e:
        raise _Failure(f"前端构建无法启动 npm：{e}")

    output = (proc.stdout or "") + (proc.stderr or "")
    index_html = FRONTEND / "dist" / "index.html"
    if proc.returncode != 0 or not index_html.exists():
        raise _Failure(
            f"前端构建失败（退出码 {proc.returncode}）。末尾输出：\n{_tail(output)}"
        )
    print("[阻断] 前端正式构建通过", flush=True)


def _run_nonblocking() -> list[str]:
    """运行非阻断检查并返回报告行；任何异常只报告，不影响退出码。

    - 工具缺失 / 启动失败 / 超时：显式标记，绝不写成「零问题」。
    - 有输出但匹配不到摘要行：显式给出退出码与末行，不伪装成通过。
    """
    notes: list[str] = []
    for _key, label, cwd, cmd, shell, summary_re in NON_BLOCKING:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd),
                env=_strip_env(),
                shell=shell,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=SCRIPT_TIMEOUT,
            )
        except FileNotFoundError as e:
            notes.append(f"{label}：工具未安装或无法启动（{e}）")
            continue
        except subprocess.TimeoutExpired:
            notes.append(f"{label}：执行超时（>{SCRIPT_TIMEOUT}s）")
            continue

        output = (proc.stdout or "") + (proc.stderr or "")
        m = re.search(summary_re, output, re.IGNORECASE)
        if m:
            notes.append(f"{label}：{m.group(0).strip()}（退出码 {proc.returncode}）")
        else:
            notes.append(
                f"{label}：未匹配到摘要行（退出码 {proc.returncode}）。末行："
                + _tail(output, 3).replace("\n", " / ")
            )
    return notes


def _force_utf8_stdio() -> None:
    """F4：预检自身输出中文/emoji 时，避免在 GBK 控制台触发二次 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _default_runtime_root() -> Path:
    """F3：与 core.config._default_runtime_root() 等价的默认 runtime 根（只计算，不创建）。"""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "ResumeAssistant"
        return Path.home() / "AppData" / "Local" / "ResumeAssistant"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ResumeAssistant"
    return Path.home() / ".local" / "share" / "resume-assistant"


# F3：core.config 在任意进程首次导入时都会 mkdir 的标准骨架目录（config.py 模块级
# RESUME_DATA_DIR.mkdir；diagnostics 由 tracker 生命周期建立）。这是产品自身导入契约的
# 副作用：任何一个不预先注入 RESUME_DATA_DIR 的 Python 进程 import core.config 都会得到
# 这些空目录。因此哨兵放行「空标准骨架目录新增」，以支持全新机器（CI runner 上默认
# runtime 尚不存在）时预检不因导入副作用假失败；其余一切变化（文件增删改、目录删除、
# 非标准或非空目录新增）仍 fail-closed。
_F3_SKELETON_DIRS = frozenset(("database", "output", "logs", "cache", "diagnostics"))


def _snapshot_runtime(root: Path) -> dict:
    """F3：只读快照默认 runtime（{dirs: set, files: {relpath: sha256}}），绝不创建或修改。"""
    dirs: set[str] = set()
    files: dict[str, str] = {}
    if not root.is_dir():
        return {"dirs": dirs, "files": files}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirnames)
        rel = Path(dirpath).relative_to(root).as_posix()
        if rel != ".":
            dirs.add(rel)
        for fn in sorted(filenames):
            fp = Path(dirpath) / fn
            relf = fp.relative_to(root).as_posix()
            try:
                files[relf] = hashlib.sha256(fp.read_bytes()).hexdigest()
            except OSError:
                files[relf] = "<unreadable>"
    return {"dirs": dirs, "files": files}


def _runtime_sentinel_diff(before: dict, after: dict) -> list[str]:
    """F3：返回「真实隔离违反」的人读差异行；无违规返回空列表。

    放行规则（仅一条）：新增的顶层空标准骨架目录（database/output/logs/cache/
    diagnostics，after 快照中整棵子树为空）属于 core.config 导入副作用，不阻断。
    除此之外的一切变化都阻断：
    - 任何文件新增 / 删除 / 内容变化（真实库被写入必然在此暴露，如 database/app.db）；
    - 任何目录删除（含空目录）；
    - 非标准目录新增（如 vectorstore）或非空目录新增。
    """
    lines: list[str] = []
    bd, ad = before["dirs"], after["dirs"]
    bf, af = before["files"], after["files"]

    def _dir_subtree_empty(rel: str) -> bool:
        prefix = rel + "/"
        return not any(d.startswith(prefix) for d in ad) and not any(
            f.startswith(prefix) for f in af
        )

    for d in sorted(bd - ad):
        lines.append(f"目录被删除: {d}")
    for d in sorted(ad - bd):
        if "/" not in d and d in _F3_SKELETON_DIRS and _dir_subtree_empty(d):
            continue  # 空标准骨架目录新增：core.config 导入副作用，放行
        lines.append(f"目录被新增(非空或非标准): {d}")
    for f in sorted(bf.keys() - af.keys()):
        lines.append(f"文件被删除: {f}")
    for f in sorted(af.keys() - bf.keys()):
        lines.append(f"文件被新增: {f}")
    for f in sorted(bf.keys() & af.keys()):
        if bf[f] != af[f]:
            lines.append(f"文件内容变化: {f} ({bf[f][:8]} -> {af[f][:8]})")
    return lines


def main() -> int:
    _force_utf8_stdio()
    print("=" * 68, flush=True)
    print("V2.0.2 统一预检（本地与 GitHub 共用入口）", flush=True)
    print("=" * 68, flush=True)

    failures: list[str] = []

    def _attempt(label: str, fn) -> None:
        try:
            fn()
        except _Failure as e:
            failures.append(str(e))
            print(f"[阻断] 失败：{e}", flush=True)

    # F3：真实 runtime 不变外层哨兵。六个阻断脚本必须不读取/不建表/不写入/不删除默认
    # runtime 的内容；core.config 导入产生的「空标准骨架目录」是产品副作用，放行（见
    # _runtime_sentinel_diff 放行规则）。全新机器上默认 runtime 不存在也不影响判定。
    default_root = _default_runtime_root()
    before_snapshot = _snapshot_runtime(default_root)
    print(f"[哨兵] 记录默认 runtime 快照：{default_root}", flush=True)

    _attempt("编译", _run_compile_check)
    for filename, pattern, label in BLOCKING_SCRIPTS:
        _attempt(label, lambda f=filename, p=pattern, l=label: _run_blocking_script(f, p, l))
    _attempt("前端构建", _run_frontend_build)

    after_snapshot = _snapshot_runtime(default_root)
    sentinel_diff = _runtime_sentinel_diff(before_snapshot, after_snapshot)
    if sentinel_diff:
        failures.append(
            "真实 runtime 哨兵（F3）：默认 runtime 在阻断检查后被修改，违反 R5 隔离——\n"
            + "\n".join("    - " + ln for ln in sentinel_diff)
        )
        print("[阻断] 失败：默认 runtime 被修改（违反 R5 隔离）", flush=True)
    else:
        print("[哨兵] 默认 runtime 内容快照一致（未读取/改写；空标准骨架目录新增放行）", flush=True)

    nonblocking_notes = _run_nonblocking()

    print("=" * 68, flush=True)
    if failures:
        print(f"预检结果：阻断检查 FAILED（{len(failures)} 项失败）", flush=True)
        for f in failures:
            print(f"  - {f}", flush=True)
    else:
        print("预检结果：阻断检查全部通过", flush=True)
    for note in nonblocking_notes:
        print(f"  [报告] {note}", flush=True)
    print("=" * 68, flush=True)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())