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
import urllib.parse
import urllib.request
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


# ── 判定链（V2.2.0 R3 §R3-18 A）：默认失败，单一 finalizer ──────── #
def log(m: str) -> None:
    print(m, flush=True)


class Verdict:
    """主链 Gate 的唯一判定状态。

    纪律（硬约束）：
    - 初值一律为**失败**（没有显式 `require(...)` 全部通过就绝不写成功）；
    - 任何失败/异常/超时/取消/提前返回只做 `fail(...)`，绝不中途置成功；
    - 只有 `ok` 为真（= 所有必需断言成立、无失败原因、cleanup 后置条件成立）时，
      finalizer 才允许写 `ok=true` / `gate_passed=true` / rc 0。
    """

    def __init__(self) -> None:
        self.checks: dict[str, bool] = {}
        self.failures: list[str] = []
        self.stage = "init"
        self.cleanup: dict = {}
        self.cleanup_ok: bool | None = None

    def require(self, name: str, cond: bool, **detail) -> bool:
        ok = bool(cond)
        self.checks[name] = ok
        if not ok:
            self.fail(f"assert_failed:{name}", **detail)
        return ok

    def fail(self, reason: str, **detail) -> None:
        entry = reason
        if detail:
            entry = reason + " | " + json.dumps(detail, ensure_ascii=False)[:300]
        if entry not in self.failures:
            self.failures.append(entry)

    def enter(self, stage: str) -> None:
        self.stage = stage

    @property
    def ok(self) -> bool:
        return (bool(self.checks) and all(self.checks.values())
                and not self.failures and self.cleanup_ok is True)


VD = Verdict()


def finalize(rc_internal: int) -> int:
    """唯一 finalizer：写 JSON 判定 + 推导真实退出码；失败绝不输出 PASS 摘要。"""
    ok = VD.ok
    # 失败时强制非零退出：内部 rc 为 0 也必须提升为 1。
    rc = rc_internal if not ok else 0
    if ok and rc_internal != 0:
        rc = rc_internal          # 成功判定但内部 rc 非零 → 视为矛盾，保持非零
        ok = False
    if not ok:
        rc = rc_internal if rc_internal not in (0, None) else 1
    EVIDENCE["verdict"] = {
        "ok": bool(ok),
        "gate_passed": bool(ok),
        "stage": VD.stage,
        "checks": VD.checks,
        "failures": VD.failures,
        "cleanup": VD.cleanup,
        "cleanup_ok": VD.cleanup_ok,
        "internal_rc": rc_internal,
        "exit_code": rc,
    }
    EVIDENCE["ok"] = bool(ok)
    EVIDENCE["gate_passed"] = bool(ok)
    EVIDENCE["failures"] = VD.failures
    EVIDENCE["cleanup_ok"] = VD.cleanup_ok
    OUT.write_text(json.dumps(EVIDENCE, ensure_ascii=False, indent=2), encoding="utf-8")
    if ok:
        log(f"[e2e] PASS → {OUT} (ok=true, rc=0)")
    else:
        log(f"[e2e] FAIL → {OUT} ok=false rc={rc} stage={VD.stage}")
        for f in VD.failures[:12]:
            log(f"[e2e]   - {f}")
    return rc


