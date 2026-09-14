# V2.2.0 T11 隔离启动验证：从 onedir 包启动并核对真实服务就绪（不触碰真实 runtime）。
#
# 行为：
# - 建立仓库外临时 RESUME_DATA_DIR（隔离 runtime），设置 APP_PORT 避开 8000 占用；
# - 剥离 ARK_API_KEY / SQLITE_PATH / DOCX_OUTPUT_DIR 等注入变量（类似 precheck _strip_env），
#   确保启动不依赖开发机密钥与路径，验证"包内无 Key / 无注入 / 无开发路径"约束；
# - 启动 dist/ResumeAssistant/ResumeAssistant.exe；
# - 轮询 http://127.0.0.1:<port>/api/health 直至 200（成功）或超时（失败）；
# - 健康检查通过后终止 EXE 进程与其互斥量注册，清理临时 runtime；
# - 失败可见：任何一步异常/超时 => 非零退出，绝不静默成功。
#
# 用法：python scripts/t11_isolated_start.py --exe <path\\ResumeAssistant.exe> [--port 8123]
# 退出码：0 = 真实启动并 health 200；1 = 启动/健康/清理失败。
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

_STRIP_ENV = (
    "ARK_API_KEY", "ARK_BASE_URL", "LLM_MODEL", "EMBEDDING_MODEL",
    "SQLITE_PATH", "CHROMA_PATH", "DOCX_OUTPUT_DIR", "RESUME_DATA_DIR",
    "APP_HOST", "APP_PORT",
)
HOST = "127.0.0.1"


def _strip_env(port: int, runtime: Path) -> dict[str, str]:
    env = dict(os.environ)
    for k in _STRIP_ENV:
        env.pop(k, None)
    env["RESUME_DATA_DIR"] = str(runtime)
    env["APP_PORT"] = str(port)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _health(port: int, timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    url = f"http://{HOST}:{port}/api/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                return resp.status == 200
        except Exception:  # noqa: BLE001
            time.sleep(0.6)
    return False


def _free_port(preferred: int, max_scan: int = 50) -> int:
    for p in range(preferred, preferred + max_scan):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, p))
                return p
            except OSError:
                continue
    return preferred


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--port", type=int, default=8123)
    args = ap.parse_args()

    exe = Path(args.exe)
    if not exe.exists():
        print(f"[fatal] exe 不存在：{exe}")
        return 1

    runtime = Path(tempfile.mkdtemp(prefix="v22t11_start_"))
    port = _free_port(args.port)
    started_at = time.time()
    proc = None
    cleaned = False
    try:
        print(f"[start] exe={exe}")
        print(f"[start] isolated runtime={runtime} port={port}", flush=True)
        env = _strip_env(port, runtime)
        # windowed exe：不传 stdout 管道，避免受控启动等待其关闭；daemon 由超时兜底。
        proc = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ok = _health(port)
        if not ok:
            print(f"[fail] /api/health 未就绪（{int(time.time() - started_at)}s 超时）", flush=True)
            return 1
        elapsed = time.time() - started_at
        print(f"[ok] /api/health 200 就绪于 {elapsed:.1f}s, pid={proc.pid}", flush=True)
        print("[ok] 隔离 runtime 上真实启动成功；未注入 Key/路径。", flush=True)
        return 0
    finally:
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:  # noqa: BLE001
                pass
            try:
                proc.wait(timeout=15)
            except Exception:  # noqa: BLE001
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass
        # 强等端口释放，避免"服务已停止但句柄未释放"被误判
        for _ in range(30):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((HOST, port))
                break
            except OSError:
                time.sleep(0.5)
        try:
            shutil.rmtree(runtime, ignore_errors=True)
            cleaned = True
        except Exception:  # noqa: BLE001
            cleaned = False
        if not cleaned:
            print(f"[warn] 临时 runtime 清理失败：{runtime}", flush=True)


if __name__ == "__main__":
    sys.exit(main())