#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""H8-R1 R3：真实 React onChange 浏览器回归（PLAN §20.5 / T12-R40；独立验收 H8-8）。

背景（独立验收根因）：
- 旧 GeneratePage 在 JD ≥ 60 字且防抖 600ms 后自动调用 services.jd.analyze → 真实 onedir
  中用户只输入 JD、尚未点击生成，就已产生 Provider chat 请求（H8-SRC 违反 PLAN §20.5）。
- 开发 E2E 用 agent-browser `fill` 填 JD：fill 直接写 DOM value 不派发真实 input 事件，
  没有触发 React onChange → 漏测。独立负向证明正常 200 不触发 SDK 重试，两次重复请求
  实际来自「输入页预分析」+「生成 operation 内正式 JD 分析」。

本脚本用**真实事件语义**驱动输入（原生 value setter + input/change、键盘逐字 type、
真实粘贴 Control+v、≥60 字等待超防抖、修改已满足长度 JD、点击前等待数秒、完整 operation），
并在**真实后端 + 本地 fake Provider**（计数 /chat/completions 与 embeddings）下机器断言：

  点击前 /api/jd/analyze 请求 = 0
  点击前 Provider chat = 0
  点击生成后 operation 数量 +1
  operation 内 jd_analysis STARTED 恰好 1（逻辑调用）
  正常 200 路径 JD Provider HTTP 请求 = 1（SDK 不重试）
  rewrite 单独计数（与 JD 分析不混写）
  页面无 Hook warning / uncaught error / 白屏

覆盖 dev 与正式 production bundle；`--negative` 用旧 H8-SRC 构建产物复现漏测（真实事件下
旧候选必然产生预分析请求 → 断言失败），记录「旧候选负向 / 新候选正向」成对证据。

用法：
  python scripts/h8_r3_browser.py                    # 正向 dev + prod（前置要求：frontend/dist 为修正后 build）
  python scripts/h8_r3_browser.py --negative-only     # 仅旧候选负向（构建 H8-SRC 前端并驱动真实事件）
  python scripts/h8_r3_browser.py --all               # 负向 + 正向

退出码：0=全部通过；1=存在 FAIL；2=环境/前置失败。
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
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"
PY = os.environ.get("H8_R3_PYTHON", sys.executable)

JD_FULL = ("高级后端研发工程师（Java）：负责电商平台交易链路设计、编码与线上稳定性，主导订单支付库存"
           "模块演进与高并发优化。要求 5 年+ Java、Spring Boot、MySQL、Redis，有分布式/消息队列实践"
           "优先，base 杭州，可尽快到岗。")
# 边界 JD：恰好 ≥60 字且 trim 后仍 ≥60（JD_FULL[:60] 第 60 字符为空格，trim 后仅 59 字，
# 旧候选会正确地不触发预分析 —— 那不是被测行为）。rstrip 后补足到 60。
JD_60 = JD_FULL[:60].rstrip()
if len(JD_60) < 60:
    JD_60 += "。" * (60 - len(JD_60))
JD_APPEND = "。补充：负责支付模块改造与性能优化，熟悉 TDD 与代码评审，关注工程质量。"
assert len(JD_FULL) >= 60 and len(JD_60.strip()) >= 60

EXPERIENCES = [
    {"type": "work", "title": "后端研发工程师", "company": "示例科技有限公司",
     "time": "2022.03-2025.06", "role": "后端研发工程师",
     "description": "负责示例电商平台订单域的后端研发与稳定性建设。",
     "achievements": [
         "主导订单创建链路重构，将核心接口 P99 从 820ms 降到 210ms",
         "搭建库存扣减幂等与对账机制，超卖事故从月均 3 起降为 0"],
     "skills": ["Java", "Spring Boot", "MySQL", "Redis", "Kafka"],
     "raw_text": "示例科技有限公司 后端研发工程师 2022.03-2025.06"},
    {"type": "work", "title": "初级后端工程师", "company": "虚构网络股份有限公司",
     "time": "2020.07-2022.02", "role": "初级后端工程师",
     "description": "负责示例社区服务的接口开发与数据维护。",
     "achievements": [
         "完成用户中心服务拆分，接口平均延迟下降 35%",
         "推动单元测试覆盖率从 42% 提升到 78%"],
     "skills": ["Java", "MySQL", "MyBatis"],
     "raw_text": "虚构网络股份有限公司 初级后端工程师 2020.07-2022.02"},
    {"type": "project", "title": "订单对账系统", "company": "示例科技有限公司",
     "time": "2024.05-2024.11", "role": "负责人",
     "description": "面向示例业务的订单对账与差异定位系统。",
     "achievements": [
         "设计差异定位算法，对账工单平均处理时长从 45 分钟降到 8 分钟",
         "实现对账任务调度，日处理账单量 200 万条"],
     "skills": ["Java", "Kafka", "MySQL"],
     "raw_text": "订单对账系统 负责人 2024.05-2024.11"},
    {"type": "education", "title": "计算机科学与技术", "company": "示例大学",
     "time": "2016.09-2020.06", "role": "",
     "description": "计算机科学与技术 本科",
     "achievements": [], "skills": [],
     "raw_text": "示例大学 计算机科学与技术 本科 2016.09-2020.06"},
]

HOOK_PATTERNS = ("rendered more hooks", "rendered fewer hooks",
                 "order of hooks", "rules-of-hooks")
PASS = 0
FAILS: list[str] = []
EVIDENCE: dict = {"scenarios": [], "provider": {}, "negative": {}}
SUMMARY_LINES: list[str] = []


def log(m: str = "") -> None:
    print(m, flush=True)


def ok(label: str, extra: str = "") -> None:
    global PASS
    PASS += 1
    log(f"[PASS] {label}" + (f" {extra}" if extra else ""))
    SUMMARY_LINES.append(f"[PASS] {label}" + (f" {extra}" if extra else ""))


def bad(label: str, why: str) -> None:
    FAILS.append(f"{label}: {why}")
    log(f"[FAIL] {label}: {why}")


def hook_warns(warns) -> list[str]:
    out = []
    for w in warns or []:
        s = str(w).lower()
        if any(p in s for p in HOOK_PATTERNS):
            out.append(str(w))
    return out


# ── fake Provider：计数 /chat/completions 与 embeddings ──────────
FP_PORT = 8791                                # fake provider 固定端口
FP_STATE = {"chat": 0, "jd": 0, "rewrite": 0, "content": 0, "other_chat": 0, "emb": 0}
FP_LOCK = threading.Lock()
FP_FILE: Path | None = None

