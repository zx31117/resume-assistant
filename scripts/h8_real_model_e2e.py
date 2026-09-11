#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""H8 阻断项 B：真实模型链纵向验证（最终 onedir + 真实豆包/火山方舟）。

纪律（硬约束）：
- 全新隔离 RESUME_DATA_DIR（仓库外临时目录），不触碰 X / current / review；
- 必须运行**最终 onedir 包**（--exe），不是源码服务；
- API Key 仅由应用自身从 Windows 凭据库读取（`core.config_resolver`）：本脚本
  不读取、不打印、不复制、不写入任何 Key；ARK 计数代理也不落任何请求头/正文；
- 无隐私测试简历 + 测试 JD（全虚构）。

产出：validation-artifacts/h8/e2e/real_model_e2e.json（+ 控制台摘要）。

用法：
  python real_model_e2e.py --exe <path\\ResumeAssistant.exe> [--keep] [--api-only]
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
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent            # scripts/
ROOT = HERE.parent                               # repo root
EVID = ROOT / "validation-artifacts" / "h8" / "e2e"
EVID.mkdir(parents=True, exist_ok=True)
OUT = EVID / "real_model_e2e.json"
PROXY_PY = HERE / "h8_ark_proxy.py"
PY = os.environ.get("H8_E2E_PYTHON", sys.executable)

# 无隐私测试数据（全虚构）
TEST_JD = (
    "高级后端研发工程师（Java）：负责电商平台交易链路设计、编码与线上稳定性，主导订单支付库存模块"
    "演进与高并发优化。要求 5 年+ Java、Spring Boot、MySQL、Redis，有分布式/消息队列实践优先，"
    "base 杭州，可尽快到岗。"
)
TEST_EXPERIENCES = [
    {
        "type": "work", "title": "后端研发工程师", "company": "示例科技有限公司",
        "time": "2022.03-2025.06", "role": "后端研发工程师",
        "description": "负责示例电商平台订单域的后端研发与稳定性建设。",
        "achievements": [
            "主导订单创建链路重构，将核心接口 P99 从 820ms 降到 210ms",
            "搭建库存扣减幂等与对账机制，超卖事故从月均 3 起降为 0",
        ],
        "skills": ["Java", "Spring Boot", "MySQL", "Redis", "Kafka"],
        "raw_text": "示例科技有限公司 后端研发工程师 2022.03-2025.06",
    },
    {
        "type": "work", "title": "初级后端工程师", "company": "虚构网络股份有限公司",
        "time": "2020.07-2022.02", "role": "初级后端工程师",
        "description": "负责示例社区服务的接口开发与数据维护。",
        "achievements": [
            "完成用户中心服务拆分，接口平均延迟下降 35%",
            "推动单元测试覆盖率从 42% 提升到 78%",
        ],
        "skills": ["Java", "MySQL", "MyBatis"],
        "raw_text": "虚构网络股份有限公司 初级后端工程师 2020.07-2022.02",
    },
    {
        "type": "project", "title": "订单对账系统", "company": "示例科技有限公司",
        "time": "2024.05-2024.11", "role": "负责人",
        "description": "面向示例业务的订单对账与差异定位系统。",
        "achievements": [
            "设计差异定位算法，对账工单平均处理时长从 45 分钟降到 8 分钟",
            "实现对账任务调度，日处理账单量 200 万条",
        ],
        "skills": ["Java", "Kafka", "MySQL"],
        "raw_text": "订单对账系统 负责人 2024.05-2024.11",
    },
    {
        "type": "education", "title": "计算机科学与技术", "company": "示例大学",
        "time": "2016.09-2020.06", "role": "",
        "description": "计算机科学与技术 本科",
        "achievements": [], "skills": [],
        "raw_text": "示例大学 计算机科学与技术 本科 2016.09-2020.06",
    },
]
TEST_PROFILE = {
    "name": "测试用户H8", "phone": "000-0000-0000", "email": "user@example.invalid",
    "location": "杭州", "target_position": "高级后端研发工程师", "summary": None,
}