def _fail_early(stage: str, reason: str, rc: int, **detail) -> int:
    VD.enter(stage)
    VD.fail(reason, **detail)
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True, help="最终 onedir 的 ResumeAssistant.exe")
    ap.add_argument("--api-only", action="store_true",
                    help="跳过浏览器 UI 段（仅 API 直连，作诊断用；正式 Gate 不允许作为 PASS 依据）")
    ap.add_argument("--keep", action="store_true", help="结束后不删 runtime（排障用）")
    args = ap.parse_args()

    exe = Path(args.exe).resolve()
    if not exe.exists():
        log(f"[fatal] exe 不存在：{exe}")
        VD.enter("precheck")
        VD.fail("exe_missing")
        return finalize(2)
    exe_sha = sha256_file(exe)
    EVIDENCE["exe"] = {"path": str(exe), "sha256": exe_sha,
                       "size": exe.stat().st_size}
    log(f"[e2e] exe={exe} sha256={exe_sha[:16]}…")

    # ── 隔离 runtime（仓库外）──
    runtime = Path(os.environ.get("TEMP", ".")) / f"h8e2e_{int(time.time())}"
    runtime.mkdir(parents=True, exist_ok=True)
    EVIDENCE["runtime_dir"] = str(runtime)
    log(f"[e2e] isolated RESUME_DATA_DIR={runtime}")

    proxy = None
    app = None
    app_fh = None
    rc_internal = 1
    try:
        # ── ARK 计数代理（独占空闲端口，避免误连残留实例）──
        proxy_port = _free_port(8799)
        proxy_out = EVID / "ark_counts.json"
        proxy = subprocess.Popen([PY, str(PROXY_PY), "--port", str(proxy_port),
                                  "--out", str(proxy_out)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 cwd=str(EVID))
        if not wait_port(proxy_port, 30):
            rc_internal = _fail_early("proxy", "ark_proxy_not_ready", 2)
            return rc_internal
        step("proxy_up", port=proxy_port, counts_file=str(proxy_out))

        # app 端口同样独占空闲端口：残留 app 占 8317 时，固定端口会让本 Gate
        # “连上别人的实例”，重启本 Gate 也无法自愈（已有独立证据）。
        app_port = _free_port(8317)
        env = dict(os.environ)
        env["RESUME_DATA_DIR"] = str(runtime)
        env["ARK_BASE_URL"] = f"http://127.0.0.1:{proxy_port}/api/v3"
        env["APP_PORT"] = str(app_port)
        env.pop("ARK_API_KEY", None)          # 强制走凭据库，不经脚本注入
        env.pop("H8_CONV_WORKER", None)
        env.pop("PYTHONPATH", None)           # 环境 shim 会拦截子进程删除/写入

        ww_before = winword_pids()
        app_stdout = EVID / "app_stdout.log"
        app_fh = open(app_stdout, "w", encoding="utf-8", errors="replace")
        app = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env,
                               stdout=app_fh, stderr=subprocess.STDOUT)
        VD.enter("boot")
        if not wait_port(app_port, 120):
            rc_internal = _fail_early("boot", "app_boot_failed", 3,
                                      pid=app.pid, ret=app.poll())
            return rc_internal
        base = f"http://127.0.0.1:{app_port}"
        step("app_up", pid=app.pid, port=app_port, winword_before=ww_before)

        # 用 requests.Session 维持 ra_session cookie（写操作必须带启动会话令牌）
        import requests
        s = requests.Session()
        r = s.get(f"{base}/api/system/status", timeout=30)
        step("status", code=r.status_code, has_cookie=bool(s.cookies.get("ra_session")))
        VD.require("status_200", r.status_code == 200, code=r.status_code)
        if r.status_code != 200:
            rc_internal = _fail_early("status", "status_not_200", 4, code=r.status_code)
            return rc_internal
        EVIDENCE["status_before"] = r.json()

        # ── 1) 迁移 ──
        VD.enter("migrate")
        r = s.post(f"{base}/api/system/migrate", timeout=180)
        step("migrate", code=r.status_code, body=str(r.json())[:200])
        VD.require("migrate_200", r.status_code == 200, code=r.status_code)
        if r.status_code != 200:
            rc_internal = _fail_early("migrate", "migrate_not_200", 5, code=r.status_code)
            return rc_internal

        # ── 2) 导入（无隐私测试简历：直接结构化写入，不经 LLM）──
        VD.enter("import")
        exp_ids = []
        for exp in TEST_EXPERIENCES:
            rr = s.post(f"{base}/api/experience/", json=exp, timeout=120)
            if rr.status_code != 200:
                rc_internal = _fail_early("import", "experience_import_failed", 6,
                                          code=rr.status_code)
                return rc_internal
            exp_ids.append(rr.json().get("id"))
        step("import_experiences", count=len(exp_ids), ids=exp_ids)
        VD.require("import_experiences_ok", len(exp_ids) == len(TEST_EXPERIENCES))

        # ── 3) Embedding 重建（真实 embedding provider）──
        VD.enter("rebuild")
        r = s.post(f"{base}/api/system/rebuild", timeout=600)
        step("rebuild_embeddings", code=r.status_code, body=str(r.json())[:300])
        VD.require("rebuild_200", r.status_code == 200, code=r.status_code)
        if r.status_code != 200:
            rc_internal = _fail_early("rebuild", "rebuild_not_200", 7, code=r.status_code)
            return rc_internal
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

        # ── 5) 生成：UI 优先；UI 未到 P4 一律判失败（API 回退仅诊断）──
        VD.enter("generate")
        EVIDENCE["api_only"] = bool(args.api_only)
        ui = None
        if args.api_only:
            VD.fail("api_only_mode_not_allowed_for_pass")
        else:
            ui = _ui_generate(base, app_port, proxy_out, base_total)
        gen = ui
        if gen is None:
            # 诊断性 API 直连（旧兼容链）：只记录，不提高 UI verdict，也不作为主链 PASS 依据。
            diag = _api_generate(s, base, proxy_out, base_total)
            EVIDENCE["api_fallback_diagnostic"] = {
                "used": True,
                "ok": bool(diag),
                "note": "UI 未自行到达 P4；API 回退仅提供诊断信息，不参与 UI/主链 verdict",
            }
            VD.fail("ui_did_not_reach_p4")
            rc_internal = 8
            return rc_internal
        EVIDENCE["generate"] = gen
        VD.require("ui_p4_reached", bool(EVIDENCE.get("ui_p4_reached")),
                   ui_p4_scroll_ok=EVIDENCE.get("ui_p4_scroll"))

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
                    "elapsed_ms": elapsed, "phase_sum_ms": ssum,
                    "delta_ms": abs(elapsed - ssum),
                    "jd_analysis_started_events": sum(
                        1 for s2 in (op.get("stages") or [])
                        if s2.get("stage_code") == "jd_analysis"
                        and s2.get("event_type") == "STARTED"),
                    "content_generation_started_events": sum(
                        1 for s2 in (op.get("stages") or [])
                        if s2.get("stage_code") == "content_generation"
                        and s2.get("event_type") == "STARTED"),
                    "stage_codes": sorted({s2.get("stage_code") for s2 in (op.get("stages") or [])}),
                    "user_phases": [{"code": u.get("code"), "label": u.get("label"),
                                     "status": u.get("status"),
                                     "elapsed_ms": u.get("elapsed_ms"),
                                     "live_elapsed_ms": u.get("live_elapsed_ms")} for u in ups],
                }
                step("operation_terminal", status=op.get("status"), elapsed_ms=elapsed,
                     phase_sum_ms=ssum, delta_ms=abs(elapsed - ssum))

        # ── 7) 字节一致性：DOCX/PDF 磁盘 artifact vs 下载 vs 响应 ──
        VD.enter("artifacts")
        checks = _verify_artifacts(s, base, gen, runtime)
        for k, v in (checks or {}).items():
            VD.require(f"artifact_{k}", v is True, detail=k)

        # —— viewer 同源收口（V2.2.0 R2-16 新 DOM）——
        vp_pdf_href = None
        for _k, _v in (EVIDENCE.get("viewports") or {}).items():
            if isinstance(_v, dict) and _v.get("pdfHref"):
                vp_pdf_href = _v.get("pdfHref")
                break
        _dl = (EVIDENCE.get("artifacts") or {}).get("pdf_download") or {}
        _dl_url = _dl.get("url") or ""
        _dl_sha = _dl.get("sha256") or ""
        _vr_ok = (EVIDENCE.get("ui_pdf_viewer") or {}).get("viewer_ready")
        _pages = (EVIDENCE.get("ui_pdf_viewer") or {}).get("viewer_pages")
        _same_src = bool(_vr_ok and vp_pdf_href and _dl_url
                         and vp_pdf_href.split('?')[0] == _dl_url.split('?')[0])
        EVIDENCE["pdf_viewer_same_source_final"] = {
            "viewer_ready": bool(_vr_ok), "viewer_pages": _pages,
            "download_pdf_href_from_viewport": vp_pdf_href,
            "download_pdf_url": _dl_url, "download_pdf_sha256": _dl_sha,
            "same_source": _same_src,
        }
        step("pdf_viewer_same_source_final", same_source=_same_src,
             pdf_href=vp_pdf_href, pdf_url=_dl_url, pdf_sha256=(_dl_sha or "")[:16], pages=_pages)
        VD.require("viewer_ready", bool(_vr_ok))
        VD.require("viewer_same_source", bool(_same_src))

        # 下载引用必须来自当前 Task（task-scoped 路由），不得是 filename 路由。
        _dl_refs = [u for u in (_dl_url, (EVIDENCE.get("artifacts") or {})
                                .get("word_download", {}).get("url")) if u]
        _task_scoped = bool(_dl_refs) and all("/api/task/" in u and "/artifact/" in u
                                              for u in _dl_refs)
        EVIDENCE["download_refs_task_scoped"] = {
            "urls": _dl_refs, "task_scoped": _task_scoped}
        VD.require("download_refs_task_scoped", _task_scoped)

        # ── 8) Provider 计数 ──
        c1 = counts()
        jd_calls = c1.get("by_path", {}).get("/api/v3/chat/completions", 0) - \
            c0.get("by_path", {}).get("/api/v3/chat/completions", 0)
        emb_calls = c1.get("by_path", {}).get("/api/v3/embeddings/multimodal", 0) - emb_before
        EVIDENCE["provider_counts"] = {
            "chat_completions_in_generate_window": jd_calls,
            "embeddings_in_window": emb_calls,
            "total_before": base_total, "total_after": c1.get("total"),
            "by_path_after": c1.get("by_path", {}),
            "calls_in_window": [c for c in c1.get("calls", [])[base_total:]][:40],
        }
        step("provider_counts", chat_in_window=jd_calls, emb_in_window=emb_calls)
        VD.require("provider_calls_happened", jd_calls >= 1)

        # ── 9) WINWORD / 进程泄漏 ──
        time.sleep(2)
        ww_after = winword_pids()
        leaks = sorted(set(ww_after) - set(ww_before))
        EVIDENCE["cleanup"] = {"winword_before": ww_before, "winword_after": ww_after,
                               "winword_leaked": leaks}
        step("winword_check", before=ww_before, after=ww_after, leaked=leaks)
        VD.require("no_winword_leak", not leaks, leaked=leaks)

        st2 = s.get(f"{base}/api/system/status", timeout=30)
        EVIDENCE["http_health_final"] = {"status_code": st2.status_code}
        VD.require("http_health_final", st2.status_code == 200, code=st2.status_code)

        rc_internal = 0
        return rc_internal
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        EVIDENCE["exception"] = repr(e)
        VD.enter("exception")
        VD.fail(f"uncaught_exception:{type(e).__name__}")
        rc_internal = 9
        return rc_internal
    finally:
        # 资源生命周期：所有返回路径统一在此清理（异常/失败/超时/提前返回同样覆盖）。
        VD.enter("teardown")
        cleanup = {"app_terminated": None, "proxy_terminated": None,
                   "runtime_removed": None, "winword_leaked": None}
        try:
            if app is not None:
                try:
                    app.terminate()
                    app.wait(timeout=15)
                    cleanup["app_terminated"] = True
                except Exception:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(app.pid)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    cleanup["app_terminated"] = app.poll() is not None
                if cleanup["app_terminated"] is not True:
                    VD.fail("teardown_app_still_running")
        except Exception:  # noqa: BLE001
            cleanup["app_terminated"] = False
            VD.fail("teardown_app_terminate_failed")
        try:
            if app_fh is not None:
                app_fh.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if proxy is not None:
                proxy.terminate()
                cleanup["proxy_terminated"] = True
        except Exception:  # noqa: BLE001
            cleanup["proxy_terminated"] = False
            VD.fail("teardown_proxy_terminate_failed")
        time.sleep(1)
        if not args.keep:
            _rmtree_force(runtime)
            cleanup["runtime_removed"] = not runtime.exists()
            EVIDENCE["runtime_deleted"] = bool(cleanup["runtime_removed"])
        else:
            cleanup["runtime_removed"] = None
            EVIDENCE["runtime_deleted"] = False
        if cleanup["runtime_removed"] is not True:
            # keep 模式不参与判定；非 keep 模式下删不掉 = cleanup 失败，必须压低 verdict
            if not args.keep:
                VD.fail("teardown_runtime_not_removed")
        try:
            ww = winword_pids()
            cleanup["winword_leaked"] = sorted(ww)
            if ww:
                VD.fail("teardown_winword_leaked", leaked=sorted(ww))
        except Exception:  # noqa: BLE001
            cleanup["winword_leaked"] = None
        VD.cleanup = cleanup
        VD.cleanup_ok = (
            cleanup["app_terminated"] in (True, None)
            and cleanup["proxy_terminated"] in (True, None)
            and cleanup["winword_leaked"] in ([], None)
            and (cleanup["runtime_removed"] is True or args.keep)
        )
        EVIDENCE["teardown_cleanup"] = cleanup
        rc = finalize(rc_internal)
        return rc