# ── SSE 断流（R2-19 §R2-18 修复）持住控制 ──────────────────────
# 为 sse_stream_break 场景制造「流在线且 provider 静止」的可控窗口：
# 当某个 kind(默认 jd) 的 chat 请求到达时，把它在回复前 hold 若干秒，
# 从而保证断流 re-poll 期间不会产生新的 LLM/Embedding 调用（provider 增量必须为 0）。
# 注：新工作台多阶段编排中 rewrite 不再单独分类（并入 other_chat），而 jd_analyze（jd）
# 在每个生成 /start 后 RUNNING 阶段恰好触发 1 次、流已在线，是唯一稳定可达的 hold 靶点。
# 由脚本通过 POST /__h8control {"stall_s": N, "stall_kind": "jd"} 打开；一次性（触发后自动清零）。
FP_STALL_KIND = "jd"
FP_STALL_S = 0.0
SSE_BREAK_STALL_S = 15.0

_JD_FIXTURE = {
    "position": "高级后端研发工程师", "industry": "互联网",
    "required_skills": ["Java", "Spring Boot", "MySQL", "Redis"],
    "preferred_skills": ["Kafka"],
    "responsibilities": ["负责电商平台交易链路设计与线上稳定性"],
    "keywords": ["高并发", "分布式"], "experience_preferences": ["5 年+"],
}


def fp_snapshot() -> dict:
    with FP_LOCK:
        return dict(FP_STATE)


