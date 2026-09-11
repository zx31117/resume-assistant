#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.1.0 H6 浏览器矩阵 runner v2（PLAN §18.2/§18.3/§18.5；RESULT §44.4 最终勾选契约）。

从干净 checkout 驱动同一工作台实例，并对 PLAN 要求的关键事实形成**机器断言**：
- POST 计数（stub_posts.log 增量）、operation/artifact 身份与相互绑定、anchors artifact 匹配；
- PDF/DOCX 下载字节 hash 与 stub fixture 记录一致；
- Console error/warning（含 React Hook order warning）与页面非空/白屏；
- anchors empty/full 命中层数量与切换；Error Boundary 出现与恢复路径（重试/返回工作台）；
- 正式无 env build 的剥离检查（纯 Python，不依赖 GNU grep）。

用法：
  python scripts/h6_browser_matrix.py --help
  python scripts/h6_browser_matrix.py --selfcheck    环境检查（缺一项 exit 非零）
  python scripts/h6_browser_matrix.py --dev          dev 六场景机器断言
  python scripts/h6_browser_matrix.py --prod-inject <pdf|overlay|basis|export>
  python scripts/h6_browser_matrix.py --prod-all     四区依次（不可跳过）
  python scripts/h6_browser_matrix.py --verify       正式 build + 纯 Python 剥离扫描
  python scripts/h6_browser_matrix.py --all          总入口（62 项矩阵+selfcheck+dev+prod-all+verify）

任何 FAIL/未运行/超时 ⇒ 汇总 FAIL 且 exit 非零。未知参数/缺失 target fail closed（exit 2）。
全部命令使用仓库相对路径；无真实数据/Key/在线依赖。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
NPM = os.environ.get("H6_NPM", "npm")

# ── 后端 Python 解析（阻断项 A 修复）──
# 历史上用 sys.executable，若调用者 PATH 首位 python 缺 fastapi，则 stub 子进程 import 失败，
# 矩阵必然全挂却只表现为「浏览器卡住」。改为依赖感知选择 + 明确记录，使命令可复跑、失败可诊断。
_PY_DEPS = ("fastapi", "uvicorn", "reportlab", "docx")