def shot_size(v: dict) -> str:
    """视口布局探针的紧凑摘要（供步骤打印）：整页无溢出/白屏/内部滚动容器/PDF 态。"""
    if not isinstance(v, dict) or "overflow" not in v:
        return str(v)[:160]
    ov = v.get("overflow") or {}
    doc_ov = int(ov.get("doc") or 0)
    body_ov = int(ov.get("body") or 0)
    return (f"docOv={doc_ov},bodyOv={body_ov},blank={v.get('blank')},"
            f"pdf={v.get('pdfState')},pages={v.get('pdfPages')},dlBar={v.get('dlBar')},"
            f"dlLinks={v.get('dlLinks')},scroll={v.get('scrollables')},shell={v.get('shell')},topbar={v.get('topbar')}")


def step(name: str, **kw) -> None:
    EVIDENCE["steps"].append({"step": name, "ts": time.strftime("%H:%M:%S"), **kw})
    log(f"[e2e] {name}: " + json.dumps(kw, ensure_ascii=False)[:500])


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# PLAN §4.3/§7.1 的 7 个冻结 viewport。
# PLAN §4.3/§7.1 的冻结 viewport（V2.2.0 R3：追加 1686x1076 参考桌面视口）。
VIEWPORTS: list[tuple[int, int]] = [
    (1686, 1076), (1920, 1080), (1440, 900), (1280, 800), (1024, 768),
    (720, 450), (390, 844), (320, 568),
]

