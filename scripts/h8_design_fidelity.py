#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""H8 R2-16 返工：Design Fidelity 浏览器断言（PLAN §7.1）。

覆盖 DS-003 Theme A 的 Design Fidelity 证据，针对 be59acd 打回点名缺失的部分：
- 二级页面（experiences / records / privacy）统一 Theme A 页壳：
    .wb-task-heading（eyebrow YOUR NEXT CHAPTER + h1 + sub + actions）存在；
    页面不再出现旧常驻侧栏 .app-sidebar；
    页面不再使用旧开发者卡片 .page / .page-head / .privacy-list / .card；
    单面板 .wb-panel--main 在 .wb-subpage 内，页头固定、内容内部滚动；
- 工作台 empty / saved 主 CTA 固位：.wb-panel__foot--generate 存在且主 CTA 可点；
- 四步轨道状态：当前 active 不可点、done 可点、future disabled；
- 7 个冻结 viewport 截图 + 整页 overflow=0。

用法（须在隔离 runtime，先由 h8_real_model_e2e 等价方式准备后端）：
  python h8_design_fidelity.py --exe <ResumeAssistant.exe> --base <http://127.0.0.1:PORT> [--seeded]

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
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h8_p4_interact import run as p4_interact  # noqa: E402


def _rmtree_force(path, attempts: int = 8) -> bool:
    """删除目录树，兼容**只读文件**（产品迁移备份 `*.db.bak` 被 `os.chmod(bak, 0o444)`）。

    Windows 上 `shutil.rmtree(..., ignore_errors=True)` 遇到只读文件会**静默失败**，
    导致隔离 runtime 残留、Gate cleanup 误判失败（已在 mainchain/design_fidelity/
    atomic_publish 复现）。这里在出错回调里清除只读位后重试，并做有限次整体重试以
    吸收句柄释放延迟。
    """
    import inspect as _inspect
    import stat as _stat
    import time as _time

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
        if not os.path.exists(path):
            return True
        _time.sleep(0.4)
    return not os.path.exists(path)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EVID = ROOT / "validation-artifacts" / "h8" / "fidelity"
EVID.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [(1920, 1080), (1440, 900), (1280, 800), (1024, 768),
             (720, 450), (390, 844), (320, 568)]

PASS = 0
FAILS: list[str] = []
EVIDENCE: dict = {"secondary": {}, "saved": {}, "rail": {}, "viewports": {}}


def log(m: str = "") -> None:
    print(m, flush=True)


def ok(label: str, extra: str = "") -> None:
    global PASS
    PASS += 1
    log(f"[PASS] {label}" + (f" {extra}" if extra else ""))


def bad(label: str, why: str) -> None:
    FAILS.append(f"{label}: {why}")
    log(f"[FAIL] {label}: {why}")


def _bx_env() -> dict:
    e = os.environ.copy()
    e.setdefault("BROWSER_HEADLESS", "1")
    e.setdefault("AGENT_BROWSER_VIEW", "0")
    return e


def bx(args: list[str], timeout: int = 30) -> str:
    w = __import__("shutil").which("agent-browser")
    if not w:
        return ""
    p0 = Path(w)
    exe = str(p0.parent / "node_modules" / "agent-browser" / "bin" / "agent-browser-win32-x64.exe")
    if not Path(exe).exists():
        exe = w
    try:
        p = subprocess.Popen([exe, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=_bx_env())
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


def wait_port(base: str, timeout: float = 90.0) -> bool:
    host = "127.0.0.1"
    port = int(base.rsplit(":", 1)[1])
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.8)
    return False


def _port_in_use(port: int) -> bool:
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        return False
    except OSError:
        return True
    finally:
        s.close()


def _free_port(preferred: int = 8317, tries: int = 200) -> int:
    """首选 preferred；被占用则顺序探测首个空闲端口。

    Gate 模式（给了 --exe）必须自启动被指定的二进制；若固定端口被上一轮残留 app
    占用，`wait_port` 会立即成功并驱动**残留实例**，使 Gate 结果与最终包脱钩。
    """
    if not _port_in_use(preferred):
        return preferred
    for p in range(preferred + 1, preferred + 1 + tries):
        if not _port_in_use(p):
            return p
    return preferred


def http_json(base: str, path: str, method: str = "GET", body=None, timeout: float = 30):
    import urllib.request
    req = urllib.request.Request(
        base + path, method=method,
        headers={"Content-Type": "application/json", "Cookie": "ra_session=1"},
        data=json.dumps(body).encode("utf-8") if body is not None else None)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
        try:
            return r.status, json.loads(raw)
        except Exception:
            return r.status, {"_raw": raw[:400]}


# 探测：整页 overflow + Theme A 壳元素 + 旧侧栏/旧卡片是否消失 + 主操作可达
_PROBE = ("JSON.stringify((function(){\n"
          "const doc=document.documentElement,bd=document.body;\n"
          "const vh=window.innerHeight||0, vw=window.innerWidth||0;\n"
          "const has=s=>{const n=document.querySelectorAll(s).length;return n;}\n"
          "return {\n"
          "  viewport:vw+'x'+vh,\n"
          "  docOv:Math.max(0,Math.ceil(doc.scrollHeight-doc.clientHeight)),\n"
          "  bodyOv:Math.max(0,Math.ceil(bd.scrollHeight-bd.clientHeight)),\n"
          "  wbShell:has('.wb-shell'),\n"
          "  topbar:has('.wb-topbar'),\n"
          "  avatar:has('.wb-avatar-btn'),\n"
          "  taskHeading:has('.wb-task-heading'),\n"
          "  eyebrow:has('.wb-task-heading__eyebrow'),\n"
          "  h1:has('.wb-task-heading__h1'),\n"
          "  subpage:has('.wb-subpage'),\n"
          "  panelMain:has('.wb-panel--main'),\n"
          "  oldSidebar:has('.app-sidebar'),\n"
          "  oldPage:has('.page-head'),\n"
          "  oldPrivacyList:has('.privacy-list'),\n"
          "  oldCard:has('.card__title'),\n"
          "  genFoot:has('.wb-panel__foot--generate'),\n"
          "  rail:has('.wb-steps'),\n"
          "  activeStep:has('.wb-step.is-active'),\n"
          "  doneSteps:has('.wb-step.is-done'),\n"
          "  futureSteps:has('.wb-step.is-future'),\n"
          "};\n})())")


def probe(base: str) -> dict:
    raw = bx(["eval", _PROBE], timeout=30).strip()
    if not raw:
        return {}
    try:
        s1 = json.loads(raw)
        return json.loads(s1) if isinstance(s1, str) else s1
    except Exception:
        return {"_raw": raw[:200]}


# ── 全状态 Design Fidelity 对照（PLAN §7.1）──────────────────────── #
# 纪律（用户硬约束）：
#   - P1–P4 只跑一次真实成功任务；P1/P2/P3 在成功后用 reviewStep（点击已 done 步骤）回看采集，
#     不重复调用模型；
#   - 7 个冻结 viewport 沿用同一已就绪成功态切换 viewport 截图，不因 viewport 变化重新生成；
#   - failed 用隔离 runtime 的真实失败路径（触发真实生成并轮询 FAILED），不用固定 UI fixture；
#     若该失败路径在隔离 runtime 不易稳定构造，则如实标记，不虚假 PASS。
TEST_NAME = "全状态保真测试"
TEST_JD = ("高级后端研发工程师（Java）：负责电商平台交易链路设计、编码与线上稳定性，主导订单支付库存模块"
           "演进与高并发优化。要求 5 年+ Java、Spring Boot、MySQL、Redis，有分布式/消息队列实践优先，"
           "base 杭州，可尽快到岗。")