EVIDENCE: dict = {"steps": [], "limits": {
    "python": PY, "note": "Key 由应用从 Windows 凭据库读取；本脚本不接触任何 Key"}}


def log(m: str) -> None:
    print(m, flush=True)


def step(name: str, **kw) -> None:
    EVIDENCE["steps"].append({"step": name, "ts": time.strftime("%H:%M:%S"), **kw})
    log(f"[e2e] {name}: " + json.dumps(kw, ensure_ascii=False)[:500])


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def wait_port(port: int, timeout: float = 90.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        for host in ("127.0.0.1", "::1", "localhost"):
            try:
                with socket.create_connection((host, port), timeout=1):
                    return True
            except OSError:
                pass
        time.sleep(0.3)
    return False


def winword_pids() -> list[int]:
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq WINWORD.EXE", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True, timeout=20)
        pids = []
        for ln in r.stdout.splitlines():
            parts = [x.strip('"') for x in ln.split(",")]
            if len(parts) >= 2 and parts[0].lower().startswith("winword"):
                pids.append(int(parts[1]))
        return pids
    except Exception:
        return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True, help="最终 onedir 的 ResumeAssistant.exe")
    ap.add_argument("--api-only", action="store_true", help="跳过浏览器 UI 段（仅 API 直连）")
    ap.add_argument("--keep", action="store_true", help="结束后不删 runtime（排障用）")
    args = ap.parse_args()

    exe = Path(args.exe).resolve()
    if not exe.exists():
        log(f"[fatal] exe 不存在：{exe}")
        return 2
    exe_sha = sha256_file(exe)
    EVIDENCE["exe"] = {"path": str(exe), "sha256": exe_sha,
                       "size": exe.stat().st_size}
    log(f"[e2e] exe={exe} sha256={exe_sha[:16]}…")

    # ── 隔离 runtime（仓库外）──
    runtime = Path(os.environ.get("TEMP", ".")) / f"h8e2e_{int(time.time())}"
    runtime.mkdir(parents=True, exist_ok=True)
    EVIDENCE["runtime_dir"] = str(runtime)
    log(f"[e2e] isolated RESUME_DATA_DIR={runtime}")

    # ── ARK 计数代理 ──
    proxy_port = 8799
    proxy_out = EVID / "ark_counts.json"
    proxy = subprocess.Popen([PY, str(PROXY_PY), "--port", str(proxy_port), "--out", str(proxy_out)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(EVID))
    if not wait_port(proxy_port, 30):
        log("[fatal] ARK 代理未就绪")
        proxy.kill()
        return 2
    step("proxy_up", port=proxy_port, counts_file=str(proxy_out))

    app_port = 8317
    env = dict(os.environ)
    env["RESUME_DATA_DIR"] = str(runtime)
    env["ARK_BASE_URL"] = f"http://127.0.0.1:{proxy_port}/api/v3"
    env["APP_PORT"] = str(app_port)
    env.pop("ARK_API_KEY", None)          # 强制走凭据库，不经脚本注入
    env.pop("H8_CONV_WORKER", None)

    ww_before = winword_pids()
    app_stdout = EVID / "app_stdout.log"
    app_fh = open(app_stdout, "w", encoding="utf-8", errors="replace")
    app = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env,
                           stdout=app_fh, stderr=subprocess.STDOUT)
    ok = False
    try:
        if not wait_port(app_port, 120):
            step("app_boot_failed", pid=app.pid, ret=app.poll())
            return 3
        ok = True
        base = f"http://127.0.0.1:{app_port}"
        step("app_up", pid=app.pid, port=app_port, winword_before=ww_before)

        # 用 requests.Session 维持 ra_session cookie（写操作必须带启动会话令牌）
        import requests
        s = requests.Session()
        r = s.get(f"{base}/api/system/status", timeout=30)
        step("status", code=r.status_code, has_cookie=bool(s.cookies.get("ra_session")))
        if r.status_code != 200:
            return 4
        EVIDENCE["status_before"] = r.json()

        # ── 1) 迁移 ──
        r = s.post(f"{base}/api/system/migrate", timeout=180)
        step("migrate", code=r.status_code, body=str(r.json())[:200])
        if r.status_code != 200:
            return 5

        # ── 2) 导入（无隐私测试简历：直接结构化写入，不经 LLM）──
        exp_ids = []
        for exp in TEST_EXPERIENCES:
            rr = s.post(f"{base}/api/experience/", json=exp, timeout=120)
            if rr.status_code != 200:
                step("experience_import_failed", code=rr.status_code, body=rr.text[:200])
                return 6
            exp_ids.append(rr.json().get("id"))
        step("import_experiences", count=len(exp_ids), ids=exp_ids)

        # ── 3) Embedding 重建（真实 embedding provider）──
        r = s.post(f"{base}/api/system/rebuild", timeout=600)
        step("rebuild_embeddings", code=r.status_code, body=str(r.json())[:300])
        if r.status_code != 200:
            return 7
        st = s.get(f"{base}/api/system/status", timeout=30).json()
        EVIDENCE["status_after_rebuild"] = st
        step("status_after_rebuild", embeddings=st.get("embeddings"), ready=st.get("ready"))

        # ── 4) 记录计数基线 ──
        def counts() -> dict:
            try:
                return json.loads(proxy_out.read_text(encoding="utf-8"))
            except Exception:
                return {"total": 0, "by_path": {}, "calls": []}
        c0 = counts()
        base_total = c0.get("total", 0)
        step("proxy_baseline", total=base_total, by_path=c0.get("by_path", {}))
        emb_before = c0.get("by_path", {}).get("/api/v3/embeddings/multimodal", 0)

        # ── 5) 生成（真实模型；浏览器 UI 驱动，若可用）──
        ui = None
        if not args.api_only:
            ui = _ui_generate(base, app_port, proxy_out, base_total)
        gen = ui
        if gen is None:
            gen = _api_generate(s, base, proxy_out, base_total)
        if not gen:
            return 8
        EVIDENCE["generate"] = gen

        op_id = gen.get("operation_id")
        # ── 6) 终态计时（P1–P4 服务端投影）──
        if op_id:
            rr = s.get(f"{base}/api/system/operations/{op_id}", timeout=60)
            if rr.status_code == 200:
                op = rr.json().get("operation", {})
                ups = op.get("user_phases") or []
                ssum = sum(int(u.get("elapsed_ms") or 0) for u in ups)
                elapsed = int(op.get("elapsed_ms") or 0)
                EVIDENCE["operation_terminal"] = {
                    "operation_id": op_id, "status": op.get("status"),
                    "elapsed_ms": elapsed, "phase_sum_ms": ssum, "delta_ms": abs(elapsed - ssum),
                    "jd_analysis_started_events": sum(
                        1 for s in (op.get("stages") or [])
                        if s.get("stage_code") == "jd_analysis" and s.get("event_type") == "STARTED"),
                    "content_generation_started_events": sum(
                        1 for s in (op.get("stages") or [])
                        if s.get("stage_code") == "content_generation" and s.get("event_type") == "STARTED"),
                    "stage_codes": sorted({s.get("stage_code") for s in (op.get("stages") or [])}),
                    "user_phases": [{"code": u.get("code"), "label": u.get("label"),
                                     "status": u.get("status"), "elapsed_ms": u.get("elapsed_ms"),
                                     "live_elapsed_ms": u.get("live_elapsed_ms")} for u in ups],
                }
                step("operation_terminal", status=op.get("status"), elapsed_ms=elapsed,
                     phase_sum_ms=ssum, delta_ms=abs(elapsed - ssum))

        # ── 7) 字节一致性：DOCX/PDF 磁盘 artifact vs 下载 vs 响应 ──
        _verify_artifacts(s, base, gen, runtime)

        # ── 8) Provider 计数（JD 恰 1 / rewrite 次数 / 无输入页预分析）──
        c1 = counts()
        jd_calls = c1.get("by_path", {}).get("/api/v3/chat/completions", 0) - \
            c0.get("by_path", {}).get("/api/v3/chat/completions", 0)
        emb_calls = c1.get("by_path", {}).get("/api/v3/embeddings/multimodal", 0) - emb_before
        EVIDENCE["provider_counts"] = {
            "chat_completions_in_generate_window": jd_calls,
            "embeddings_in_window": emb_calls,
            "total_before": base_total, "total_after": c1.get("total"),
            "by_path_after": c1.get("by_path", {}),
            "calls_in_window": [c for c in c1.get("calls", [])[base_total:]
                                if True][:40],
        }
        step("provider_counts", chat_in_window=jd_calls, emb_in_window=emb_calls)

        # ── 9) WINWORD / 进程泄漏 ──
        time.sleep(2)
        ww_after = winword_pids()
        leaks = sorted(set(ww_after) - set(ww_before))
        EVIDENCE["cleanup"] = {"winword_before": ww_before, "winword_after": ww_after,
                               "winword_leaked": leaks}
        step("winword_check", before=ww_before, after=ww_after, leaked=leaks)

        st2 = s.get(f"{base}/api/system/status", timeout=30)
        EVIDENCE["http_health_final"] = {"status_code": st2.status_code}
        return 0 if not leaks else 9
    finally:
        try:
            app.terminate()
            app.wait(timeout=15)
        except Exception:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(app.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            app_fh.close()
        except Exception:
            pass
        proxy.terminate()
        time.sleep(1)
        if not args.keep:
            # 只删本次全新隔离 runtime（仓库外、本脚本创建）
            shutil.rmtree(runtime, ignore_errors=True)
            EVIDENCE["runtime_deleted"] = True
        OUT.write_text(json.dumps(EVIDENCE, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[e2e] wrote {OUT} ok={ok}")


# ── 浏览器 UI 驱动（真实点击下载）──────────────────────────────── #
BROWSER_SESSION = f"h8e2e-{os.getpid()}"


def _browser_env() -> dict:
    e = dict(os.environ)
    e["AGENT_BROWSER_SESSION"] = BROWSER_SESSION
    return e


def _bx(args: list[str], timeout: int = 30) -> str:
    """有界调用 agent-browser。

    注意：不能用 `subprocess.run(..., capture_output=True, timeout=...)` —— daemon 持有
    stdout/stderr 管道时收尾 `communicate()` 会在超时后继续阻塞（已在阻断项 A 复现）。
    这里用显式 Popen + kill 后次级 communicate 兜底，保证永不悬挂。
    """
    w = shutil.which("agent-browser")
    if not w:
        return ""
    p0 = Path(w)
    exe = str(p0.parent / "node_modules" / "agent-browser" / "bin" / "agent-browser-win32-x64.exe")
    if not Path(exe).exists():
        exe = w
    try:
        p = subprocess.Popen([exe, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=_browser_env())
    except Exception:
        return ""
    try:
        out, _err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        try:
            out, _err = p.communicate(timeout=10)
        except Exception:
            out = b""
    return out.decode("utf-8", "replace").strip()


def _ui_generate(base: str, port: int, proxy_out: Path, base_total: int) -> dict | None:
    """真实 UI：打开 → 填表 → 点击生成 → 轮询 P1–P4 → 捕获响应 → 点击双下载。"""
    try:
        _bx(["open", base], timeout=12)
        t0 = time.time()
        ready = False
        while time.time() - t0 < 45:
            if "粘贴完整岗位描述" in _bx(["snapshot", "-i"], timeout=20):
                ready = True
                break
            time.sleep(0.6)
        if not ready:
            step("ui_not_ready", note="回退 API 直连")
            return None
        inject = ("window.__h8={errs:[],resp:null};"
                  "window.addEventListener('error',e=>__h8.errs.push('uncaught:'+e.message));"
                  "window.addEventListener('unhandledrejection',e=>__h8.errs.push('rej:'+String(e.reason)));"
                  "const _f=window.fetch;window.fetch=(...a)=>{const u=String(a[0]);const p=_f.apply(window,a);"
                  "if(u.includes('/api/resume/generate-docx')){p.then(r=>r.clone().json().then(j=>{__h8.resp=j}).catch(()=>{}))}"
                  "return p};'ok'")
        _bx(["eval", inject], timeout=25)
        snap = _bx(["snapshot", "-i"], timeout=25)
        m = re.search(r'button "编辑[^\n]*?ref=([a-z0-9]+)', snap)
        if m:
            _bx(["click", f"@{m.group(1)}"], timeout=25)
            time.sleep(1)
            snap = _bx(["snapshot", "-i"], timeout=25)
        nm = re.search(r'textbox "姓名[^\n]*?ref=([a-z0-9]+)', snap)
        if nm:
            _bx(["fill", f"@{nm.group(1)}", TEST_PROFILE["name"]], timeout=25)
        jd = re.search(r'textbox "粘贴完整岗位描述[^\n]*?ref=([a-z0-9]+)', snap)
        if jd:
            _bx(["fill", f"@{jd.group(1)}", TEST_JD], timeout=25)
        time.sleep(1)
        snap = _bx(["snapshot", "-i"], timeout=25)
        gb = re.search(r'button "生成岗位简历[^\n]*?ref=([a-z0-9]+)', snap)
        if not gb:
            step("ui_generate_button_missing", note="回退 API 直连")
            return None
        _bx(["click", f"@{gb.group(1)}"], timeout=25)
        step("ui_generate_clicked")

        # 并发采样 P1–P4 实时（服务端投影）
        samples: list[dict] = []
        stop = {"v": False}

        def sampler():
            import requests as _rq
            ss = _rq.Session()
            ss.get(f"{base}/api/system/status", timeout=10)
            while not stop["v"]:
                try:
                    lst = ss.get(f"{base}/api/system/operations",
                                 params={"operation_type": "generate", "limit": 5}, timeout=10).json()
                    for o in lst.get("operations", []):
                        if o.get("status") == "RUNNING":
                            detail = ss.get(f"{base}/api/system/operations/{o['operation_id']}",
                                            timeout=10).json().get("operation", {})
                            samples.append({"t": round(time.time(), 2),
                                            "elapsed_ms": detail.get("elapsed_ms"),
                                            "phases": [(u.get("code"), u.get("status"),
                                                        u.get("live_elapsed_ms")) for u in
                                                       (detail.get("user_phases") or [])]})
                except Exception:
                    pass
                time.sleep(0.35)
        th = threading.Thread(target=sampler, daemon=True)
        th.start()

        t0 = time.time()
        resp = None
        while time.time() - t0 < 600:
            raw = _bx(["eval", "window.__h8?.resp?JSON.stringify(window.__h8.resp):''"], timeout=25)
            raw = raw.strip()
            if raw.startswith('"') and raw.endswith('"'):
                try:
                    raw = json.loads(raw)
                except Exception:
                    pass
            if isinstance(raw, str) and raw.strip().startswith("{"):
                try:
                    resp = json.loads(raw)
                    break
                except Exception:
                    pass
            time.sleep(1.0)
        stop["v"] = True
        EVIDENCE["live_phase_samples"] = samples
        step("ui_live_samples", n=len(samples))
        if not resp:
            step("ui_no_response", note="回退 API 直连")
            return None

        # 真实点击双下载 + 页面内取证
        # 1) 定位页面上的 `<a data-role=download-*>`，读其 href 并**在页面内**同步取回
        #    字节长度与 HTTP 状态（overrideMimeType 保证字节保真）；证明「被点击的元素」
        #    指向的正是响应里的 download_url / pdf_download_url，且 200 且字节数一致。
        # 2) 再用文本定位真实点击该元素（agent-browser find/click）。
        probe = ("(function(){var out={};"
                 "var map={word:'[data-role=\"download-word\"]',pdf:'[data-role=\"download-pdf\"]'};"
                 "for(var k in map){var el=document.querySelector(map[k]);"
                 "if(!el){out[k]={missing:true};continue;}"
                 "var href=el.getAttribute('href');"
                 "var x=new XMLHttpRequest();x.open('GET',href,false);"
                 "try{x.overrideMimeType('text/plain; charset=x-user-defined');x.send();"
                 "out[k]={href:href,status:x.status,size:x.responseText.length};}"
                 "catch(e){out[k]={href:href,error:String(e)};}}"
                 "window.__h8dl=out;return 'ok';})()")
        _bx(["eval", probe], timeout=30)
        raw = _bx(["eval", "JSON.stringify(window.__h8dl||{})"], timeout=25).strip()
        probe_res = {}
        try:
            # agent-browser eval 输出的是「JSON 字符串」，需两次解码
            s1 = json.loads(raw)
            probe_res = json.loads(s1) if isinstance(s1, str) else s1
        except Exception:
            probe_res = {"raw": raw[:400]}
        EVIDENCE["ui_download_probe"] = probe_res

        dl = {}
        for label, url_key, role, text, outp in (
                ("word", "download_url", "download-word", "下载 Word", EVID / "dl_word.docx"),
                ("pdf", "pdf_download_url", "download-pdf", "下载 PDF", EVID / "dl_viewer.pdf")):
            url = resp.get(url_key)
            if not url:
                dl[label] = {"url": url, "error": "url_empty"}
                continue
            out = str(outp)
            try:
                Path(out).unlink(missing_ok=True)
            except Exception:
                pass
            click_out = _bx(["find", "text", text, "click"], timeout=40)
            _bx(["download", f'[data-role="{role}"]', out], timeout=90)
            saved = Path(out).exists()
            pr = probe_res.get(label) if isinstance(probe_res, dict) else None
            dl[label] = {"url": url,
                         "clicked_element_href": (pr or {}).get("href"),
                         "href_matches_response_url": bool(pr) and (pr or {}).get("href") == url,
                         "in_page_status": (pr or {}).get("status"),
                         "in_page_size": (pr or {}).get("size"),
                         "click_out": click_out[:120],
                         "saved_by_agent_browser": saved,
                         "saved_sha256": sha256_file(outp) if saved else None,
                         "saved_size": outp.stat().st_size if saved else None}
        EVIDENCE["ui_downloads"] = dl
        step("ui_downloads", word=dl.get("word", {}).get("saved_sha256"),
             pdf=dl.get("pdf", {}).get("saved_sha256"))
        _bx(["close"], timeout=20)
        return resp
    except Exception as e:  # noqa: BLE001
        step("ui_exception", err=repr(e))
        return None


def _api_generate(s, base: str, proxy_out: Path, base_total: int) -> dict | None:
    """回退：直接调用真实生成接口（同一 onedir / 同一真实模型）。"""
    body = {"user_id": None, "template_id": "pm_template", "jd_text": TEST_JD,
            "profile": TEST_PROFILE, "top_k": 5}
    t0 = time.time()
    r = s.post(f"{base}/api/resume/generate-docx", json=body, timeout=1200)
    dur = int((time.time() - t0) * 1000)
    step("api_generate", code=r.status_code, dur_ms=dur)
    if r.status_code != 200:
        EVIDENCE["api_generate_error"] = {"code": r.status_code, "body": r.text[:500]}
        return None
    return r.json()


def _verify_artifacts(s, base: str, gen: dict, runtime: Path) -> None:
    """DOCX/PDF 磁盘 artifact vs HTTP 下载 字节一致；无 404/405/5xx。"""
    out: dict = {}
    # 磁盘定位
    docx_disk = None
    fp = gen.get("file_path")
    cands = []
    if fp:
        cands.append(Path(fp) if Path(fp).is_absolute() else runtime / fp)
    cands.append(runtime / "output" / str(gen.get("file_name") or ""))
    for c in cands:
        if c and c.exists():
            docx_disk = c
            break
    pdf_disk = None
    for c in sorted((runtime / "output").glob("*.pdf")) if (runtime / "output").is_dir() else []:
        pdf_disk = c
        break
    out["docx_disk"] = {"path": str(docx_disk), "sha256": sha256_file(docx_disk),
                        "size": docx_disk.stat().st_size} if docx_disk else None
    out["pdf_disk"] = {"path": str(pdf_disk), "sha256": sha256_file(pdf_disk),
                       "size": pdf_disk.stat().st_size} if pdf_disk else None

    def http_get(url: str) -> tuple[int, bytes, str]:
        r = s.get(base + url, timeout=120)
        return r.status_code, r.content, r.headers.get("Content-Type", "")

    if gen.get("download_url"):
        code, data, ctype = http_get(gen["download_url"])
        out["word_download"] = {"url": gen["download_url"], "status": code, "mime": ctype,
                                "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                                "size_bytes": gen.get("file_name") and len(data)}
    if gen.get("pdf_download_url"):
        code, data, ctype = http_get(gen["pdf_download_url"])
        out["pdf_download"] = {"url": gen["pdf_download_url"], "status": code, "mime": ctype,
                               "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        code2, data2, _ = http_get(gen["pdf_download_url"])
        out["pdf_download_repeat_same"] = hashlib.sha256(data2).hexdigest() == hashlib.sha256(data).hexdigest()
    out["response"] = {
        "operation_id": gen.get("operation_id"),
        "file_name": gen.get("file_name"),
        "download_url": gen.get("download_url"),
        "pdf_file_name": gen.get("pdf_file_name"),
        "pdf_download_url": gen.get("pdf_download_url"),
        "pdf_artifact_id": gen.get("pdf_artifact_id"),
        "pdf_sha256": gen.get("pdf_sha256"),
        "pdf_size_bytes": gen.get("pdf_size_bytes"),
        "page_count": gen.get("page_count"),
        "anchor_count": len(gen.get("pdf_anchors") or []),
        "anchors_bound": _anchors_bound(gen),
        "warnings": gen.get("warnings"),
    }
    EVIDENCE["artifacts"] = out
    # 一致性判定
    checks = {}
    if out.get("docx_disk") and out.get("word_download"):
        checks["word_download_eq_disk_docx"] = \
            out["docx_disk"]["sha256"] == out["word_download"]["sha256"]
    if out.get("pdf_disk") and out.get("pdf_download"):
        checks["pdf_download_eq_disk_pdf"] = \
            out["pdf_disk"]["sha256"] == out["pdf_download"]["sha256"]
    if gen.get("pdf_sha256") and out.get("pdf_download"):
        checks["pdf_download_eq_response_sha"] = gen["pdf_sha256"] == out["pdf_download"]["sha256"]
    if gen.get("pdf_sha256") and out.get("pdf_disk"):
        checks["pdf_disk_eq_response_sha"] = gen["pdf_sha256"] == out["pdf_disk"]["sha256"]
    codes = [v.get("status") for k, v in out.items() if isinstance(v, dict) and "status" in v]
    checks["no_4xx_5xx"] = all(isinstance(c, int) and c < 400 for c in codes) and bool(codes)
    EVIDENCE["artifact_checks"] = checks
    step("artifact_checks", **checks)


def _anchors_bound(gen: dict) -> dict:
    arts = [a.get("artifact_id") for a in (gen.get("pdf_anchors") or [])]
    pid = gen.get("pdf_artifact_id")
    return {"total": len(arts), "bound_to_pdf_artifact": sum(1 for a in arts if a == pid),
            "unavailable": sum(1 for a in (gen.get("pdf_anchors") or [])
                               if not a.get("artifact_id"))}


if __name__ == "__main__":
    sys.exit(main())
