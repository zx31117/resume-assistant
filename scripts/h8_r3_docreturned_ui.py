#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 DOC_RETURNED 返工 · 离线 UI 正反向门（无真实模型、无外网外呼）。

目的（对应本轮返工目标 1/2/3/4 的机器证据）：
  [U1] 工作台顶栏路由感知：`/` 上 running→取消 / 其他→「＋ 开始新任务」；
       非工作台同壳路由 → 「← 返回工作台」，且不出现「开始新任务」。
  [U2] P4/success 简历预览交互：fact / 整段(work|project) / skills 三类真实可点目标，
       真实 mouse / Enter / Space，selected + aria-pressed 反馈，右侧详情随选择变化，
       再次点击取消；两类互斥。
  [U3] 几何：热点矩形在各冻结 viewport 与滚动后仍落在真实渲染页内，且与页面等比缩放。
  [U4] 反向（诚实退出）：anchors 为空 / artifact 错配 → 不渲染任何热点（无幽灵热区），
       PDF 查看与 Word/PDF 双下载仍可用。
  [U5] 非工作台路由返回：点/Enter/Space 返回工作台，同一 Task（id/status/input revision/
       发布 revision/快照字节）不变；反向证明：无 startNewTask、无新 Task、无模型请求。
  [U6] 事件单飞：同一毫秒内重复激活（Enter+Enter / 双击）只产生一次导航。
  [U7] 单 fact：provider 只产出一条事实时恰好一个事实热区，且仍可点/可取消。

隔离与成本边界：
  - 真实后端（源码 uvicorn）+ 本地 fake Provider（仅本脚本内，替换 ARK_BASE_URL）；
  - 独立 RESUME_DATA_DIR（系统临时目录），运行结束删除；
  - 全脱敏 fixture，无 Key、无外呼、不读取/修改 Product Owner runtime；
  - 不运行六格、不调用真实模型主链（本门即离线替代）。