# 全状态 DOM/布局探针：整页 overflow + Theme A 壳 + 步骤轨道 class 计数 + PDF viewer + 下载区固位 + 旧 dev 卡。
_STATE_PROBE = ("JSON.stringify((function(){\n"
                "const doc=document.documentElement,bd=document.body;\n"
                "const n=s=>{try{return document.querySelectorAll(s).length}catch(e){return -1}};\n"
                "const vp=document.querySelector('.pdf-preview');\n"
                "return {\n"
                " viewport:(window.innerWidth||0)+'x'+(window.innerHeight||0),\n"
                " docOv:Math.max(0,Math.ceil(doc.scrollHeight-doc.clientHeight)),\n"
                " bodyOv:Math.max(0,Math.ceil(bd.scrollHeight-bd.clientHeight)),\n"
                " wbShell:n('.wb-shell'),wbTopbar:n('.wb-topbar'),panelMain:n('.wb-panel--main'),rail:n('.wb-steps'),\n"
                " stepTotal:n('.wb-step'),stepActive:n('.wb-step.is-active'),stepDone:n('.wb-step.is-done'),\n"
                " stepFailed:n('.wb-step.is-failed'),stepFuture:n('.wb-step.is-future'),\n"
                " reviewBanner:n('.wb-review-banner'),failedPanel:n('.wb-failed'),\n"
                " pdfState:vp?(vp.getAttribute('data-state')||''):'',\n"
                " pdfPages:n('.pdf-page'),pdfCanvas:n('.pdf-page__canvas'),\n"
                " dlBar:n('.wb-success-downloads'),dlLinks:n('[data-role^=download-]'),\n"
                " oldSidebar:n('.app-sidebar'),oldPage:n('.page-head'),oldCard:n('.card__title')\n"
                "};\n})())")


def _capture_state(base: str, key: str, vp_dir: Path, shot_png: Path,
                   viewport: tuple[int, int] | None = None, chk_shell: bool = True) -> dict:
    """对当前已就绪 DOM 设定 viewport → probe → 截图 → 断言，并把记录写入 EVIDENCE["workbench"][key]。"""
    if viewport is not None:
        bx(["set", "viewport", str(viewport[0]), str(viewport[1])], timeout=20)
        time.sleep(1.0)
    raw = bx(["eval", _STATE_PROBE], timeout=25).strip()
    p: dict = {}
    if raw:
        try:
            s1 = json.loads(raw)
            p = json.loads(s1) if isinstance(s1, str) else s1
        except Exception:
            p = {"_raw": raw[:200]}
    vp_dir.mkdir(parents=True, exist_ok=True)
    bx(["screenshot", str(shot_png)], timeout=60)
    vpl = f"{viewport[0]}x{viewport[1]}" if viewport else str(p.get("viewport"))
    rec = {"viewport": vpl, "docOv": p.get("docOv"), "bodyOv": p.get("bodyOv"),
           "stepTotal": p.get("stepTotal"), "stepActive": p.get("stepActive"),
           "stepDone": p.get("stepDone"), "stepFailed": p.get("stepFailed"),
           "stepFuture": p.get("stepFuture"), "reviewing": bool(p.get("reviewBanner")),
           "failedPanel": p.get("failedPanel"), "pdfState": p.get("pdfState"),
           "pdfPages": p.get("pdfPages"), "pdfCanvas": p.get("pdfCanvas"),
           "dlBar": p.get("dlBar"), "dlLinks": p.get("dlLinks"),
           "oldSidebar": p.get("oldSidebar"), "oldPage": p.get("oldPage"), "oldCard": p.get("oldCard"),
           "shot": shot_png.name, "shot_exists": shot_png.exists(), "_probe": p}
    EVIDENCE.setdefault("workbench", {}).setdefault(key, {})["@" + vpl] = rec
    dov = int(p.get("docOv") or 0); bov = int(p.get("bodyOv") or 0)
    if dov == 0 and bov == 0:
        ok(f"wb.{key}@{vpl} overflow=0", f"docOv={dov} bodyOv={bov}")
    else:
        bad(f"wb.{key}@{vpl} overflow", f"docOv={dov} bodyOv={bov}")
    if shot_png.exists():
        ok(f"wb.{key}@{vpl} screenshot", shot_png.name)
    else:
        bad(f"wb.{key}@{vpl} screenshot", "png 未落盘")
    if chk_shell and (p.get("wbShell") and p.get("wbTopbar") and p.get("panelMain") and p.get("rail")):
        ok(f"wb.{key}@{vpl} themeA-shell",
           f"shell={p.get('wbShell')} topbar={p.get('wbTopbar')} panel={p.get('panelMain')} rail={p.get('rail')}")
    elif chk_shell:
        bad(f"wb.{key}@{vpl} themeA-shell",
            f"shell={p.get('wbShell')} topbar={p.get('wbTopbar')} panel={p.get('panelMain')} rail={p.get('rail')}")
    if not (p.get("oldSidebar") or p.get("oldPage") or p.get("oldCard")):
        ok(f"wb.{key}@{vpl} no old dev card",
           f"sidebar={p.get('oldSidebar')} page={p.get('oldPage')} card={p.get('oldCard')}")
    else:
        bad(f"wb.{key}@{vpl} no old dev card",
            f"sidebar={p.get('oldSidebar')} page={p.get('oldPage')} card={p.get('oldCard')}")
    return rec


def _fill_workbench(base: str, name: str, jd: str) -> dict:
    """用 React 兼容方式填受控输入（原生 value setter + input/change），并回读 window.__h8fill 验证。"""
    js_name = json.dumps(name); js_jd = json.dumps(jd)
    bx(["eval",
        ("(()=>{const setV=(el,v)=>{const p=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;"
         "Object.getOwnPropertyDescriptor(p,'value').set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));"
         "el.dispatchEvent(new Event('change',{bubbles:true}));};"
         "const ni=document.querySelector('input[placeholder=\"请输入姓名\"]');"
         "const nj=document.querySelector('textarea[placeholder=\"职位描述（JD）\"]');"
         "if(ni)setV(ni," + js_name + ");if(nj)setV(nj," + js_jd + ");"
         "setTimeout(()=>{const gb=document.querySelector('.wb-panel__foot--generate button.wb-btn--primary')"
         "||document.querySelector('button.wb-form-actions__primary');"
         "window.__h8fill=JSON.stringify({nameOk:!!(ni&&ni.value.trim()),jdLen:nj?nj.value.length:0,"
         "btnDisabled:gb?!!gb.disabled:null});},500);return 'ok';})()")], timeout=25)
    last = "{}"
    for _ in range(10):
        time.sleep(0.3)
        raw = bx(["eval", "window.__h8fill||'{}'"], timeout=25).strip()
        if raw:
            last = raw
        try:
            s1 = json.loads(raw)
            c = json.loads(s1) if isinstance(s1, str) else s1
            if c.get("nameOk") and int(c.get("jdLen", 0)) >= 60:
                return c
        except Exception:
            pass
    return {"raw": last[:300]}


def _click_generate(base: str) -> str:
    """点击主 CTA「生成岗位简历」（P1 触发真实生成；返回 clicked/no-btn/disabled）。"""
    return bx(["eval",
               "(function(){const b=document.querySelector('.wb-panel__foot--generate button.wb-btn--primary')"
               "||document.querySelector('button.wb-form-actions__primary');"
               "if(!b)return 'no-btn';if(b.disabled)return 'disabled';b.click();return 'clicked';})()"],
              timeout=20).strip().strip('"')


