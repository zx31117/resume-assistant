"""V2.0.0 验证脚本共享的测试进程资源生命周期 runner（测试专用，非产品模块）。

用途：把临时 runtime 建立、环境保存/覆盖/恢复、资源取得登记、cleanup 后置验证和
唯一退出码仲裁统一收口，供 `_v20_smoke.py` 与 `_v2_t5_crud_check.py` 复用，消除重复实现。

不可变条件（PLAN §11.1）：
- 导入无副作用：本模块仅依赖标准库；不创建目录、不改环境、不导入任何产品模块。
- 取得即登记：临时目录创建后立即登记；覆盖环境前保存原值；engine/client 取得后即刻登记。
- 清理独立可核对：dispose / close / rmtree / 环境恢复逐项执行，前一步失败不阻止后一步；
  除捕获异常外显式核对目录确实不存在；重复 cleanup 幂等。
- 唯一退出码仲裁：业务返回、普通异常、SystemExit、KeyboardInterrupt 与 cleanup 结果先归并，
  最后只执行一次 sys.exit；SystemExit(None/0) 不绕过 cleanup；任一 cleanup/后置条件失败必非零。
- 真实 runtime 不可触碰：临时环境在导入任何产品模块前生效，退出时恢复调用前环境。
- 边界：os._exit、强制结束进程与断电等无法执行 Python cleanup 的情形不属于本 runner 范围。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

_ENV_KEY = "RESUME_DATA_DIR"


class _RuntimeState:
    """一次运行持有的可变状态；所有资源取得后立即登记到本对象。"""

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.tmp: Path | None = None
        self.original_env: str | None = None
        self.original_env_present = False
        self.env_overwritten = False
        self.engine = None
        self.client = None

    def register_engine(self, engine) -> None:
        self.engine = engine

    def register_client(self, client) -> None:
        self.client = client


def _setup(state: _RuntimeState) -> None:
    """建立唯一临时 runtime 并覆盖环境；任一失败都可能抛异常，由调用方统一进入 cleanup。

    顺序保证“取得即登记”与“真实 runtime 不可触碰”：先建目录并登记，再保存原环境，
    最后覆盖环境，使后续延迟导入的产品模块在临时环境中生效。
    """
    state.tmp = Path(tempfile.mkdtemp(prefix=state.prefix))
    state.original_env_present = _ENV_KEY in os.environ
    state.original_env = os.environ.get(_ENV_KEY)
    os.environ[_ENV_KEY] = str(state.tmp)
    state.env_overwritten = True


def _dispose_engine(state: _RuntimeState) -> bool:
    """释放 SQLite engine；已登记但未初始化时跳过，dispose 失败不阻止后续清理。"""
    ok = True
    if state.engine is not None:
        try:
            state.engine.dispose()
        except Exception:
            ok = False
            print("[CLEANUP] engine.dispose() 失败：")
            traceback.print_exc()
    return ok


def _close_client(state: _RuntimeState) -> bool:
    """关闭 TestClient（幂等；上下文管理器已关闭时不再重复关闭）。"""
    ok = True
    c = state.client
    if c is not None:
        try:
            if not getattr(c, "is_closed", False):
                c.close()
        except Exception:
            ok = False
            print("[CLEANUP] TestClient.close() 失败：")
            traceback.print_exc()
    return ok


def _remove_tmp(state: _RuntimeState) -> bool:
    """删除临时 runtime，并显式核对目录确实不存在，防止“rmtree 无异常但未删除”被判成功。"""
    ok = True
    if state.tmp is None:
        return True
    try:
        shutil.rmtree(state.tmp, ignore_errors=False)
    except FileNotFoundError:
        pass  # 已不存在 => 幂等
    except Exception:
        ok = False
        print("[CLEANUP] 临时 runtime 删除失败：")
        traceback.print_exc()
    try:
        if state.tmp.exists():
            ok = False
            print(f"[CLEANUP] 临时 runtime 仍存在（rmtree 声称成功但目录未删除）：{state.tmp}")
    except Exception:
        ok = False
        print("[CLEANUP] 临时 runtime 存在性核对失败：")
        traceback.print_exc()
    return ok


def _restore_env(state: _RuntimeState) -> bool:
    """恢复调用前 RESUME_DATA_DIR；未覆盖过环境时不动作，避免误删既有环境变量。"""
    if not state.env_overwritten:
        return True
    try:
        if state.original_env_present:
            os.environ[_ENV_KEY] = state.original_env
        else:
            os.environ.pop(_ENV_KEY, None)
    except Exception:
        print("[CLEANUP] 环境恢复失败：")
        traceback.print_exc()
        return False
    return True


def _cleanup(state: _RuntimeState) -> bool:
    """逐项清理，前一步失败不阻止后一步；返回所有资源后置条件是否全部满足。"""
    results = (
        _dispose_engine(state),
        _close_client(state),
        _remove_tmp(state),
        _restore_env(state),
    )
    return all(results)


def _systemexit_code(code) -> int:
    """把 SystemExit.code 归并为一个进程退出码。"""
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    # 字符串或其他对象：Python 会打印该对象并以 1 退出
    try:
        print(code)
    except Exception:
        pass
    return 1


def run_isolated(prefix: str, test_fn, description: str) -> None:
    """在隔离临时 runtime 中执行 test_fn 并做唯一退出码仲裁。

    `test_fn(state)` 负责延迟导入产品模块、登记 engine/client、执行断言并返回业务退出码
    （0=通过），或抛出异常 / SystemExit / KeyboardInterrupt。本函数统一归并业务结果与
    cleanup 结果，最后仅执行一次进程退出；SystemExit(0) 不绕过 cleanup，cleanup 失败必非零。
    """
    state = _RuntimeState(prefix)
    exit_code = 1
    try:
        _setup(state)
        exit_code = test_fn(state)
    except SystemExit as e:
        exit_code = _systemexit_code(e.code)
    except KeyboardInterrupt:
        print(f"[FATAL] {description} 被 KeyboardInterrupt 中断")
        exit_code = 130
    except Exception:
        print(f"[FATAL] {description} 执行异常：")
        traceback.print_exc()
        exit_code = 1
    finally:
        if not _cleanup(state) and exit_code == 0:
            exit_code = 1
    sys.exit(exit_code)