用法：python scripts/h8_r3_docreturned_ui.py [--keep] [--skip-u7]
退出码：0=全部通过；1=存在 FAIL；2=环境/前置失败。
"""
from __future__ import annotations

import argparse
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

APP_PORT = 8013
FP_PORT = 8795
JD = ("高级后端研发工程师（Java）：负责电商平台交易链路设计、编码与线上稳定性，主导订单支付库存"
      "模块演进与高并发优化。要求 5 年+ Java、Spring Boot、MySQL、Redis，有分布式/消息队列实践"
      "优先，base 杭州，可尽快到岗。")
NAME = "离线门用户"

# 脱敏 fixture（与仓库既有离线资产同源，全虚构）
EXPERIENCES = [
    {"type": "work", "title": "后端研发工程师", "company": "示例科技有限公司",
     "time": "2022.03-2025.06", "role": "后端研发工程师",
     "description": "负责示例电商平台订单域的后端研发与稳定性建设。",
     "achievements": ["主导订单创建链路重构，将核心接口 P99 从 820ms 降到 210ms",
                      "搭建库存扣减幂等与对账机制，超卖事故从月均 3 起降为 0"],
     "skills": ["Java", "Spring Boot", "MySQL", "Redis", "Kafka"],
     "raw_text": "示例科技有限公司 后端研发工程师 2022.03-2025.06"},
    {"type": "work", "title": "初级后端工程师", "company": "虚构网络股份有限公司",
     "time": "2020.07-2022.02", "role": "初级后端工程师",
     "description": "负责示例社区服务的接口开发与数据维护。",
     "achievements": ["完成用户中心服务拆分，接口平均延迟下降 35%",
                      "推动单元测试覆盖率从 42% 提升到 78%"],
     "skills": ["Java", "MySQL", "MyBatis"],
     "raw_text": "虚构网络股份有限公司 初级后端工程师 2020.07-2022.02"},
    {"type": "project", "title": "订单对账系统", "company": "示例科技有限公司",
     "time": "2024.05-2024.11", "role": "负责人",
     "description": "面向示例业务的订单对账与差异定位系统。",
     "achievements": ["设计差异定位算法，对账工单平均处理时长从 45 分钟降到 8 分钟",
                      "实现对账任务调度，日处理账单量 200 万条"],
     "skills": ["Java", "Kafka", "MySQL"],
     "raw_text": "订单对账系统 负责人 2024.05-2024.11"},
    {"type": "education", "title": "计算机科学与技术", "company": "示例大学",
     "time": "2016.09-2020.06", "role": "",
     "description": "计算机科学与技术 本科",
     "achievements": [], "skills": [],
     "raw_text": "示例大学 计算机科学与技术 本科 2016.09-2020.06"},
]

# 冻结 viewport（与 DS-003 设计对照一致）
VIEWPORTS = [(1920, 1080), (1686, 1076), (1440, 900), (1280, 800)]

PASS = 0
FAILS: list[str] = []
DUMP_LAYOUT = False
EVIDENCE: dict = {"assertions": [], "provider": {}, "browser": {}}


def log(m: str = "") -> None:
    print(m, flush=True)


def ok(label: str, extra: str = "") -> None:
    global PASS
    PASS += 1
    log(f"[PASS] {label}" + (f" | {extra}" if extra else ""))
    EVIDENCE["assertions"].append({"label": label, "ok": True, "extra": extra})


def bad(label: str, why: str) -> None:
    FAILS.append(label)
    log(f"[FAIL] {label} | {why}")
    EVIDENCE["assertions"].append({"label": label, "ok": False, "why": why})


# ══════════════════════════ fake Provider（V2.2.0 任务管线形状）══════════════════════════
FP_LOCK = threading.Lock()
FP_STATE = {"jd": 0, "fact": 0, "reason": 0, "other": 0, "emb": 0, "chat": 0}
FP_MODE = {"mode": "normal", "stall_s": 0.0, "stall_kind": "jd"}

_FACT_RX = re.compile(r'"fact_id"\s*:\s*"([^"]+)"')
_EXP_RX = re.compile(r'"experience_id"\s*:\s*"([^"]+)"')
_REASON_ID_RX = re.compile(r'"fact_id"\s*:\s*"([^"]+)"')
# facts_json 形如 [{"fact_id": "...", "text": "..."}]，每次调用恰好下发一条源事实。
_FACTS_JSON_RX = re.compile(r'\[\s*\{\s*"fact_id".*?\}\s*\]', re.S)

_JD_FIXTURE = {
    "position": "高级后端研发工程师", "industry": "互联网",
    "required_skills": ["Java", "MySQL", "Redis"],
    "preferred_skills": ["Kafka", "Spring Boot"],
    "responsibilities": ["负责电商平台交易链路设计与线上稳定性"],
    "keywords": ["高并发", "分布式"], "experience_preferences": ["5 年+"],
}


def _fp_snapshot() -> dict:
    with FP_LOCK:
        return dict(FP_STATE)


def _classify(body: bytes) -> str:
    try:
        j = json.loads(body.decode("utf-8", "replace"))
    except Exception:
        return "other"
    txt = json.dumps(j, ensure_ascii=False)
    if "资深招聘分析师" in txt:
        return "jd"
    if "资深简历内容专家" in txt:
        return "fact"
    if "资深简历顾问" in txt:
        return "reason"
    return "other"


def _user_text(body: bytes) -> str:
    try:
        j = json.loads(body.decode("utf-8", "replace"))
    except Exception:
        return ""
    return "\n".join(str(m.get("content") or "") for m in (j.get("messages") or []))


def _fact_content(body: bytes) -> dict:
    mode = FP_MODE.get("mode") or "normal"
    txt = _user_text(body)
    eid_m = _EXP_RX.search(txt)
    fid_m = _FACT_RX.search(txt)
    eid = eid_m.group(1) if eid_m else ""
    fid = fid_m.group(1) if fid_m else ""
    if mode == "single_fact":
        # 仅第一条源事实产出条目：其余视为材料不足（空 headline/body → 不进入成品行）
        with FP_LOCK:
            first = FP_STATE.get("_first_fact")
            if first is None:
                FP_STATE["_first_fact"] = fid
                first = fid
        if fid != first:
            return {"experience_id": eid, "fact_id": "", "headline": "", "body": "",
                    "fact_refs": [], "ok": False, "insufficient_reason": "离线门：单事实模式"}
    # 逐条条目必须互不相同：真实模型每次只针对一条源事实生成条目，若离线 fixture 复用同一段
    # headline/body，成品 PDF 里会出现多条完全相同的正文行，anchor 生成侧按「首个出现位置」
    # 定位就会把全部事实塌缩到同一坐标（本次返工暴露的正是这一情形）。
    # 因此这里从本次下发的源事实 text 派生 headline，并带上 fact_id 尾号保证逐条唯一。
    src_text = ""
    m = _FACTS_JSON_RX.search(txt)
    if m:
        try:
            src_text = str((json.loads(m.group(0))[0] or {}).get("text") or "").strip()
        except Exception:
            src_text = ""
    head = (src_text.split("，")[0] if src_text else "")[:14] or "岗位能力建设"
    tag = fid.split("-")[0][:4] if fid else ""
    if tag:
        head = head + tag
    return {
        "experience_id": eid,
        "fact_id": "",
        "headline": head,
        # 正文保持与 JD 技能同名（Java/MySQL）→ 保证技能区有 Fact 依据（build_skill_groups
        # 按「技能名出现在已生成事实文本里」判定），否则 skills 整段锚点会诚实缺席。
        "body": "使用 Java 与 MySQL 重构订单链路并落地对账机制，核心接口与工单处理耗时显著下降。",
        "fact_refs": [fid] if fid else [],
        "ok": True, "insufficient_reason": "",
    }


def _reason_content(body: bytes) -> dict:
    txt = _user_text(body)
    m = re.search(r'fact_id=([^\s\n\r）]+)', txt) or _REASON_ID_RX.search(txt)
    return {"fact_id": (m.group(1).strip() if m else ""),
            "delta": "该条与目标岗位的 Java / MySQL 要求直接对应。", "done": True}


def _chat_body(content: dict) -> dict:
    return {
        "id": "chatcmpl-docreturned", "object": "chat.completion", "created": 0, "model": "offline",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant",
                                 "content": json.dumps(content, ensure_ascii=False)}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


class FPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        return

    def _send(self, obj, status: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_GET(self):
        if self.path.startswith("/__count"):
            self._send(_fp_snapshot())
        else:
            self._send({"error": "unknown"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        body = self._body()
        if path.endswith("/__ctl"):
            try:
                ctrl = json.loads(body.decode("utf-8", "replace"))
            except Exception:
                ctrl = {}
            with FP_LOCK:
                if "mode" in ctrl:
                    FP_MODE["mode"] = str(ctrl["mode"])
                    FP_STATE.pop("_first_fact", None)
                if ctrl.get("reset_first"):
                    FP_STATE.pop("_first_fact", None)
                FP_MODE["stall_s"] = float(ctrl.get("stall_s") or 0)
                FP_MODE["stall_kind"] = str(ctrl.get("stall_kind") or "jd")
            self._send({"ok": True, "mode": FP_MODE.get("mode")})
            return
        if path.endswith("/chat/completions"):
            kind = _classify(body)
            with FP_LOCK:
                FP_STATE["chat"] += 1
                FP_STATE[kind] = FP_STATE.get(kind, 0) + 1
                delay = 0.0
                if kind == FP_MODE.get("stall_kind"):
                    delay = float(FP_MODE.get("stall_s") or 0)
                    FP_MODE["stall_s"] = 0.0
            if delay > 0:
                time.sleep(delay)
            if kind == "jd":
                self._send(_chat_body(dict(_JD_FIXTURE)))
            elif kind == "fact":
                self._send(_chat_body(_fact_content(body)))
            elif kind == "reason":
                self._send(_chat_body(_reason_content(body)))
            else:
                self._send(_chat_body({"experiences": []}))
            return
        if path.endswith("/embeddings/multimodal") or path.endswith("/embeddings"):
            with FP_LOCK:
                FP_STATE["emb"] += 1
            self._send({"data": {"embedding": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]}})
            return
        self._send({"error": f"unknown path {path}"}, 404)


def start_fp(port: int) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), FPHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log(f"[fp] fake provider 127.0.0.1:{port}")
    return srv


def fp_ctl(**kw) -> None:
    req = urllib.request.Request(
        f"http://127.0.0.1:{FP_PORT}/__ctl",
        data=json.dumps(kw).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        r.read()


def fp_counts() -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:{FP_PORT}/__count", timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


# ══════════════════════════ 后端（源码 uvicorn）══════════════════════════
def wait_port(port: int, timeout: float = 120.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        with socket.socket() as s:
            s.settimeout(1.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.5)
    return False


def port_in_use(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_backend(runtime: Path, fp_port: int, port: int) -> subprocess.Popen:
    env = dict(os.environ)
    env["RESUME_DATA_DIR"] = str(runtime)
    env["ARK_BASE_URL"] = f"http://127.0.0.1:{fp_port}/v1"
    env["ARK_API_KEY"] = "offline-gate-key"
    env["APP_HOST"] = "127.0.0.1"
    env["APP_PORT"] = str(port)
    env.pop("ARK_EMBEDDING_API_KEY", None)
    fh = open(runtime / "backend.log", "w", encoding="utf-8", errors="replace")
    p = subprocess.Popen(
        [PY, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port),
         "--log-level", "warning"],
        cwd=str(BACKEND), env=env, stdout=fh, stderr=subprocess.STDOUT)
    p._log_fh = fh  # type: ignore[attr-defined]
    return p


def kill_tree(p) -> None:
    if p is None:
        return
    try:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=15)
            except Exception:
                p.kill()
    except Exception:
        pass
    try:
        p._log_fh.close()  # type: ignore[attr-defined]
    except Exception:
        pass


_OPENER = None


def _api(method: str, path: str, payload=None, timeout: int = 300, port: int = APP_PORT):
    """带启动会话 Cookie 的 API 调用（写操作需进程级 ra_session cookie）。"""
    global _OPENER
    if _OPENER is None:
        import http.cookiejar
        cj = http.cookiejar.CookieJar()
        _OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def seed(port: int = APP_PORT) -> dict:
    _api("GET", "/api/system/status")
    st, mig = _api("POST", "/api/system/migrate", timeout=240)
    if st != 200:
        raise RuntimeError(f"migrate failed: {st} {mig}")
    ids = []
    for e in EXPERIENCES:
        st, body = _api("POST", "/api/experience/", e, timeout=120)
        if st != 200:
            raise RuntimeError(f"import failed: {st} {body}")
        ids.append(body.get("id"))
    st, rb = _api("POST", "/api/system/rebuild", timeout=600)
    if st != 200:
        raise RuntimeError(f"rebuild failed: {st} {rb}")
    return {"experience_ids": ids}


# ══════════════════════════ 浏览器 ══════════════════════════
BROWSER_SESSION = f"docret-{os.getpid()}-{int(time.time())}"


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
    env = dict(os.environ)
    env["AGENT_BROWSER_SESSION"] = BROWSER_SESSION
    if INJECT_PATH is not None and INJECT_PATH.exists():
        env["AGENT_BROWSER_INIT_SCRIPTS"] = str(INJECT_PATH)
    try:
        p = subprocess.Popen([exe, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=env, cwd=str(ROOT))
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


def parse_res(res: str):
    for _ in range(4):
        if not isinstance(res, str):
            return res
        try:
            res = json.loads(res)
        except Exception:
            return res
    return res


def ev(js: str):
    return parse_res(bx(["eval", js], timeout=40))


def js_eval(js: str):
    """eval 一个 JSON 字符串表达式并解析（失败返回 None）。"""
    raw = bx(["eval", js], timeout=40)
    return parse_res(raw)


def dom(js_expr: str):
    """执行返回 JSON.stringify(...) 的 JS，解析为 Python 对象。"""
    r = bx(["eval", js_expr], timeout=40)
    v = parse_res(r)
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return None
    return v


def ev_str(js_expr: str) -> str | None:
    """执行返回标量的 JS，稳健取出字符串值（容忍 CLI 的 ✓/✗ 行与引号包裹）。"""
    raw = bx(["eval", js_expr], timeout=40)
    if not raw:
        return None
    lines = [l.strip() for l in raw.splitlines()
             if l.strip() and not l.strip().startswith(("✓", "✗"))]
    if not lines:
        return None
    cand = lines[-1]
    if len(cand) >= 2 and cand[0] == '"' and cand[-1] == '"':
        try:
            return json.loads(cand)
        except Exception:
            return cand[1:-1]
    return cand


def ev_json(js_expr: str):
    """eval 一个返回 `JSON.stringify(...)` 的表达式并解析（字符串/数字/布尔/null 都安全）。

    `dom()` 会对已是纯字符串的结果再做一次 json.loads，导致 `"empty"` 这类值被吞成 None；
    标量与字符串一律走这里。
    """
    raw = bx(["eval", js_expr], timeout=40)
    v = parse_res(raw)
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


def click_at(x: float, y: float) -> str:
    """在视口坐标处执行一次真实鼠标按下/抬起（用于验证不存在幽灵热区）。"""
    bx(["mouse", "move", str(int(x)), str(int(y))], timeout=20)
    down = bx(["mouse", "down"], timeout=20)
    up = bx(["mouse", "up"], timeout=20)
    return f"{down}|{up}"


def elem_at(x: float, y: float) -> str:
    """该视口坐标处最上层元素是否落在 PDF 热点内（用于幽灵热区反向证明）。"""
    v = ev_str(
        f"(function(){{var e=document.elementFromPoint({int(x)},{int(y)});"
        f"if(!e)return 'none';var h=e.closest?e.closest('[data-fact],[data-section]'):null;"
        f"return h?('hotspot:'+(h.getAttribute('data-fact')||h.getAttribute('data-section'))):"
        f"(e.tagName+'.'+(e.className||''));}})()")
    return v or "unknown"


# 浏览器侧注入（以 agent-browser init script 形式在每次新文档开始时执行，
# 因此 `open` 整页重载后依然生效；锚点改写模式经 sessionStorage 跨文档传递）。
# 记录：真实请求序列 / 页面错误 / POST 建任务与 generate 次数 / pushState 次数 /
# 权威 task 快照原文 / 当前 task_id；可改写 pdf_anchors 以模拟 artifact 缺失或错配。
_INJECT = r"""
(function(){
  var mode = null;
  try { mode = sessionStorage.getItem('__p4_anchorMode') || null; } catch(e) {}
  window.__p4 = {reqs:[],errs:[],creates:0,generates:0,push:0,
                 anchorMode:mode,lastTaskJson:null,lastTaskLen:0,lastTaskHash:null,taskId:null};
  // 权威快照指纹在浏览器内计算（FNV-1a + DJB2 + 长度），避免把整段 JSON 经 CLI 传输/截断。
  function _p4hash(s){
    var a=2166136261,b=5381;
    for(var i=0;i<s.length;i++){
      var c=s.charCodeAt(i);
      a^=c; a=Math.imul(a,16777619);
      b=((b<<5)+b+c)|0;
    }
    return ((a>>>0).toString(16))+'-'+(((b>>>0)).toString(16));
  }
  window.__p4.fingerprint = function(txt){ return _p4hash(txt)+':'+txt.length; };
  window.__p4SetAnchorMode = function(m){
    window.__p4.anchorMode = m || null;
    try { m ? sessionStorage.setItem('__p4_anchorMode', String(m))
            : sessionStorage.removeItem('__p4_anchorMode'); } catch(e) {}
    return window.__p4.anchorMode;
  };
  window.addEventListener('error',function(e){try{window.__p4.errs.push('uncaught:'+e.message)}catch(_){}});
  window.addEventListener('unhandledrejection',function(e){try{window.__p4.errs.push('rej:'+String(e.reason))}catch(_){}});
  var _ce = console.error;
  console.error = function(){try{window.__p4.errs.push([].map.call(arguments,String).join(' '))}catch(_){} return _ce.apply(console,arguments)};
  var _of = window.fetch;
  window.fetch = function(){
    var a = arguments, url = String(a[0]);
    var method = (a[1] && a[1].method ? a[1].method : 'GET').toUpperCase();
    try{
      window.__p4.reqs.push(method+' '+url);
      if(/\/api\/task(\?|$)/.test(url) && method==='POST') window.__p4.creates++;
      if(/\/api\/task\/[^/]+\/generate/.test(url)) window.__p4.generates++;
    }catch(_){}
    return _of.apply(window, a).then(function(res){
      try{
        var m = url.match(/\/api\/task\/([0-9a-fA-F-]{36})(\?|$)/);
        if(m && method === 'GET'){
          window.__p4.taskId = m[1];
          if(window.__p4.anchorMode){
            return res.clone().text().then(function(txt){
              var j = JSON.parse(txt);
              var p = (j.snapshot && j.snapshot.payload) || {};
              var arts = p.artifacts || {};
              if(Array.isArray(arts.pdf_anchors)){
                if(window.__p4.anchorMode === 'empty'){ arts.pdf_anchors = []; }
                if(window.__p4.anchorMode === 'mismatch'){
                  arts.pdf_anchors = arts.pdf_anchors.map(function(x){
                    return Object.assign({}, x, {artifact_id:'artifact_OTHER'}); });
                }
              }
              var out = JSON.stringify(j);
              window.__p4.lastTaskJson = out;
              window.__p4.lastTaskLen = out.length;
              window.__p4.lastTaskHash = window.__p4.fingerprint(out);
              return new Response(out, {status: res.status, headers: res.headers});
            });
          }
          return res.clone().text().then(function(txt){
            window.__p4.lastTaskJson = txt;
            window.__p4.lastTaskLen = txt.length;
            window.__p4.lastTaskHash = window.__p4.fingerprint(txt);
            return res; });
        }
      }catch(_){}
      return res;
    });
  };
  var _ps = history.pushState;
  history.pushState = function(){ try{window.__p4.push++}catch(_){} return _ps.apply(this, arguments); };
})();
"""

INJECT_PATH: Path | None = None


def install_init_script(runtime: Path) -> None:
    """把注入脚本落盘，并通过 AGENT_BROWSER_INIT_SCRIPTS 在每次新文档注入。"""
    global INJECT_PATH
    INJECT_PATH = runtime / "_p4_inject.js"
    INJECT_PATH.write_text(_INJECT, encoding="utf-8")
    log(f"[inject] init script = {INJECT_PATH}")


def install_inject() -> None:
    """（幂等）确保当前文档已注入；init script 已在文档开始时执行，这里只校验。"""
    v = dom("window.__p4?1:0")
    if v != 1:
        bx(["eval", _INJECT + ";'ok'"], timeout=30)


def open_page(url: str) -> bool:
    bx(["open", url], timeout=20)
    t0 = time.time()
    while time.time() - t0 < 45:
        snap = bx(["snapshot", "-i"], timeout=30)
        if "粘贴完整岗位描述" in snap or "wb-topbar" in snap or "我的" in snap:
            return True
        time.sleep(0.8)
    return False


def errors() -> list:
    v = dom("JSON.stringify((window.__p4&&window.__p4.errs)||[])")
    return v if isinstance(v, list) else []


def hotspot_layout() -> dict:
    """每页 canvas/page 几何 + 每个热点的种类/身份/矩形/选中态（浏览器真实布局）。"""
    v = dom(
        "JSON.stringify([].map.call(document.querySelectorAll('.pdf-page'),function(pg){"
        "  var pr=pg.getBoundingClientRect(); var cv=pg.querySelector('canvas');"
        "  var cr=cv?cv.getBoundingClientRect():null;"
        "  return {page:{l:pr.left,t:pr.top,w:pr.width,h:pr.height},"
        "          canvas:cr?{l:cr.left,t:cr.top,w:cr.width,h:cr.height}:null,"
        "          hits:[].map.call(pg.querySelectorAll('.pdf-hit'),function(b){"
        "            var r=b.getBoundingClientRect();"
        "            return {kind:b.getAttribute('data-anchor-kind'),"
        "                    id:b.getAttribute('data-fact')||b.getAttribute('data-section')||'',"
        "                    cls:b.className,"
        "                    pressed:b.getAttribute('aria-pressed'),"
        "                    label:b.getAttribute('aria-label')||'',"
        "                    l:r.left,t:r.top,w:r.width,h:r.height};})};}))")
    return v if isinstance(v, dict) else {"pages": []}


def layout_of() -> list:
    v = dom(
        "JSON.stringify([].map.call(document.querySelectorAll('.pdf-page'),function(pg){"
        "  var pr=pg.getBoundingClientRect(); var cv=pg.querySelector('canvas');"
        "  var cr=cv?cv.getBoundingClientRect():null;"
        "  var hits=[].map.call(pg.querySelectorAll('.pdf-hit'),function(b){"
        "    var r=b.getBoundingClientRect();"
        "    return {kind:b.getAttribute('data-anchor-kind'),"
        "            id:b.getAttribute('data-fact')||b.getAttribute('data-section')||'',"
        "            cls:b.className,pressed:b.getAttribute('aria-pressed'),"
        "            label:b.getAttribute('aria-label')||'',"
        "            l:r.left,t:r.top,w:r.width,h:r.height};});"
        "  return {canvas:cr?{l:cr.left,t:cr.top,w:cr.width,h:cr.height}:null,hits:hits};}))")
    return v if isinstance(v, list) else []


def aside_state() -> dict:
    v = dom(
        "JSON.stringify({title:(document.querySelector('.wb-panel--aside .wb-panel__head-title')||{}).textContent||'',"
        "badge:(document.querySelector('.wb-panel--aside .wb-panel__head-sub')||{}).textContent||'',"
        "factTitle:(document.querySelector('.wb-panel--aside .detail-stream h3')||{}).textContent||'',"
        "factHost:(document.querySelector('.wb-panel--aside .detail-stream p')||{}).textContent||'',"
        "reason:(document.querySelector('.wb-panel--aside .reason-box span')||{}).textContent||'',"
        "source:(document.querySelector('.wb-panel--aside .source-box blockquote')||{}).textContent||'',"
        "secTitle:(document.querySelector('.wb-panel--aside .section-detail h3')||{}).textContent||'',"
        "secHelp:(document.querySelector('.wb-panel--aside .section-detail .field-help')||{}).textContent||'',"
        "skillRows:document.querySelectorAll('.wb-panel--aside .section-detail-row').length,"
        "secFacts:document.querySelectorAll('.wb-panel--aside .section-fact').length,"
        "intro:(document.querySelector('.wb-panel--aside .wb-aside-desc')||{}).textContent||'',"
        "dl:[].map.call(document.querySelectorAll('[data-role^=download-]'),function(a){return a.getAttribute('data-role')}),"
        "pdfState:(document.querySelector('.pdf-preview')||{}).getAttribute?document.querySelector('.pdf-preview').getAttribute('data-state'):null,"
        "hotTotal:document.querySelectorAll('.pdf-hit').length,"
        "ghost:document.querySelectorAll('[data-fact],[data-section]').length,"
        "factHot:document.querySelectorAll('.pdf-fact-hotspot').length,"
        "secHot:document.querySelectorAll('.pdf-section-hotspot').length})")
    return v if isinstance(v, dict) else {}


def topbar_state() -> dict:
    v = dom(
        "JSON.stringify({path:location.pathname,"
        "newTask:[].some.call(document.querySelectorAll('[data-action=new-task]'),function(b){return true}),"
        "newTaskText:(document.querySelector('[data-action=new-task]')||{}).textContent||'',"
        "cancel:[].some.call(document.querySelectorAll('[data-action=cancel]'),function(b){return true}),"
        "cancelText:(document.querySelector('[data-action=cancel]')||{}).textContent||'',"
        "back:[].some.call(document.querySelectorAll('[data-role=top-back]'),function(b){return true}),"
        "backText:(document.querySelector('[data-role=top-back]')||{}).textContent||'',"
        "statusText:(document.querySelector('.wb-top-status')||{}).textContent||'',"
        "anyStartNew:(document.body.innerText||'').indexOf('开始新任务')>=0})")
    return v if isinstance(v, dict) else {}


def nav(url_path: str) -> None:
    bx(["open", f"http://127.0.0.1:{APP_PORT}{url_path}"], timeout=20)
    time.sleep(2.0)


def click_sel(sel: str) -> str:
    """真实鼠标点击：先滚动到可见，再点击；返回 CLI 原始输出（失败诊断用）。"""
    bx(["scrollintoview", sel], timeout=25)
    time.sleep(0.35)
    return bx(["click", sel], timeout=30)


LAST_CLICK: dict = {"sel": "", "out": "", "top": "", "pt": None, "kind": ""}


def click_ok(sel: str) -> bool:
    """真实鼠标点击是否成功（✗/空输出视为未执行）。用于顶栏按钮等常规元素。"""
    out = click_sel(sel)
    LAST_CLICK.update({"sel": sel, "out": out, "top": "", "pt": None, "kind": "selector"})
    return bool(out) and not out.lstrip().startswith("✗")


def hit_probe(sel: str) -> dict:
    """PDF 热点的「可视点击点」+ 诊断。

    合法点须同时满足：在热点矩形内、在预览滚动可视区内、且**该点最上层元素正是该热点**。
    返回 {found, pt, rect, clamped, scroll, cls, tops}；pt 为 null → 热点不可点（遮挡/越界）。

    关键：`pt` 必须是**将要真正点击的整数像素**（`click_at`/`elem_at` 用 `int()` 截断）。
    若此处用浮点矩心探测、点击侧再截断，两者可能相差 1px；section 这类被 fact 覆盖大部分
    宽度的整段热点只剩几像素可点带，1px 偏移就会点到上层 fact 上（本轮 R3-24 实测根因）。
    故候选点一律先 `Math.trunc` 成整数再探测，并直接以该整数点为 `pt`。
    此外探测与点击之间还隔着 CLI 往返（版面可能抖动 1–2px），故优先选「与其它热点边界
    保持 ≥4px 净空」的点，取不到才退回第一个合法点。
    """
    js = (
        "(function(){var el=document.querySelector(" + json.dumps(sel) + ");"
        "if(!el)return JSON.stringify({found:false});"
        "el.scrollIntoView({block:'center'});"
        "var r=el.getBoundingClientRect();"
        "var sc=document.querySelector('.pdf-preview__pages');"
        "var sr=sc?sc.getBoundingClientRect():null;"
        "var x0=Math.max(r.left,sr?sr.left:0,0),y0=Math.max(r.top,sr?sr.top:0,0);"
        "var x1=Math.min(r.right,sr?sr.right:window.innerWidth,window.innerWidth),"
        "    y1=Math.min(r.bottom,sr?sr.bottom:window.innerHeight,window.innerHeight);"
        "var c=[[(x0+x1)/2,(y0+y1)/2],[x0+3,(y0+y1)/2],[x1-3,(y0+y1)/2],"
        "[(x0+x1)/2,y0+3],[(x0+x1)/2,y1-3]];"
        "var others=[].filter.call(document.querySelectorAll('.pdf-hit'),function(o){return o!==el;});"
        "function clr(x,y){var m=1e9;for(var j=0;j<others.length;j++){"
        "var b=others[j].getBoundingClientRect();"
        "if(x>=b.left&&x<=b.right&&y>=b.top&&y<=b.bottom)return -1;"
        "var dx=Math.max(b.left-x,0,x-b.right),dy=Math.max(b.top-y,0,y-b.bottom);"
        "var d=dx>dy?dx:dy;if(d<m)m=d;}return m;}"
        "var pts=[],pt=null,fb=null;"
        "for(var i=0;i<c.length;i++){"
        "var cx=Math.trunc(c[i][0]),cy=Math.trunc(c[i][1]);"
        "var e=document.elementFromPoint(cx,cy);"
        "pts.push({x:cx,y:cy,clr:clr(cx,cy),"
        "tag:e?e.tagName:null,cls:e?(typeof e.className==='string'?e.className:null):null,"
        "df:e&&e.getAttribute?e.getAttribute('data-fact'):null,"
        "ds:e&&e.getAttribute?e.getAttribute('data-section'):null,"
        "same:!!e&&e===el,sameNode:!!e&&el.isSameNode(e),"
        "pe:e?getComputedStyle(e).pointerEvents:null,"
        "outer:e?String(e.outerHTML).slice(0,200):null});"
        "if(e===el){if(fb===null)fb=[cx,cy];if(clr(cx,cy)>=4&&pt===null)pt=[cx,cy];}}"
        "if(pt===null)pt=fb;"
        "return JSON.stringify({found:true,pt:pt,"
        "count:document.querySelectorAll(" + json.dumps(sel) + ").length,"
        "elIdx:[].indexOf.call(document.querySelectorAll(" + json.dumps(sel) + "),el),"
        "allFacts:document.querySelectorAll('[data-fact]').length,"
        "allSecs:document.querySelectorAll('[data-section]').length,"
        "elOuter:String(el.outerHTML).slice(0,200),"
        "elPE:getComputedStyle(el).pointerEvents,elZ:getComputedStyle(el).zIndex,"
        "parentCls:el.parentElement?String(el.parentElement.className):null,"
        "rect:[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)],"
        "clamped:[Math.round(x0),Math.round(y0),Math.round(x1),Math.round(y1)],"
        "viewport:[window.innerWidth,window.innerHeight],"
        "scroll:sr?[Math.round(sr.left),Math.round(sr.top),Math.round(sr.width),Math.round(sr.height)]:null,"
        "cls:String(el.className),pts:pts});})()")
    v = ev_json(js)
    return v if isinstance(v, dict) else {"found": False}


def click_hit(sel: str) -> dict:
    """对 PDF 热点执行**真实鼠标**点击（视口坐标 mouse move/down/up），并记录该点最上层元素。

    agent-browser 的 `click <selector>` 在本产品 PDF 命中层上会静默空转（无输出、无状态变化），
    而 `mouse move/down/up` 等价于真人操作（空白处点击清空选择即由此验证）。
    """
    pr = hit_probe(sel)
    pt = pr.get("pt")
    if not pt:
        LAST_CLICK.update({"sel": sel, "out": "", "top": "no-point", "pt": None,
                           "kind": "hit", "probe": pr})
        return {"ok": False, "pt": None, "top": "no-point", "probe": pr}
    top = elem_at(*pt)
    out = click_at(*pt)
    LAST_CLICK.update({"sel": sel, "out": out, "top": top, "pt": (pt[0], pt[1]),
                       "kind": "hit", "probe": pr})
    return {"ok": True, "pt": (pt[0], pt[1]), "top": top, "out": out, "probe": pr}


def fill_and_generate(expect_running: bool = False) -> dict:
    """填姓名/JD（React 原生 setter 语义）→ 点击生成 → 返回观测。"""
    js = ("(()=>{const setV=(el,v)=>{const proto=el.tagName==='TEXTAREA'?"
          "HTMLTextAreaElement.prototype:HTMLInputElement.prototype;"
          "Object.getOwnPropertyDescriptor(proto,'value').set.call(el,v);"
          "el.dispatchEvent(new Event('input',{bubbles:true}));"
          "el.dispatchEvent(new Event('change',{bubbles:true}));};"
          "const ni=document.querySelector('#wb-name');const nj=document.querySelector('#wb-jd');"
          "if(ni)setV(ni," + json.dumps(NAME, ensure_ascii=False) + ");"
          "if(nj)setV(nj," + json.dumps(JD, ensure_ascii=False) + ");"
          "setTimeout(()=>{window.__fill=JSON.stringify({nameOk:!!(ni&&ni.value.trim()),"
          "jdLen:nj?nj.value.length:0});},350);return 'ok';})()")
    bx(["eval", js], timeout=30)
    fv = None
    for _ in range(12):
        time.sleep(0.4)
        cand = dom("window.__fill||'{}'")
        if isinstance(cand, dict) and cand.get("nameOk") and (cand.get("jdLen") or 0) >= 60:
            fv = cand
            break
    if fv is None:
        return {"filled": False}
    time.sleep(0.6)
    snap = bx(["snapshot", "-i"], timeout=30)
    m = re.search(r'button "生成岗位简历[^\n]*?ref=([a-z0-9]+)', snap)
    if not m:
        m = re.search(r'"生成岗位简历[^\n]*?ref=([a-z0-9]+)', snap)
    if not m:
        return {"filled": True, "clicked": False}
    bx(["click", f"@{m.group(1)}"], timeout=30)
    running_seen = False
    if expect_running:
        t0 = time.time()
        while time.time() - t0 < 25:
            tb = topbar_state()
            if tb.get("cancel"):
                running_seen = True
                break
            time.sleep(0.4)
    return {"filled": True, "clicked": True, "running_seen": running_seen}


def wait_succeeded(timeout: float = 420.0) -> dict:
    """轮询 P4 成品视图就绪（PDF canvas + 下载区）。"""
    t0 = time.time()
    last = {}
    while time.time() - t0 < timeout:
        st = aside_state()
        last = st
        if (st.get("pdfState") == "ready" and st.get("dl")
                and len(st.get("dl") or []) >= 2 and st.get("hotTotal") is not None):
            return st
        time.sleep(2.0)
    return last


def capture_task_json() -> str | None:
    """权威任务快照指纹（浏览器内计算：FNV-1a+DJB2+长度），用于「同一 Task 字节不变」断言。"""
    v = ev_json("JSON.stringify(window.__p4?window.__p4.lastTaskHash:null)")
    return v if isinstance(v, str) and v else None


# ══════════════════════════ 场景 ══════════════════════════

def s_u1_and_u2(base: str, vp_dir: Path) -> dict:
    """U1 顶栏（DRAFT/RUNNING）+ U2 P4 交互（mouse/Enter/Space/toggle/互斥/详情）。"""
    log("\n=== U1/U2 P4 简历预览交互（真实鼠标 / Enter / Space）===")
    if not open_page(base + "/"):
        bad("u0-open", "工作台未加载出输入视图")
        return {}
    tb = topbar_state()
    if tb.get("newTask") and "开始新任务" in (tb.get("newTaskText") or "") and not tb.get("back"):
        ok("u1.topbar.draft", f"action=new-task text={tb.get('newTaskText')!r} path={tb.get('path')}")
    else:
        bad("u1.topbar.draft", f"probe={tb}")
    install_inject()

    fp_ctl(mode="normal", reset_first=True)
    gen = fill_and_generate(expect_running=True)
    if not gen.get("filled"):
        bad("u2.fill", "姓名/JD 未进入 React 受控 state")
        return {}
    if not gen.get("clicked"):
        bad("u2.generate-click", "未找到「生成岗位简历」按钮")
        return {}
    if gen.get("running_seen"):
        tb2 = topbar_state()
        if tb2.get("cancel") and "取消" in (tb2.get("cancelText") or ""):
            ok("u1.topbar.running", f"action=cancel text={tb2.get('cancelText')!r}")
        else:
            bad("u1.topbar.running", f"probe={tb2}")
    else:
        bad("u1.topbar.running", "RUNNING 期间未观察到取消动作（stall 未生效）")

    st = wait_succeeded()
    if not (st.get("pdfState") == "ready" and len(st.get("dl") or []) >= 2):
        bad("u2.p4-reached", f"未到达 P4 成品视图：{st}")
        return {}
    ok("u2.p4-reached",
       f"pdf={st.get('pdfState')} downloads={st.get('dl')} fact={st.get('factHot')} "
       f"section={st.get('secHot')}")

    lay = layout_of()
    allhits = [h for p in lay for h in (p.get("hits") or [])]
    if DUMP_LAYOUT:
        log("[dump] 热点几何（l,t,w,h 视口 CSS px）：")
        for h in allhits:
            log(f"   {h.get('kind'):<8} {h.get('id'):<45} "
                f"l={h['l']:.0f} t={h['t']:.0f} w={h['w']:.0f} h={h['h']:.0f} "
                f"cls={h.get('cls')} label={h.get('label')!r}")
    facts = [h for h in allhits if h.get("kind") == "fact"]
    secs = [h for h in allhits if h.get("kind") == "section"]
    skills = [h for h in allhits if h.get("kind") == "skills"]
    if facts and secs and skills:
        ok("u2.hotspot-kinds", f"fact={len(facts)} section={len(secs)} skills={len(skills)}")
    else:
        bad("u2.hotspot-kinds", f"fact={len(facts)} section={len(secs)} skills={len(skills)}")

    # 反向：事实热区必须逐条独立定位。若后端 anchor 把多条正文塌缩到同一坐标
    # （例如成品 PDF 出现完全相同的正文行、按「首个出现位置」匹配），就会出现
    # 「点得到但选不中」的幽灵堆叠热区——正是本轮返工要关闭的失效形态。
    frects = [(round(h["l"]), round(h["t"]), round(h["w"]), round(h["h"])) for h in facts]
    if len(set(frects)) == len(frects):
        ok("u2.fact-geometry-distinct", f"{len(facts)} 条事实热区坐标互不相同")
    else:
        bad("u2.fact-geometry-distinct", f"事实热区塌缩/重合：{frects}")

    # —— U3 几何：热点在真实渲染页内，且相对 canvas 等比（多 viewport + 滚动）——
    ratios: dict[str, list] = {}
    for (vw, vh) in VIEWPORTS[:3]:
        bx(["set", "viewport", str(vw), str(vh)], timeout=25)
        time.sleep(1.6)
        lay2 = layout_of()
        bad_geo = []
        for pi, p in enumerate(lay2):
            cv = p.get("canvas")
            if not cv:
                continue
            for h in p.get("hits") or []:
                inside = (h["l"] >= cv["l"] - 2 and h["t"] >= cv["t"] - 2
                          and h["l"] + h["w"] <= cv["l"] + cv["w"] + 2
                          and h["t"] + h["h"] <= cv["t"] + cv["h"] + 2)
                if not (inside and h["w"] > 0 and h["h"] > 0):
                    bad_geo.append({"page": pi, "hit": h.get("id"), "inside": inside})
                if cv.get("w"):
                    ratios.setdefault(h.get("id") or h.get("kind"), []).append(
                        round(h["w"] / cv["w"], 4))
        if bad_geo:
            bad(f"u3.geometry@{vw}x{vh}", f"越界/零面积：{bad_geo[:3]}")
        else:
            ok(f"u3.geometry@{vw}x{vh}", f"全部 {sum(len(p.get('hits') or []) for p in lay2)} 个热点在页内")
    drift = []
    for k, rs in ratios.items():
        if len(rs) >= 2 and (max(rs) - min(rs)) > 0.02:
            drift.append({k: rs})
    if drift:
        bad("u3.scale-proportional", f"缩放后热区比例漂移：{drift[:3]}")
    else:
        ok("u3.scale-proportional", f"等比缩放稳定 n={len(ratios)}")
    # 滚动后仍在页内
    first_sel = _sel_for(facts[0]) if facts else None
    if first_sel:
        bx(["scrollintoview", first_sel], timeout=25)
        time.sleep(0.8)
        lay3 = layout_of()
        p0 = lay3[0] if lay3 else {}
        cv = p0.get("canvas")
        h0 = next((h for h in (p0.get("hits") or []) if h.get("id") == facts[0].get("id")), None)
        if cv and h0 and (h0["l"] >= cv["l"] - 2 and h0["t"] >= cv["t"] - 2
                          and h0["l"] + h0["w"] <= cv["l"] + cv["w"] + 2
                          and h0["t"] + h0["h"] <= cv["t"] + cv["h"] + 2):
            ok("u3.after-scroll", f"scrollintoview 后仍在页内 id={h0.get('id')}")
        else:
            bad("u3.after-scroll", f"cv={cv} hit={h0}")
    bx(["set", "viewport", str(VIEWPORTS[0][0]), str(VIEWPORTS[0][1])], timeout=25)
    time.sleep(1.2)

    # 三类目标不齐时无法执行交互断言：诚实报 FAIL 并跳过，而不是在 secs[0]/skills[0] 上抛异常。
    if not (facts and secs and skills):
        bad("u2.targets-incomplete",
            f"三类目标不齐：fact={len(facts)} section={len(secs)} skills={len(skills)}（交互断言跳过）")
        return {"layout": lay, "facts": facts, "secs": secs, "skills": skills}

    # —— 鼠标：fact 选中 → 详情 → 再次点击取消 ——
    fsel = _sel_for(facts[0])
    cr = click_hit(fsel)
    time.sleep(0.8)
    st1 = aside_state()
    lay1 = layout_of()
    pressed = _pressed_of(lay1, facts[0])
    landed = cr.get("top") == f"hotspot:{facts[0].get('id')}"
    if cr.get("pt") and landed:
        ok("u2.mouse-fact-click",
           f"真实鼠标 pt=({cr['pt'][0]:.0f},{cr['pt'][1]:.0f}) 命中 {cr.get('top')!r}")
    else:
        bad("u2.mouse-fact-click",
            f"pt={cr.get('pt')} top={cr.get('top')!r}（热点遮挡/不可点）probe={cr.get('probe')}")
    if pressed and st1.get("title") == "Fact 详情" and "再次点击可取消" in (st1.get("badge") or ""):
        ok("u2.mouse-fact-select", f"aria-pressed={pressed} title={st1.get('title')!r}")
    else:
        bad("u2.mouse-fact-select", f"pressed={pressed} aside={st1}")
    if (st1.get("reason") or "").strip() and (st1.get("source") or "").strip() \
            and (st1.get("factTitle") or "").strip() and (st1.get("factHost") or "").strip():
        ok("u2.fact-detail", f"reason={((st1.get('reason') or '')[:24])!r} source={((st1.get('source') or '')[:24])!r}")
    else:
        bad("u2.fact-detail", f"详情缺字段：{ {k: st1.get(k) for k in ('factTitle','factHost','reason','source')} }")
    fact_title_before = st1.get("factTitle")
    # 再次点击取消
    click_hit(fsel)
    time.sleep(0.7)
    st2 = aside_state()
    lay2b = layout_of()
    if (not _pressed_of(lay2b, facts[0])) and st2.get("title") == "已为这个岗位整理好" \
            and "再次点击可取消" not in (st2.get("badge") or ""):
        ok("u2.mouse-fact-toggle-off", f"title={st2.get('title')!r} pressed={_pressed_of(lay2b, facts[0])}")
    else:
        bad("u2.mouse-fact-toggle-off", f"aside={st2}")

    # —— 键盘：Enter 选中 / Space 取消（真实按键） ——
    bx(["focus", fsel], timeout=25)
    bx(["press", "Enter"], timeout=25)
    time.sleep(0.8)
    lay_k1 = layout_of()
    st_k1 = aside_state()
    if _pressed_of(lay_k1, facts[0]) and st_k1.get("title") == "Fact 详情":
        ok("u2.keyboard-enter-select", f"pressed={_pressed_of(lay_k1, facts[0])} title={st_k1.get('title')!r}")
    else:
        bad("u2.keyboard-enter-select", f"pressed={_pressed_of(lay_k1, facts[0])} aside={st_k1}")
    bx(["focus", fsel], timeout=25)
    bx(["press", " "], timeout=25)
    time.sleep(0.8)
    lay_k2 = layout_of()
    if not _pressed_of(lay_k2, facts[0]):
        ok("u2.keyboard-space-toggle-off", "Space 取消选中")
    else:
        bad("u2.keyboard-space-toggle-off", "Space 未取消选中")

    # —— focus-visible 可见焦点（键盘 Tab 进入热点应产生 outline） ——
    fv = dom(
        "(()=>{var el=document.querySelector(" + json.dumps(fsel) + ");if(!el)return JSON.stringify({ok:false});"
        "el.focus();var cs=getComputedStyle(el);"
        "return JSON.stringify({ok:true,outlineStyle:cs.outlineStyle,outlineWidth:cs.outlineWidth,"
        "matches:el.matches(':focus-visible')});})()")
    if isinstance(fv, dict) and fv.get("matches") and fv.get("outlineStyle") != "none" \
            and float(str(fv.get("outlineWidth", "0px")).replace("px", "") or 0) > 0:
        ok("u2.focus-visible", f"outline={fv.get('outlineStyle')} {fv.get('outlineWidth')}")
    else:
        bad("u2.focus-visible", f"{fv}")

    # —— 互斥：先选 section，再选 fact，section 必须清除 ——
    ssel = _sel_for(secs[0])
    cs = click_hit(ssel)
    time.sleep(0.8)
    st_s = aside_state()
    if st_s.get("title") == "段落详情" and _pressed_of(layout_of(), secs[0]):
        ok("u2.mouse-section-select",
           f"真实鼠标 pt={cs.get('pt') and tuple(round(v, 1) for v in cs['pt'])} "
           f"title={st_s.get('title')!r} secTitle={st_s.get('secTitle')!r} secFacts={st_s.get('secFacts')}")
    else:
        bad("u2.mouse-section-select",
            f"pt={cs.get('pt')} top={cs.get('top')!r} probe={cs.get('probe')} aside={st_s}")
    if (st_s.get("secTitle") or "").strip() and (st_s.get("secHelp") or "").strip():
        ok("u2.section-detail", f"h3={st_s.get('secTitle')!r} help={st_s.get('secHelp')!r}")
    else:
        bad("u2.section-detail", f"{ {k: st_s.get(k) for k in ('secTitle','secHelp','secFacts')} }")
    click_hit(fsel)
    time.sleep(0.8)
    lay_m = layout_of()
    if _pressed_of(lay_m, facts[0]) and not _pressed_of(lay_m, secs[0]):
        ok("u2.mutual-exclusion", "fact 与 section 选择互斥")
    else:
        bad("u2.mutual-exclusion",
            f"fact={_pressed_of(lay_m, facts[0])} section={_pressed_of(lay_m, secs[0])}")
    click_hit(fsel)  # 收尾取消
    time.sleep(0.5)

    # —— skills 整段 ——
    ksel = _sel_for(skills[0])
    if not ksel:
        bad("u2.skills-missing", "未渲染 skills 整段热点")
    else:
        ck = click_hit(ksel)
        time.sleep(0.8)
        st_k = aside_state()
        if st_k.get("title") == "段落详情" and (st_k.get("skillRows") or 0) >= 1:
            ok("u2.skills-select",
               f"真实鼠标 pt={ck.get('pt') and tuple(round(v, 1) for v in ck['pt'])} "
               f"rows={st_k.get('skillRows')} title={st_k.get('secTitle')!r}")
        else:
            bad("u2.skills-select", f"pt={ck.get('pt')} top={ck.get('top')!r} aside={st_k}")
        # Enter 触发 skills 取消
        bx(["focus", ksel], timeout=25)
        bx(["press", "Enter"], timeout=25)
        time.sleep(0.8)
        if not _pressed_of(layout_of(), skills[0]):
            ok("u2.skills-keyboard-toggle", "Enter 取消 skills 选中")
        else:
            bad("u2.skills-keyboard-toggle", "Enter 未取消 skills 选中")

    # —— 空白页点击取消（DS-003：点页面非热点区清空选择）——
    click_hit(fsel)
    time.sleep(0.7)
    blank_click = ev_str(
        "(function(){var cv=document.querySelector('.pdf-page__canvas');if(!cv)return 'no-canvas';"
        "var pg=cv.closest('.pdf-page');var r=cv.getBoundingClientRect();"
        "var pts=[[r.left+3,r.top+3],[r.right-3,r.top+3],[r.left+3,r.bottom-3],[r.right-3,r.bottom-3],"
        "[r.left+r.width/2,r.top+2]];"
        "for(var i=0;i<pts.length;i++){"
        "var x=Math.min(Math.max(pts[i][0],2),window.innerWidth-3);"
        "var y=Math.min(Math.max(pts[i][1],2),window.innerHeight-3);"
        "var e=document.elementFromPoint(x,y);"
        "if(e&&pg&&pg.contains(e)&&!(e.closest&&e.closest('[data-fact],[data-section]')))"
        "return String(x)+','+String(y);}"
        "return 'none';})()")
    try:
        bx_, by_ = [float(t) for t in (blank_click or "").split(",")[:2]]
        click_at(bx_ + 4, by_ + 4)
    except Exception:
        bad("u2.canvas-click-clears", f"无法取得页面空白坐标 blank={blank_click!r}")
        bx_ = by_ = None
    time.sleep(0.7)
    if bx_ is not None:
        if not _pressed_of(layout_of(), facts[0]) and not errors():
            ok("u2.canvas-click-clears", "真实点击页面空白清空选择")
        else:
            bad("u2.canvas-click-clears",
                f"空白点击未清空选择 pressed={_pressed_of(layout_of(), facts[0])} errs={errors()[:2]}")

    if not errors():
        ok("u2.no-console-errors", "无 uncaught/console.error")
    else:
        bad("u2.no-console-errors", str(errors()[:3]))
    EVIDENCE["browser"]["p4"] = {
        "facts": [h.get("id") for h in facts], "sections": [h.get("id") for h in secs],
        "skills": [h.get("id") for h in skills], "fact_title": fact_title_before,
    }
    return {"layout": lay, "facts": facts, "secs": secs, "skills": skills}


def _sel_for(hit: dict) -> str:
    """agent-browser 的 click/focus 会剥掉属性选择器中的双引号 → 统一用单引号。"""
    if not hit:
        return ""
    if hit.get("kind") == "fact":
        return f"[data-fact='{hit.get('id')}']"
    if hit.get("kind") == "skills":
        return "[data-section='skills']"
    return f"[data-section='{hit.get('id')}']"


def _pressed_of(lay: list, hit: dict) -> bool:
    for p in lay:
        for h in p.get("hits") or []:
            if h.get("kind") == hit.get("kind") and h.get("id") == hit.get("id"):
                return str(h.get("pressed")).lower() == "true"
    return False


def s_u4_negative(base: str) -> None:
    """U4：anchors 空 / artifact 错配 → 无热点（无幽灵热区）；PDF 与双下载仍可用。

    改写模式经 init script 的 fetch 包装作用于真实 GET /api/task/{id} 响应
    （整页重载后仍生效），等价于"后端返回的 artifact/revision 与当前 PDF 不一致"。
    """
    log("\n=== U4 反向：anchors 缺失 / artifact 错配（诚实关闭交互）===")
    install_inject()
    within_before = aside_state().get("hotTotal")
    for mode in ("empty", "mismatch"):
        bx(["eval", f"window.__p4SetAnchorMode('{mode}')"], timeout=20)
        nav("/")
        st = wait_succeeded(timeout=180)
        mode_now = ev_json("JSON.stringify(window.__p4?window.__p4.anchorMode:null)")
        if (st.get("hotTotal") or 0) == 0 and (st.get("ghost") or 0) == 0 \
                and st.get("pdfState") == "ready" and len(st.get("dl") or []) >= 2 \
                and mode_now == mode:
            ok(f"u4.{mode}-no-hotspots",
               f"hotTotal=0 ghost=0 pdf={st.get('pdfState')} downloads={st.get('dl')} "
               f"（改写前 hotTotal={within_before}，生效模式={mode_now}）")
        else:
            bad(f"u4.{mode}-no-hotspots",
                f"mode_now={mode_now} hotTotal={st.get('hotTotal')} ghost={st.get('ghost')} "
                f"pdf={st.get('pdfState')} dl={st.get('dl')}")
        if not errors():
            ok(f"u4.{mode}-no-console-errors", "诚实退出无异常")
        else:
            bad(f"u4.{mode}-no-console-errors", str(errors()[:3]))
    bx(["eval", "window.__p4SetAnchorMode(null)"], timeout=20)
    nav("/")
    st = wait_succeeded(timeout=180)
    if (st.get("hotTotal") or 0) > 0:
        ok("u4.restore-hotspots", f"恢复真实 anchors 后热点回归 n={st.get('hotTotal')}")
    else:
        bad("u4.restore-hotspots", f"清零改写后热点未恢复：{st}")


def s_u5_u6_routes(base: str) -> None:
    """U5 非工作台路由返回 + 反向证明；U6 事件单飞。"""
    log("\n=== U5/U6 非工作台路由：返回工作台 / 同一 Task / 无副作用 / 单飞 ===")
    install_inject()
    nav("/")
    wait_succeeded(timeout=120)
    before_json = capture_task_json()
    before_fp = fp_counts()
    before_reqs = [r for r in (dom("JSON.stringify(window.__p4.reqs)") or []) if isinstance(r, str)]
    before_creates = ev_json("JSON.stringify(window.__p4.creates)")
    before_generates = ev_json("JSON.stringify(window.__p4.generates)")
    task_id = ev_json("JSON.stringify(window.__p4?window.__p4.taskId:null)")
    if before_json and task_id:
        ok("u5.baseline", f"task_id={task_id} creates={before_creates} generates={before_generates}")
    else:
        bad("u5.baseline", f"未捕获权威快照/任务 id（json={bool(before_json)} id={task_id}）")

    activations = ("mouse", "Enter", "Space")
    for route in ("/experiences", "/records", "/privacy"):
        nav(route)
        tb = topbar_state()
        if tb.get("back") and "返回工作台" in (tb.get("backText") or "") and not tb.get("newTask"):
            ok(f"u5.{route}.topbar", f"back={tb.get('backText')!r} newTask={tb.get('newTask')}")
        else:
            bad(f"u5.{route}.topbar", f"probe={tb}")
        if "开始新任务" not in (tb.get("newTaskText") or "") and not tb.get("newTask"):
            ok(f"u5.{route}.no-start-new-task", "顶栏不提供「开始新任务」")
        else:
            bad(f"u5.{route}.no-start-new-task", f"probe={tb}")
        # 记录「进入该路由后」的起点：请求序列长度与写操作计数（重载后注入计数器已归零）
        bx(["eval", "window.__p4.creates=0;window.__p4.generates=0;'ok'"], timeout=20)
        reqs_mark = len(dom("JSON.stringify(window.__p4.reqs)") or [])
        how = activations[("/experiences", "/records", "/privacy").index(route)]
        if how == "mouse":
            click_sel("[data-role='top-back']")
        else:
            bx(["focus", "[data-role='top-back']"], timeout=25)
            bx(["press", how], timeout=25)
        time.sleep(2.2)
        tb2 = topbar_state()
        after_json = capture_task_json()
        after_fp = fp_counts()
        after_reqs = [r for r in (dom("JSON.stringify(window.__p4.reqs)") or []) if isinstance(r, str)]
        new_reqs = after_reqs[reqs_mark:]
        if tb2.get("path") == "/":
            ok(f"u5.{route}.returned", f"via={how} path=/")
        else:
            bad(f"u5.{route}.returned", f"via={how} probe={tb2}")
        same = bool(before_json) and after_json == before_json
        if same:
            ok(f"u5.{route}.task-unchanged", "同一 Task 快照字节完全一致")
        else:
            bad(f"u5.{route}.task-unchanged",
                f"快照变化（len {len(before_json or '')} → {len(after_json or '')}）")
        if after_fp == before_fp:
            ok(f"u5.{route}.no-model-request",
               f"provider 计数不变 {after_fp}")
        else:
            bad(f"u5.{route}.no-model-request", f"{before_fp} → {after_fp}")
        creates_now = ev_json("JSON.stringify(window.__p4.creates)")
        generates_now = ev_json("JSON.stringify(window.__p4.generates)")
        write_posts = [r for r in new_reqs if r.startswith("POST ")]
        if creates_now == 0 and generates_now == 0 and not write_posts:
            ok(f"u5.{route}.no-new-task-or-generate",
               f"返回期间 POST 写操作 0（creates={creates_now} generates={generates_now}，"
               f"期间请求 {len(new_reqs)} 条）")
        else:
            bad(f"u5.{route}.no-new-task-or-generate",
                f"creates={creates_now} generates={generates_now} posts={write_posts[:3]}")
        after_task_id = ev_json("JSON.stringify(window.__p4?window.__p4.taskId:null)")
        if after_task_id == task_id:
            ok(f"u5.{route}.task-id-stable", f"task_id={task_id}")
        else:
            bad(f"u5.{route}.task-id-stable", f"{task_id} → {after_task_id}")

    # —— U6 单飞：同一毫秒内 Enter+Enter 只导航一次 ——
    nav("/records")
    bx(["eval", "window.__p4.push=0;'ok'"], timeout=20)
    bx(["focus", "[data-role='top-back']"], timeout=25)
    bx(["eval",
        "(()=>{var el=document.querySelector('[data-role=top-back]');"
        "var opt={bubbles:true,cancelable:true,key:'Enter'};"
        "el.dispatchEvent(new KeyboardEvent('keydown',opt));"
        "el.dispatchEvent(new KeyboardEvent('keydown',opt));"
        "return 'ok';})()"], timeout=25)
    time.sleep(2.0)
    pushes = ev_json("JSON.stringify(window.__p4.push)")
    if pushes == 1:
        ok("u6.brandlink-single-flight", f"双击/双 Enter 仅 1 次 pushState（push={pushes}）")
    else:
        bad("u6.brandlink-single-flight", f"push={pushes}（期望 1）")
    # 热点双击 = 同一热点上两次真实鼠标点击（真实用户双击语义）：必须净未选中、无异常。
    # 不用 agent-browser 的 `dblclick` 命令：其在本产品透明命中层上的派发语义不受本仓控制
    # （可能只派发单次 click + dblclick 事件），断言会变成验证工具行为而非产品行为。
    nav("/")
    st = wait_succeeded(timeout=120)
    lay = layout_of()
    facts = [h for p in lay for h in (p.get("hits") or []) if h.get("kind") == "fact"]
    if facts:
        sel = _sel_for(facts[0])
        p1 = click_hit(sel)
        press1 = _pressed_of(layout_of(), facts[0])
        p2 = click_hit(sel)
        press2 = _pressed_of(layout_of(), facts[0])
        if p1.get("ok") and press1 and p2.get("ok") and not press2 and not errors():
            ok("u6.hotspot-dblclick-net-off",
               f"同一热点两次真实点击：选中→取消（pt={p1.get('pt')}，净未选中，无异常）")
        else:
            bad("u6.hotspot-dblclick-net-off",
                f"click1={p1.get('ok')}/{press1} click2={p2.get('ok')}/{press2} "
                f"aside={aside_state()} errs={errors()[:2]}")
    else:
        bad("u6.hotspot-dblclick-net-off", "无 fact 热点")


def s_u7_single_fact(base: str) -> None:
    """U7：单 fact 文档 → 恰好 1 个事实热区，仍可选中/取消。"""
    log("\n=== U7 单 fact：恰好一个事实热区 ===")
    install_inject()
    fp_ctl(mode="single_fact", reset_first=True)
    nav("/")
    tb = topbar_state()
    if tb.get("newTask"):
        click_sel("[data-action='new-task']")
        time.sleep(2.0)
    gen = fill_and_generate()
    if not gen.get("clicked"):
        bad("u7.generate-click", f"{gen}")
        return
    st = wait_succeeded()
    lay = layout_of()
    facts = [h for p in lay for h in (p.get("hits") or []) if h.get("kind") == "fact"]
    secs = [h for p in lay for h in (p.get("hits") or []) if h.get("kind") == "section"]
    if st.get("pdfState") == "ready" and len(facts) == 1:
        ok("u7.single-fact-count",
           f"fact={len(facts)} section={len(secs)} id={facts[0].get('id')}")
        click_hit(_sel_for(facts[0]))
        time.sleep(0.8)
        st2 = aside_state()
        if _pressed_of(layout_of(), facts[0]) and st2.get("title") == "Fact 详情":
            ok("u7.single-fact-select", f"title={st2.get('title')!r}")
        else:
            bad("u7.single-fact-select", f"aside={st2}")
        click_hit(_sel_for(facts[0]))
        time.sleep(0.7)
        if not _pressed_of(layout_of(), facts[0]):
            ok("u7.single-fact-toggle-off", "再次点击取消")
        else:
            bad("u7.single-fact-toggle-off", "未取消")
    else:
        bad("u7.single-fact-count",
            f"fact={len(facts)} pdf={st.get('pdfState')} （期望恰好 1）")


def write_evidence(vp_dir: Path) -> None:
    EVIDENCE["provider"] = fp_counts()
    EVIDENCE["pass"] = PASS
    EVIDENCE["fails"] = FAILS
    out = vp_dir / "docreturned_ui_summary.json"
    out.write_text(json.dumps(EVIDENCE, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[evidence] {out}")


def _rmtree_force(path, attempts: int = 8) -> bool:
    """删除目录树，兼容**只读文件**（产品迁移备份 `*.db.bak` 被 `os.chmod(bak, 0o444)`）。

    Windows 上 `shutil.rmtree(..., ignore_errors=True)` 遇到只读文件会**静默失败**，
    导致隔离 runtime 残留、Gate cleanup 误判失败（已在 mainchain/design_fidelity/
    atomic_publish 复现）。这里在出错回调里清除只读位后重试，并做有限次整体重试以
    吸收句柄释放延迟。
    """
    import inspect as _inspect
    import stat as _stat

    def _fix(func, p, exc=None):
        try:
            os.chmod(p, _stat.S_IWRITE)
            func(p)
        except Exception:  # noqa: BLE001
            pass

    _params = _inspect.signature(shutil.rmtree).parameters
    _kw = {"onexc": _fix} if "onexc" in _params else {"onerror": _fix}
    for _ in range(attempts):
        try:
            shutil.rmtree(path, **_kw)
        except Exception:  # noqa: BLE001
            pass
        if not path.exists():
            return True
        time.sleep(0.3)
    return not path.exists()


def record_cleanup(vp_dir: Path, runtime: Path) -> None:
    """runtime 删除后回填 cleanup 记账（供 Gate runner 逐 Gate 核验隔离与清理）。

    只在 summary 已产出时回填（否则视为早期阻断，不伪造证据文件）。
    """
    p = vp_dir / "docreturned_ui_summary.json"
    if not p.is_file():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        data["cleanup"] = {"runtime_removed": not runtime.exists(),
                           "runtime_dir": str(runtime)}
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


# ══════════════════════════ U0：同根重复实现退出的静态反向证明 ══════════════════════════
SRC = FRONTEND / "src"

# 已退出（删除）的旧实现：既不可被路由到达，也不得再存在可被重新接入的文件
RETIRED_FILES = (
    "components/layout/AppShell.tsx",   # 旧常驻侧栏壳（与 WorkbenchShell 同根重复）
    "components/ResultPaperPreview.tsx",  # 另行维护可选中 props 的第二套结果预览真源
    "pages/GeneratePage.tsx",           # 未挂路由；自带第二套 P4 预览 + 本地选中态
    "pages/WelcomeGate.tsx",            # 未挂路由；唯一引用 GeneratePage 的入口
)


def _src_files() -> list[Path]:
    return [p for p in SRC.rglob("*") if p.suffix in (".ts", ".tsx")]


def _files_matching(pattern: str) -> list[str]:
    rx = re.compile(pattern)
    out: list[str] = []
    for p in _src_files():
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        if rx.search(txt):
            out.append(p.relative_to(SRC).as_posix())
    return sorted(out)


def s_u0_static_retirement() -> None:
    """U0：静态反向证明「导航」与「P4 选择」各只剩一个正式活动实现。

    纯源码扫描（无浏览器/无后端），但同为 exit code 阻断项：
      - 已退出的旧实现文件不得再存在（存在即可被重新 import 接入）；
      - PdfPreview 必须是唯一 P4 预览/热点渲染实现，且唯一被 StepDownload 引用；
      - 热点类名与 data-fact/data-section 只允许出现在 PdfPreview 内；
      - 选中态唯一持有者 = WorkbenchPage（useState<PdfAnchor）；PdfPreview 不得自持选择状态；
      - 导航壳唯一 = WorkbenchShell（AppShell 零出现）；BrandLink 为唯一品牌/返回导航原语。
    """
    log("\n=== U0 静态反向证明：同根重复实现退出 ===")
    missing = [rel for rel in RETIRED_FILES if (SRC / rel).exists()]
    if missing:
        bad("u0.retired-files-gone", f"旧实现文件仍然存在：{missing}")
    else:
        ok("u0.retired-files-gone", f"4 个旧实现文件均已删除：{list(RETIRED_FILES)}")

    for token, label in (("AppShell", "u0.no-appshell"), ("ResultPaperPreview", "u0.no-resultpaper")):
        hits = _files_matching(token)
        if hits:
            bad(label, f"失效实现残留引用：{hits}")
        else:
            ok(label, "源码零出现")

    # —— P4 选择：唯一正式活动实现 ——
    definers = _files_matching(r"export\s+default\s+function\s+PdfPreview")
    if definers == ["components/PdfPreview.tsx"]:
        ok("u0.pdfpreview-single-definer", f"唯一实现：{definers}")
    else:
        bad("u0.pdfpreview-single-definer", f"实现者={definers}（期望仅 components/PdfPreview.tsx）")
    # 组件默认导入（渲染实现）唯一；`anchorSelectionKey` 是共享身份键原语，
    # 允许被详情卡消费（不得被重新实现）。
    importers = _files_matching(r"import\s+PdfPreview\s+from\s+'[^']*components/PdfPreview'")
    if importers == ["pages/workbench/StepDownload.tsx"]:
        ok("u0.pdfpreview-single-importer", f"组件唯一引用者：{importers}")
    else:
        bad("u0.pdfpreview-single-importer", f"引用者={importers}（期望仅 StepDownload.tsx）")
    key_users = _files_matching(r"import\s*\{[^}]*anchorSelectionKey")
    if key_users == ["pages/workbench/StepSuccessAside.tsx"]:
        ok("u0.selkey-single-consumer", f"身份键唯一外部消费者：{key_users}")
    else:
        bad("u0.selkey-single-consumer", f"消费者={key_users}（期望仅 StepSuccessAside.tsx）")

    for token, label in (
        (r"pdf-fact-hotspot", "u0.hotspot-class-single-source"),
        (r"pdf-section-hotspot", "u0.section-class-single-source"),
        (r"'data-fact'|data-fact=|data-fact\b", "u0.data-fact-single-source"),
        (r"'data-section'|data-section=|data-section\b", "u0.data-section-single-source"),
        (r"function\s+anchorSelectionKey", "u0.selkey-single-definer"),
    ):
        hits = _files_matching(token)
        if hits == ["components/PdfPreview.tsx"]:
            ok(label, "仅 PdfPreview.tsx")
        else:
            bad(label, f"命中={hits}（期望仅 components/PdfPreview.tsx）")

    # —— 选中态唯一持有者 = WorkbenchPage；PdfPreview 不得自持选择状态 ——
    holders = _files_matching(r"useState<\s*PdfAnchor")
    if holders == ["pages/workbench/WorkbenchPage.tsx"]:
        ok("u0.selection-single-owner", f"唯一 useState<PdfAnchor>：{holders}")
    else:
        bad("u0.selection-single-owner", f"持有者={holders}（期望仅 WorkbenchPage.tsx）")
    consumers = _files_matching(r"selectedAnchor")
    expect_consumers = ["components/PdfPreview.tsx", "pages/workbench/StepDownload.tsx"]
    if consumers == expect_consumers:
        ok("u0.selection-consumers", f"受控 props 仅出现在：{consumers}")
    else:
        bad("u0.selection-consumers", f"出现于={consumers}（期望 {expect_consumers}）")
    # PdfPreview 只通过 props 接收选择：文件内不得出现 useState 局部选中态
    pp = (SRC / "components" / "PdfPreview.tsx").read_text(encoding="utf-8")
    if not re.search(r"useState<[^>]*Anchor", pp) and "const [selection" not in pp:
        ok("u0.pdfpreview-no-local-selection", "PdfPreview 无本地选择状态（纯受控）")
    else:
        bad("u0.pdfpreview-no-local-selection", "PdfPreview 仍自持选择状态")

    # —— 导航：唯一壳 + 唯一品牌/返回原语 ——
    shell_defs = _files_matching(r"export\s+default\s+function\s+WorkbenchShell")
    shell_uses = _files_matching(r"from\s+'[^']*layout/WorkbenchShell'")
    if shell_defs == ["components/layout/WorkbenchShell.tsx"] and shell_uses == ["App.tsx"]:
        ok("u0.shell-single", f"定义={shell_defs} 使用={shell_uses}")
    else:
        bad("u0.shell-single", f"定义={shell_defs} 使用={shell_uses}（期望 1 定义 / App.tsx 唯一使用）")
    brand_users = _files_matching(r"from\s+'[^']*BrandLink'")
    if brand_users == ["components/layout/WorkbenchShell.tsx"]:
        ok("u0.brandlink-single", f"唯一引用者：{brand_users}")
    else:
        bad("u0.brandlink-single", f"引用者={brand_users}（期望仅 WorkbenchShell.tsx）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="保留 runtime 与证据目录")
    ap.add_argument("--skip-u7", action="store_true")
    ap.add_argument("--only-u2", action="store_true", help="只跑 U1/U2（快速定位 P4 交互）")
    ap.add_argument("--dump-layout", action="store_true", help="打印全部热点几何（诊断用）")
    args = ap.parse_args()
    global DUMP_LAYOUT
    DUMP_LAYOUT = bool(args.dump_layout)

    # U0 纯静态反向证明（不依赖浏览器/后端），先跑以便早期阻断重复实现回归。
    s_u0_static_retirement()

    if not resolve_browser():
        bad("env-browser", "agent-browser 不可用")
        return 2
    if not DIST.is_dir():
        bad("env-dist", "frontend/dist 缺失（需先 npm run build）")
        return 2
    if port_in_use(APP_PORT):
        bad("env-port", f"{APP_PORT} 已被占用")
        return 2
    if port_in_use(FP_PORT):
        bad("env-port", f"{FP_PORT} 已被占用")
        return 2

    runtime = Path(tempfile.mkdtemp(prefix="docret_ui_"))
    vp_dir = ROOT / "validation-artifacts" / "h8" / "docreturned_ui"
    vp_dir.mkdir(parents=True, exist_ok=True)
    EVIDENCE["runtime_dir"] = str(runtime)
    install_init_script(runtime)
    srv = None
    backend = None
    try:
        srv = start_fp(FP_PORT)
        if not wait_port(FP_PORT, 20):
            bad("env-fp", "fake provider 未就绪")
            return 2
        backend = start_backend(runtime, FP_PORT, APP_PORT)
        if not wait_port(APP_PORT, 120):
            bad("env-backend", "后端未就绪")
            return 2
        info = seed()
        EVIDENCE["seed"] = {"experience_ids": info.get("experience_ids")}
        log(f"[gate] runtime={runtime} seeded={len(info.get('experience_ids') or [])}")

        base = f"http://127.0.0.1:{APP_PORT}"
        # 先生成一次「运行中」证据所需：U1/U2 用 stall 观察 running 顶栏
        fp_ctl(mode="normal", stall_s=12.0, stall_kind="jd", reset_first=True)
        s_u1_and_u2(base, vp_dir)
        if not args.only_u2:
            s_u4_negative(base)
            s_u5_u6_routes(base)
            if not args.skip_u7:
                s_u7_single_fact(base)

        write_evidence(vp_dir)
        log("\n" + "=" * 60)
        log(f"DOC_RETURNED 离线 UI 门：PASS={PASS} FAIL={len(FAILS)}")
        for f in FAILS:
            log("  - " + f)
        return 1 if FAILS else 0
    finally:
        try:
            bx(["close"], timeout=15)
        except Exception:
            pass
        if srv is not None:
            try:
                srv.shutdown()
            except Exception:
                pass
        kill_tree(backend)
        if not args.keep:
            _rmtree_force(runtime)
            record_cleanup(vp_dir, runtime)


if __name__ == "__main__":
    sys.exit(main())