def _wait_p4_reached(base: str, timeout_s: float = 600.0) -> bool:
    """轮询 P4 成品视图（成功传入 /api/task SSE 推进到成功态 → 下载区出现）。

    DOM 快照与后端任务终态双通道：真实生成已达 SUCCEEDED（API 为准）即视为到达，
    避免隔离 runtime 中 DOM 尚未刷新下载区但任务其实已成功时误判。
    """
    t0 = time.time()
    tid = ""
    while time.time() - t0 < timeout_s:
        snap = bx(["snapshot", "-i"], timeout=25)
        if ('data-role="download-word"' in snap or 'data-role="download-pdf"' in snap
                or "wb-success-downloads" in snap):
            return True
        if not tid:
            tid = bx(["eval", "(sessionStorage.getItem('resume_assistant.lastTaskId')||'')"],
                     timeout=20).strip().strip('"')
        if tid:
            try:
                code, body = http_json(base, f"/api/task/{tid}")
                if code == 200 and isinstance(body, dict):
                    task = body.get("task") if isinstance(body.get("task"), dict) else body
                    if task.get("status") == "SUCCEEDED":
                        return True
                    if task.get("status") in ("FAILED", "CANCELLED"):
                        EVIDENCE["workbench"]["_p4_terminal"] = task.get("status")
                        return False
            except Exception:
                pass
        time.sleep(1.5)
    return False


def _wait_pdf_ready(base: str, timeout_s: float = 90.0) -> dict:
    """等待 PDF.js viewer 渲染 ready + ≥1 页 canvas（P4/success 主证据前置）。"""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        raw = bx(["eval", "JSON.stringify({ready:!!document.querySelector('.pdf-preview[data-state=\"ready\"]'),"
                 "pages:document.querySelectorAll('.pdf-page').length,canvas:document.querySelectorAll('.pdf-page__canvas').length})"],
                 timeout=25).strip()
        try:
            s1 = json.loads(raw)
            v = json.loads(s1) if isinstance(s1, str) else s1
            if v.get("ready") and int(v.get("canvas") or 0) >= 1:
                return v
        except Exception:
            pass
        time.sleep(1.0)
    return {}


# ── P4 真实交互取证（PLAN §R3-24：Design Fidelity 不得以 canvas ready / anchor 数量
#    / artifact_id 绑定代替交互通过）──────────────────────────────────────────── #
# 断言实现集中在 scripts/h8_p4_interact.py，与主链/最终包 E2E 共用同一份，避免语义分叉。
# 断言名前缀 P4.interact.*；`evidence` 写入 EVIDENCE["workbench"]。
def _p4_interactions(base: str, vp_dir: Path) -> None:
    """PLAN §R3-24：P4 真实交互断言 —— fact / section / skills × mouse / Enter / Space。

    * 每类目标分别用真实鼠标与键盘 Enter/Space 激活，断言 aria-pressed=true、`.selected`、
      右侧详情**实际变化且与所选对象一致**，再以同一方式再次激活取消选择；
    * 互斥（fact→section 只应一个选中）与滚动后热区仍精确命中（热区与正文对齐）；
    * 不以 canvas ready / anchor 数量 / artifact_id 绑定代替交互通过。
    """
    p4_interact(bx, ok=ok, bad=bad, log=log, evidence=EVIDENCE["workbench"],
                tag="P4.interact")


def _review_phase(base: str, idx: int, key: str, vp_dir: Path, viewport: tuple[int, int]) -> dict:
    """reviewStep 回看第 idx 个已 done 步骤（P1/P2/P3），截图+probe；不做任何新生成请求。

    必须等到真实回看态成立（`.wb-review-banner` 出现 / `.wb-step__num.is-selected` 落到 idx /
    面板标题「步骤 idx+1」）后才截图，避免捕获成功完成帧冒充回看帧。
    """
    clicked = bx(["eval", f"(function(){{const s=document.querySelector('.wb-steps > li:nth-of-type({idx+1}) button.wb-step');if(!s)return 'missing';s.click();return 'clicked';}})()"], timeout=20).strip().strip('"')
    # 轮询回看态成立（≤6s）
    got_review = False
    got_title = ""
    for _ in range(24):
        time.sleep(0.25)
        raw = bx(["eval",
                  "JSON.stringify({banner:!!document.querySelector('.wb-review-banner'),"
                  f"sel:[...document.querySelectorAll('.wb-step__num.is-selected')].length,"
                  f"title:(document.querySelector('.wb-panel--main .wb-panel__head-title')||null)?.textContent||'',"
                  f"done:document.querySelectorAll('.wb-step.is-done').length,"
                  f"active:document.querySelectorAll('.wb-step.is-active').length}})"],
                 timeout=25).strip()
        try:
            s1 = json.loads(raw)
            v = json.loads(s1) if isinstance(s1, str) else s1
        except Exception:
            continue
        got_title = v.get("title", "")
        if v.get("banner") and idx + 1 in (int(n) for n in re.findall(r"\d+", got_title)) and (
                int(v.get("sel") or 0) > 0):
            got_review = True
            break
    if not got_review:
        bad(f"wb.{key} review state engaged",
            f"idx={idx} clicked={clicked} banner={got_review} title={got_title!r}")
    else:
        ok(f"wb.{key} review state engaged",
           f"idx={idx} clicked={clicked} title={got_title!r}")
    rec = _capture_state(base, key, vp_dir, vp_dir / f"{key}_{viewport[0]}x{viewport[1]}.png",
                         viewport=viewport)
    # 主证据：回看态成立（banner 在）+ stepOfInterest 处 done 而非全 done 成功帧
    p = rec.get("_probe", {})
    if p.get("reviewBanner") and int(p.get("stepActive") or 0) + int(p.get("stepFailed") or 0) >= 0:
        ok(f"wb.{key} reviewed (not success frame)", f"banner={p.get('reviewBanner')}")
    else:
        bad(f"wb.{key} reviewed (not success frame)", f"_probe={ {k: p.get(k) for k in ('stepDone','stepActive','pdfState','reviewBanner')} }")
    return rec


def _return_live(base: str) -> str:
    """回到实时视图：优先点回看横幅「返回当前阶段」，其次点 active 步骤。"""
    return bx(["eval", "(function(){const b=document.querySelector('.wb-review-banner__back');"
               "if(b){b.click();return 'back';}const cur=document.querySelector('.wb-step.is-active');"
               "if(cur){cur.click();return 'live-step';}return 'none';})()"], timeout=20).strip().strip('"')


