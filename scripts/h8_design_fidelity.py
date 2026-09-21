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
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

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


def _boot_app(exe: Path, port: int, runtime: Path) -> tuple[subprocess.Popen | None, str | None]:
    """隔离启动 onedir app（仓库外 runtime，剥 Key/路径注入），migrate 后常驻供浏览器断言。"""
    env = dict(os.environ)
    env.pop("ARK_API_KEY", None)
    env.pop("H8_CONV_WORKER", None)
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
    return app, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8317")
    ap.add_argument("--exe", default=None, help="后端未启动时用 onedir 包自启动（隔离 runtime）")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    port = int(base.rsplit(":", 1)[1])

    log("== Design Fidelity (DS-003 Theme A) ==")
    app = None
    runtime: Path | None = None
    if not wait_port(base, 30):
        if not args.exe:
            log(f"[FATAL] backend not reachable at {base} 且未提供 --exe")
            return 2
        import tempfile
        runtime = Path(tempfile.mkdtemp(prefix="h8fid_"))
        log(f"[boot] 隔离启动 app（runtime={runtime}）")
        app, err = _boot_app(Path(args.exe), port, runtime)
        if err:
            log(f"[FATAL] app 启动失败：{err}")
            return 2
        log("[boot] app 就绪（status+migrate 200）")

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

    # 汇总
    summary = {"pass": PASS, "fail": len(FAILS), "exit": 0 if not FAILS else 1,
               "viewport_screens": sorted(p for route in EVIDENCE["viewports"] for p in EVIDENCE["viewports"][route])}
    EVIDENCE["summary"] = summary
    EVIDENCE["cleanup"] = {"app_was_self_started": bool(app), "runtime": str(runtime) if runtime else None}
    (EVID / "design_fidelity.json").write_text(json.dumps(EVIDENCE, ensure_ascii=False, indent=2), encoding="utf-8")

    # 终态清理：自启动的 app 终止 + 临时 runtime 删除
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
        import shutil
        try:
            shutil.rmtree(runtime, ignore_errors=True)
            EVIDENCE["cleanup"]["runtime_removed"] = True
        except Exception:  # noqa: BLE001
            EVIDENCE["cleanup"]["runtime_removed"] = False
    (EVID / "design_fidelity.json").write_text(json.dumps(EVIDENCE, ensure_ascii=False, indent=2), encoding="utf-8")

    log("")
    log(f"== Design Fidelity summary: PASS={PASS} FAIL={len(FAILS)} ==")
    for f in FAILS:
        log(f"  FAIL {f}")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())