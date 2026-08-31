"""V2.0.0 验证脚本进程生命周期负向矩阵（PLAN §11.2 F2 正式回归测试）。

以独立子进程覆盖 §11.2 全矩阵：导入边界、正常/业务失败、bootstrap 失败、部分资源取得、
普通/提前退出、cleanup 单项失败、组合失败、重复与占用；并对每个场景断言进程退出码、
临时目录集合差异、环境恢复与真实 runtime/哨兵后置条件。

失败注入通过子进程 `-c` 包裹脚本模块、在调用 `main()` 前 monkeypatch 实现。每个脚本都在
独立子进程内执行，本进程不 import 任何产品模块，不写真实数据或本机绝对路径（workspace
全部在系统临时目录内，运行结束统一删除）。
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
_ENV_KEY = "RESUME_DATA_DIR"

SCRIPTS = (
    ("_v20_smoke", "ra_v20_smoke_"),
    ("_v2_t5_crud_check", "ra_v2_t5_"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ─────────────────────────── 注入代码片段 ───────────────────────────

_INJ_MKDTEMP_FAIL = "import tempfile as _t\n_t.mkdtemp = lambda *a, **k: (_ for _ in ()).throw(OSError('injected mkdtemp failure'))"

_INJ_ENV_SET_FAIL = (
    "import os as _os\n"
    "_org_set = _os._Environ.__setitem__\n"
    "_flag = [True]\n"
    "def _fake_set(self, k, v):\n"
    "    if k == 'RESUME_DATA_DIR' and _flag[0]:\n"
    "        _flag[0] = False\n"
    "        raise OSError('injected env set failure')\n"
    "    return _org_set(self, k, v)\n"
    "_os._Environ.__setitem__ = _fake_set"
)

_INJ_IMPORT_MAIN_FAIL = (
    "import builtins as _b\n"
    "_real_imp = _b.__import__\n"
    "def _fake_imp(name, *a, **k):\n"
    "    if name == 'main':\n"
    "        raise ImportError('injected import main failure')\n"
    "    return _real_imp(name, *a, **k)\n"
    "_b.__import__ = _fake_imp"
)

_INJ_IMPORT_TESTCLIENT_FAIL = (
    "import builtins as _b\n"
    "_real_imp2 = _b.__import__\n"
    "def _fake_imp2(name, *a, **k):\n"
    "    if name == 'fastapi.testclient' or name.startswith('fastapi.testclient.'):\n"
    "        raise ImportError('injected testclient import failure')\n"
    "    return _real_imp2(name, *a, **k)\n"
    "_b.__import__ = _fake_imp2"
)

_INJ_LIFESPAN_FAIL = (
    "import builtins as _b\n"
    "_real_imp3 = _b.__import__\n"
    "def _fake_imp3(name, *a, **k):\n"
    "    m = _real_imp3(name, *a, **k)\n"
    "    if name == 'main':\n"
    "        m.init_db = lambda *aa, **kk: (_ for _ in ()).throw(RuntimeError('injected lifespan init_db failure'))\n"
    "    return m\n"
    "_b.__import__ = _fake_imp3"
)

_INJ_RMTREE_FAIL = "import shutil as _sh\n_sh.rmtree = lambda *a, **k: (_ for _ in ()).throw(OSError('injected rmtree failure'))"

_INJ_RMTREE_NOOP = "import shutil as _sh2\n_sh2.rmtree = lambda *a, **k: None"

_INJ_ENV_RESTORE_FAIL = (
    "import os as _os\n"
    "_org_set2 = _os._Environ.__setitem__\n"
    "_cnt = [0]\n"
    "def _fake_set2(self, k, v):\n"
    "    if k == 'RESUME_DATA_DIR':\n"
    "        _cnt[0] += 1\n"
    "        if _cnt[0] == 2:\n"
    "            raise OSError('injected env restore failure')\n"
    "    return _org_set2(self, k, v)\n"
    "_os._Environ.__setitem__ = _fake_set2"
)

# _run_tests 桩：业务返回/提前退出，不触发产品导入（快速）
_STUB_RETURN_0 = "def _stub(state):\n    return 0\nS._run_tests = _stub"

_STUB_RAISE = "def _stub(state):\n    raise RuntimeError('injected normal exception')\nS._run_tests = _stub"

_STUB_KI = "def _stub(state):\n    raise KeyboardInterrupt()\nS._run_tests = _stub"

_STUB_SE0 = "S._run_tests = lambda state: sys.exit(0)"
_STUB_SE3 = "S._run_tests = lambda state: sys.exit(3)"
_STUB_SE_STR = "S._run_tests = lambda state: sys.exit('boom')"
_STUB_SE_NONE = "S._run_tests = lambda state: sys.exit(None)"

# 注册一个 dispose 必失败的假 engine 后返回 0
_STUB_DISPOSE_FAIL = (
    "class _E:\n"
    "    def dispose(self):\n"
    "        raise OSError('injected dispose failure')\n"
    "def _stub(state):\n"
    "    state.register_engine(_E())\n"
    "    return 0\n"
    "S._run_tests = _stub"
)

# 注册假 engine 后 SystemExit(0)
_STUB_DISPOSE_FAIL_SE0 = (
    "class _E:\n"
    "    def dispose(self):\n"
    "        raise OSError('injected dispose failure')\n"
    "def _stub(state):\n"
    "    state.register_engine(_E())\n"
    "    sys.exit(0)\n"
    "S._run_tests = _stub"
)

_INJ_BUSINESS_FAIL = 'S.check = lambda c, n, e="": setattr(S, "_failed", S._failed + 1)'


# 场景：名称、注入代码（或 None）、是否 call_main、期望退出码（int 或 "nonzero"）、
#       期望残留、期望环境恢复。
_SCENARIOS = [
    ("import 边界（仅 import，不调用 main）", None, False, 0, False, True),
    ("正常成功", None, True, 0, False, True),
    ("业务失败（check 全失败）", _INJ_BUSINESS_FAIL, True, "nonzero", False, True),
    ("bootstrap：mkdtemp 自身失败", _INJ_MKDTEMP_FAIL, True, "nonzero", False, True),
    ("bootstrap：环境设置失败（mkdtemp 后）", _INJ_ENV_SET_FAIL, True, "nonzero", False, True),
    ("bootstrap：import main 失败", _INJ_IMPORT_MAIN_FAIL, True, "nonzero", False, True),
    ("部分资源：engine 后导入失败", _INJ_IMPORT_TESTCLIENT_FAIL, True, "nonzero", False, True),
    ("部分资源：TestClient/lifespan 进入失败", _INJ_LIFESPAN_FAIL, True, "nonzero", False, True),
    ("普通异常", _STUB_RAISE, True, "nonzero", False, True),
    ("KeyboardInterrupt", _STUB_KI, True, 130, False, True),
    ("SystemExit(0)", _STUB_SE0, True, 0, False, True),
    ("SystemExit(None)", _STUB_SE_NONE, True, 0, False, True),
    ("SystemExit(非零)", _STUB_SE3, True, 3, False, True),
    ("SystemExit(字符串)", _STUB_SE_STR, True, "nonzero", False, True),
    ("cleanup：dispose 抛错", _STUB_DISPOSE_FAIL, True, "nonzero", False, True),
    ("cleanup：rmtree 抛错", _INJ_RMTREE_FAIL + "\n" + _STUB_RETURN_0, True, "nonzero", True, True),
    ("cleanup：rmtree 无异常但目录仍存在", _INJ_RMTREE_NOOP + "\n" + _STUB_RETURN_0, True, "nonzero", True, True),
    ("cleanup：环境恢复失败", _INJ_ENV_RESTORE_FAIL + "\n" + _STUB_RETURN_0, True, "nonzero", False, False),
    ("组合：SystemExit(0)+dispose 失败", _STUB_DISPOSE_FAIL_SE0, True, "nonzero", False, True),
    ("组合：SystemExit(0)+rmtree 失败", _INJ_RMTREE_FAIL + "\n" + _STUB_SE0, True, "nonzero", True, True),
    ("组合：SystemExit(0)+目录仍存在", _INJ_RMTREE_NOOP + "\n" + _STUB_SE0, True, "nonzero", True, True),
    ("组合：SystemExit(0)+环境恢复失败", _INJ_ENV_RESTORE_FAIL + "\n" + _STUB_SE0, True, "nonzero", False, False),
    ("组合：业务非零+rmtree 失败", _INJ_RMTREE_FAIL + "\n" + _STUB_SE3, True, 3, True, True),
]


def _build_program(script: str, inject: str | None, call_main: bool) -> str:
    inj = inject or ""
    if call_main:
        body = (
            "_code = None\n"
            "try:\n"
            "    S.main()\n"
            "except SystemExit as _e:\n"
            "    _code = _e.code\n"
            "_exit = _code if isinstance(_code, int) else (0 if _code is None else 1)\n"
            "_restored = (os.environ.get('RESUME_DATA_DIR') == _was)\n"
        )
    else:
        body = "_exit = 0\n_restored = True\n"

    return (
        "import os, sys\n"
        "_was = os.environ.get('RESUME_DATA_DIR')\n"
        f"import {script} as S\n"
        "_imported_main = ('main' in sys.modules)\n"
        "_runtime_changed = (os.environ.get('RESUME_DATA_DIR') != _was)\n"
        f"{inj}\n"
        f"{body}"
        "print('__MATRIX__|exit={}|restored={}|imported_main={}|runtime_changed={}'.format("
        "_exit, _restored, _imported_main, _runtime_changed))\n"
        "sys.exit(_exit)\n"
    )


def _run_one(script: str, prefix: str, program: str, runtime: str, tmp_root: str) -> dict:
    env = dict(os.environ)
    env[_ENV_KEY] = runtime
    # 把脚本 mkdtemp 重定向到受控临时根，便于确定性核算残留
    env["TMP"] = tmp_root
    env["TEMP"] = tmp_root
    env["TMPDIR"] = tmp_root
    proc = subprocess.run(
        [sys.executable, "-c", program],
        cwd=str(_BACKEND),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    out = proc.stdout
    marker = None
    for line in out.splitlines():
        if line.startswith("__MATRIX__|"):
            marker = line.split("|", 1)[1]
            break
    # 残留：受控临时根下以该脚本前缀开头的目录
    residues = [
        p for p in Path(tmp_root).iterdir()
        if p.is_dir() and p.name.startswith(prefix)
    ]
    result = {
        "returncode": proc.returncode,
        "marker": marker,
        "residues": [p.name for p in residues],
    }
    return result


def _assert_exit(expected, actual: int, label: str) -> bool:
    if expected == "nonzero":
        return actual != 0
    return actual == expected


def main() -> int:
    total = 0
    failed = 0

    for script, prefix in SCRIPTS:
        for (name, inject, call_main, exp_exit, exp_residue, exp_restored) in _SCENARIOS:
            total += 1
            # 每个场景独立受控临时根 + 真实 runtime/哨兵
            with tempfile.TemporaryDirectory(prefix="ra_matrix_") as base:
                base = Path(base)
                tmp_root = base / "tmp"
                tmp_root.mkdir()
                runtime = base / "real_runtime"
                runtime.mkdir()
                sentinel = runtime / "sentinel.bin"
                sentinel.write_bytes(b"REAL-RUNTIME-SENTINEL-0")
                adjacent = base / "adjacent_sentinel"
                adjacent.mkdir()
                adj_file = adjacent / "keep.txt"
                adj_file.write_bytes(b"ADJACENT-SENTINEL-1")

                s_before = (sentinel.exists(), sentinel.stat().st_mtime_ns, _sha256(sentinel))
                a_before = (adj_file.exists(), adj_file.stat().st_mtime_ns, _sha256(adj_file))

                program = _build_program(script, inject, call_main)
                r = _run_one(script, prefix, program, str(runtime), str(tmp_root))

                ok = True
                msgs = []
                if not _assert_exit(exp_exit, r["returncode"], name):
                    ok = False
                    msgs.append(f"退出码 {r['returncode']}，期望 {exp_exit}")
                if bool(r["residues"]) != exp_residue:
                    ok = False
                    msgs.append(f"残留 {r['residues']}，期望残留={exp_residue}")
                s_after = (sentinel.exists(), sentinel.stat().st_mtime_ns, _sha256(sentinel))
                a_after = (adj_file.exists(), adj_file.stat().st_mtime_ns, _sha256(adj_file))
                if s_after != s_before:
                    ok = False
                    msgs.append("真实 runtime 哨兵变化")
                if a_after != a_before:
                    ok = False
                    msgs.append("相邻哨兵变化")

                # 环境恢复：仅当子进程成功走到 main 时才从 marker 断言
                if call_main and r["marker"] is not None:
                    parts = dict(kv.split("=", 1) for kv in r["marker"].split("|"))
                    restored = parts.get("restored") == "True"
                    if restored != exp_restored:
                        ok = False
                        msgs.append(f"环境恢复={restored}，期望={exp_restored}")
                elif call_main and r["marker"] is None:
                    ok = False
                    msgs.append("未解析到子进程 marker")

                if call_main is False:
                    # 导入边界：额外断言无产品模块副作用
                    if r["marker"] is None:
                        ok = False
                        msgs.append("导入边界未解析 marker")
                    else:
                        parts = dict(kv.split("=", 1) for kv in r["marker"].split("|"))
                        if parts.get("imported_main") != "False":
                            ok = False
                            msgs.append("导入脚本时误导入产品 main")
                        if parts.get("runtime_changed") != "False":
                            ok = False
                            msgs.append("导入脚本时环境被改变")

                if ok:
                    print(f"  [PASS] {script} :: {name}")
                else:
                    failed += 1
                    print(f"  [FAIL] {script} :: {name}  " + " | ".join(msgs))

    # 重复与占用（直接驱动 runner，验证幂等与释放后重试）：2 脚本 × 2 子测试
    total += 4
    for script, prefix in SCRIPTS:
        with tempfile.TemporaryDirectory(prefix="ra_matrix_") as base:
            base = Path(base)
            env = dict(os.environ)
            env["TMP"] = str(base)
            env["TEMP"] = str(base)
            env["TMPDIR"] = str(base)
            # 清理连续调用（幂等）
            prog_idem = (
                "import sys\n"
                "import _v2_test_runner as _r\n"
                "st = _r._RuntimeState('ra_idem_')\n"
                "_r._setup(st)\n"
                "ok1 = _r._cleanup(st)\n"
                "ok2 = _r._cleanup(st)\n"
                "print('__IDEM__|{}|{}|{}'.format(ok1, ok2, st.tmp.exists()))\n"
                "sys.exit(0 if (ok1 and ok2 and not st.tmp.exists()) else 1)\n"
            )
            p = subprocess.run([sys.executable, "-c", prog_idem], cwd=str(_BACKEND), env=env, capture_output=True, text=True, timeout=120)
            ok = p.returncode == 0
            if ok:
                print(f"  [PASS] {script} :: 重复 cleanup 幂等")
            else:
                failed += 1
                print(f"  [FAIL] {script} :: 重复 cleanup 幂等  rc={p.returncode} out={p.stdout.strip()}")

            # 文件句柄占用：首次删除失败，释放后重试成功
            prog_occupy = (
                "import sys\n"
                "import _v2_test_runner as _r\n"
                "st = _r._RuntimeState('ra_occupy_')\n"
                "_r._setup(st)\n"
                "held = st.tmp / 'held.bin'\n"
                "fh = open(held, 'wb')\n"
                "fh.write(b'x')\n"
                "fh.flush()\n"
                "ok1 = _r._cleanup(st)\n"
                "fh.close()\n"
                "ok2 = _r._cleanup(st)\n"
                "print('__OCCUPY__|{}|{}|{}'.format(ok1, ok2, st.tmp.exists()))\n"
                "sys.exit(0 if (ok2 and not st.tmp.exists()) else 1)\n"
            )
            p = subprocess.run([sys.executable, "-c", prog_occupy], cwd=str(_BACKEND), env=env, capture_output=True, text=True, timeout=120)
            ok = p.returncode == 0
            if ok:
                print(f"  [PASS] {script} :: 文件句柄占用释放后重试")
            else:
                failed += 1
                print(f"  [FAIL] {script} :: 文件句柄占用释放后重试  rc={p.returncode} out={p.stdout.strip()}")

    print("-" * 60)
    print(f"矩阵合计 {total} 项，失败 {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())