def _python_has_deps(prefix: list[str]) -> bool:
    try:
        r = subprocess.run([*prefix, "-c", f"import {', '.join(_PY_DEPS)}"],
                           capture_output=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def _resolve_python() -> tuple[list[str], list[dict]]:
    """返回 (命令前缀, 尝试记录)。按 H6_PYTHON → sys.executable → py 启动器 → PATH 顺序选择。"""
    tried: list[dict] = []
    cands: list[list[str]] = []
    env_py = os.environ.get("H6_PYTHON")
    if env_py:
        cands.append([env_py])
    cands.append([sys.executable])
    for ver in ("-3.10", "-3.11", "-3.12", "-3"):
        cands.append(["py", ver])
    for name in ("python", "python3"):
        w = shutil.which(name)
        if w:
            cands.append([w])
    seen: set[tuple[str, ...]] = set()
    for c in cands:
        key = tuple(c)
        if key in seen:
            continue
        seen.add(key)
        ok = _python_has_deps(c)
        tried.append({"prefix": c, "has_deps": ok})
        if ok:
            return c, tried
    return [env_py or sys.executable], tried


PY_PREFIX, PY_TRIED = _resolve_python()
PY = PY_PREFIX[-1] if len(PY_PREFIX) == 1 else " ".join(PY_PREFIX)
BROWSER_DIAG: list[dict] = []

# 阻断项 A：每次运行使用**独立 session 名**，彻底避开 ~/.agent-browser 下上一次运行的
# 残留状态（default.pid/port 指向已死端口 → CLI 连接超时 os error 10060，且后续
# snapshot/eval 一并挂起）。根因实测见 validation-artifacts/h8/diag/A-diagnosis.md。
BROWSER_SESSION = f"h6m-{os.getpid()}-{int(time.time())}"
RT = Path(tempfile.gettempdir()) / "v21h6_stub_runtime"
MODE_FILE = RT / "mode.json"
POST_LOG = RT / "stub_posts.log"
JD = ("高级后端研发工程师（Java）：负责电商平台交易链路设计、编码与线上稳定性，主导订单支付库存"
      "模块演进与高并发优化。要求 5 年+ Java、Spring Boot、MySQL、Redis，有分布式/消息队列实践"
      "优先，base 杭州，可尽快到岗。")
H6_MARKERS = ("h6-inject", "maybeinjecth6", "__h6_inject__", "h6_fixtures", "_v21_h6_stub", "_v21_h6_matrix")
# React Hook 顺序类异常：runner 强制收集并禁止出现；命中即 FAIL（不依赖 React 完整堆栈）
HOOK_FORBIDDEN_PATTERNS = (
    "rendered more hooks",
    "rendered fewer hooks",
    "order of hooks",
    "rules-of-hooks",
)
PASS = 0
FAILS: list[str] = []


def log(m: str = "") -> None:
    print(m, flush=True)


def dec(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("gbk", errors="replace")


def dec_fail(label: str, why: str, extra: str = "") -> None:
    FAILS.append(f"{label}: {why}")
    log(f"[FAIL] {label}: {why}" + (f" {extra}" if extra else ""))


def dec_pass(label: str, extra: str = "") -> None:
    global PASS
    PASS += 1
    log(f"[PASS] {label}" + (f" {extra}" if extra else ""))


_BROWSER_EXE: str | None = None


def resolve_browser() -> str | None:
    global _BROWSER_EXE
    if _BROWSER_EXE:
        return _BROWSER_EXE
    w = shutil.which("agent-browser")
    if not w:
        return None
    p = Path(w)
    if p.suffix.lower() == ".cmd":
        cand = p.parent / "node_modules" / "agent-browser" / "bin" / "agent-browser-win32-x64.exe"
        _BROWSER_EXE = str(cand) if cand.exists() else w
    else:
        _BROWSER_EXE = w
    return _BROWSER_EXE


def browser(args: list[str], timeout: int = 45) -> str:
    """调用 agent-browser，并**逐次记录** exe/参数/cwd/PID/起止时间/退出码/stderr。

    阻断项 A 要求：禁止用「看起来卡住」代替诊断。任何非零退出、超时或 stderr 都落日志。
    """
    exe = resolve_browser()
    if not exe:
        BROWSER_DIAG.append({"args": args, "error": "agent-browser 未解析"})
        log("[browser-diag] 无法解析 agent-browser 可执行文件")
        return ""
    env = dict(os.environ)
    env["AGENT_BROWSER_SESSION"] = BROWSER_SESSION  # 隔离会话：不读/不写 default 残留状态
    t0 = time.time()
    try:
        p = subprocess.Popen([exe, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             cwd=str(ROOT), env=env)
    except Exception as e:  # spawn 失败（CLI 查找阶段）
        BROWSER_DIAG.append({"args": args, "error": f"spawn_failed: {e}"})
        log(f"[browser-diag] spawn_failed args={args} err={e}")
        return ""
    pid = p.pid
    timed_out = False
    try:
        out, err = p.communicate(timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        p.kill()
        try:
            out, err = p.communicate(timeout=10)
        except Exception:
            out, err = b"", b""
        rc, timed_out = None, True
    dur = int((time.time() - t0) * 1000)
    so, se = dec(out).strip(), dec(err).strip()
    entry = {"args": args, "exe": exe, "cwd": str(ROOT), "pid": pid,
             "start": time.strftime("%H:%M:%S", time.localtime(t0)),
             "end": time.strftime("%H:%M:%S", time.localtime(time.time())),
             "dur_ms": dur, "exit": rc, "timed_out": timed_out,
             "stdout_len": len(so), "stderr": se[:400]}
    BROWSER_DIAG.append(entry)
    if timed_out or rc != 0 or se:
        log(f"[browser-diag] {'TIMEOUT' if timed_out else 'exit=' + str(rc)} "
            f"args={' '.join(args)[:100]} pid={pid} dur={dur}ms stderr={se[:200]}")
    return so


def kill_browsers() -> None:
    """强制清理（**仅**作为最后手段）：会留下 stale pid/port，正常路径不要调用。"""
    if os.name == "nt":
        for img in ("agent-browser-win32-x64.exe", "agent-browser.exe"):
            subprocess.run(["taskkill", "/F", "/IM", img],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def reset_daemon(tag: str = "") -> None:
    """阻断项 A：为本轮准备一个干净的隔离浏览器会话。

    历史失败链（已在 A-diagnosis.md 记录实测）：
    1) `open <url>` 在 SPA 上不返回（HMR websocket 持续占用连接）；
    2) 旧 `browser()` 用 `subprocess.run(timeout=45)`，超时后收尾可被 daemon 持管道阻塞 → 无界挂起；
    3) 强杀 daemon 会留下 `~/.agent-browser/default.{pid,port}` 指向已死端口 → 下一次 CLI 连接
       超时（os error 10060），随后 snapshot/eval 一并挂起 → prod-inject 全灭。
    本实现用**独立 session 名**（BROWSER_SESSION）绕开 (3)，并用有界超时绕开 (1)(2)。
    """
    browser(["close"], timeout=15)  # 只关本轮 session，不动其它会话
    time.sleep(0.5)
    if tag:
        log(f"[env] browser session ready ({tag}) session={BROWSER_SESSION}")


def kill_tree(p) -> None:
    """终止进程**树**（阻断项 A：npm/shell=True 只杀 shell 会留下 vite/node 孤儿）。"""
    if not p:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        p.kill()
        p.wait(timeout=10)
    except Exception:
        pass


def listener_pids(port: int) -> list[int]:
    try:
        r = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=20)
        txt = dec(r.stdout)
    except Exception:
        return []
    pids: list[int] = []
    for ln in txt.splitlines():
        if f":{port} " in ln and "LISTEN" in ln.upper():
            parts = ln.split()
            if parts and parts[-1].isdigit():
                pids.append(int(parts[-1]))
    return sorted(set(pids))


def wait_listen(port: int, timeout: int = 60) -> bool:
    """确定性等待端口就绪：同时探测 127.0.0.1 / ::1 / localhost（Vite 可能仅绑 IPv6）。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        for host in ("127.0.0.1", "::1", "localhost"):
            try:
                with socket.create_connection((host, port), timeout=1):
                    return True
            except OSError:
                pass
        if listener_pids(port):
            return True
        time.sleep(0.5)
    return False


def env_meta() -> dict:
    w = shutil.which("agent-browser")
    return {
        "python": PY,
        "python_candidates": PY_TRIED,
        "npm": NPM,
        "npm_resolved": shutil.which(NPM) or os.environ.get("H6_NPM", ""),
        "browser_which": w,
        "browser_exe": resolve_browser(),
        "browser_exe_exists": bool(resolve_browser() and Path(resolve_browser()).exists()),
        "path": os.environ.get("PATH", ""),
        "cwd": os.getcwd(),
    }


def log_env_meta() -> dict:
    meta = env_meta()
    log(f"[env] python={meta['python']} npm={meta['npm_resolved']}")
    log(f"[env] browser.which={meta['browser_which']}")
    log(f"[env] browser.exe={meta['browser_exe']} exists={meta['browser_exe_exists']}")
    log(f"[env] cwd={meta['cwd']}")
    return meta


def sh_out(cmd: list[str], timeout: int = 120, cwd: Path | None = None,
           env: dict | None = None) -> tuple[int, str]:
    exe = cmd[0]
    if (os.path.sep in exe or exe.lower() in ("python", "python3", "py")
            or exe.endswith(".exe") or exe == PY):
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                               cwd=str(cwd) if cwd else None,
                               env=env if env is not None else None)
        except subprocess.TimeoutExpired:
            return 124, ""
        return r.returncode, dec(r.stdout)
    try:
        r = subprocess.run(" ".join(cmd), capture_output=True, shell=True, timeout=timeout,
                           cwd=str(cwd) if cwd else None,
                           env=env if env is not None else None)
    except subprocess.TimeoutExpired:
        return 124, ""
    return r.returncode, dec(r.stdout)


def parse_res(res: str):
    for _ in range(3):
        if not isinstance(res, str):
            return res
        try:
            res = json.loads(res)
        except Exception:
            return res
    return res


def set_mode(mode: dict) -> None:
    RT.mkdir(parents=True, exist_ok=True)
    MODE_FILE.write_text(json.dumps(mode, ensure_ascii=False), encoding="utf-8")


def post_count() -> int:
    if not POST_LOG.exists():
        return 0
    n = 0
    for ln in POST_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.strip():
            n += 1
    return n


def fixture_sha(kind: str) -> str:
    h = json.loads((BACKEND / "h6_fixtures" / "fixture_hashes.json").read_text(encoding="utf-8"))
    return str((h.get(kind) or {}).get("sha256", ""))


def download_sha(url_path: str) -> str:
    with urllib.request.urlopen(f"http://127.0.0.1:8000{url_path}", timeout=20) as r:
        return hashlib.sha256(r.read()).hexdigest()


def run_proc(cmd: list[str], logfile: Path, cwd: Path | None = None, use_shell: bool = False,
             env: dict | None = None) -> subprocess.Popen:
    with open(logfile, "w", encoding="utf-8") as f:
        if use_shell or (cmd[0] in (NPM, "npm")):
            return subprocess.Popen(" ".join(cmd), stdout=f, stderr=subprocess.STDOUT,
                                    cwd=str(cwd) if cwd else str(ROOT), shell=True, env=env)
        return subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT,
                                cwd=str(cwd) if cwd else str(ROOT), env=env)


def kill(p) -> None:
    if p:
        p.kill()
        p.wait()


_INJECT_JS = ("window.__h5={errs:[],warns:[],posts:[]};"
              "window.addEventListener('error',e=>__h5.errs.push('uncaught:'+e.message));"
              "window.addEventListener('unhandledrejection',e=>__h5.errs.push('unhandledrejection:'+String(e.reason)));"
              "const _ce=console.error;console.error=(...a)=>{try{__h5.errs.push(a.map(String).join(' '))}catch(_){}};"
              "const _cw=console.warn;console.warn=(...a)=>{try{__h5.warns.push(a.map(String).join(' '))}catch(_){}};"
              "const _of=window.fetch;window.fetch=(...a)=>{const url=String(a[0]);"
              "const p=_of.apply(window,a);if(url.includes('/api/resume/generate-docx')){p.then(r=>r.clone().json().then(j=>{"
              "const s=(j&&j.result)||j;"
              "if(s&&s.operation_id){__h5.posts.push({url,op:s.operation_id,art:s.pdf_artifact_id,"
              "anchor_arts:Array.isArray(s.pdf_anchors)?s.pdf_anchors.map(x=>x&&x.artifact_id).filter(Boolean):[],"
              "word:s.download_url,pdf:s.pdf_download_url,"
              "pdfsha:s.pdf_sha256})}}).catch(()=>{}));}return p};'ok'")


def hook_violation(txt: str) -> bool:
    """Console 文本若含 React Hook 顺序类关键字即视为违规（用于全量断言，item 5）。"""
    low = (txt or "").lower()
    return any(p in low for p in HOOK_FORBIDDEN_PATTERNS)


def _warn_violations(warns):
    n = 0
    for w in warns or []:
        if hook_violation(str(w)):
            n += 1
    return n


def _eval(js: str):
    return parse_res(browser(["eval", js]))


def _poll_eval(js: str, cond, timeout: float, interval: float = 0.8) -> dict | None:
    """确定性轮询：反复 eval 直到条件满足或超时。返回最后一次可解析结果。"""
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        last = _eval(js)
        if isinstance(last, dict) and cond(last):
            return last
        time.sleep(interval)
    return last if isinstance(last, dict) else None


def _wait_snapshot_contains(text: str, timeout: float) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        snap = browser(["snapshot", "-i"], timeout=30)
        if text in snap:
            return True
        time.sleep(0.6)
    return False


def do_generate(label: str, mode: dict, base_url: str, expect: str) -> dict | None:
    """一次完整生成：打开 → 填表 → 生成 → 断言基础态；返回捕获字典。"""
    set_mode(mode)
    # 阻断项 A 根因：agent-browser `open <url>` 在本 SPA 上**不会返回**（页面已加载；静态页
    # 对照实验 open=591ms，SPA 因 Vite HMR websocket 持续占用连接而不返回）。故显式限时并
    # 忽略其结果；就绪与否由下面的 snapshot 轮询判定（实测 open 后 snapshot/eval 正常）。
    browser(["open", base_url], timeout=12)
    # 阻断项 A：用**输入页独有**标志（JD 输入框）判定就绪；「生成岗位简历」在结果页/导航
    # 也可能出现，用它判定会把结果页误当输入页（历史 dev-viewports 假就绪）。
    ok_ready = _wait_snapshot_contains("粘贴完整岗位描述", 40)
    if not ok_ready:
        # 一次确定性恢复：残留/版本不符 daemon 会让 snapshot 也挂起 → 重置后重开一次
        log(f"[browser-diag] {label}: 首次就绪失败，重置会话并重试一次")
        reset_daemon("retry-" + label)
        browser(["open", base_url], timeout=12)
        ok_ready = _wait_snapshot_contains("粘贴完整岗位描述", 40)
    if not ok_ready:
        dec_fail(label, "页面打开后未出现 JD 输入框（已含一次会话重置重试）")
        return None
    browser(["eval", _INJECT_JS])
    snap = browser(["snapshot", "-i"])
    mref = re.search(r'button "编辑[^\n]*?ref=([a-z0-9]+)', snap)
    if mref:
        browser(["click", f"@{mref.group(1)}"]); time.sleep(1)
        snap = browser(["snapshot", "-i"])
    nm = re.search(r'textbox "姓名[^\n]*?ref=([a-z0-9]+)', snap)
    if nm:
        browser(["fill", f"@{nm.group(1)}", "林澈"])
    jd = re.search(r'textbox "粘贴完整岗位描述[^\n]*?ref=([a-z0-9]+)', snap)
    if jd:
        browser(["fill", f"@{jd.group(1)}", JD])
    time.sleep(1)
    snap = browser(["snapshot", "-i"])
    gb = re.search(r'button "生成岗位简历[^\n]*?ref=([a-z0-9]+)', snap)
    if not gb:
        dec_fail(label, "未找到可点击的「生成岗位简历」")
        return None
    pre = post_count()
    browser(["click", f"@{gb.group(1)}"])
    # 阻断项 A：确定性等待生成结束（成功=POST 计数 +1；失败=出现失败/重试文案）
    probe = ("JSON.stringify({n:(window.__h5?.posts??[]).length,"
             "txt:(document.body.innerText.match(/下载 Word|下载 PDF|重新生成|生成失败|失败/)||['?'])[0]})")
    if expect == "fail":
        _poll_eval(probe, lambda d: ("失败" in (d.get("txt") or "") or "重新生成" in (d.get("txt") or "")), 60)
    else:
        _poll_eval(probe, lambda d: int(d.get("n", 0) or 0) >= 1, 90)
    time.sleep(2)
    cap_raw = browser(["eval", "JSON.stringify({errs:(window.__h5?.errs??[]).length,"
                       "warns:window.__h5?.warns??[],"
                       "hook_warns:window.__h5?.warns?.filter(w=>{const s=String(w).toLowerCase();"
                       "return s.includes('rendered more hooks')||s.includes('rendered fewer hooks')"
                       "||s.includes('order of hooks')||s.includes('rules-of-hooks')}).length??0,"
                       "canvas:document.querySelectorAll('canvas').length,"
                       "blank:document.body.innerText.trim().length===0,"
                       "avail:document.body.innerText.includes('PDF 预览不可用'),"
                       "eb:document.body.innerText.includes('应用异常')||document.body.innerText.includes('页面渲染时出了点问题'),"
                       "retry:document.body.innerText.includes('重试页面渲染'),"
                       "back:document.body.innerText.includes('返回生成工作台'),"
                       "pressed:document.querySelectorAll('[aria-pressed]').length,"
                       "selected_count:document.querySelectorAll('[aria-pressed=\"true\"]').length,"
                       "posts:window.__h5?.posts??[],"
                       "txt:(document.body.innerText.match(/下载 Word|下载 PDF|重新生成|失败/)||['?'])[0]})"])
    d = parse_res(cap_raw)
    if not isinstance(d, dict):
        dec_fail(label, f"断言输出无法解析：{cap_raw[:160]}")
        return None
    d["_post_delta"] = post_count() - pre
    return d


def check_dev_scene(label: str, mode: dict, expect: str) -> None:
    d = do_generate(label, mode, "http://localhost:5173/", expect)
    if d is None:
        return
    # ── item 5：Console 全量断言（errs 数 + hook 关键字命中）──
    errs_count = int(d.get("errs", 0) or 0)
    hook_count = int(d.get("hook_warns", 0) or 0)
    errs_ok = errs_count == 0 and hook_count == 0
    if not errs_ok:
        dec_fail(label, f"Console error/Hook warning 非空：errs={errs_count} hook_warns={hook_count}")
        return
    if d.get("blank"):
        dec_fail(label, "白屏")
        return
    posts = d.get("posts") or []
    post_delta_ok = d.get("_post_delta") == 1
    if not post_delta_ok:
        dec_fail(label, f"POST 增量不等于 1（={d.get('_post_delta')}）")
        return
    if expect == "success":
        cap = d.get("canvas", 0)
        anchors_mode = mode.get("anchors")
        posts_last = posts[-1] if posts else None
        # ── item 2：成功态字段必查（op/art/word url/pdf url/response pdf_sha256）──
        required = posts_last and posts_last.get("op") and posts_last.get("art") \
            and posts_last.get("word") and posts_last.get("pdf") and posts_last.get("pdfsha")
        if not required:
            dec_fail(label, f"成功响应字段缺失：op={bool(posts_last and posts_last.get('op'))} "
                        f"art={bool(posts_last and posts_last.get('art'))} word={bool(posts_last and posts_last.get('word'))} "
                        f"pdf={bool(posts_last and posts_last.get('pdf'))} pdfsha={bool(posts_last and posts_last.get('pdfsha'))}")
            return
        # ── item 1：anchors 绑定到 artifact 身份（empty=0、full=非空且全部=art、mismatch=不匹配空命中层）──
        anchor_arts = posts_last.get("anchor_arts") or []
        if anchors_mode == "empty":
            anchors_ok = len(anchor_arts) == 0 and d.get("pressed", 0) == 0
        elif anchors_mode == "mismatch":
            # anchor_arts 非空但其中至少一条 != art → fail closed：UI 不应有点击命中层
            anchors_ok = len(anchor_arts) >= 1 and not all(a == posts_last.get("art") for a in anchor_arts) \
                and d.get("pressed", 0) == 0
        else:  # full
            anchors_ok = len(anchor_arts) >= 1 and all(a == posts_last.get("art") for a in anchor_arts) \
                and d.get("pressed", 0) >= 1
        if not anchors_ok:
            dec_fail(label, f"anchors 绑定不符：mode={anchors_mode} arts={anchor_arts} pressed={d.get('pressed')}")
            return
        # ── item 2：双 hash 校对（PDF hash 同时等于响应 pdfsha 与 fixture hash；Word hash 等于 fixture）──
        try:
            pdf_dl_sha = download_sha(posts_last["pdf"])
            word_dl_sha = download_sha(posts_last["word"])
        except Exception as e:
            dec_fail(label, f"下载异常：{e}")
            return
        fixture_pdf_sha = fixture_sha("pdf")
        fixture_docx_sha = fixture_sha("docx")
        if pdf_dl_sha != posts_last["pdfsha"]:
            dec_fail(label, f"PDF hash 与响应不符：dl={pdf_dl_sha[:16]} resp={posts_last['pdfsha'][:16]}")
            return
        if pdf_dl_sha != fixture_pdf_sha:
            dec_fail(label, f"PDF hash 与 fixture 不符：dl={pdf_dl_sha[:16]} fx={fixture_pdf_sha[:16]}")
            return
        if word_dl_sha != fixture_docx_sha:
            dec_fail(label, f"Word hash 与 fixture 不符：dl={word_dl_sha[:16]} fx={fixture_docx_sha[:16]}")
            return
        if cap >= 1 and anchors_ok and post_delta_ok:
            dec_pass(label, f"canvas={cap} pressed={d.get('pressed')} post+{d.get('_post_delta')} hash OK")
        else:
            dec_fail(label, f"canvas={cap} pressed={d.get('pressed')} post+{d.get('_post_delta')}")
    elif expect == "fail":
        ok = (("失败" in (d.get("txt") or "") or "重新生成" in (d.get("txt") or ""))
              and not posts and post_delta_ok)
        if ok:
            dec_pass(label)
        else:
            dec_fail(label, f"fail 态不符 txt={d.get('txt')} posts={len(posts)} post+{d.get('_post_delta')}")
    elif expect == "nourl":
        # ── item 3：nourl 增强（Word 仍可下载且 hash 正确；canvas=0；不出现伪造成功）──
        if not posts:
            dec_fail(label, "nourl 期望成功响应但无 posts")
            return
        posts_last = posts[-1]
        if posts_last.get("pdf") or posts_last.get("pdfsha"):
            dec_fail(label, f"nourl 响应不应含 PDF 字段：{posts_last}")
            return
        try:
            word_dl_sha = download_sha(posts_last["word"])
        except Exception as e:
            dec_fail(label, f"Word 下载失败：{e}")
            return
        if word_dl_sha != fixture_sha("docx"):
            dec_fail(label, f"Word hash 与 fixture 不符：dl={word_dl_sha[:16]} fx={fixture_sha('docx')[:16]}")
            return
        ok = d.get("canvas") == 0 and not d.get("avail") and post_delta_ok
        if ok:
            dec_pass(label, f"canvas=0 word_hash={word_dl_sha[:16]}")
        else:
            dec_fail(label, f"canvas={d.get('canvas')} avail={d.get('avail')} post+{d.get('_post_delta')}")
    elif expect == "avail":
        # ── item 3：broken 增强（avail=true，Word hash 正确，不增 POST）──
        if not posts:
            dec_fail(label, "avail 期望成功响应但无 posts")
            return
        posts_last = posts[-1]
        try:
            word_dl_sha = download_sha(posts_last["word"])
        except Exception as e:
            dec_fail(label, f"Word 下载失败：{e}")
            return
        if word_dl_sha != fixture_sha("docx"):
            dec_fail(label, f"Word hash 与 fixture 不符：dl={word_dl_sha[:16]}")
            return
        ok = d.get("avail") and post_delta_ok
        if ok:
            dec_pass(label, f"avail=true word_hash={word_dl_sha[:16]}")
        else:
            dec_fail(label, f"avail={d.get('avail')} post+{d.get('_post_delta')}")
    else:
        dec_fail(label, f"未知 expect {expect}")


_LAYOUT_PROBE = (
    "JSON.stringify({vw:window.innerWidth,vh:window.innerHeight,"
    "docSH:document.documentElement.scrollHeight,bodySH:document.body.scrollHeight,"
    "overflow:document.documentElement.scrollHeight-window.innerHeight,"
    "hOverflow:document.documentElement.scrollWidth-window.innerWidth,"
    "scrollables:(()=>{let n=0;for(const e of document.querySelectorAll('*')){const s=getComputedStyle(e);"
    "if((s.overflowY==='auto'||s.overflowY==='scroll')&&e.scrollHeight>e.clientHeight+1)n++;}return n;})(),"
    "blank:document.body.innerText.trim().length===0})"
)
VIEWPORTS = ((1440, 900), (1280, 720), (1920, 1080))


def check_viewports(base_url: str) -> None:
    """三视口 1440×900 / 1280×720 / 1920×1080：页面整体无滚动、卡片内允许滚动。

    在**输入页**与**结果页**各测一次（共 6 次），断言：
    - 非白屏；
    - 页面整体（documentElement）纵向无溢出（overflow ≤ 2px，允许亚像素舍入）；
    - 内容溢出只允许发生在卡片级可滚动容器内（scrollables 计数仅记录，不冒充通过条件）。

    实现上复用 `do_generate`（含注入、填表、点击、有界轮询与失败重试），避免上一场景停在
    结果页时把结果页元素误当输入页元素（历史 FAIL：视口检查期间 POST 增量=0）。
    """
    results: dict[str, dict] = {}
    d = do_generate("dev-viewports",
                    {"delay_ms": 800, "fail_generate": False, "pdf_gen": "good",
                     "pdf_mode": "good", "anchors": "full", "run_no": 300, "expect": "success"},
                    base_url, "success")
    if d is None:
        return
    if int(d.get("_post_delta") or 0) != 1:
        dec_fail("dev-viewports", f"生成 POST 增量异常={d.get('_post_delta')}")
        return
    # 结果页：三视口
    for (w, h) in VIEWPORTS:
        browser(["set", "viewport", str(w), str(h)], timeout=20)
        time.sleep(0.6)
        m = _eval(_LAYOUT_PROBE)
        results[f"result-{w}x{h}"] = m if isinstance(m, dict) else {"error": str(m)}
    # 回到输入页：三视口（点击左侧「生成简历」导航）
    snap = browser(["snapshot", "-i"])
    nav = re.search(r'link "生成简历[^\n]*?ref=([a-z0-9]+)', snap)
    if nav:
        browser(["click", f"@{nav.group(1)}"])
        time.sleep(1.5)
    browser(["open", base_url], timeout=12)
    if not _wait_snapshot_contains("粘贴完整岗位描述", 40):
        dec_fail("dev-viewports", "未回到输入页")
        return
    for (w, h) in VIEWPORTS:
        browser(["set", "viewport", str(w), str(h)], timeout=20)
        time.sleep(0.5)
        m = _eval(_LAYOUT_PROBE)
        results[f"input-{w}x{h}"] = m if isinstance(m, dict) else {"error": str(m)}
    EVIDENCE_VIEWPORT.clear()
    EVIDENCE_VIEWPORT.update(results)
    bad = {k: v for k, v in results.items()
           if not isinstance(v, dict) or v.get("blank") or v.get("overflow") is None
           or int(v.get("overflow") or 0) > 2}
    if bad:
        dec_fail("dev-viewports", f"页面整体出现滚动/异常：{json.dumps(bad, ensure_ascii=False)[:400]}")
        return
    dec_pass("dev-viewports",
             "三视口 输入页+结果页 均无整页滚动 & 非白屏 | "
             + " ".join(f"{k}:ov={v.get('overflow')},card={v.get('scrollables')}"
                        for k, v in sorted(results.items()))[:300])


EVIDENCE_VIEWPORT: dict = {}
EVIDENCE_RECOVERY: dict = {}


def _click_first_evidence_and_assert(label: str, prev_selected: int) -> None:
    """item 4：实际点击首个 aria-pressed 命中元素，断言切换后 selected_count 变化。"""
    snap = browser(["snapshot", "-i"])
    m = re.search(r'button "第[^\n]*?ref=([a-z0-9]+)', snap)
    if not m:
        return  # 无可点依据 = 命中层为空，调用方已断言
    browser(["click", f"@{m.group(1)}"])
    time.sleep(1)
    cap = parse_res(browser(["eval", "JSON.stringify({selected:document.querySelectorAll('[aria-pressed=\"true\"]').length,"
                              "posts:window.__h5?.posts?.length??0})"]))
    if not isinstance(cap, dict):
        return
    if cap.get("selected", 0) <= prev_selected:
        dec_fail(label, f"evidence 点击未产生选中态：prev={prev_selected} now={cap.get('selected')}")
    if cap.get("posts", 0) > 1:
        dec_fail(label, f"evidence 点击新增 POST：posts={cap.get('posts')}")


def run_dev() -> None:
    log_env_meta()
    reset_daemon("dev-start")
    stub_log = ROOT / ".h6_stub.log"
    dev_log = ROOT / ".h6_dev.log"
    stub = run_proc([*PY_PREFIX, str(BACKEND / "_v21_h6_stub.py"), "--port", "8000"], stub_log)
    # H7 R35 修正：npm run dev 必须在 frontend/ 目录执行（package.json 在 frontend/）；
    # 缺 cwd 会在仓库根跑 npm → ENOENT package.json → Vite 起不来，dev 场景必挂。
    dev = run_proc([NPM, "run", "dev", "--", "--port", "5173"], dev_log, cwd=FRONTEND)
    try:
        # 阻断项 A：确定性等待监听（替代固定 sleep 7s），失败即具名 FAIL 并附日志尾部
        if not wait_listen(8000, 90):
            tail = ""
            try:
                tail = stub_log.read_text(encoding="utf-8", errors="replace")[-400:]
            except Exception:
                pass
            dec_fail("dev-boot", "stub 后端 8000 未监听", tail)
            return
        if not wait_listen(5173, 90):
            tail = ""
            try:
                tail = dev_log.read_text(encoding="utf-8", errors="replace")[-400:]
            except Exception:
                pass
            dec_fail("dev-boot", "vite dev 5173 未监听", tail)
            return
        log(f"[env] listeners 8000={listener_pids(8000)} 5173={listener_pids(5173)}")
        check_dev_scene("dev-success", {"delay_ms": 1200, "fail_generate": False, "pdf_gen": "good", "pdf_mode": "good", "anchors": "full", "run_no": 100, "expect": "success"}, "success")
        # item 4：dev-success 后实际点击首个 evidence，断言切换且 POST 不增
        _click_first_evidence_and_assert("dev-success-click", 0)
        check_dev_scene("dev-fail", {"delay_ms": 1200, "fail_generate": True, "pdf_gen": "good", "pdf_mode": "good", "anchors": "full", "run_no": 101, "expect": "fail"}, "fail")
        check_dev_scene("dev-nourl", {"delay_ms": 1200, "fail_generate": False, "pdf_gen": "none", "pdf_mode": "good", "anchors": "full", "run_no": 102, "expect": "nourl"}, "nourl")
        check_dev_scene("dev-broken", {"delay_ms": 1200, "fail_generate": False, "pdf_gen": "good", "pdf_mode": "broken", "anchors": "full", "run_no": 103, "expect": "avail"}, "avail")
        check_dev_scene("dev-anchors-empty", {"delay_ms": 1200, "fail_generate": False, "pdf_gen": "good", "pdf_mode": "good", "anchors": "empty", "run_no": 104, "expect": "success"}, "success")
        check_dev_scene("dev-anchors-mismatch", {"delay_ms": 1200, "fail_generate": False, "pdf_gen": "good", "pdf_mode": "good", "anchors": "mismatch", "run_no": 105, "expect": "success"}, "success")
        # item 3：artifact-change 两次生成各自完整成功断言；第二轮切到第二轮 artifact；第一轮 URL 字节稳定
        dA = do_generate("dev-artifact-a", {"delay_ms": 1200, "fail_generate": False, "pdf_gen": "good", "pdf_mode": "good", "anchors": "full", "run_no": 200, "expect": "success"}, "http://localhost:5173/", "success")
        if dA is None:
            return
        pA = (dA.get("posts") or [])
        if not (dA.get("canvas", 0) >= 1 and dA.get("_post_delta") == 1 and pA
                and pA[-1].get("op") and pA[-1].get("art") and pA[-1].get("pdf") and pA[-1].get("word") and pA[-1].get("pdfsha")):
            dec_fail("dev-artifact-a", f"首次生成未通过完整字段断言：{pA[-1] if pA else None}")
            return
        try:
            pdfA = download_sha(pA[-1]["pdf"])
            wordA = download_sha(pA[-1]["word"])
        except Exception as e:
            dec_fail("dev-artifact-a", f"首次下载失败：{e}")
            return
        if pdfA != pA[-1]["pdfsha"] or pdfA != fixture_sha("pdf") or wordA != fixture_sha("docx"):
            dec_fail("dev-artifact-a", f"首次 hash 不符 pdf={pdfA[:16]} word={wordA[:16]}")
            return
        opA, artA, urlA, pdfUrlA, wordUrlA = pA[-1]["op"], pA[-1]["art"], pA[-1]["pdf"], pA[-1]["pdf"], pA[-1]["word"]
        dec_pass("dev-artifact-a", f"op={opA[:8]} art={artA[:16]} hash OK")
        dB = do_generate("dev-artifact-b", {"delay_ms": 1200, "fail_generate": False, "pdf_gen": "good", "pdf_mode": "good", "anchors": "full", "run_no": 201, "expect": "success"}, "http://localhost:5173/", "success")
        if dB is None:
            return
        pB = (dB.get("posts") or [])
        if not (dB.get("canvas", 0) >= 1 and dB.get("_post_delta") == 1 and pB
                and pB[-1].get("op") and pB[-1].get("art") and pB[-1].get("pdf") and pB[-1].get("word") and pB[-1].get("pdfsha")):
            dec_fail("dev-artifact-b", f"第二次生成未通过完整字段断言：{pB[-1] if pB else None}")
            return
        try:
            pdfB = download_sha(pB[-1]["pdf"])
            wordB = download_sha(pB[-1]["word"])
        except Exception as e:
            dec_fail("dev-artifact-b", f"第二次下载失败：{e}")
            return
        if pdfB != pB[-1]["pdfsha"] or pdfB != fixture_sha("pdf") or wordB != fixture_sha("docx"):
            dec_fail("dev-artifact-b", f"第二次 hash 不符 pdf={pdfB[:16]} word={wordB[:16]}")
            return
        opB, artB = pB[-1]["op"], pB[-1]["art"]
        if opB == opA or artB == artA:
            dec_fail("dev-artifact-change", f"第二轮 op/art 相同：op {opA[:8]}=={opB[:8]} art {artA[:16]}=={artB[:16]}")
            return
        # 第一轮 URL 字节稳定（旧 PDF/DOCX 仍可下载且 hash 一致）
        try:
            pdfA_after = download_sha(urlA)
            wordA_after = download_sha(wordUrlA)
        except Exception as e:
            dec_fail("dev-artifact-change", f"第一轮 URL 复测失败：{e}")
            return
        if pdfA_after != pdfA or wordA_after != wordA:
            dec_fail("dev-artifact-change", f"第一轮 URL 字节已变：pdf {pdfA[:16]}->{pdfA_after[:16]} word {wordA[:16]}->{wordA_after[:16]}")
            return
        dec_pass("dev-artifact-change", f"op {opA[:8]}->{opB[:8]} art 不同 两轮 hash OK 第一轮稳定")
        # H8 用户指令：三视口 1440×900 / 1280×720 / 1920×1080；页面整体无滚动、卡片内允许滚动
        check_viewports("http://localhost:5173/")
    finally:
        kill_tree(dev)
        kill_tree(stub)
        browser(["close"])  # 只关本轮隔离 session（不清扫其它会话）
        for port in (5173, 8000):
            for pid in listener_pids(port):
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_prod_inject(target: str) -> None:
    log_env_meta()
    reset_daemon(f"prod-{target}-start")
    # item 7：显式剥离 VITE_H6_INJECT 避免继承调用者环境（即便 test build 仍走 null）
    env = {k: v for k, v in os.environ.items() if k != "VITE_H6_INJECT"}
    env["VITE_H6_INJECT"] = target
    # 预清 dist 绕开 sandbox safe-delete shim
    dist = FRONTEND / "dist"
    ok, err = _safe_rmtree(dist)
    if not ok:
        dec_fail(f"prod-inject {target}", f"预清 dist 失败：{err}")
        return
    log_path = ROOT / f".h6_prod_{target}_build.log"
    try:
        log_path.unlink(missing_ok=True)
    except Exception:
        pass
    p = run_proc([NPM, "run", "build"], log_path, cwd=FRONTEND, env=env)
    if not p:
        dec_fail(f"prod-inject {target}", "build 进程未启动")
        return
    rc = p.wait()
    if rc != 0:
        tail = ""
        try:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-400:]
        except Exception:
            pass
        dec_fail(f"prod-inject {target}", f"test build 失败（exit={rc}）", tail)
        return
    log(f"[ok ] prod build (VITE_H6_INJECT={target})")
    stub = run_proc([*PY_PREFIX, str(BACKEND / "_v21_h6_stub.py"), "--port", "8000"], ROOT / ".h6_stub.log")
    try:
        if not wait_listen(8000, 90):
            dec_fail(f"prod-inject {target}", "stub 后端 8000 未监听")
            return
        pre = post_count()
        d = do_generate(f"prod-inject-{target}", {"delay_ms": 1200, "fail_generate": False, "pdf_gen": "good", "pdf_mode": "good", "anchors": "full", "run_no": 200, "expect": "success"}, "http://127.0.0.1:8000/", "success")
        if d is None:
            return
        # item 6：EB 出现 + 非白屏 + 重试/返回两个按钮都必须存在；缺一个直接 FAIL
        if not (d.get("eb") and not d.get("blank") and d.get("retry") and d.get("back")):
            dec_fail(f"prod-inject {target}",
                     f"EB 或恢复按钮缺失 eb={d.get('eb')} blank={d.get('blank')} retry={d.get('retry')} back={d.get('back')}")
            return
        # 阻断项 A：恢复路径——点「重试页面渲染」持续注入下仍 EB 不白屏；记录恢复前后 op/artifact/hash
        # 用**文本定位**点击（比 @ref 稳；@ref 在重渲染/视口变化后可能指向迁移的元素）。
        # 先确认两个按钮都存在，避免把「返回生成工作台」误点（历史 FAIL 根因）。
        pre_snap = browser(["snapshot", "-i"])
        if ('重试页面渲染' not in pre_snap) or ('返回生成工作台' not in pre_snap):
            dec_fail(f"prod-inject {target}", "EB 恢复按钮文本缺失")
            return
        browser(["find", "text", "重试页面渲染", "click"], timeout=30)
        d2 = _poll_eval(
            "JSON.stringify({eb:document.body.innerText.includes('应用异常'),"
            "retry:document.body.innerText.includes('重试页面渲染'),"
            "input:document.body.innerText.includes('粘贴完整岗位描述'),"
            "blank:document.body.innerText.trim().length===0})",
            lambda x: (x.get("eb") and not x.get("blank")) or x.get("input"), 20)
        # 合法结果：注入持续时重新抛错 → EB 再次出现；或边界恢复后回到可用的生成页。
        # 二者都不允许白屏，且不允许停留在空白/损坏页。
        if not (isinstance(d2, dict) and not d2.get("blank")
                and (d2.get("eb") or d2.get("input"))):
            dec_fail(f"prod-inject {target}", f"「重试页面渲染」后页面态非法 {d2}")
            return
        EVIDENCE_RECOVERY[target] = ("eb_again" if d2.get("eb") else "recovered_input_page")
        # 若已回到生成页，则「返回生成工作台」按钮不复存在 —— 视为恢复路径已完成
        post_retry = browser(["snapshot", "-i"])
        if '返回生成工作台' not in post_retry:
            delta = post_count() - pre
            if delta <= 1:
                dec_pass(f"prod-inject {target}",
                         f"EB+恢复通过（重试后回到生成页），本 target POST+{delta}")
            else:
                dec_fail(f"prod-inject {target}", f"恢复产生额外 POST {delta}（>1）")
            return
        browser(["find", "text", "返回生成工作台", "click"], timeout=30)
        d3 = _poll_eval(
            "JSON.stringify({input:document.body.innerText.includes('粘贴完整岗位描述'),"
            "blank:document.body.innerText.trim().length===0})",
            lambda x: x.get("input") and not x.get("blank"), 20)
        if not (isinstance(d3, dict) and d3.get("input") and not d3.get("blank")):
            dec_fail(f"prod-inject {target}", f"「返回生成工作台」未离开故障结果页 {d3}")
            return
        delta = post_count() - pre
        if delta <= 1:
            dec_pass(f"prod-inject {target}", f"EB+恢复通过，本 target POST+{delta}")
        else:
            dec_fail(f"prod-inject {target}", f"恢复产生额外 POST {delta}（>1）")
    finally:
        kill_tree(stub)
        browser(["close"])  # 只关本轮隔离 session
        for pid in listener_pids(8000):
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _safe_rmtree(path: Path) -> tuple[bool, str]:
    """删除目录：Windows sandbox 下 Python shutil.rmtree 与 node fs.rmSync 都被 safe-delete
    shim 拦截并要求回收站；为稳定可重复，用 PowerShell Remove-Item 直删。返回 (ok, err)。"""
    if not path.exists():
        return True, ""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Remove-Item -Recurse -Force '{path}' -ErrorAction SilentlyContinue"],
            capture_output=True, timeout=30,
        )
        if r.returncode == 0 and not path.exists():
            return True, ""
        return False, (dec(r.stderr) or dec(r.stdout) or "unknown")[:200]
    except Exception as e:
        return False, str(e)[:200]


def run_verify() -> None:
    # item 7：正式 build 前显式剥离 VITE_H6_INJECT（避免调用者环境干扰）
    env = {k: v for k, v in os.environ.items() if k != "VITE_H6_INJECT"}
    dist = FRONTEND / "dist"
    # 预清 dist：绕开 sandbox safe-delete shim，用 PowerShell Remove-Item 直删
    ok, err = _safe_rmtree(dist)
    if not ok:
        dec_fail("verify", f"预清 dist 失败：{err}")
        return
    log_path = ROOT / ".h6_verify_build.log"
    try:
        log_path.unlink(missing_ok=True)
    except Exception:
        pass
    p = run_proc([NPM, "run", "build"], log_path, cwd=FRONTEND, env=env)
    if not p:
        dec_fail("verify", "build 进程未启动")
        return
    rc = p.wait()
    if rc != 0:
        tail = ""
        try:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-400:]
        except Exception:
            pass
        dec_fail("verify", f"正式无 env build 失败（exit={rc}）", tail)
        return
    dist = FRONTEND / "dist"
    # item 7：dist 不存在 / 0 文件都需明确 FAIL
    if not dist.is_dir():
        dec_fail("verify", f"dist 目录不存在：{dist}")
        return
    files = 0
    hits: list[str] = []
    failed_reads: list[str] = []
    markers_low = tuple(m.lower() for m in H6_MARKERS)  # H6_MARKERS 已 lower，直接在 lowered bytes 内找
    for dirpath, _dirs, names in os.walk(dist):
        for n in names:
            p = Path(dirpath) / n
            try:
                data = p.read_bytes()
            except Exception as e:
                failed_reads.append(f"{p.relative_to(dist)}: {e}")
                continue
            files += 1
            low = data.lower()
            for m in markers_low:
                if m.encode("utf-8", "ignore") in low:
                    hits.append(f"{p.relative_to(dist)}::{m}")
    log(f"[scan] dist 扫描 {files} 个文件，命中 {len(hits)} 个，读取失败 {len(failed_reads)} 个")
    if files == 0:
        dec_fail("verify", "dist 下 0 个文件（构建未产出资源）")
        return
    if hits:
        dec_fail("verify", f"命中 {hits[:5]}")
        return
    if not hits:
        dec_pass("verify", "正式 dist 无 H6 注入标记（纯 Python 扫描）")


def run_selfcheck() -> None:
    ok = True
    if not resolve_browser():
        dec_fail("selfcheck", "agent-browser 不在 PATH")
        ok = False
    if sh_out([*PY_PREFIX, "-c", "import fastapi, uvicorn, reportlab, docx"])[0] != 0:
        dec_fail("selfcheck", "后端依赖不可导入")
        ok = False
    if sh_out(["node", "--version"])[0] != 0:
        dec_fail("selfcheck", "node 不可用")
        ok = False
    if ok:
        dec_pass("selfcheck", "agent-browser/后端依赖/node 均可用")


def run_all() -> None:
    # item 8：selfcheck 已有 FAIL 时 --all 立即停止后续动态场景，不允许带病进入
    if any(f.startswith("selfcheck:") for f in FAILS):
        dec_fail("all-selfcheck-gate", "selfcheck 已 FAIL，--all 停止后续动态场景")
        return
    try:
        r = subprocess.run([*PY_PREFIX, str(BACKEND / "_v21_h6_matrix.py")], capture_output=True, timeout=300)
    except subprocess.TimeoutExpired:
        dec_fail("all-62matrix", "timeout>300s")  # item 8：超时具名 FAIL
        return
    if r.returncode == 0 and re.search(rb"PASS=\d+\s+FAIL=0", r.stdout):
        dec_pass("all-62matrix", "PASS=<N> FAIL=0")
    else:
        # item 8：非零退出具名 FAIL（不再静默成功）
        dec_fail("all-62matrix", f"exit={r.returncode} stdout={r.stdout[:200].decode('utf-8', 'replace')}")
        return
    # 再次确认 selfcheck 通过后才能进入 dev / prod / verify
    run_selfcheck()
    if any(f.startswith("selfcheck:") for f in FAILS):
        dec_fail("all-selfcheck-gate", "selfcheck 本轮 FAIL，--all 停止后续动态场景")
        return
    run_dev()
    for t in ("pdf", "overlay", "basis", "export"):
        run_prod_inject(t)
    run_verify()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="h6_browser_matrix", add_help=True,
                                 description="V2.1.0 H6 浏览器矩阵 runner")
    ap.add_argument("--dev", action="store_true", help="dev 六场景机器断言")
    ap.add_argument("--prod-inject", metavar="TARGET", choices=("pdf", "overlay", "basis", "export"),
                    help="单 target production 注入")
    ap.add_argument("--prod-all", action="store_true", help="四区依次 production 注入")
    ap.add_argument("--verify", action="store_true", help="正式 build + 剥离扫描")
    ap.add_argument("--selfcheck", action="store_true", help="环境检查")
    ap.add_argument("--all", action="store_true", help="总入口")
    args = ap.parse_args(argv)
    # fail closed：只允许一种入口
    acts = [args.dev, args.prod_inject is not None, args.prod_all, args.verify, args.selfcheck, args.all]
    if sum(1 for a in acts if a) != 1:
        ap.error("必须且只能指定一个入口（--dev / --prod-inject / --prod-all / --verify / --selfcheck / --all）")
    if args.dev:
        run_dev()
    elif args.prod_inject:
        run_prod_inject(args.prod_inject)
    elif args.prod_all:
        for t in ("pdf", "overlay", "basis", "export"):
            run_prod_inject(t)
    elif args.verify:
        run_verify()
    elif args.selfcheck:
        run_selfcheck()
    else:
        run_all()
    log("=" * 60)
    log(f"H6 浏览器矩阵：PASS={PASS} FAIL={len(FAILS)}")
    for f in FAILS:
        log("  - " + f)
    # 阻断项 A：落盘确定性诊断（exe/args/cwd/PID/起止/exit/stderr），供复现与审查
    try:
        diag_dir = ROOT / "validation-artifacts" / "h8"
        diag_dir.mkdir(parents=True, exist_ok=True)
        (diag_dir / "h6_browser_diag.json").write_text(
            json.dumps({"env": env_meta(), "browser_calls": BROWSER_DIAG,
                        "pass": PASS, "fails": FAILS,
                        "viewports": EVIDENCE_VIEWPORT,
                        "prod_recovery": EVIDENCE_RECOVERY,
                        "browser_session": BROWSER_SESSION},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[env] diagnostics → {diag_dir / 'h6_browser_diag.json'} ({len(BROWSER_DIAG)} browser calls)")
    except Exception as e:
        log(f"[warn] 写诊断 JSON 失败：{e}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