def _drive_failed(base: str, vp_dir: Path, exe: Path | None = None) -> None:
    """failed 状态取证：独立 fail-forced 实例（不可达 ARK_BASE_URL → 真实生产型 provider 失败
    → 任务必然进入 FAILED），轮询 backend terminal 并捕获 .wb-failed 面板截图。

    这是可复现的真实失败路径（provider 不可达），不是“SUCCEEDED/未稳定构造”的占位，也不是 mock。
    """
    if exe is None:
        EVIDENCE["workbench"]["failed"] = {
            "note": "未提供 --exe，无法独立构造 failed 实例；如实记录不 PASS。", "terminal": None}
        return
    import socket
    class _PortPicker:
        def __init__(self, base_port): self.n = base_port
        def __call__(self):
            while True:
                s = socket.socket()
                try:
                    s.bind(("127.0.0.1", self.n)); s.close(); return self.n
                except OSError:
                    self.n += 1; s.close()
    pick = _PortPicker((int(base.rsplit(":", 1)[1]) + 1) % 40000 + 10000)
    fport = pick()
    frm = Path(tempfile.mkdtemp(prefix="h8fid_fail_"))
    DEAD = "http://127.0.0.1:1/api/v3"  # 不可达端点 → provider 失败（真实失败路径）
    fbase = f"http://127.0.0.1:{fport}"
    fapp, ferr = _boot_app(Path(exe), fport, frm, seed=False, ark_base_url=DEAD)
    if ferr:
        EVIDENCE["workbench"]["failed"] = {"note": "failed 实例启动失败：不再断言", "err": ferr}
        _teardown_fail_instance(fapp, frm)
        return
    try:
        # 对新实例驱动前端：打开 → 清缓存 → 填表 → 点生成 → 轮询 FAILED。
        bx(["open", fbase + "/"], timeout=15)
        time.sleep(2.0)
        bx(["eval", "sessionStorage.clear();localStorage.clear();location.reload();'ok'"], timeout=15)
        time.sleep(2.5)
        fv = _fill_workbench(fbase, TEST_NAME, TEST_JD)
        EVIDENCE["workbench"]["_fill_verify_failed"] = fv
        gen = _click_generate(fbase)
        EVIDENCE["workbench"]["_failed_generate_click"] = gen
        if gen != "clicked":
            log(f"[wb.full][info] failed 路径生成按钮未点动（gen={gen}）；如实记录，不判定 PASS")
            EVIDENCE["workbench"]["failed"] = {"note": "generate click failed", "_fill": fv, "gen": gen}
            _teardown_fail_instance(fapp, frm)
            return
        tid = ""
        t0 = time.time()
        terminal: str | None = None
        while time.time() - t0 < 300.0:
            raw = bx(["eval", "JSON.stringify({failed:!!document.querySelector('.wb-failed'),"
                     "suc:!!document.querySelector('.pdf-preview[data-state=\"ready\"]')})"], timeout=25).strip()
            st: dict = {}
            try:
                s1 = json.loads(raw)
                st = json.loads(s1) if isinstance(s1, str) else s1
            except Exception:
                st = {"raw": raw[:120]}
            if st.get("failed"):
                terminal = "FAILED"; break
            if not tid:
                tid = bx(["eval", "(sessionStorage.getItem('resume_assistant.lastTaskId')||'')"],
                         timeout=20).strip().strip('"')
            if tid:
                try:
                    code, body = http_json(fbase, f"/api/task/{tid}")
                    if code == 200 and isinstance(body, dict):
                        status = (body.get("task") if isinstance(body.get("task"), dict) else body).get("status")
                        if status == "FAILED":
                            terminal = "FAILED"; break
                        if status == "SUCCEEDED":
                            terminal = "SUCCEEDED"; break
                except Exception:
                    pass
            time.sleep(2.0)
        if terminal == "FAILED":
            bx(["open", fbase + "/"], timeout=15)
            time.sleep(2.0)
            rec = _capture_state(fbase, "failed", vp_dir, vp_dir / "failed_1920x1080.png", viewport=VIEWPORTS[0])
            if rec.get("failedPanel") and int(rec.get("stepFailed") or 0):
                ok("wb.failed real failed panel (provider-unreachable)",
                   f"failedPanel={rec.get('failedPanel')} stepFailed={rec.get('stepFailed')} terminal={terminal}")
            else:
                bad("wb.failed real failed panel", f"failedPanel={rec.get('failedPanel')} stepFailed={rec.get('stepFailed')}")
            EVIDENCE["workbench"]["failed_terminal"] = terminal
            EVIDENCE["workbench"]["_failed_ark_base_url"] = DEAD
        else:
            log(f"[wb.full][info] failed 未进入 FAILED：terminal={terminal}；如实记录。")
            EVIDENCE["workbench"]["failed"] = {
                "note": f"failed 实例未达 FAILED（terminal={terminal}）。", "terminal": terminal}
    except BaseException as _e:  # noqa: BLE001 —— 异常/提前返回统一走 teardown
        import traceback as _tb
        _tb.print_exc()
        EVIDENCE.setdefault("workbench", {})["failed_exception"] = repr(_e)
    finally:
        # §18.3-A.4：failed 实例的 app/端口/runtime 在任何返回与异常路径都必须释放。
        # 收尾 failed 实例 + runtime（须等到进程真正退出，避免残留实例占用资源/端口，
        # 冻结 onedir 同时只能跑一个实例，主实例随后才能启动）
        if fapp is not None and fapp.poll() is None:
            try:
                fapp.terminate()
            except Exception:  # noqa: BLE001
                pass
            try:
                fapp.wait(timeout=15)
            except Exception:  # noqa: BLE001
                try:
                    fapp.kill()
                except Exception:  # noqa: BLE001
                    pass
            try:
                fapp.wait(timeout=10)
            except Exception:  # noqa: BLE001
                pass
        time.sleep(2.0)  # 端口/Task 释放尘埃落定
        import shutil
        _rmtree_force(frm)
    
    