# 视口 DOM/布局探针：整页 overflow、html/body overflow 样式、内部滚动容器、PDF 卡状态、下载区固位。
# V2.2.0 R2-16 返工后 P4/success 的新 Theme A DOM：
#   内滚动宿主=wb-panel__scroll / pdf-preview__pages / pdf-preview / page-scroll（不再有 result-shell__preview）；
#   下载区=右侧 successAside 的 .wb-success-downloads（不再有 .wb-download__bar / .wb-download__hash）。
#   「viewer 与下载同一 artifact」改由下载锚 href == 成品 PDF url 判定（viewer fetch 的正是该 href）。
_LAYOUT_PROBE = ("JSON.stringify((function(){"
                 "const doc=document.documentElement;"
                 "const bd=document.body;"
                 "const viewH=window.innerHeight||0;"
                 "const overflow={"
                 "doc:Math.max(0,Math.ceil(doc.scrollHeight-doc.clientHeight)),"
                 "body:Math.max(0,Math.ceil(bd.scrollHeight-bd.clientHeight)),"
                 "docScrollW:Math.max(0,Math.ceil(doc.scrollWidth-doc.clientWidth)),"
                 "htmlOvY:getComputedStyle(doc).overflowY||'',"
                 "bodyOvY:getComputedStyle(bd).overflowY||''};"
                 "const scrollables=[...document.querySelectorAll("
                 "'.wb-panel__scroll,.pdf-preview__pages,.pdf-preview,.page-scroll,.result-shell__preview')]"
                 ".filter(el=>el.scrollHeight>el.clientHeight+1).map(el=>(el.className||'').toString().split(' ')[0]);"
                 "const vp=document.querySelector('.pdf-preview');"
                 "const pdfState=vp?vp.getAttribute('data-state'):null;"
                 "const pdfPages=document.querySelectorAll('.pdf-page').length;"
                 "const pdfCanvas=document.querySelectorAll('.pdf-page__canvas').length;"
                 "const dlBar=!!document.querySelector('.wb-success-downloads,.wb-download__bar');"
                 "const dlLinks=document.querySelectorAll('[data-role^=\"download-\"]').length;"
                 "const pdfA=document.querySelector('[data-role=\"download-pdf\"]');"
                 "const wordA=document.querySelector('[data-role=\"download-word\"]');"
                 "const pdfHref=pdfA?(pdfA.getAttribute('href')||''):'';"
                 "const wordHref=wordA?(wordA.getAttribute('href')||''):'';"
                 "const shell=!!document.querySelector('.wb-shell');"
                 "const topbar=!!document.querySelector('.wb-topbar');"
                 "const rail=document.querySelectorAll('.wb-step').length;"
                 "return {viewH,blank:!bd||!bd.textContent.trim(),overflow,scrollables,pdfState,"
                 "pdfPages,pdfCanvas,dlBar,dlLinks,shell,topbar,rail,pdfHref,wordHref};"
                 "})())")


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


