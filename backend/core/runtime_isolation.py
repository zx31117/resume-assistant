"""V2.2.0 P0：测试 / demo / 验证脚本的 runtime 隔离守卫（PLAN G06 / §3.3 / §6）。

约束（用户结果 V220-R3-G06）：
- 会写 Experience / Fact / Task / artifact 的测试或 demo **必须**在隔离 runtime 下运行；
- 隔离目录缺失、等于默认 runtime 或无法确认时必须**拒绝启动**（fail-closed，不靠调用者记得传参）；
- 不得 `pop` 用户现有 `RESUME_DATA_DIR` 覆盖后回退默认 runtime；
- 本模块只负责“身份是否隔离”的判定与失败拒绝，不做任何数据读写。

用法（在导入任何产品模块**之前**调用）：
    from core.runtime_isolation import ensure_write_capable_isolation
    ensure_write_capable_isolation(guard_prefix="my_demo")
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _default_runtime_root() -> Path:
    """与 core.config._default_runtime_root 一致的默认 runtime 根（不入读 config 以免循环导入）。"""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "ResumeAssistant"
        return Path.home() / "AppData" / "Local" / "ResumeAssistant"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ResumeAssistant"
    return Path.home() / ".local" / "share" / "resume-assistant"


def _is_isolated(prj_root: Path, default_root: Path, data_dir: Path) -> tuple[bool, str]:
    """判定 data_dir 是否构成可靠隔离 runtime。

    判据（可靠性从高到低）：
    1. 显式非默认：data_dir 存在且 != default（排除空串退默认、显式指向本机默认目录）；
    2. 隔离锚点：data_dir 含 /tmp、/Temp、tempfile 前缀（临时目录）→ 视为隔离；
    3. 项目内测试目录：data_dir 位于项目根 .v22_test_runtime / test_runtime 下 → 视为隔离；
    其余一律不视为隔离（fail-closed）。
    """
    if not data_dir.is_absolute():
        data_dir = Path.cwd() / data_dir
    data_dir = data_dir.resolve()

    # 判据 1：等于默认 runtime → 明确不可隔离
    if _same_path(data_dir, default_root):
        return False, "RESUME_DATA_DIR 等于默认 runtime，拒绝写入"

    # 判据 2：位于临时目录树
    tmp_hints = ("/tmp", "\\tmp", "/Temp", "\\Temp", "tempfile")
    s = str(data_dir).lower()
    if any(h in s for h in tmp_hints):
        return True, "位于系统临时目录"

    # 判据 3：项目内测试目录（显式可见锚点）
    try:
        prj_str = str(prj_root.resolve()).lower()
        if prj_str and prj_str in s and ("test_runtime" in s or "_test_" in s):
            return True, "位于项目测试 runtime 目录"
    except Exception:
        pass

    return False, "无法确认隔离目录（非默认但不属于任何已识别隔离树）"


def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except Exception:
        return str(a) == str(b)


def ensure_write_capable_isolation(
    guard_prefix: str,
    *,
    src_default_root: Path | None = None,
) -> Path:
    """测试 / demo 写入前的强制守卫：非隔离 runtime 直接抛 RuntimeError。

    - 要求进程内已设置 `RESUME_DATA_DIR` 且是可靠隔离目录；
    - 不写入任何文件、不改环境（隔离目录由调用方在 import 产品配置前建立）。
    """
    data_dir_raw = os.environ.get("RESUME_DATA_DIR", "").strip()
    if not data_dir_raw:
        raise RuntimeError(
            f"[{guard_prefix}] RESUME_DATA_DIR 未设置：禁止写入默认 runtime")
    prj_root = Path(__file__).resolve().parent.parent
    default_root = src_default_root or _default_runtime_root()
    data_dir = Path(data_dir_raw)
    if not data_dir.is_absolute():
        data_dir = (Path.cwd() / data_dir).resolve()
    ok, reason = _is_isolated(prj_root, default_root, data_dir)
    if not ok:
        raise RuntimeError(
            f"[{guard_prefix}] {reason}（RESUME_DATA_DIR={data_dir_raw}）")
    return data_dir