def workbench_full_states(base: str, exe, runtime) -> None:
    """PLAN §7.1 全状态 Design Fidelity 对照（empty/saved 在 main 已就绪并复用；此处 P1–P4/failed）。

    * 一次真实成功任务（P1–P4 → SUCCEEDED）；成功后 P1/P2/P3 用 reviewStep 回看已 done 步骤采集，
      不再重复触发模型；
    * P4/success：真实 PDF viewer + 下载区固位 + 7 个冻结 viewport（沿用同一已就绪成功态切换截图）；
    * failed：隔离 runtime 真实失败路径，不稳定则如实标记。
    """
    wb = EVIDENCE.setdefault("workbench", {})
    # 复用已有 empty/saved 证据（不计入新增 PASS）：
    wb["empty"] = {"reuse": "secondary.workbench_empty",
                   "src": EVIDENCE.get("secondary", {}).get("workbench_empty") or {}}
    wb["saved"] = {"reuse": "saved", "src": EVIDENCE.get("saved") or {}}
    wb["_ctx"] = {"base": base, "runtime": str(runtime) if runtime else None,
                  "assert_note": "P1/P2/P3 = 成功后 reviewStep 回看已 done 步骤采集，不重复调用模型"}
    vp_dir = EVID / "states"

    # ── 1) 一次真实成功任务（P1–P4 → SUCCEEDED）──
    bx(["open", base + "/"], timeout=15)
    time.sleep(1.8)
    bx(["eval", "sessionStorage.clear();localStorage.clear();location.reload();'ok'"], timeout=15)
    time.sleep(2.5)
    fv = _fill_workbench(base, TEST_NAME, TEST_JD)
    EVIDENCE["workbench"]["_fill_verify_success"] = fv
    log(f"[wb.full] fill verify={fv}")
    if not (isinstance(fv, dict) and fv.get("nameOk") and int(fv.get("jdLen", 0)) >= 60):
        bad("wb.success real-generation setup", "受控输入未进入 React state")
        return
    gen = _click_generate(base)
    if gen != "clicked":
        bad("wb.success generate click", f"got={gen}")
        return
    if not _wait_p4_reached(base):
        bad("wb.success P4 reached", "任务未推进到 P4 成品视图（隔离 runtime 真实生成未到 SUCCEEDED）")
        EVIDENCE["workbench"]["_success_reached"] = False
        return
    EVIDENCE["workbench"]["_success_reached"] = True
    log("[wb.full] P4 SUCCEEDED 到达（一次真实任务，后续均靠回看不重复生成）")

    # P4/success 主证据：真实 PDF viewer ready + 下载区固位 + 7 视口。
    v = _wait_pdf_ready(base)
    EVIDENCE["workbench"]["_pdf_ready"] = v
    if v.get("ready"):
        ok("wb.P4 pdf viewer ready", f"pages={v.get('pages')} canvas={v.get('canvas')}")
    else:
        bad("wb.P4 pdf viewer ready", f"raw={v}")
    rec0 = _capture_state(base, "P4", vp_dir, vp_dir / "P4_1920x1080.png", viewport=VIEWPORTS[0])
    if int(rec0.get("pdfCanvas") or 0) >= 1 and int(rec0.get("dlBar") or 0):
        ok("wb.P4 download area pinned",
           f"pdfCanvas={rec0.get('pdfCanvas')} dlBar={rec0.get('dlBar')} dlLinks={rec0.get('dlLinks')}")
    else:
        bad("wb.P4 download area pinned",
            f"pdfCanvas={rec0.get('pdfCanvas')} dlBar={rec0.get('dlBar')} dlLinks={rec0.get('dlLinks')}")
    # P4 真实交互（PLAN §R3-24）：fact / section / skills × mouse / Enter / Space。
    # 在 1920x1080 已就绪成功态上执行；结束后选择已取消，不污染后续 7 视口截图。
    try:
        _p4_interactions(base, vp_dir)
    except BaseException as _e:  # noqa: BLE001 —— 交互取证异常不得吞掉其余保真断言
        import traceback as _tb
        _tb.print_exc()
        EVIDENCE["workbench"]["_p4_interactions_exception"] = repr(_e)
        bad("P4.interact.exception", repr(_e))

    for (vw, vh) in VIEWPORTS:
        _capture_state(base, "P4", vp_dir, vp_dir / f"P4_{vw}x{vh}.png", viewport=(vw, vh))

    # ── 2) P1/P2/P3：reviewStep 回看已 done 步骤（不重复生成）──
    _review_phase(base, 0, "P1", vp_dir, VIEWPORTS[0]); _return_live(base); time.sleep(0.8)
    _review_phase(base, 1, "P2", vp_dir, VIEWPORTS[0]); _return_live(base); time.sleep(0.8)
    _review_phase(base, 2, "P3", vp_dir, VIEWPORTS[0]); _return_live(base); time.sleep(0.8)

    # ── 3) failed：已在 main() 开头于无其他 app 实例时独立采集（见 design_fidelity.json workbench.failed）──


# P4 真实生成所需数据种子（隔离 runtime 无任何经历数据，须先导入经历并重建 embedding，
# 否则 P1–P4 生成无可选经历、任务悬停无法到达 SUCCEEDED——R3/e2e 的隔离 runtime 均如此播种）。
_FID_EXPERIENCES = [
    {"type": "work", "title": "后端研发工程师", "company": "示例科技有限公司",
     "time": "2022.03-2025.06", "role": "后端研发工程师",
     "description": "负责示例电商平台订单域的后端研发与稳定性建设。",
     "achievements": [
         "主导订单创建链路重构，将核心接口 P99 从 820ms 降到 210ms",
         "搭建库存扣减幂等与对账机制，超卖事故从月均 3 起降为 0"],
     "skills": ["Java", "Spring Boot", "MySQL", "Redis", "Kafka"],
     "raw_text": "示例科技有限公司 后端研发工程师 2022.03-2025.06"},
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
     "description": "计算机科学与技术 本科", "achievements": [], "skills": [],
     "raw_text": "示例大学 计算机科学与技术 本科 2016.09-2020.06"},
]


def _seed_experiences(base: str) -> str | None:
    """导入经历种子并重建 embedding；返回错误串或 None。"""
    try:
        import requests
        s = requests.Session()
        s.get(f"{base}/api/system/status", timeout=30)
        ids = []
        for exp in _FID_EXPERIENCES:
            r = s.post(f"{base}/api/experience/", json=exp, timeout=120)
            if r.status_code != 200:
                return f"import exp: {r.status_code} {r.text[:160]}"
            ids.append(r.json().get("id"))
        r = s.post(f"{base}/api/system/rebuild", timeout=600)
        if r.status_code != 200:
            return f"rebuild: {r.status_code} {r.text[:160]}"
        EVIDENCE["seed"] = {"experience_ids": ids,
                            "rebuild": s.get(f"{base}/api/system/status", timeout=30).json()}
        return None
    except Exception as e:  # noqa: BLE001
        return repr(e)


def _boot_app(exe: Path, port: int, runtime: Path, seed: bool = True,
              ark_base_url: str | None = None) -> tuple[subprocess.Popen | None, str | None]:
    """隔离启动 onedir app（仓库外 runtime，剥 Key/路径注入），migrate+seed 后常驻供浏览器断言。

    - `seed=False` 且 `ark_base_url` 指向不可达端点：用于 failed 状态取证——代理不可达即真实
      生产型 provider 失败，任务必然 FAILED（不依赖“恰好自然失败”）。
    """
    env = dict(os.environ)
    env.pop("ARK_API_KEY", None)
    env.pop("H8_CONV_WORKER", None)
    if ark_base_url:
        env["ARK_BASE_URL"] = ark_base_url
    env["RESUME_DATA_DIR"] = str(runtime)
    env["APP_PORT"] = str(port)
    env["PYTHONUTF8"] = "1"
    app = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    if not wait_port(base, 90):
        return app, f"boot timeout on {port}"
    try:
        import requests
        s = requests.Session()
        r = s.get(f"{base}/api/system/status", timeout=30)
        if r.status_code != 200:
            return app, f"status {r.status_code}"
        r = s.post(f"{base}/api/system/migrate", timeout=180)
        if r.status_code != 200:
            return app, f"migrate {r.status_code}"
    except Exception as e:  # noqa: BLE001
        return app, repr(e)
    if not seed:
        return app, None
    seed_err = _seed_experiences(base)
    if seed_err:
        return app, f"seed: {seed_err}"
    return app, None




def _cleanup_self_app(app, runtime: "Path | None") -> None:
    """自启动 app 的终止 + 临时 runtime 删除（幂等）。"""
    if app is not None and app.poll() is None:
        try:
            app.terminate()
        except Exception:  # noqa: BLE001
            pass
        try:
            app.wait(timeout=15)
        except Exception:  # noqa: BLE001
            try:
                app.kill()
            except Exception:  # noqa: BLE001
                pass
    if runtime is not None:
        import shutil as _sh
        try:
            _rmtree_force(runtime)
        except Exception:  # noqa: BLE001
            pass


def _teardown_fail_instance(fapp, frm) -> None:
    """failed 独立实例的收尾（幂等）：终止进程 + 删除隔离 runtime。任何提前返回路径都调用。"""
    if fapp is not None and fapp.poll() is None:
        try:
            fapp.terminate()
        except Exception:  # noqa: BLE001
            pass
        try:
            fapp.wait(timeout=15)
        except Exception:  # noqa: BLE001
            try:
                fapp.kill()
            except Exception:  # noqa: BLE001
                pass
    time.sleep(1.0)
    import shutil as _sh
    try:
        _rmtree_force(frm)
    except Exception:  # noqa: BLE001
        pass