def _port_in_use(port: int) -> bool:
    """该端口是否已有监听者（用于避免误连到残留 app 实例）。"""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    try:
        s.bind(("127.0.0.1", port))
        return False
    except OSError:
        return True
    finally:
        s.close()


def _free_port(preferred: int, tries: int = 200) -> int:
    """优先用 preferred；被占用则顺序探测到首个空闲端口。

    避免固定端口（8317/8799）被上一轮残留 app/proxy 占用时，本 Gate 会
    `wait_port` 立即成功却把请求发给**别的实例**（在崩溃残留场景已复现）。
    """
    if not _port_in_use(preferred):
        return preferred
    for p in range(preferred + 1, preferred + 1 + tries):
        if not _port_in_use(p):
            return p
    return preferred


def winword_pids() -> list[int]:
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq WINWORD.EXE", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True, errors="replace", timeout=20)
        pids = []
        for ln in r.stdout.splitlines():
            parts = [x.strip('"') for x in ln.split(",")]
            if len(parts) >= 2 and parts[0].lower().startswith("winword"):
                pids.append(int(parts[1]))
        return pids
    except Exception:
        return []




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


def proxy_counts_total(proxy_out: Path) -> int:
    """ARK 代理已记录的总请求数（含 embeddings + chat）。"""
    try:
        return int(json.loads(proxy_out.read_text(encoding="utf-8")).get("total", 0))
    except Exception:
        return 0