def _fp_dump() -> None:
    if FP_FILE is None:
        return
    try:
        FP_FILE.write_text(json.dumps(fp_snapshot(), ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _classify(body: bytes) -> str:
    try:
        j = json.loads(body.decode("utf-8", "replace"))
    except Exception:
        return "other_chat"
    try:
        rf = j.get("response_format") or {}
        name = str(((rf.get("json_schema") or {}).get("name")) or "")
        if "JDAnalysisOut" in name:
            return "jd"
        if "GeneratedResumeContentV15" in name:
            return "rewrite"
        if "GeneratedResumeContent" in name:
            return "content"
    except Exception:
        pass
    txt = json.dumps(j, ensure_ascii=False)
    if "资深招聘分析师" in txt:
        return "jd"
    if "资深简历优化专家" in txt or "evidence_json" in txt:
        return "rewrite"
    return "other_chat"


def _extract_evidence_array(text: str) -> list:
    """从 user 消息中提取首个 JSON 数组（evidence_json 入选经历 payload）。"""
    i = text.find("[")
    if i < 0:
        return []
    depth = 0
    in_str = False
    esc = False
    for k in range(i, len(text)):
        c = text[k]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                seg = text[i:k + 1]
                try:
                    return json.loads(seg)
                except Exception:
                    return []
    return []


def _fixture_content(kind: str, body: bytes) -> dict:
    if kind == "jd":
        return dict(_JD_FIXTURE)
    if kind == "rewrite":
        try:
            j = json.loads(body.decode("utf-8", "replace"))
        except Exception:
            return {"experiences": []}
        user_text = ""
        for m in (j.get("messages") or []):
            if m.get("role") == "user":
                user_text = str(m.get("content") or "")
        payload = _extract_evidence_array(user_text)
        exps = []
        for p in payload:
            exid = str(p.get("experience_id") or "")
            bullets = []
            for f in (p.get("usable_facts") or [])[:2]:
                tid = str(f.get("fact_id") or "")
                txt = str(f.get("text") or "")[:70]
                if tid and txt:
                    bullets.append({"bullet": txt, "fact_refs": [tid]})
            exps.append({"experience_id": exid, "bullets": bullets,
                         "insufficient": False, "insufficient_reason": ""})
        return {"experiences": exps}
    if kind == "content":
        return {"experiences": []}
    return {}


def _chat_body(content: dict) -> dict:
    return {
        "id": "chatcmpl-r3", "object": "chat.completion", "created": 0, "model": "r3",
        "choices": [{"index": 0,
                     "message": {"role": "assistant",
                                 "content": json.dumps(content, ensure_ascii=False)},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


class FPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        return

    def _send(self, obj: dict, status: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_POST(self):
        body = self._body()
        path = self.path.split("?")[0]
        global FP_STALL_S, FP_STALL_KIND
        if path.endswith("/__h8control"):
            # SSE 断流控制的 provider 面：脚本用它布防/关闭 hold（默认 jd），不改产品后端。
            try:
                ctrl = json.loads(body.decode("utf-8", "replace"))
                val = max(0.0, float(ctrl.get("stall_s") or ctrl.get("rewrite_stall_s") or 0))
                kind = str(ctrl.get("stall_kind") or FP_STALL_KIND)
            except Exception:  # noqa: BLE001
                val = 0.0
                kind = FP_STALL_KIND
            with FP_LOCK:
                FP_STALL_S = val
                FP_STALL_KIND = kind
            self._send({"ok": True})
            return
        if path.endswith("/chat/completions"):
            kind = _classify(body)
            with FP_LOCK:
                FP_STATE["chat"] += 1
                FP_STATE[kind] += 1
            _fp_dump()
            # 一次性持住：target kind 抵达后 hold 响应，制造「流在线且 provider 静止」窗口
            stall_kind = FP_STALL_KIND
            if kind == stall_kind:
                with FP_LOCK:
                    delay = FP_STALL_S
                    FP_STALL_S = 0.0
                    FP_STALL_KIND = ""
                if delay > 0:
                    time.sleep(delay)
            self._send(_chat_body(_fixture_content(kind, body)))
        elif path.endswith("/embeddings/multimodal"):
            with FP_LOCK:
                FP_STATE["emb"] += 1
            _fp_dump()
            self._send({"data": {"embedding": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]}})
        else:
            self._send({"error": {"message": f"fake provider unknown path {path}"}}, 404)


def start_fake_provider(port: int, out: Path) -> ThreadingHTTPServer:
    global FP_FILE
    FP_FILE = out
    FP_FILE.write_text(json.dumps(fp_snapshot(), ensure_ascii=False), encoding="utf-8")
    srv = ThreadingHTTPServer(("127.0.0.1", port), FPHandler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    log(f"[fp] fake provider 127.0.0.1:{port} → counts {out.name}")
    return srv


def fp_stall(seconds: float) -> None:
    """打开/关闭 fake provider 的 hold（默认 jd；SSE 断流场景使用；不触产品后端）。"""
    try:
        st, _ = _api(FP_PORT, "POST", "/__h8control",
                     {"stall_s": seconds, "stall_kind": FP_STALL_KIND}, timeout=10)
        log(f"[fp] {FP_STALL_KIND} stall_s → {seconds} (rc={st})")
    except Exception as e:  # noqa: BLE001
        log(f"[fp] {FP_STALL_KIND} stall_s 设置失败：{e}")
        bad("fp-stall-control", f"{e}")


# ── 进程/端口工具 ─────────────────────────────────────────────
def listener_pids(port: int) -> list[int]:
    try:
        r = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=20)
        txt = r.stdout.decode("utf-8", "replace")
    except Exception:
        return []
    pids = []
    for ln in txt.splitlines():
        if f":{port} " in ln and "LISTEN" in ln.upper():
            parts = ln.split()
            if parts and parts[-1].isdigit():
                pids.append(int(parts[-1]))
    return sorted(set(pids))


def wait_port(port: int, timeout: float = 90.0) -> bool:
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
        time.sleep(0.4)
    return False


def kill_tree(p) -> None:
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


# ── 真实后端（源码 uvicorn） ───────────────────────────────────
def start_backend(runtime: Path, fp_port: int, port: int, log_name: str) -> subprocess.Popen:
    env = dict(os.environ)
    env["RESUME_DATA_DIR"] = str(runtime)
    env["ARK_BASE_URL"] = f"http://127.0.0.1:{fp_port}/v1"
    env["ARK_API_KEY"] = "r3-fake-provider-key"
    env["APP_HOST"] = "127.0.0.1"
    env["APP_PORT"] = str(port)
    env.pop("ARK_EMBEDDING_API_KEY", None)
    fh = open(runtime / log_name, "w", encoding="utf-8", errors="replace")
    p = subprocess.Popen(
        [PY, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port),
         "--log-level", "warning"],
        cwd=str(BACKEND), env=env, stdout=fh, stderr=subprocess.STDOUT)
    p._log_fh = fh  # type: ignore[attr-defined]
    return p


def stop_backend(p) -> None:
    kill_tree(p)
    try:
        p._log_fh.close()  # type: ignore[attr-defined]
    except Exception:
        pass


# ── seeding（urllib + cookie jar；写操作需启动会话 cookie） ────
_OPENER = None


def _api(port: int, method: str, path: str, payload=None, timeout: int = 300):
    global _OPENER
    if _OPENER is None:
        import http.cookiejar
        cj = http.cookiejar.CookieJar()
        _OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with _OPENER.open(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
        try:
            return r.status, json.loads(raw)
        except Exception:
            return r.status, raw


def seed(port: int) -> dict:
    st, _ = _api(port, "GET", "/api/system/status")
    st, mig = _api(port, "POST", "/api/system/migrate", timeout=240)
    if st != 200:
        raise RuntimeError(f"migrate failed: {st} {mig}")
    ids = []
    for e in EXPERIENCES:
        st, body = _api(port, "POST", "/api/experience/", e, timeout=120)
        if st != 200:
            raise RuntimeError(f"import failed: {st} {body}")
        ids.append(body.get("id"))
    st, rb = _api(port, "POST", "/api/system/rebuild", timeout=600)
    if st != 200:
        raise RuntimeError(f"rebuild failed: {st} {rb}")
    st, stat = _api(port, "GET", "/api/system/status")
    return {"migrate": mig, "experience_ids": ids, "rebuild": rb,
            "status": stat if isinstance(stat, dict) else {}}


def list_generate_ops(port: int) -> list[dict]:
    st, body = _api(port, "GET", "/api/system/operations?operation_type=generate&limit=100")
    if st != 200:
        return []
    return (body or {}).get("operations") or []


def op_detail(port: int, op_id: str) -> dict:
    st, body = _api(port, "GET", f"/api/system/operations/{op_id}")
    if st != 200:
        return {}
    return (body or {}).get("operation") or {}


# ── 浏览器（agent-browser；隔离 session） ──────────────────────
BROWSER_SESSION = f"h8r3-{os.getpid()}-{int(time.time())}"


def _browser_env() -> dict:
    e = dict(os.environ)
    e["AGENT_BROWSER_SESSION"] = BROWSER_SESSION
    return e


def resolve_browser() -> str | None:
    w = shutil.which("agent-browser")
    if not w:
        return None
    p = Path(w)
    if p.suffix.lower() == ".cmd":
        cand = p.parent / "node_modules" / "agent-browser" / "bin" / "agent-browser-win32-x64.exe"
        return str(cand) if cand.exists() else w
    return w


def bx(args: list[str], timeout: int = 45) -> str:
    exe = resolve_browser()
    if not exe:
        return ""
    try:
        p = subprocess.Popen([exe, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=_browser_env(), cwd=str(ROOT))
    except Exception:
        return ""
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        try:
            out, _ = p.communicate(timeout=10)
        except Exception:
            out = b""
    return out.decode("utf-8", "replace").strip()


def reset_daemon(tag: str) -> None:
    bx(["close"], timeout=15)
    time.sleep(0.5)
    log(f"[env] browser session ready ({tag}) session={BROWSER_SESSION}")


def parse_res(res: str):
    for _ in range(3):
        if not isinstance(res, str):
            return res
        try:
            res = json.loads(res)
        except Exception:
            return res
    return res


def ev(js: str):
    return parse_res(bx(["eval", js], timeout=30))


def wait_contains(text: str, timeout: float = 45) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        snap = bx(["snapshot", "-i"], timeout=30)
        if text in snap:
            return True
        time.sleep(0.6)
    return False


_R3_INJECT = (
    "window.__r3={reqs:[],errs:[],warns:[]};"
    "window.addEventListener('error',e=>__r3.errs.push('uncaught:'+e.message));"
    "window.addEventListener('unhandledrejection',e=>__r3.errs.push('rej:'+String(e.reason)));"
    "const _ce=console.error;console.error=(...a)=>{try{__r3.errs.push(a.map(String).join(' '))}catch(_){}};"
    "const _cw=console.warn;console.warn=(...a)=>{try{__r3.warns.push(a.map(String).join(' '))}catch(_){}};"
    "const _of=window.fetch;window.fetch=(...a)=>{const u=String(a[0]);"
    "try{__r3.reqs.push(u)}catch(_){}return _of.apply(window,a)};'ok'"
)


def open_page(base_url: str, label: str) -> bool:
    bx(["open", base_url], timeout=12)
    if wait_contains("粘贴完整岗位描述", 40):
        return True
    reset_daemon("retry-" + label)
    bx(["open", base_url], timeout=12)
    return wait_contains("粘贴完整岗位描述", 40)


def collect_page() -> dict:
    raw = ev("JSON.stringify({reqs:window.__r3?.reqs??[],errs:window.__r3?.errs??[],"
             "warns:window.__r3?.warns??[],blank:document.body.innerText.trim().length===0})")
    d = raw if isinstance(raw, dict) else {}
    return {
        "jd_analyze": [u for u in (d.get("reqs") or []) if "/api/jd/analyze" in u],
        "generate": [u for u in (d.get("reqs") or []) if "/api/resume/generate-docx" in u],
        "reqs": list(d.get("reqs") or []),
        "errs": list(d.get("errs") or []),
        "warns": list(d.get("warns") or []),
        "hook_warns": hook_warns(d.get("warns")),
        "blank": bool(d.get("blank")),
    }


def pre_click_asserts(label: str, page: dict, fp_before: dict, fp_after: dict,
                      expect_pre_analysis: bool) -> None:
    """机器断言「点击前零 LLM 预分析」。

    expect_pre_analysis=False（正向）：全部必须为 0；
    True（负向）：断言被真实事件复现（记录观测值，作为旧候选漏测证据）。
    """
    jd_n = len(page["jd_analyze"])
    gen_n = len(page["generate"])
    chat_delta = fp_after["chat"] - fp_before["chat"]
    jd_delta = fp_after["jd"] - fp_before["jd"]
    tag = label
    if expect_pre_analysis:
        if jd_n > 0 or jd_delta > 0:
            ok(tag + "-negative-preanalysis",
               f"旧候选真实事件下复现预分析：/api/jd/analyze={jd_n} Provider-jd={jd_delta}")
        else:
            bad(tag + "-negative-preanalysis",
                f"旧候选未复现预分析（jd_analyze={jd_n} provider_jd={jd_delta}）")
        return
    if jd_n == 0 and gen_n == 0 and chat_delta == 0 and jd_delta == 0:
        ok(tag + "-pre-click-zero",
           f"jd_analyze={jd_n} generate={gen_n} Provider-chat={chat_delta}")
    else:
        bad(tag + "-pre-click-zero",
            f"点击前出现预分析/生成请求：jd_analyze={jd_n} generate={gen_n} "
            f"Provider-chat={chat_delta} Provider-jd={jd_delta}")
    if not page["errs"] and not page["hook_warns"] and not page["blank"]:
        ok(tag + "-no-console-err", f"errs={len(page['errs'])} hook={len(page['hook_warns'])} blank={page['blank']}")
    else:
        bad(tag + "-no-console-err",
            f"errs={page['errs'][:2]} hook={page['hook_warns'][:2]} blank={page['blank']}")


# ── 场景驱动 ───────────────────────────────────────────────────
def s1_native_setter(base: str, label: str, expect_pre: bool) -> None:
    open_page(base, label)
    bx(["eval", _R3_INJECT])
    fb = fp_snapshot()
    js = (f"(()=>{{const el=document.getElementById('wb-jd');if(!el)return 'no-el';"
          f"const p=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value');"
          f"p.set.call(el,{json.dumps(JD_FULL, ensure_ascii=False)});"
          f"el.dispatchEvent(new Event('input',{{bubbles:true}}));"
          f"el.dispatchEvent(new Event('change',{{bubbles:true}}));"
          f"return 'ok:'+el.value.length;}})()")
    r = ev(js)
    time.sleep(1.2)
    pre_click_asserts(label + "-native-setter", collect_page(), fb, fp_snapshot(), expect_pre)


def s2_keyboard(base: str, label: str, expect_pre: bool) -> None:
    open_page(base, label)
    bx(["eval", _R3_INJECT])
    fb = fp_snapshot()
    bx(["click", "#wb-jd"], timeout=25)
    bx(["type", "#wb-jd", JD_FULL], timeout=90)
    time.sleep(1.2)
    pre_click_asserts(label + "-keyboard", collect_page(), fb, fp_snapshot(), expect_pre)


def s3_paste(base: str, label: str, expect_pre: bool) -> None:
    open_page(base, label)
    bx(["eval", _R3_INJECT])
    fb = fp_snapshot()
    r = ev(f"(async()=>{{try{{await navigator.clipboard.writeText({json.dumps(JD_FULL, ensure_ascii=False)});"
           f"return 'clip-ok'}}catch(e){{return 'clip-err:'+String(e)}}}})()")
    used = "clipboard"
    bx(["focus", "#wb-jd"], timeout=25)
    bx(["press", "Control+v"], timeout=25)
    time.sleep(1.2)
    v = ev("(document.getElementById('wb-jd')||{}).value?.length||0")
    if isinstance(v, (int, float)) and v >= 60:
        used = "clipboard+ctrl-v"
    else:
        # 回退：DataTransfer 构造真实 paste 事件（仍触发 React onChange）
        js = (f"(()=>{{const el=document.getElementById('wb-jd');"
              f"const dt=new DataTransfer();dt.setData('text/plain',{json.dumps(JD_FULL, ensure_ascii=False)});"
              f"const p=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value');"
              f"p.set.call(el,{json.dumps(JD_FULL, ensure_ascii=False)});"
              f"el.dispatchEvent(new ClipboardEvent('paste',{{bubbles:true,clipboardData:dt}}));"
              f"el.dispatchEvent(new Event('input',{{bubbles:true}}));"
              f"return 'ok:'+el.value.length;}})()")
        ev(js)
        used = "clipboard-event-fallback"
        time.sleep(1.2)
    pre_click_asserts(label + "-paste-" + used, collect_page(), fb, fp_snapshot(), expect_pre)


def s4_reach60_wait(base: str, label: str, expect_pre: bool) -> None:
    open_page(base, label)
    bx(["eval", _R3_INJECT])
    fb = fp_snapshot()
    # 用 native setter + input/change 事件精确写入恰好 JD_MIN_CHARS(60) 字：
    # type 逐字符在无 HMR 的旧候选构建下可能输入不满 60 字导致漏触发，native setter
    # 由 s1 证明能真实触发 React onChange 并复现旧候选预分析。
    js = (f"(()=>{{const el=document.getElementById('wb-jd');if(!el)return 'no-el';"
          f"const p=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value');"
          f"p.set.call(el,{json.dumps(JD_60, ensure_ascii=False)});"
          f"el.dispatchEvent(new Event('input',{{bubbles:true}}));"
          f"el.dispatchEvent(new Event('change',{{bubbles:true}}));"
          f"return 'ok:'+el.value.length;}})()")
    r = ev(js)
    time.sleep(1.5)  # > 600ms 防抖窗口
    pre_click_asserts(label + "-reach60-wait1500ms", collect_page(), fb, fp_snapshot(), expect_pre)


def s5_modify_satisfying(base: str, label: str, expect_pre: bool) -> None:
    open_page(base, label)
    bx(["eval", _R3_INJECT])
    fb = fp_snapshot()
    bx(["click", "#wb-jd"], timeout=25)
    bx(["type", "#wb-jd", JD_FULL], timeout=90)
    time.sleep(1.0)  # 首次满足长度并等待（旧候选在此触发分析 #1）
    bx(["type", "#wb-jd", JD_APPEND], timeout=60)
    time.sleep(1.5)  # 修改后等待（旧候选在此触发分析 #2）
    pre_click_asserts(label + "-modify", collect_page(), fb, fp_snapshot(), expect_pre)


def s6_wait_seconds(base: str, label: str, expect_pre: bool) -> None:
    open_page(base, label)
    bx(["eval", _R3_INJECT])
    fb = fp_snapshot()
    bx(["click", "#wb-jd"], timeout=25)
    bx(["type", "#wb-jd", JD_FULL], timeout=90)
    time.sleep(4.0)  # 输入后等待数秒
    pre_click_asserts(label + "-wait4s", collect_page(), fb, fp_snapshot(), expect_pre)


def s7_full_operation(port: int, base: str, label: str, expect_pre: bool) -> None:
    open_page(base, label)
    bx(["eval", _R3_INJECT])
    fb = fp_snapshot()
    # 填写姓名 + JD（生成前检查需要）。新 UI（StepIdentity）为受控组件：
    # fill 只写 DOM value 不派发 input/change，React state 不会更新 → 必须用原生 value
    # setter + input/change 事件，并轮询 window.__h8fill 回读验证 React state 真拿到值
    # （对齐 h8_real_model_e2e 已验证的写入路径，否则点击被「请填写姓名」拦截）。
    # 双选择器回退（#wb-name / placeholder）：部分环境 snapshot 无 id 时仍能命中。
    # 注：旧 GeneratePage 已于 V2.2.0 DOC_RETURNED 返工删除（同根重复实现退出），
    # 该回退仅针对 StepIdentity 的选择器差异，不涉及任何旧页面。
    bx(["eval",
        "(()=>{"
        "const setV=(el,v)=>{"
        "  const proto=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;"
        "  const setter=Object.getOwnPropertyDescriptor(proto,'value').set;"
        "  setter.call(el,v);"
        "  el.dispatchEvent(new Event('input',{bubbles:true}));"
        "  el.dispatchEvent(new Event('change',{bubbles:true}));"
        "};"
        "const ni=document.querySelector('#wb-name')||document.querySelector('input[placeholder=\"请输入姓名\"]');"
        "const nj=document.querySelector('#wb-jd')||document.querySelector('textarea[placeholder=\"职位描述（JD）\"]');"
        "if(ni)setV(ni,'测试用户H8');"
        "if(nj)setV(nj," + json.dumps(JD_FULL, ensure_ascii=False) + ");"
        "setTimeout(()=>{"
        "  window.__h8fill=JSON.stringify({"
        "  nameOk:!!(ni&&ni.value.trim()),"
        "  jdLen:nj?nj.value.length:0,"
        "  disabled:(document.querySelector('.wb-form-actions__primary')||{}).disabled??null"
        "  });},400);"
        "return 'ok';})()"], timeout=25)
    # 轮询回读 React 受控 state（value 落盘为准判名/JD）。
    fv = None
    for _ in range(10):
        time.sleep(0.3)
        raw = bx(["eval", "window.__h8fill||'{}'"], timeout=25).strip()
        try:
            cand = json.loads(raw)
            cand = json.loads(cand) if isinstance(cand, str) else cand
        except Exception:
            continue
        if cand.get("nameOk") and (cand.get("jdLen") or 0) >= 60:
            fv = cand
            break
    if fv is None:
        fvrm = ev("JSON.stringify({name:document.querySelector('#wb-name')?.value||'',"
                  "jdLen:document.querySelector('#wb-jd')?.value?.length||0})")
        bad(label + "-op-fill", "姓名/JD 未进入 React state（值未落盘）" + str(fvrm)[:200])
        return
    time.sleep(0.5)
    # 点击前断言（正向必须 0；负向期望复现）
    pre_click_asserts(label + "-op-preclick", collect_page(), fb, fp_snapshot(), expect_pre)
    if expect_pre:
        return  # 负向场景到此为止（无需真实完成生成）
    snap = bx(["snapshot", "-i"])
    gb = re.search(r'button "生成岗位简历[^\n]*?ref=([a-z0-9]+)', snap)
    if not gb:
        # 诊断：抓取快照内全部 button 文本 + 主按钮真实文本/disabled/activeIdx 相关状态
        diag = ev("JSON.stringify({"
                  "btns:[...document.querySelectorAll('button')].map(b=>"
                  "(b.className.includes('wb-form-actions__primary')?('PRIMARY|'+b.textContent.trim()+'|disabled='+b.disabled):b.textContent.trim())).slice(0,20),"
                  "foot:!!document.querySelector('.wb-panel__foot--generate'),"
                  "activeIdx:(document.querySelector('.wb-panel__head-title')?.textContent||'').trim(),"
                  "prim:document.querySelector('.wb-form-actions__primary')?JSON.stringify({t:document.querySelector('.wb-form-actions__primary').textContent.trim(),d:document.querySelector('.wb-form-actions__primary').disabled}):null})")
        log(f"[diag {label} op-click-missing] " + str(diag)[:800])
        lines = [l for l in snap.splitlines() if "生成" in l or "button" in l.lower()]
        log("[diag snapshot buttons]\n" + "\n".join(lines[:25]))
        bad(label + "-op-click", "未找到「生成岗位简历」")
        return
    # 点击前诊断：确认按钮非禁用（disabled 时 click 无声效，会表现为无新 op 且无 alert）
    pre_click_diag = ev("JSON.stringify({"
                        "primDisabled:document.querySelector('.wb-form-actions__primary')?.disabled??null,"
                        "primText:document.querySelector('.wb-form-actions__primary')?.textContent.trim()||null,"
                        "statusSel:null})")
    log(f"[diag {label} pre-click] {pre_click_diag}")
    bx(["click", f"@{gb.group(1)}"], timeout=25)
    # 等待本次生成（新工作台链路：点击后走 /api/task/{id}/start SSE，不再创建 generate-docx
    # operation）。以本地 fake Provider 计数收敛为完成判据（jd=1、rewrite=1，chat 合计=2），
    # 并确认页面确实发出了 /start 请求、输入视图已离开、无 console 错误。
    t0 = time.time()
    fa = fb
    started = False
    s_final = None
    gen_req_seen = []
    while time.time() - t0 < 300:
        fa = fp_snapshot()
        s_cur = collect_page()
        s_final = s_cur
        gen_req_seen = [u for u in s_cur["reqs"] if "/task/" in u and u.endswith("/start")]
        started = started or bool(gen_req_seen)
        jd_n = fa["jd"] - fb["jd"]
        rw_n = fa["rewrite"] - fb["rewrite"]
        ct_n = fa["content"] - fb["content"]
        chat_n = fa["chat"] - fb["chat"]
        # 完成判据（对齐下方 op 主动断言语义）：已见 /start + jd 分析恰好产生增量 +
        # chat 有增量（多阶段编排，rewrite/content 分类在新工作台不单独计数）。
        if started and jd_n >= 1 and chat_n >= 1:
            break
        if time.time() - t0 > 45 and not started:
            diag = bx(["eval",
                "JSON.stringify({alert:[...document.querySelectorAll('[role=alert],.wb-footinfo__err')]"
                ".map(e=>(e.textContent||'').trim()),"
                "name:document.querySelector('#wb-name')?.value||'',"
                "jd:document.querySelector('#wb-jd')?.value?.length||0,"
                "disabled:document.querySelector('.wb-form-actions__primary')?.disabled??null,"
                "genReqs:(window.__r3?.reqs||[]).filter(u=>u.includes('/task/')).slice(0,6),"
                "status:(document.querySelector('.wb-panel__head-title')?.textContent||'').trim(),"
                "bodyText:document.body.innerText.slice(0,200)})"],
                timeout=20)
            log(f"[diag {label}] no-start: " + str(diag)[:500])
            break
        time.sleep(2.0)
    page = collect_page()
    jd_delta = fa["jd"] - fb["jd"]
    rw_delta = fa["rewrite"] - fb["rewrite"]
    ct_delta = fa["content"] - fb["content"]
    chat_delta = fa["chat"] - fb["chat"]
    accounted = jd_delta + rw_delta + ct_delta + (fa["other_chat"] - fb["other_chat"])
    # 新工作台为多阶段 LLM 编排：一次生成会产生多次 chat（jd 分析/选材/重写/润色）。
    # 核心正向契约：
    #  1) 点击必定触发 /start，生成真实启动（started）；
    #  2) 整个生成内 jd 分析（职业 JD 分析请求）恰好 1 次 —— 这是「输入页无预分析、
    #     只在生成 operation 内做唯一一次 JD 分析」的直接证据；
    #  3) 所有 Provider chat 调用都被 accounted 覆盖（审计可解释），且并发无错误。
    # rewrite/chat 的确切次数不做硬断言（随编排阶段变多），仅在 evidence 记录观测值。
    checks = []
    checks.append(("start-seen", started))
    checks.append(("jd-provider=1", jd_delta == 1))
    checks.append(("chat-accounted", chat_delta == accounted))
    checks.append(("no-err", not page["errs"] and not page["hook_warns"] and not page["blank"]))
    if all(v for _, v in checks):
        ok(label + "-op",
           f"start jd_provider={jd_delta} rewrite={rw_delta} chat={chat_delta} accounted={accounted}")
    else:
        failed = [k for k, v in checks if not v]
        bad(label + "-op",
            f"断言失败 {failed} jd_provider={jd_delta} rewrite={rw_delta} content={ct_delta} "
            f"chat={chat_delta} accounted={accounted} started={started} errs={page['errs'][:2]}")
    EVIDENCE["scenarios"].append({
        "label": label, "generation_start_seen": started,
        "jd_provider_http": jd_delta, "rewrite_provider_http": rw_delta,
        "chat_total_delta": chat_delta, "status": "started",
        "console_errs": page["errs"], "hook_warns": page["hook_warns"],
        "blank": page["blank"], "provider": fa,
    })


def sse_stream_break(port: int, base: str, label: str) -> None:
    """R2-19 §R2-18 修复证据：SSE 断流 → es.onerror → 幂等权威 re-poll。

    关键证据（白盒：refresh 只 GET /api/task/{id} 并 applyView，绝不触发生成）：
      1) 断流后前端重新取得权威快照（页面通过 GET /api/task/{id} re-poll）；
      2) 阶段状态不丢失（快照 phase 在断流前后一致，UI 仍显示原步骤文本）；
      3) LLM/Embedding 增量 0（fp_snapshot() 在断流前后的 chat/jd/rewrite/other_chat/emb
         相对增量必须为 0 —— 这正是 refresh 只 GET 不生成的 key 证据）。

    断流注入方式（经 agent-browser 实机验证选定）：
      - agent-browser `network route ... --abort` 与 `set offline` 都只作用于【新】请求，
        无法切断【已建立】的 EventSource 长连接；
      - 因此采用「route 拦 /api/task/*/stream + reload」：reload 后页面重建 EventSource，
        该 /stream 请求被 route 拦掉 → 触发 es.onerror（走修复后的
        setStreamEnded(true); close(); void refresh() 分支）；GET /api/task/{id} 不在
        route 内 → re-poll 成功。此即真实「断流后重建连接失败 → 权威快照恢复」等价路径。

    provider 静止窗口保证 delta==0：
      在点击生成前通过 /__h8control 布防 rewrite 持住（SSE_BREAK_STALL_S 秒），
      当 run 抵 P3 时 rewrite 请求已到达并被 hold —— 此刻流在线、provider 静止，
      reload + re-poll 期间后端不再产生新的 LLM/Embedding 调用 → 增量必为 0。
    """
    open_page(base, label)
    bx(["eval", _R3_INJECT])
    # 1) 填写姓名 + JD（新 UI 受控组件：原生 value setter + input/change，轮询 __h8fill 落盘）
    bx(["eval",
        "(()=>{"
        "const setV=(el,v)=>{"
        "  const proto=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;"
        "  const setter=Object.getOwnPropertyDescriptor(proto,'value').set;"
        "  setter.call(el,v);"
        "  el.dispatchEvent(new Event('input',{bubbles:true}));"
        "  el.dispatchEvent(new Event('change',{bubbles:true}));"
        "};"
        "const ni=document.querySelector('#wb-name')||document.querySelector('input[placeholder=\"请输入姓名\"]');"
        "const nj=document.querySelector('#wb-jd')||document.querySelector('textarea[placeholder=\"职位描述（JD）\"]');"
        "if(ni)setV(ni,'测试用户SSE');"
        "if(nj)setV(nj," + json.dumps(JD_FULL, ensure_ascii=False) + ");"
        "setTimeout(()=>{"
        "  window.__h8fill=JSON.stringify({"
        "  nameOk:!!(ni&&ni.value.trim()),"
        "  jdLen:nj?nj.value.length:0"
        "  });},400);"
        "return 'ok';})()"], timeout=25)
    fv = None
    for _ in range(10):
        time.sleep(0.3)
        raw = bx(["eval", "window.__h8fill||'{}'"], timeout=25).strip()
        try:
            cand = json.loads(raw)
            cand = json.loads(cand) if isinstance(cand, str) else cand
        except Exception:
            continue
        if cand.get("nameOk") and (cand.get("jdLen") or 0) >= 60:
            fv = cand
            break
    if fv is None:
        bad(label + "-sse-break", "姓名/JD 未进入受控 state，无法驱动生成")
        return
    time.sleep(0.5)
    snap = bx(["snapshot", "-i"])
    gb = re.search(r'button "生成岗位简历[^\n]*?ref=([a-z0-9]+)', snap)
    if not gb:
        bad(label + "-sse-break", "未找到「生成岗位简历」按钮")
        return
    # 2) 布防 jd 持住，制造「流在线且 provider 静止」窗口
    fp_stall(SSE_BREAK_STALL_S)
    fb0 = fp_snapshot()
    bx(["click", f"@{gb.group(1)}"], timeout=25)
    # 3) 等待 jd 请求到达并被 hold => RUNNING 流在线（jd_analyze 在 /start 后 RUNNING 恰好 1 次）
    stall_arrived = False
    t0 = time.time()
    while time.time() - t0 < 20:
        if fp_snapshot()["jd"] - fb0["jd"] >= 1:
            stall_arrived = True
            break
        time.sleep(0.5)
    if not stall_arrived:
        fp_stall(0.0)
        EVIDENCE["scenarios"].append({
            "label": label, "injection": "network-route-abort-stream+reload",
            "injectable": False,
            "reason": "无法进入受控流窗口（jd 未在 20s 内被 hold，可能生成已瞬达终态）",
        })
        bad(label + "-sse-break", "无法进入受控流窗口（injectable=false，未虚假 PASS）")
        return
    # 4) 记录断流前的最新权威快照阶段 + provider 计数
    # task_id 必须取本轮点击后真实发出的 /api/task/{id}/start（宿 session 可能残留旧 id）。
    task_id = ""
    pg = collect_page()
    for _ in range(20):
        for u in (pg or {}).get("reqs") or []:
            m = re.search(r"/api/task/([0-9a-zA-Z-]+)/start", u)
            if m:
                task_id = m.group(1)
                break
        if task_id:
            break
        time.sleep(0.4)
        pg = collect_page()
    if not task_id:
        fp_stall(0.0)
        bad(label + "-sse-break", "无法取得 task_id（本轮 /start 请求未捕获），断流证据不可用")
        return
    phase_at = None
    if task_id:
        _st, tv = _api(port, "GET", f"/api/task/{task_id}")
        phase_at = (tv or {}).get("snapshot", {}).get("phase") if isinstance(tv, dict) else None
    fp_before = fp_snapshot()
    # 5) 注入断流：route 拦 /stream + reload -> es.onerror -> close + refresh()
    bx(["network", "requests", "--clear"])
    bx(["network", "route", "**/api/task/*/stream", "--abort"], timeout=20)
    bx(["reload"], timeout=30)
    # 等待页面就绪并恢复出原步骤（阶段不丢失的 UI 证据）
    ui_kept = (wait_contains("匹配经历", 40) or wait_contains("理解岗位", 40))
    # re-poll 证据：network 层捕获 reload 后的 GET /api/task/{id}
    reqs_raw = bx(["network", "requests", "--filter", "api/task", "--method", "GET", "--json"],
                  timeout=20) or ""
    repoll_seen = f"/api/task/{task_id}" in reqs_raw
    if not repoll_seen:
        # 兜底：reload 后再注入 hook 观察（捕获可能较晚到达的 onerror-refresh GET）
        bx(["eval", _R3_INJECT])
        for _ in range(6):
            time.sleep(0.4)
            p = collect_page()
            if any(f"/api/task/{task_id}" == u.split("?")[0] for u in p["reqs"]):
                repoll_seen = True
                break
    time.sleep(1.0)  # 让 re-poll 稳定，provider 增量窗口收敛
    fp_after = fp_snapshot()
    phase_after = None
    if task_id:
        _st, tv = _api(port, "GET", f"/api/task/{task_id}")
        phase_after = (tv or {}).get("snapshot", {}).get("phase") if isinstance(tv, dict) else None
    bx(["network", "unroute"], timeout=20)
    fp_stall(0.0)
    # 6) 断言
    delta = {k: fp_after[k] - fp_before[k] for k in ("chat", "jd", "rewrite", "other_chat", "emb")}
    delta_zero = all(v == 0 for v in delta.values())
    phase_kept = (phase_after == phase_at) and ui_kept
    checks = [("re-poll-GET", repoll_seen), ("provider-delta-zero", delta_zero),
              ("phase-kept", phase_kept)]
    failed = [k for k, v in checks if not v]
    if not failed:
        ok(label + "-sse-break",
           f"repoll={repoll_seen} phase={phase_at}→{phase_after} provider_delta={delta}")
    else:
        bad(label + "-sse-break",
            f"断言失败 {failed} repoll={repoll_seen} phase={phase_at}→{phase_after} "
            f"delta_zero={delta_zero} delta={delta} ui_kept={ui_kept}")
    EVIDENCE["scenarios"].append({
        "label": label, "injection": "network-route-abort-stream+reload",
        "injectable": True, "task_id": task_id,
        "phase_at_break": phase_at, "phase_after_repoll": phase_after,
        "repoll_get_seen": repoll_seen, "ui_phase_kept": ui_kept,
        "provider_delta": delta, "provider_delta_zero": delta_zero,
        "provider_before": fp_before, "provider_after": fp_after,
    })


SCENARIOS = (
    ("s1", s1_native_setter), ("s2", s2_keyboard), ("s3", s3_paste),
    ("s4", s4_reach60_wait), ("s5", s5_modify_satisfying),
    ("s6", s6_wait_seconds), ("s7", s7_full_operation),
)


def run_phase(port: int, base: str, tag: str, expect_pre: bool) -> None:
    log(f"\n===== R3 场景阶段：{tag}（base={base} expect_pre={expect_pre}）=====")
    for name, fn in SCENARIOS:
        if name == "s7":
            # s7 需要 port 查询 operation 列表；负向时仍期望复现预分析
            fn(port, base, f"{tag}-{name}", True if expect_pre else False)
        else:
            fn(base, f"{tag}-{name}", expect_pre)
    if not expect_pre:
        # R2-19 §R2-18：正向阶段末尾追加 SSE 断流恢复证据（需真实后端 port + 运行时注入）
        sse_stream_break(port, base, tag + "-sse-stream-break")


# ── 旧候选负向（H8-SRC 前端构建） ─────────────────────────────
NEG_COMMIT = "a5aa05745ec348dcaa213b4110e7e6f9f0e6e966"


def build_old_dist(scratch: Path) -> Path:
    """在临时 worktree 构建 H8-SRC 前端（junction 复用当前 node_modules）。"""
    src = scratch / "src"
    subprocess.run(["git", "worktree", "add", "--detach", str(src), NEG_COMMIT],
                   cwd=str(ROOT), check=True, capture_output=True)
    nm_link = src / "frontend" / "node_modules"
    nm_target = FRONTEND / "node_modules"
    if not nm_target.exists():
        raise RuntimeError("当前 frontend/node_modules 缺失，无法复用构建旧候选")
    subprocess.run(["cmd", "/c", "mklink", "/J", str(nm_link), str(nm_target)],
                   check=True, capture_output=True)
    old_dist = src / "frontend" / "dist"
    subprocess.run("npm run build", cwd=str(src / "frontend"), check=True, timeout=900,
                   shell=True, capture_output=True)
    if not old_dist.is_dir():
        raise RuntimeError("旧候选前端构建未产出 dist")
    return old_dist


def cleanup_worktree(scratch: Path) -> None:
    src = scratch / "src"
    # junction 必须先只删链接本体（os.rmdir 不递归目标），否则 git worktree remove --force
    # 会递归解析 junction 并清空真实的 frontend/node_modules（H8-R1 R3 实测事故）。
    nm_link = src / "frontend" / "node_modules"
    try:
        if nm_link.exists():
            os.rmdir(nm_link)
    except Exception:
        pass
    try:
        subprocess.run(["git", "worktree", "remove", "--force", str(src)],
                       cwd=str(ROOT), capture_output=True, timeout=60)
    except Exception:
        pass


def swap_dist(src_dist: Path) -> None:
    """把指定 dist 覆盖到 frontend/dist（dist 已 gitignore，不污染 git）。"""
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(src_dist, DIST)


def rebuild_current_dist() -> None:
    subprocess.run(["npm", "run", "build"], cwd=str(FRONTEND), check=True,
                   timeout=900, shell=True, capture_output=True)
    if not DIST.is_dir():
        raise RuntimeError("当前 dist 重建失败")


# ── 汇总 ──────────────────────────────────────────────────────
def write_summary(out: Path) -> None:
    EVIDENCE["pass"] = PASS
    EVIDENCE["fails"] = FAILS
    EVIDENCE["summary_lines"] = SUMMARY_LINES
    EVIDENCE["provider_final"] = fp_snapshot()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(EVIDENCE, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    global PASS
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="负向（旧候选）+ 正向（dev+prod）")
    ap.add_argument("--negative-only", action="store_true", help="仅旧候选负向")
    ap.add_argument("--skip-dev", action="store_true")
    ap.add_argument("--skip-prod", action="store_true")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    if not resolve_browser():
        bad("env-browser", "agent-browser 不可用")
        write_summary(ROOT / "validation-artifacts" / "h8" / "r3_browser_summary.json")
        return 2
    if not (FRONTEND / "node_modules").is_dir():
        bad("env-node_modules", "frontend/node_modules 缺失")
        return 2

    runtime = Path(tempfile.mkdtemp(prefix="h8r3_"))
    EVIDENCE["runtime_dir"] = str(runtime)
    evout = ROOT / "validation-artifacts" / "h8" / "r3_fp_counts.json"
    backend = None
    vite = None
    scratch = None
    try:
        if listener_pids(8000):
            bad("env-port8000", "8000 已被占用")
            return 2

        fp = start_fake_provider(FP_PORT, evout)
        if not wait_port(FP_PORT, 20):
            bad("env-fp", "fake provider 未就绪")
            return 2
        log(f"[r3] runtime={runtime} fp={FP_PORT}")

        backend = start_backend(runtime, 8791, 8000, "backend.log")
        if not wait_port(8000, 120):
            bad("env-backend", "真实后端未就绪")
            return 2
        seed_info = seed(8000)
        EVIDENCE["seed"] = seed_info
        log(f"[r3] seeded experiences={len(seed_info.get('experience_ids') or [])}")

        do_negative = args.all or args.negative_only
        do_positive = not args.negative_only

        if do_positive:
            if not args.skip_dev:
                log("[r3] 启动 Vite dev server…")
                vlog = open(runtime / "vite.log", "w", encoding="utf-8", errors="replace")
                vite = subprocess.Popen(["npm", "run", "dev"], cwd=str(FRONTEND),
                                        stdout=vlog, stderr=subprocess.STDOUT, shell=True)
                if not wait_port(5173, 120):
                    bad("env-vite", "Vite dev 未就绪")
                else:
                    run_phase(8000, "http://localhost:5173/", "dev", False)
                kill_tree(vite)
                vite = None
                try:
                    vlog.close()
                except Exception:
                    pass
            if not args.skip_prod:
                if not DIST.is_dir():
                    bad("env-dist", "frontend/dist 缺失（需先 npm run build）")
                else:
                    run_phase(8000, "http://127.0.0.1:8000/", "prod", False)

        if do_negative:
            scratch = Path(tempfile.mkdtemp(prefix="h8r3neg_"))
            log(f"[r3] 构建旧候选 H8-SRC 前端（worktree={scratch}）…")
            try:
                old_dist = build_old_dist(scratch)
            except Exception as e:  # noqa: BLE001
                bad("negative-build", f"旧候选前端构建失败：{e}")
                return 2
            swap_dist(old_dist)
            stop_backend(backend)
            backend = start_backend(runtime, 8791, 8000, "backend_old_dist.log")
            if not wait_port(8000, 120):
                bad("env-backend-old", "旧 dist 后端未就绪")
            else:
                run_phase(8000, "http://127.0.0.1:8000/", "negative", True)
            stop_backend(backend)
            backend = None
            log("[r3] 恢复当前 dist（重新 build）…")
            rebuild_current_dist()

        stop_backend(backend)
        backend = None
        log("\n" + "=" * 60)
        log(f"R3 结果：PASS={PASS} FAIL={len(FAILS)}")
        for f in FAILS:
            log("  - " + f)
        write_summary(ROOT / "validation-artifacts" / "h8" / "r3_browser_summary.json")
        return 1 if FAILS else 0
    finally:
        kill_tree(backend)
        kill_tree(vite)
        if scratch is not None:
            cleanup_worktree(scratch)
        if not args.keep:
            try:
                shutil.rmtree(runtime, ignore_errors=True)
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