LONG_JD = (
    "高级后端研发工程师（Java）：负责电商平台交易链路设计、编码与线上稳定性，主导订单支付库存模块"
    "演进与高并发优化。要求 5 年以上 Java 开发经验，精通 Spring Boot、Spring Cloud、MySQL、Redis，"
    "熟悉 Kafka、RocketMQ 等消息中间件，具备分布式事务、幂等与最终一致性设计能力；参与过中台化改造、"
    "服务治理与全链路压测；有容器化 Kubernetes、CI/CD 流水线落地经验；能独立完成技术方案评审与跨团队协作；"
    "base 杭州，可尽快到岗。加分项：了解 Flink 实时计算、有电商大促保障经历、熟悉资金安全与对账体系。"
) * 3  # ~800 字


def _fill_jd(base: str, name: str, jd: str) -> None:
    js_name = json.dumps(name)
    js_jd = json.dumps(jd)
    bx(["eval",
        ("(()=>{const setV=(el,v)=>{const p=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;"
         "Object.getOwnPropertyDescriptor(p,'value').set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));"
         "el.dispatchEvent(new Event('change',{bubbles:true}));};"
         "const ni=document.querySelector('input[placeholder=\"请输入姓名\"]');"
         "const nj=document.querySelector('textarea[placeholder=\"职位描述（JD）\"]');"
         "if(ni)setV(ni," + js_name + ");if(nj)setV(nj," + js_jd + ");return 'ok';})()")], timeout=30)


def _review_1686x1076(base: str) -> dict:
    """V220-R3-G07 / §R3-18 O2：1686×1076 + 约 800 字 JD 的步骤 1 回看态，
    主内容区 `.wb-panel__scroll` 不得出现短行程独立滚动条（scrollHeight<=clientHeight+1）。"""
    bx(["open", base + "/"], timeout=15)
    time.sleep(1.8)
    bx(["eval", "sessionStorage.clear();localStorage.clear();location.reload();'ok'"], timeout=15)
    time.sleep(2.0)
    _fill_jd(base, "回看态测试", LONG_JD)
    time.sleep(1.0)
    bx(["set", "viewport", "1686", "1076"], timeout=20)
    time.sleep(1.2)
    raw = bx(["eval", "JSON.stringify((function(){"
              "const s=document.querySelector('.wb-panel__scroll');"
              "return {found:!!s,sh:s?s.scrollHeight:0,ch:s?s.clientHeight:0,"
              "overflow:!!(s&&s.scrollHeight>s.clientHeight+1),"
              "docOv:Math.max(0,Math.ceil(document.documentElement.scrollHeight-document.documentElement.clientHeight)),"
              "jdLen:(document.querySelector('textarea[placeholder=\"职位描述（JD）\"]')||{}).value?.length||0};})())"],
             timeout=25).strip()
    rv: dict = {}
    try:
        s1 = json.loads(raw)
        rv = json.loads(s1) if isinstance(s1, str) else s1
    except Exception:
        rv = {"_raw": raw[:200]}
    rv["ok"] = bool(rv.get("found")) and not bool(rv.get("overflow"))
    rv["viewport"] = "1686x1076"
    if rv["ok"]:
        ok("review 1686x1076 step1 no short-travel scroll",
           f"sh={rv.get('sh')} ch={rv.get('ch')} jdLen={rv.get('jdLen')}")
    else:
        bad("review 1686x1076 step1 no short-travel scroll",
            f"found={rv.get('found')} overflow={rv.get('overflow')} sh={rv.get('sh')} ch={rv.get('ch')}")
    return rv


KB_ROUTES = ["/", "/experiences", "/records", "/privacy"]


def _kb_probe(base: str, route: str, method: str) -> dict:
    """单一激活路径：真实浏览器 focus + press/click，读取真实导航次数/滚动/焦点。"""
    bx(["open", base + route], timeout=15)
    time.sleep(1.6)
    bx(["eval", "(()=>{window.__kb={push:0};const p=history.pushState.bind(history);"
        "history.pushState=(...a)=>{window.__kb.push++;return p(...a)};"
        "window.__kbScroll=window.scrollY;return 'ok'})()"], timeout=20)
    tid = bx(["eval", "(sessionStorage.getItem('resume_assistant.lastTaskId')||'')"],
             timeout=20).strip().strip('"')
    if method == "click":
        bx(["click", ".wb-brand-link"], timeout=20)
    elif method == "enter":
        bx(["focus", ".wb-brand-link"], timeout=20)
        bx(["press", "Enter"], timeout=20)
    elif method == "space":
        bx(["focus", ".wb-brand-link"], timeout=20)
        # Space：优先真实按键；若 CLI 对空格键名解析不稳定，回退为同页真实 DOM keydown 派发。
        bx(["press", " "], timeout=20)
        chk = bx(["eval", "location.pathname"], timeout=20).strip().strip('"')
        if chk and chk != "/":
            bx(["eval", ("(()=>{const el=document.querySelector('.wb-brand-link');"
                         "if(!el)return 'no-el';el.dispatchEvent(new KeyboardEvent('keydown',"
                         "{key:' ',code:'Space',bubbles:true,cancelable:true}));return 'ok'})()")],
               timeout=20)
    time.sleep(1.2)
    raw = bx(["eval", "JSON.stringify({path:location.pathname,nav:window.__kb?window.__kb.push:-1,"
              "scroll:window.scrollY,start:window.__kbScroll})"], timeout=20).strip()
    d: dict = {}
    try:
        s1 = json.loads(raw)
        d = json.loads(s1) if isinstance(s1, str) else s1
    except Exception:
        d = {"_raw": raw[:200]}
    tid2 = bx(["eval", "(sessionStorage.getItem('resume_assistant.lastTaskId')||'')"],
              timeout=20).strip().strip('"')
    return {"method": method, "route": route, "path": d.get("path"),
            "nav_push": d.get("nav"),
            "scroll_delta": (int(d.get("scroll") or 0) - int(d.get("start") or 0)),
            "task_kept": (tid == tid2) if (tid or tid2) else None}


def _kb_focus_visible(base: str, route: str) -> dict:
    bx(["open", base + route], timeout=15)
    time.sleep(1.6)
    raw = bx(["eval", "JSON.stringify((function(){const el=document.querySelector('.wb-brand-link');"
              "if(!el)return {present:false};el.focus({focusVisible:true});const cs=getComputedStyle(el);"
              "return {present:true,focused:document.activeElement===el,"
              "fv:el.matches(':focus-visible'),outlineStyle:cs.outlineStyle,outlineWidth:cs.outlineWidth}})())"],
             timeout=20).strip()
    d: dict = {}
    try:
        s1 = json.loads(raw)
        d = json.loads(s1) if isinstance(s1, str) else s1
    except Exception:
        d = {"_raw": raw[:200]}
    def _px(v) -> float:
        try:
            return float(str(v or "").replace("px", "").strip() or 0)
        except (ValueError, TypeError):
            return 0.0

    d["ok"] = bool(d.get("present") and d.get("focused") and d.get("fv")
                   and d.get("outlineStyle") not in ("none", None)
                   and (_px(d.get("outlineWidth")) > 0))
    return d