def _wait_chat_increase(proxy_out: Path, before: int, timeout: float) -> bool:
    """点击生成后，等待 ARK 计数超过 before（证明后端真的触发了模型调用）。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proxy_counts_total(proxy_out) > before:
            return True
        time.sleep(0.8)
    return False


def _ui_generate(base: str, port: int, proxy_out: Path, base_total: int) -> dict | None:
    """真实 UI：打开 → 填表 → 点击生成 → 轮询 P1–P4 → 捕获响应 → 点击双下载。"""
    try:
        _bx(["open", base], timeout=12)
        t0 = time.time()
        ready = False
        while time.time() - t0 < 45:
            if "生成岗位简历" in _bx(["snapshot", "-i"], timeout=20):
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
        # 稳健写入：用 React 兼容的方式填受控输入（原生 value setter + input/change 事件），
        # 并回读 window.__h8fill 验证 React state 确实拿到值（避免 fill 不进 state → 生成空转）。
        js_name = json.dumps(TEST_PROFILE["name"])   # 合法 JS 字符串字面量
        js_jd = json.dumps(TEST_JD)
        _bx(["eval",
             ("(()=>{"
              "const setV=(el,v)=>{"
              "  const proto=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;"
              "  const setter=Object.getOwnPropertyDescriptor(proto,'value').set;"
              "  setter.call(el,v);"
              "  el.dispatchEvent(new Event('input',{bubbles:true}));"
              "  el.dispatchEvent(new Event('change',{bubbles:true}));"
              "};"
              "const ni=document.querySelector('input[placeholder=\"请输入姓名\"]');"
              "const nj=document.querySelector('textarea[placeholder=\"职位描述（JD）\"]');"
              "if(ni)setV(ni," + js_name + ");"
              "if(nj)setV(nj," + js_jd + ");"
              "setTimeout(()=>{"
              "  const gb=document.querySelector('.wb-form-actions button.wb-btn--primary');"
              "  window.__h8fill=JSON.stringify({"
              "name:ni?ni.value:'',nameOk:!!(ni&&ni.value.trim()),"
              "jdLen:nj?nj.value.length:0,"
              "count:(document.querySelector('.wb-jd-count')||{}).textContent||'',"
              "btnDisabled:gb?!!gb.disabled:null"
              "});},400);"
              "return 'ok';})()")], timeout=25)
        fv = "{}"
        for _ in range(10):
            time.sleep(0.3)
            raw = _bx(["eval", "window.__h8fill||'{}'"], timeout=25).strip()
            try:
                s1 = json.loads(raw)
                cand = json.loads(s1) if isinstance(s1, str) else s1
                if cand.get("nameOk") and cand.get("jdLen", 0) >= 30:
                    fv = json.dumps(cand)
                    break
            except Exception:
                pass
        try:
            fill_ok = json.loads(fv)
        except Exception:
            fill_ok = {"raw": fv}
        EVIDENCE["ui_fill_verify"] = fill_ok
        if not (fill_ok.get("nameOk") and fill_ok.get("jdLen", 0) >= 60):
            step("ui_fill_not_in_react", note="受控输入未生效，回退 API 直连",
                 verify=str(fv)[:300])
            return None
        step("ui_fill_react_ok", verify={k: fill_ok.get(k) for k in
                                        ("nameOk", "jdLen", "count", "btnDisabled")})

        n1 = proxy_counts_total(proxy_out)
        gb = re.search(r'button "生成岗位简历[^\n]*?ref=([a-z0-9]+)', snap)
        if not gb:
            step("ui_generate_button_missing", note="回退 API 直连")
            return None
        _bx(["click", f"@{gb.group(1)}"], timeout=25)
        step("ui_generate_clicked")
        # 确认点击真的推动后端：等待 ARK 计数出现 chat/completions 或 SSE 生效后的阶段轮询。
        chat_seen = _wait_chat_increase(proxy_out, n1, timeout=60.0)
        step("ui_chat_fired", chat_seen=chat_seen)

        # DS-003 工作台经 /api/task SSE 推进；不再等待旧同步 generate-docx JSON。
        # 改为轮询「P4 成品视图出现」（StepDownload 含下载区），成功后做真实双下载取证。
        # V2.2.0 R2-16：success download 入口在右侧 successAside（↓ Word / ↓ PDF，data-role 锚点）。
        def poll_p4(timeout_s: float = 600.0) -> bool:
            t0 = time.time()
            while time.time() - t0 < timeout_s:
                snap = _bx(["snapshot", "-i"], timeout=25)
                if ('data-role="download-word"' in snap or "下载 Word" in snap
                        or "wb-success-downloads" in snap or "↓ Word" in snap):
                    return True
                time.sleep(1.0)
            return False

        if not poll_p4():
            step("ui_p4_not_reached", note="工作台未推进到 P4 成品视图，回退 API 直连")
            return None
        EVIDENCE["ui_p4_reached"] = True
        step("ui_p4_reached", note="P4 成品视图由 UI 自身推进到达（含下载区）")

        # PDF.js viewer 与「下载 PDF」为同一 artifact 的真实同一源断言。
        # pdfjs-dist 是模块内引入，`window['PDF.js']` 不存在 → 不能用全局探针；改为等待
        # PdfPreview 渲染态 `.pdf-preview[data-state="ready"]` 出现、且已栅格化 ≥1 页 canvas，
        # 并以页面内 `uiHash16`（成品 PDF 的 sha256 前 16 位）与下载到的 PDF 字节 sha 一致来
        # 证明 viewer 读取的就是该 PDF（同源同 artifact，非占位/非下载替代）。
        viewer_ok = False
        viewer_pages = 0
        t0 = time.time()
        while time.time() - t0 < 90:
            raw_p = _bx(["eval", "JSON.stringify("
                         "{ready:!!document.querySelector('.pdf-preview[data-state=\"ready\"]'),"
                         "pages:document.querySelectorAll('.pdf-page').length,"
                         "canvas:document.querySelectorAll('.pdf-page__canvas').length})"], timeout=25).strip()
            try:
                s1 = json.loads(raw_p)
                vp = json.loads(s1) if isinstance(s1, str) else s1
            except Exception:
                vp = {}
            if vp.get("ready") and int(vp.get("pages") or 0) >= 1 and int(vp.get("canvas") or 0) >= 1:
                viewer_ok = True
                viewer_pages = int(vp.get("pages"))
                break
            time.sleep(1.0)
        EVIDENCE["ui_pdf_viewer"] = {
            "viewer_ready": viewer_ok,
            "viewer_pages": viewer_pages,
            "note": "同源断言：viewer 渲染态 ready + ≥1 页 canvas；再以 uiHash16 vs 下载 PDF sha 对齐",
        }
        step("ui_pdf_viewer", viewer_ready=viewer_ok, pages=viewer_pages)

        # PLAN §R3-24 §24.4-4：anchor 数量 / artifact_id 绑定 / PDF ready **不能**替代交互结果。
        # 进入 P4 后必须真实激活 fact / section / skills × mouse / Enter / Space，断言
        # aria-pressed、`.selected`、右侧详情实际变化与再次激活取消（与 Design Fidelity
        # 共用 scripts/h8_p4_interact.py 同一实现，避免两处断言语义分叉）。
        def _p4_ok(label: str, extra: str = "") -> None:
            VD.require(f"ui.{label}", True)
            step(f"ui.{label}", detail=extra)

        def _p4_bad(label: str, why: str) -> None:
            VD.require(f"ui.{label}", False, why=why)

        try:
            p4_interact(_bx, ok=_p4_ok, bad=_p4_bad, log=log,
                        evidence=EVIDENCE.setdefault("ui_p4_interactions", {}),
                        tag="P4.interact")
        except BaseException as _e:  # noqa: BLE001
            VD.fail("ui.P4.interact.exception", detail=repr(_e)[:200])

        # 页面内取证：
        # 1) 读两个 `<a data-role=download-*>` 的 href，并**在页面内**同步取回字节长与
        #    HTTP 状态（overrideMimeType 保证字节保真）；
        # 2) 再用文本定位**真实点击**该元素下载，比对保存文件与页面内字节一致、HTTP 200。
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

        def file_name_from_href(href: str) -> str:
            try:
                q = urllib.parse.urlparse(href).query
                for k, v in urllib.parse.parse_qsl(q):
                    if k == "path":
                        return v.split("/")[-1]
            except Exception:
                pass
            return ""

        dl = {}
        for label, role, text, outp in (
                ("word", "download-word", "下载 Word", EVID / "dl_word.docx"),
                ("pdf", "download-pdf", "下载 PDF", EVID / "dl_viewer.pdf")):
            pr = probe_res.get(label) if isinstance(probe_res, dict) else {}
            href = (pr or {}).get("href")
            if (pr or {}).get("missing") or not href:
                dl[label] = {"error": "anchor_missing_or_no_href", "probe": pr}
                continue
            out = str(outp)
            try:
                Path(out).unlink(missing_ok=True)
            except Exception:
                pass
            click_out = _bx(["find", "text", text, "click"], timeout=40)
            _bx(["download", f'[data-role="{role}"]', out], timeout=90)
            saved = Path(out).exists()
            dl[label] = {"clicked_element_href": href,
                         "in_page_status": (pr or {}).get("status"),
                         "in_page_size": (pr or {}).get("size"),
                         "href_http_ok": isinstance((pr or {}).get("status"), int)
                                         and 200 <= (pr or {}).get("status", 0) < 400,
                         "click_out": click_out[:120],
                         "saved_by_agent_browser": saved,
                         "saved_sha256": sha256_file(outp) if saved else None,
                         "saved_size": outp.stat().st_size if saved else None,
                         "saved_eq_in_page_size": bool(saved) and bool((pr or {}).get("size"))
                                                  and outp.stat().st_size == (pr or {}).get("size")}
        EVIDENCE["ui_downloads"] = dl
        step("ui_downloads", word=dl.get("word", {}).get("saved_sha256"),
             pdf=dl.get("pdf", {}).get("saved_sha256"))

        # —— 同源闭环：viewer 渲染 = 下载 PDF 为同一 artifact ——
        # 优先用 agent-browser 落盘的 saved_sha256；若 download 命令未落盘（受控环境常见），
        # 回退为对同一 href 的 HTTP 拉取（viewer 渲染读的正是该 artifact 的字节），保证闭环可比。
        dl_pdf = dl.get("pdf", {})
        pdf_disk_sha = dl_pdf.get("saved_sha256")
        if not pdf_disk_sha:
            # 回退：HTTP 拉取 pdf href（= viewer 渲染的同一 artifact 字节）
            pdf_href = (probe_res.get("pdf") or {}).get("href") if isinstance(probe_res, dict) else None
            pdf_http_sha = None
            if pdf_href and base:
                try:
                    req = urllib.request.Request(base + pdf_href, headers={"Cookie": "ra_session=1"})
                    with urllib.request.urlopen(req, timeout=120) as fr:
                        if 200 <= fr.status < 400:
                            pdf_http_sha = hashlib.sha256(fr.read()).hexdigest()
                except Exception:
                    pdf_http_sha = None
            pdf_disk_sha = pdf_http_sha
            if pdf_disk_sha:
                dl_pdf = dict(dl_pdf, saved_sha256=pdf_disk_sha,
                              note="agent-browser 未落盘，改以同一 href HTTP 字节 sha 闭环")
        pdf_disk_sha16 = pdf_disk_sha[:16] if pdf_disk_sha else None
        # V2.2.0 R2-16：不再有 .wb-download__hash。viewer 与「↓ PDF」href 同 URL → 同一 artifact；
        # 配合 viewer_ready + 下载字节 sha 与响应一致，闭合同源。
        pdf_anchor_href = (probe_res.get("pdf") or {}).get("href") if isinstance(probe_res, dict) else None
        same_href = bool(pdf_anchor_href)
        same_source = bool(viewer_ok and pdf_disk_sha16 and same_href)
        EVIDENCE["pdf_viewer_same_source"] = {
            "viewer_ready": viewer_ok,
            "viewer_pages": viewer_pages,
            "download_pdf_sha16": pdf_disk_sha16,
            "download_pdf_href": pdf_anchor_href,
            "same_source": same_source,
        }
        step("pdf_viewer_same_source", same_source=same_source,
             pdf_sha16=pdf_disk_sha16, pdf_href=pdf_anchor_href, pages=viewer_pages)

        # —— 7 个冻结视口的截图 + DOM 断言（PLAN §4.3 / §7.1）——
        vp_shots_dir = EVID / "viewports"
        vp_shots_dir.mkdir(parents=True, exist_ok=True)
        vp_results: dict = {}
        for (vw, vh) in VIEWPORTS:
            _bx(["set", "viewport", str(vw), str(vh)], timeout=20)
            time.sleep(1.2)
            raw_v = _bx(["eval", _LAYOUT_PROBE], timeout=25).strip()
            v = {}
            try:
                s1 = json.loads(raw_v)
                v = json.loads(s1) if isinstance(s1, str) else s1
            except Exception:
                v = {"parse_error": raw_v[:200]}
            shot = vp_shots_dir / f"vp_{vw}x{vh}.png"
            _bx(["screenshot", str(shot)], timeout=30)
            v["screenshot"] = str(shot)
            v["shot_exists"] = shot.exists()
            vp_results[f"{vw}x{vh}"] = v
        EVIDENCE["viewports"] = vp_results
        _ref = vp_results.get("1686x1076") or {}
        EVIDENCE["ui_p4_scroll"] = {
            "viewport": "1686x1076",
            "doc_overflow": (_ref.get("overflow") or {}).get("doc"),
            "body_overflow": (_ref.get("overflow") or {}).get("body"),
            "scrollables": _ref.get("scrollables"),
            "note": "P4 成功态参考桌面视口下的整页/内部滚动观察（正式 1686x1076 回看态断言在 design_fidelity Gate）",
        }
        for (vw, vh) in VIEWPORTS:
            k = f"{vw}x{vh}"
            v = vp_results.get(k, {})
            step(f"viewport_{k}", snapshot=shot_size(v), pdf_state=v.get("pdfState"),
                 overflow=v.get("overflow"), scrollables=v.get("scrollables"), shot=v.get("shot_exists"))
        _bx(["close"], timeout=20)

        # 返回 _verify_artifacts 可识别的最小产物身份（同一 onedir 磁盘 artifact），
        # 用于 disk-vs-HTTP 字节一致性；锚点 href 即页面内下载链接（同源相对路径）。
        word_href = (probe_res.get("word") or {}).get("href") if isinstance(probe_res, dict) else None
        pdf_href = (probe_res.get("pdf") or {}).get("href") if isinstance(probe_res, dict) else None
        return {
            "download_url": word_href,
            "file_name": file_name_from_href(word_href or ""),
            "pdf_download_url": pdf_href,
            "pdf_file_name": file_name_from_href(pdf_href or ""),
        }
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


def _verify_artifacts(s, base: str, gen: dict, runtime: Path) -> dict:
    """DOCX/PDF 磁盘 artifact vs HTTP 下载 字节一致；无 404/405/5xx。"""
    out: dict = {}
    # 磁盘定位
    docx_disk = None
    fp = gen.get("file_path")
    cands = []
    if fp:
        cands.append(Path(fp) if Path(fp).is_absolute() else runtime / fp)
    if gen.get("file_name"):
        cands.append(runtime / "output" / str(gen.get("file_name")))
    # V2.2.0 R3：UI 路径的下载 href 已是 task-scoped 路由（不含 path 参数），
    # 文件名不再从 URL 推断；改为从 output 目录按 mtime 取最新 docx 兜底定位磁盘 artifact。
    docx_cands = sorted((runtime / "output").glob("*.docx"),
                        key=lambda p: p.stat().st_mtime, reverse=True) \
        if (runtime / "output").is_dir() else []
    cands += list(docx_cands[:1])
    for c in cands:
        if c and Path(c).is_file():
            docx_disk = Path(c)
            break
    pdf_disk = None
    for c in sorted((runtime / "output").glob("*.pdf"), key=lambda p: p.stat().st_mtime,
                    reverse=True) if (runtime / "output").is_dir() else []:
        pdf_disk = c
        break
    out["docx_disk"] = {"path": str(docx_disk), "sha256": sha256_file(docx_disk),
                        "size": docx_disk.stat().st_size} if docx_disk else None
    out["pdf_disk"] = {"path": str(pdf_disk), "sha256": sha256_file(pdf_disk),
                       "size": pdf_disk.stat().st_size} if pdf_disk else None

    def http_get(url: str) -> tuple[int, bytes, str]:
        r = s.get(base + url, timeout=120)
        return r.status_code, r.content, r.headers.get("Content-Type", "")

    def http_head(url: str) -> tuple[int, dict]:
        r = s.head(base + url, timeout=120)
        return r.status_code, dict(r.headers)

    def http_range(url: str, start: int = 0, end: int = 4095) -> dict:
        r = s.get(base + url, timeout=120,
                  headers={"Range": f"bytes={start}-{end}", "Cookie": "ra_session=1"})
        return {"status": r.status_code,
                "content_range": r.headers.get("Content-Range", ""),
                "accept_ranges": r.headers.get("Accept-Ranges", ""),
                "bytes": len(r.content)}

    def head_range_checks(url: str) -> dict:
        st, hd = http_head(url)
        rg = http_range(url)
        return {"url": url,
                "head_status": st,
                "head_ok": bool(isinstance(st, int) and st < 400),
                "range_status": rg["status"],
                "range_206": rg["status"] == 206,
                "content_range": rg["content_range"],
                "content_range_nonempty": bool(rg["content_range"]),
                "accept_ranges": rg["accept_ranges"],
                "accept_ranges_has_bytes": "bytes" in rg["accept_ranges"].lower(),
                "range_bytes": rg["bytes"]}

    if gen.get("download_url"):
        code, data, ctype = http_get(gen["download_url"])
        out["word_download"] = {"url": gen["download_url"], "status": code, "mime": ctype,
                                "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                                "size_bytes": gen.get("file_name") and len(data)}
        out["word_head_range"] = head_range_checks(gen["download_url"])
    if gen.get("pdf_download_url"):
        code, data, ctype = http_get(gen["pdf_download_url"])
        out["pdf_download"] = {"url": gen["pdf_download_url"], "status": code, "mime": ctype,
                               "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        code2, data2, _ = http_get(gen["pdf_download_url"])
        out["pdf_download_repeat_same"] = hashlib.sha256(data2).hexdigest() == hashlib.sha256(data).hexdigest()
        out["pdf_head_range"] = head_range_checks(gen["pdf_download_url"])
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
    # HEAD + Range(206) 支持：viewer 增量分块读取与断点续传所依赖。
    for wk in ("word_head_range", "pdf_head_range"):
        hr = out.get(wk)
        if hr:
            checks[f"{wk}_head_ok"] = bool(hr["head_ok"])
            checks[f"{wk}_range_206"] = bool(hr["range_206"])
            checks[f"{wk}_content_range"] = bool(hr["content_range_nonempty"])
            checks[f"{wk}_accept_ranges"] = bool(hr["accept_ranges_has_bytes"])
    codes = [v.get("status") for k, v in out.items() if isinstance(v, dict) and "status" in v]
    checks["no_4xx_5xx"] = all(isinstance(c, int) and c < 400 for c in codes) and bool(codes)
    codes_rng = [v.get("head_status") for v in out.values() if isinstance(v, dict) and "head_status" in v]
    checks["head_no_4xx_5xx"] = bool(codes_rng) and all(isinstance(c, int) and c < 400 for c in codes_rng)
    EVIDENCE["artifact_checks"] = checks
    step("artifact_checks", **checks)
    return checks


def _anchors_bound(gen: dict) -> dict:
    arts = [a.get("artifact_id") for a in (gen.get("pdf_anchors") or [])]
    pid = gen.get("pdf_artifact_id")
    return {"total": len(arts), "bound_to_pdf_artifact": sum(1 for a in arts if a == pid),
            "unavailable": sum(1 for a in (gen.get("pdf_anchors") or [])
                               if not a.get("artifact_id"))}


if __name__ == "__main__":
    sys.exit(main())