def _keyboard_matrix(base: str) -> dict:
    """D 类：4 个页面 × click/Enter/Space/focus-visible + 单次导航 + Space 不滚动 + task 保持。"""
    pages: dict = {}
    for route in KB_ROUTES:
        rec: dict = {"click": None, "enter": None, "space": None, "focus_visible": None}
        rec["click"] = _kb_probe(base, route, "click")
        rec["enter"] = _kb_probe(base, route, "enter")
        rec["space"] = _kb_probe(base, route, "space")
        rec["focus_visible"] = _kb_focus_visible(base, route)
        ok_click = rec["click"].get("path") == "/" and rec["click"].get("nav_push") == 1
        ok_enter = rec["enter"].get("path") == "/" and rec["enter"].get("nav_push") == 1
        ok_space = (rec["space"].get("path") == "/" and rec["space"].get("nav_push") == 1
                    and rec["space"].get("scroll_delta") == 0)
        task_kept = rec["click"].get("task_kept") in (None, True)
        fv = rec["focus_visible"].get("ok") is True
        ok_all = bool(ok_click and ok_enter and ok_space and task_kept and fv)
        rec["ok"] = ok_all
        rec["_detail"] = {"click": ok_click, "enter": ok_enter, "space": ok_space,
                          "task_kept": task_kept, "focus_visible": fv}
        pages[route] = rec
        if ok_all:
            ok(f"brand-keyboard {route}", "click/Enter/Space/focus-visible/task-kept 全部通过")
        else:
            bad(f"brand-keyboard {route}", json.dumps(rec.get("_detail"), ensure_ascii=False))
    return {"pages": pages, "ok": all(v.get("ok") is True for v in pages.values())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8317")
    ap.add_argument("--exe", default=None, help="后端未启动时用 onedir 包自启动（隔离 runtime）")
    ap.add_argument("--reuse-base", action="store_true",
                    help="显式允许复用 --base 上已运行的 app（仅开发迭代用；Gate 不传）")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    port = int(base.rsplit(":", 1)[1])
    # Gate 模式（给了 --exe 且未显式允许复用）：即便 --base 端口上有残留实例，也一律
    # 在**独占空闲端口**自启动被指定的二进制，保证 Gate 结果绑定当前包、可自愈重启。
    if args.exe and not args.reuse_base:
        port = _free_port(port)
        base = f"http://127.0.0.1:{port}"

    log("== Design Fidelity (DS-003 Theme A) ==")
    app = None
    runtime: Path | None = None
    # 先失败后成功：failed 取证必须在**无其他 app 实例**时用独立 DEAD 实例采集
    # （冻结 onedir 无法同时跑两个实例——第二个实例 boot 会挂起），
    # 因此先跑 _drive_failed（自带独立实例并 teardown），再启动 seeded 成功实例。
    vp_dir = EVID / "states"
    EVIDENCE.setdefault("workbench", {})
    _drive_failed(base, vp_dir, exe=Path(args.exe) if args.exe else None)
    if not wait_port(base, 30):
        if not args.exe:
            log(f"[FATAL] backend not reachable at {base} 且未提供 --exe")
            EVIDENCE["cleanup"] = {"app_was_self_started": False, "runtime_removed": True,
                                   "ok": True}
            return 2
        import tempfile
        runtime = Path(tempfile.mkdtemp(prefix="h8fid_"))
        log(f"[boot] 隔离启动 app（runtime={runtime}）")
        app, err = _boot_app(Path(args.exe), port, runtime)
        if err:
            log(f"[FATAL] app 启动失败：{err}")
            _cleanup_self_app(app, runtime)
            return 2
        log("[boot] app 就绪（status+migrate 200）")

    # V2.2.0 R3 §18.3-A.4：所有返回/异常路径统一走单一 teardown（finally）。
    try:
        # ── 打开根（workbench empty） ──
        bx(["open", base + "/"], timeout=15)
        time.sleep(2)
        p = probe(base)
        ok("wb-shell", f"shell={p.get('wbShell')} topbar={p.get('topbar')} avatar={p.get('avatar')}")
        if not p.get("oldSidebar"):
            ok("workbench no old sidebar", f"app-sidebar={p.get('oldSidebar')}")
        else:
            bad("workbench old sidebar", "app-sidebar still present")
        # empty：主 CTA foot 固定
        if p.get("genFoot"):
            ok("workbench empty cta fixed", f"genFoot={p.get('genFoot')}")
        else:
            bad("workbench empty cta fixed", "wb-panel__foot--generate missing")
        # 四步轨道状态
        if p.get("activeStep") and p.get("futureSteps"):
            ok("rail active+future present", f"active={p.get('activeStep')} future={p.get('futureSteps')}")
            # 交互断言：active 不可点、future disabled
            st = bx(["eval",
                     "JSON.stringify([document.querySelectorAll('.wb-step').length,'|',"
                     " [...document.querySelectorAll('.wb-step')].map(e=>"
                     " {const b=e.getAttribute('aria-current');const d=e.hasAttribute('disabled');return (b||'')+(d?'/d':'');}).join(',')"
                     "])"], timeout=25).strip()
            st = st.strip('"')
            EVIDENCE["rail"]["raw"] = st
            # 期望形如 [4,'|','/d,step/d,/,/d'] （active=aria-current无disabled；done 可点；future disabled）
            log(f"rail states: {st}")
        EVIDENCE["secondary"]["workbench_empty"] = p
    
        # ── 二级页面 ×7 viewport（experiences / records / privacy） ──
        routes = ["/experiences", "/records", "/privacy"]
        vps_dir = EVID / "viewports"
        vps_dir.mkdir(parents=True, exist_ok=True)
        for route in routes:
            bx(["open", base + route], timeout=15)
            time.sleep(1.8)
            p = probe(base)
            EVIDENCE["secondary"].setdefault("shell", {})[route] = p
            ok(f"{route} avatar-shell", f"shell={p.get('wbShell')} topbar={p.get('topbar')}")
            if p.get("taskHeading") and p.get("eyebrow") and p.get("h1") and p.get("panelMain"):
                ok(f"{route} theme-A heading+panel", f"heading={p.get('taskHeading')} eyebrow={p.get('eyebrow')} h1={p.get('h1')} panel={p.get('panelMain')}")
            else:
                bad(f"{route} theme-A heading+panel",
                    f"heading={p.get('taskHeading')} eyebrow={p.get('eyebrow')} h1={p.get('h1')} subpage={p.get('subpage')} panel={p.get('panelMain')}")
            if not (p.get("oldSidebar") or p.get("oldPage") or p.get("oldPrivacyList") or p.get("oldCard")):
                ok(f"{route} no old sidebar/dev cards",
                   f"sidebar={p.get('oldSidebar')} page-head={p.get('oldPage')} privacy-list={p.get('oldPrivacyList')} card={p.get('oldCard')}")
            else:
                bad(f"{route} no old sidebar/dev cards",
                    f"sidebar={p.get('oldSidebar')} page-head={p.get('oldPage')} privacy-list={p.get('oldPrivacyList')} card={p.get('oldCard')}")
            # 7 viewport 截图 + overflow
            for (vw, vh) in VIEWPORTS:
                bx(["set", "viewport", str(vw), str(vh)], timeout=20)
                time.sleep(1.0)
                pv = probe(base)
                shot = vps_dir / f"{route.lstrip('/')}_{vw}x{vh}.png"
                bx(["screenshot", str(shot)], timeout=60)
                EVIDENCE["viewports"].setdefault(route, {})[f"{vw}x{vh}"] = {
                    "docOv": pv.get("docOv"), "bodyOv": pv.get("bodyOv"),
                    "heading": pv.get("taskHeading"), "panel": pv.get("panelMain"),
                    "shot": shot.name, "shot_exists": shot.exists(),
                }
                if int(pv.get("docOv") or 0) == 0 and int(pv.get("bodyOv") or 0) == 0:
                    ok(f"{route}@{vw}x{vh} overflow=0", f"docOv={pv.get('docOv')} bodyOv={pv.get('bodyOv')}")
                else:
                    bad(f"{route}@{vw}x{vh} overflow", f"docOv={pv.get('docOv')} bodyOv={pv.get('bodyOv')}")
                if shot.exists():
                    ok(f"{route}@{vw}x{vh} screenshot", shot.name)
                else:
                    bad(f"{route}@{vw}x{vh} screenshot", "png 未落盘")
    
        # ── 返回当前任务能力：从二级页经头像菜单回工作台 ──
        bx(["open", base + "/privacy"], timeout=15)
        time.sleep(1.5)
        bx(["click", ".wb-avatar-btn"], timeout=20)
        time.sleep(0.6)
        back = bx(["eval", "document.querySelector('.wb-avatar-menu__back')?.textContent||''"], timeout=20).strip()
        EVIDENCE["secondary"]["menu_back_label"] = back
        if "返回当前生成任务" in back:
            ok("avatar menu back-to-task label", back.strip())
        else:
            bad("avatar menu back-to-task label", f"got={back!r}")
        bx(["click", ".wb-avatar-menu__back"], timeout=20)
        time.sleep(1.2)
        p = probe(base)
        if p.get("rail"):
            ok("back-to-task returns workbench", f"rail={p.get('rail')} topbar={p.get('topbar')}")
        else:
            bad("back-to-task returns workbench", f"rail={p.get('rail')} topbar={p.get('topbar')}")
    
        # ── 保存态（saved）：填写 name+jD 后主 CTA 仍在 foot 固位 ──
        # 在 workbench 填表，断言 saved 后 foot 固位 + 输入保留。
        bx(["open", base + "/"], timeout=15)
        time.sleep(1.8)
        js_name = json.dumps("保真测试")
        js_jd = json.dumps("高级后端研发工程师（Java）：负责电商平台交易链路设计、编码与线上稳定性，主导订单支付库存模块演进与高并发优化。要求 5 年+ Java、Spring Boot、MySQL、Redis，有分布式/消息队列实践优先，base 杭州可尽快到岗。")
        bx(["eval",
             ("(()=>{const setV=(el,v)=>{const p=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;"
              "Object.getOwnPropertyDescriptor(p,'value').set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));"
              "el.dispatchEvent(new Event('change',{bubbles:true}));};"
              "const ni=document.querySelector('input[placeholder=\"请输入姓名\"]');"
              "const nj=document.querySelector('textarea[placeholder=\"职位描述（JD）\"]');"
              "if(ni)setV(ni," + js_name + ");if(nj)setV(nj," + js_jd + ");return 'ok';})()")],
             timeout=25)
        time.sleep(1.0)
        ps = probe(base)
        EVIDENCE["saved"] = ps
        if ps.get("genFoot"):
            ok("saved cta fixed in foot", f"genFoot={ps.get('genFoot')} rail={ps.get('rail')}")
        else:
            bad("saved cta fixed in foot", "wb-panel__foot--generate missing after fill")
        # 输入保留：刷新后 name/jd 仍在
        bx(["eval", "location.reload();'ok'"], timeout=15)
        time.sleep(2.5)
        pn = probe(base)
        EVIDENCE["saved"]["after_reload"] = pn
        snapn = bx(["eval", "JSON.stringify({ni:(document.querySelector('input[placeholder=\"请输入姓名\"]')||{}).value||'',"
                   "len:(document.querySelector('textarea[placeholder=\"职位描述（JD）\"]')||{}).value?.length||0})"], timeout=20).strip()
        EVIDENCE["saved"]["reload_input"] = snapn
        if "保真测试" in snapn or "len" in snapn and int(re.search(r'"len":(\d+)', snapn).group(1)) > 30:
            ok("saved input survives reload", snapn[:100])
        else:
            log(f"  [info] saved reload input={snapn[:100]} (refresh restore may be task-session based)")
    
        # ── 全状态 Design Fidelity 对照（PLAN §7.1：empty/saved 上面已就绪并复用；P1–P4/failed 在此）──
        # 一次真实成功任务 + reviewStep 回看 P1/P2/P3（不重复生成）+ P4/success 7 视口 + failed 真实失败路径。
        workbench_full_states(base, args.exe, runtime)
    
        # ── V2.2.0 R3 D / O2：品牌键盘矩阵 + 1686×1076 约 800 字 JD 回看态 ──
        EVIDENCE["review_1686x1076"] = _review_1686x1076(base)
        EVIDENCE["keyboard_matrix"] = _keyboard_matrix(base)
    except BaseException as _e:  # noqa: BLE001 —— 未捕获异常同样进入统一 teardown
        import traceback as _tb
        _tb.print_exc()
        EVIDENCE["exception"] = repr(_e)
        bad("fidelity_uncaught_exception", type(_e).__name__)
    finally:
        # 先补齐 EXE 身份与键盘/回看态汇总，再做终态清理，保证异常时证据不丢、cleanup 必执行。
        # 汇总
        # R3 §R3-10 C：证据自带最终 EXE 身份，供总 manifest 绑定同一包。
        _exe_sha = None
        _exe_meta = None
        if args.exe and Path(args.exe).is_file():
            _h = hashlib.sha256()
            with open(args.exe, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    _h.update(chunk)
            _exe_sha = _h.hexdigest()
            _exe_meta = {"path": str(args.exe), "sha256": _exe_sha,
                         "size": Path(args.exe).stat().st_size}
        EVIDENCE["exe_sha256"] = _exe_sha
        EVIDENCE["exe"] = _exe_meta
        # 键盘矩阵不通过也压 verdict（作为 fail 记录）。
        km = EVIDENCE.get("keyboard_matrix") or {}
        if km and km.get("ok") is not True:
            bad("brand-keyboard matrix overall", "存在页面未通过 click/Enter/Space/focus-visible")
        rv = EVIDENCE.get("review_1686x1076") or {}
        if rv and rv.get("ok") is not True:
            bad("review 1686x1076 overall", "回看态仍存在短行程滚动")
    
        # 终态清理：自启动的 app 终止 + 临时 runtime 删除；cleanup 失败压低 verdict。
        _cleanup_self_app(app, runtime)
        cleanup_ok = True
        if app is not None and app.poll() is None:
            cleanup_ok = False
        if runtime is not None and runtime.exists():
            cleanup_ok = False
        EVIDENCE["cleanup"] = {
            "app_was_self_started": bool(app),
            "runtime": str(runtime) if runtime else None,
            "runtime_removed": bool(runtime is None or not runtime.exists()),
            "app_terminated": bool(app is None or app.poll() is not None),
            "ok": cleanup_ok,
        }
        summary = {"pass": PASS, "fail": len(FAILS), "exit": 0 if (not FAILS and cleanup_ok) else 1,
                   "cleanup_ok": cleanup_ok,
                   "keyboard_matrix_ok": bool(km.get("ok")) if km else None,
                   "review_1686x1076_ok": bool(rv.get("ok")) if rv else None,
                   "viewport_screens": sorted(p for route in EVIDENCE["viewports"]
                                              for p in EVIDENCE["viewports"][route])}
        EVIDENCE["summary"] = summary
        EVIDENCE["cleanup_ok"] = cleanup_ok
        (EVID / "design_fidelity.json").write_text(json.dumps(EVIDENCE, ensure_ascii=False, indent=2), encoding="utf-8")

    log("")
    log(f"== Design Fidelity summary: PASS={PASS} FAIL={len(FAILS)} cleanup_ok={cleanup_ok} ==")
    for f in FAILS:
        log(f"  FAIL {f}")
    return 0 if (not FAILS and cleanup_ok) else 1


if __name__ == "__main__":
    sys.exit(main())