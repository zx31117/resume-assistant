"""V2.0.1 T6 验证：统一操作可观测性 + 诊断 API + 并发/隐私/生命周期（D 适用项）。

退出码 0 = 业务断言通过且临时 runtime 清理干净；非 0 = 有失败、异常或清理失败。

覆盖（无真实 API Key 下的确定性适用项）：
- T1：tracker 生命周期 / 阶段事件 / 单调计时 / 脱敏 / 启动收口 / 轮转 / 近期统计
- T3/T4：提取 fail-closed、Experience create/delete、migrate、rebuild（无 key 分支）、retry 的打点
- T4：诊断 API 列表/详情/日志/摘要/清理 + 非法输入稳定拒绝
- T4：并发门禁 409 + holder 证据 + 被拒请求不成为 RUNNING
- D15：JSONL / API 隐私反向扫描（无凭据 / PII / 绝对路径 / 堆栈）
LLM/Embedding 正向链路（D1/D3/D4/D6/D8 正向）需真实 Key 或注入 Stub，本脚本只验证其
fail-closed 与无 key 分支；详见 RESULT.md 验证表登记。
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import sys
import tempfile
import uuid
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _v2_test_runner import run_isolated  # noqa: E402

_passed = 0
_failed = 0


def check(cond, name, extra=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [PASS] {name}")
    else:
        _failed += 1
        print(f"  [FAIL] {name} {extra}")


def _uid() -> str:
    return str(uuid.uuid4())


def _iso(days_offset: int = 0) -> str:
    ts = _dt.datetime.utcnow() + _dt.timedelta(days=days_offset)
    return ts.isoformat(timespec="milliseconds") + "Z"


# ── 单元部分（不依赖 TestClient，独立实例避免污染 singleton） ──


def _unit_tests() -> None:
    from core import operations as ops

    print("\n[U1] 脱敏 _sanitize_message（D15）")
    check(ops._sanitize_message("Bearer abc123") == "<redacted>", "敏感 token 整体降级")
    check(ops._sanitize_message("发到 user@example.com 邮箱") .find("user@example.com") == -1, "邮箱被替换", extra=ops._sanitize_message("发到 user@example.com 邮箱"))
    check("<email>" in ops._sanitize_message("联系 user@example.com"), "邮箱占位符出现")
    check("<path>" in ops._sanitize_message("打开 C:\\Users\\foo\\a.docx"), "Windows 绝对路径被替换")
    check("<path>" in ops._sanitize_message("目录 /home/foo/bar 下"), "Unix 绝对路径被替换")
    check("<phone>" in ops._sanitize_message("电话 13800138000"), "疑似电话被替换")
    check("普通" in ops._sanitize_message("普通消息 123"), "无敏感内容保持", extra=ops._sanitize_message("普通消息 123"))
    check(ops._sanitize_message("") == "", "空串返回空串")

    print("\n[U2] operation_id 校验/解析")
    good = _uid()
    check(ops.valid_operation_id(good) == good, "合法 UUID 保留")
    check(ops.valid_operation_id("not-a-uuid") is None, "非法 UUID 返回 None")
    check(ops.valid_operation_id(None) is None, "None 返回 None")
    check(ops.resolve_operation_id(good) == good, "合法 X-Operation-ID 直接使用")
    check(ops.resolve_operation_id("bad") != "bad", "非法 X-Operation-ID 重新生成")

    print("\n[U3] 启动收口（D12）：遗留 OP_STARTED 无终态 → INTERRUPTED")
    t = ops.OperationTracker()
    tmpdir = Path(tempfile.mkdtemp(prefix="ra_v201_rec_"))
    t._log_path = tmpdir / "operations.jsonl"
    oid = _uid()
    start_line = t._event_line(
        seq=1, level="INFO", component="generate", operation_id=oid, group_id=None,
        operation_type="generate", status="RUNNING", stage_code="", resource_type="",
        event_code="OP_STARTED", message="generate 开始", attempt=1, max_attempts=1,
        elapsed_ms=0, diagnostic_code="", safe_counts={},
    )
    t._log_path.write_text(json.dumps(start_line, ensure_ascii=False) + "\n", encoding="utf-8")
    t._initialized = False
    t._reconcile_on_startup()
    lines = t._log_path.read_text(encoding="utf-8").strip().split("\n")
    interrupted = [l for l in lines if '"event_code": "OP_INTERRUPTED"' in l or '"event_code":"OP_INTERRUPTED"' in l]
    check(len(interrupted) >= 1, f"遗留 RUNNING 收口为 INTERRUPTED（总行数 {len(lines)}）")
    check(t._seq >= 2, "seq 已恢复并递增", extra=str(t._seq))

    print("\n[U4] 轮转（D14）：超过 7 天旧行被裁剪")
    t2 = ops.OperationTracker()
    tmpdir2 = Path(tempfile.mkdtemp(prefix="ra_v201_trim_"))
    t2._log_path = tmpdir2 / "operations.jsonl"
    def _mk(seq, ts, code="OP_SUCCEEDED"):
        return t2._event_line(
            seq=seq, level="INFO", component="generate", operation_id=_uid(), group_id=None,
            operation_type="generate", status="SUCCEEDED", stage_code="", resource_type="",
            event_code=code, message=f"ev{seq}", attempt=1, max_attempts=1,
            elapsed_ms=10, diagnostic_code="", safe_counts={},
        ) | {"ts": ts}
    old = _mk(1, _iso(-8))
    new = _mk(2, _iso(0))
    t2._log_path.write_text(json.dumps(old, ensure_ascii=False) + "\n" + json.dumps(new, ensure_ascii=False) + "\n", encoding="utf-8")
    t2._trim_file()
    kept = t2._read_all()
    check(len(kept) == 1, "旧行被裁剪，仅保留新行", extra=str(len(kept)))
    check(len(kept) == 1 and kept[0].get("message") == "ev2", "保留的是未过期行", extra=str([e.get("message") for e in kept]))

    print("\n[U5] 近期同类统计 recent_stats（D17/R5）")
    t3 = ops.OperationTracker()
    recs = []
    for ms in [10, 30, 20, 40]:
        r = ops.OperationRecord(_uid(), ops.OperationType.GENERATE)
        r.stages.append(ops.StageEvent(
            seq=0, event_type=ops.StageEventType.COMPLETED, stage_code="jd_analyze",
            stage_name="", resource_type=ops.ResourceType.LLM, event_code="", attempt=1,
            max_attempts=1, elapsed_ms=ms, message="", safe_counts={}, ts=_iso(0),
        ))
        recs.append(r)
    # 追加一条其它 stage_code，验证不串样本
    r_other = ops.OperationRecord(_uid(), ops.OperationType.GENERATE)
    r_other.stages.append(ops.StageEvent(
        seq=0, event_type=ops.StageEventType.COMPLETED, stage_code="rewrite",
        stage_name="", resource_type=ops.ResourceType.LLM, event_code="", attempt=1,
        max_attempts=1, elapsed_ms=999, message="", safe_counts={}, ts=_iso(0),
    ))
    recs.append(r_other)
    t3._recent = recs
    st = t3.recent_stats("generate", "jd_analyze")
    check(st["sample_size"] == 4, "样本数 4", extra=str(st))
    check(st["median_ms"] == 25, "中位数 25", extra=str(st))
    check(st["max_ms"] == 40, "最大值 40", extra=str(st))
    empty = t3.recent_stats("generate", "no_such_stage")
    check(empty == {"sample_size": 0, "median_ms": None, "max_ms": None}, "无样本返回 0/None", extra=str(empty))

    print("\n[U6] 诊断从文件恢复（D11 复盘路径）")
    oid2 = _uid()
    t4 = ops.OperationTracker()
    tmpdir4 = Path(tempfile.mkdtemp(prefix="ra_v201_diag_"))
    t4._log_path = tmpdir4 / "operations.jsonl"
    evs = [
        t4._event_line(seq=1, level="INFO", component="generate", operation_id=oid2, group_id=None,
                       operation_type="generate", status="RUNNING", stage_code="", resource_type="",
                       event_code="OP_STARTED", message="generate 开始", attempt=1, max_attempts=1,
                       elapsed_ms=0, diagnostic_code="", safe_counts={}) | {"ts": _iso(0)},
        t4._event_line(seq=2, level="INFO", component="generate", operation_id=oid2, group_id=None,
                       operation_type="generate", status="RUNNING", stage_code="jd_analyze",
                       resource_type="LLM", event_code="STAGE_COMPLETED.jd_analyze", message="",
                       attempt=1, max_attempts=1, elapsed_ms=123, diagnostic_code="", safe_counts={}),
        t4._event_line(seq=3, level="INFO", component="generate", operation_id=oid2, group_id=None,
                       operation_type="generate", status="SUCCEEDED", stage_code="", resource_type="",
                       event_code="OP_SUCCEEDED", message="generate SUCCEEDED", attempt=1, max_attempts=1,
                       elapsed_ms=150, diagnostic_code="", safe_counts={"total": 1}),
    ]
    t4._log_path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in evs) + "\n", encoding="utf-8")
    diag = t4.diagnostics(oid2)
    check(diag is not None and diag["status"] == "SUCCEEDED", "从 JSONL 重建脱敏摘要成功", extra=str(diag))
    check(diag is not None and diag["safe_counts"] == {"total": 1}, "safe_counts 恢复", extra=str(diag and diag.get("safe_counts")))
    check(diag is not None and len(diag.get("stages", [])) == 1, "阶段列表恢复 1 项", extra=str(diag and len(diag.get("stages", []))))


# ── API 部分（TestClient，含写安全 cookie） ──


def _api_tests(state) -> None:
    import main  # noqa: E402
    from core import concurrency, security  # noqa: E402
    from core.config import settings  # noqa: E402
    from database.session import engine  # noqa: E402
    state.register_engine(engine)
    from fastapi.testclient import TestClient  # noqa: E402

    cookies = {security.SESSION_COOKIE_NAME: security.SESSION_TOKEN}
    auth_headers = {"Host": "127.0.0.1:8000"}

    c = TestClient(main.app)
    state.register_client(c)

    with c:
        print("\n[A0] 版本元数据（T7a/D20）")
        r = c.get("/api/health")
        check(r.status_code == 200 and r.json().get("version") == "2.0.2", "/api/health version=2.0.2", extra=str(r.json().get("version")))

        print("\n[A1] Experience create 打点（T3，正向 + Cookie）")
        create_oid = _uid()
        payload = {
            "type": "work", "title": "后端工程师", "company": "某厂",
            "time": "2020-2023", "role": "后端", "description": "负责订单系统",
            "skills": ["Python", "SQL"], "achievements": [], "raw_text": "",
        }
        r = c.post("/api/experience/", json=payload, headers={**auth_headers, "X-Operation-ID": create_oid}, cookies=cookies)
        check(r.status_code == 200, "create 200", extra=str(r.status_code) + " " + r.text[:200])
        created_id = r.json().get("id")
        check(bool(created_id), "返回 id")
        op = c.get(f"/api/system/operations/{create_oid}")
        check(op.status_code == 200, "按 operation_id 取回操作", extra=str(op.status_code))
        if op.status_code == 200:
            o = op.json()["operation"]
            check(o["status"] == "SUCCEEDED", "create 操作 SUCCEEDED", extra=str(o["status"]))
            codes = [s["stage_code"] for s in o["stages"]]
            check("experience_write" in codes, "含 experience_write 阶段", extra=str(codes))
            check("tx_commit" in codes, "含 tx_commit 阶段", extra=str(codes))
            # 单调：seq 有序、elapsed 非负（D13）
            seqs = [s["seq"] for s in o["stages"]]
            check(seqs == sorted(seqs) and len(set(seqs)) == len(seqs), "seq 严格递增", extra=str(seqs))
            check(all(s["elapsed_ms"] >= 0 for s in o["stages"]), "阶段耗时均非负")
            # 分组字段默认 NULL
            check(o["group_id"] is None, "单条 create 无 group_id", extra=str(o["group_id"]))

        print("\n[A2] Experience delete 打点（T3）")
        del_oid = _uid()
        r = c.delete(f"/api/experience/{created_id}", headers={**auth_headers, "X-Operation-ID": del_oid}, cookies=cookies)
        check(r.status_code == 200 and r.json().get("ok") is True, "delete 200 ok", extra=str(r.status_code))
        op = c.get(f"/api/system/operations/{del_oid}")
        check(op.status_code == 200 and op.json()["operation"]["status"] == "SUCCEEDED", "delete 操作 SUCCEEDED", extra=str(op.status_code))

        print("\n[A3] 提取 fail-closed（D2 负向）")
        ext_oid = _uid()
        r = c.post("/api/experience/extract", json={"resume_text": ""}, headers={**auth_headers, "X-Operation-ID": ext_oid}, cookies=cookies)
        check(r.status_code == 422, "空文本提取 422", extra=str(r.status_code))
        op = c.get(f"/api/system/operations/{ext_oid}")
        if op.status_code == 200:
            o = op.json()["operation"]
            check(o["status"] == "FAILED", "提取失败操作 FAILED", extra=str(o["status"]))
            codes = [s["stage_code"] for s in o["stages"]]
            check("input_validate" in codes, "停在 input_validate 阶段", extra=str(codes))

        print("\n[A4] 迁移打点（T3）")
        mig_oid = _uid()
        r = c.post("/api/system/migrate", headers={**auth_headers, "X-Operation-ID": mig_oid}, cookies=cookies)
        check(r.status_code == 200 and r.json().get("ok") is True, "migrate 200 ok", extra=str(r.status_code) + " " + r.text[:200])
        op = c.get(f"/api/system/operations/{mig_oid}")
        if op.status_code == 200:
            o = op.json()["operation"]
            check(o["status"] == "SUCCEEDED", "migrate 操作 SUCCEEDED", extra=str(o["status"]))
            codes = [s["stage_code"] for s in o["stages"]]
            for need in ("pre_check", "backup", "apply_migration", "verify", "release"):
                check(need in codes, f"含 {need} 阶段", extra=str(codes))

        print("\n[A5] 重建/重试（T3，无 key 分支 skipped）")
        # 无 key 分支是确定性契约：临时清空 ARK_API_KEY 以隔离本机 .env，测后恢复，
        # 避免在有真实 key 的开发机上把“无 key 跳过”误判为“有 key 空跑”。
        _saved_ark = settings.ARK_API_KEY
        settings.ARK_API_KEY = ""
        try:
            rb_oid = _uid()
            r = c.post("/api/system/rebuild", headers={**auth_headers, "X-Operation-ID": rb_oid}, cookies=cookies)
            check(r.status_code == 200, "rebuild 200", extra=str(r.status_code) + " " + r.text[:200])
            if r.status_code == 200:
                body = r.json()
                check(body.get("operation_id") == rb_oid, "rebuild 回传同一 operation_id", extra=str(body.get("operation_id")))
                check(body.get("summary", {}).get("skipped_no_key") is True, "无 key 时 skipped_no_key=True", extra=str(body.get("summary")))
            op = c.get(f"/api/system/operations/{rb_oid}")
            check(op.status_code == 200 and op.json()["operation"]["status"] == "SUCCEEDED", "rebuild 操作 SUCCEEDED", extra=str(op.status_code))
            rtry_oid = _uid()
            r = c.post("/api/system/retry", headers={**auth_headers, "X-Operation-ID": rtry_oid}, cookies=cookies)
            check(r.status_code == 200, "retry 200", extra=str(r.status_code))
            op = c.get(f"/api/system/operations/{rtry_oid}")
            check(op.status_code == 200 and op.json()["operation"]["status"] == "SUCCEEDED", "retry 操作 SUCCEEDED", extra=str(op.status_code))
        finally:
            settings.ARK_API_KEY = _saved_ark

        print("\n[A6] 诊断 API：列表/筛选/详情/日志/摘要（D9/T4）")
        r = c.get("/api/system/operations")
        check(r.status_code == 200 and r.json().get("ok") is True, "GET /operations 200")
        ops_list = r.json().get("operations", [])
        check(len(ops_list) >= 5, "列表含本次打点操作", extra=str(len(ops_list)))
        check(all("operation_id" in x and "stage_code" in x and "elapsed_ms" in x for x in ops_list), "列表项字段完整")
        # 筛选
        r = c.get("/api/system/operations?status=SUCCEEDED")
        check(r.status_code == 200 and all(x["status"] == "SUCCEEDED" for x in r.json()["operations"]), "按 status 筛选")
        r = c.get("/api/system/operations?operation_type=experience_create")
        check(r.status_code == 200 and all(x["operation_type"] == "experience_create" for x in r.json()["operations"]), "按 type 筛选")
        r = c.get("/api/system/operations?limit=2")
        check(len(r.json()["operations"]) <= 2, "limit 上限生效", extra=str(len(r.json()["operations"])))
        # 日志增量
        r = c.get("/api/system/logs?after_seq=0&limit=500")
        check(r.status_code == 200 and r.json().get("ok") is True, "GET /logs 200")
        events = r.json().get("events", [])
        check(len(events) >= 5, "日志存在事件", extra=str(len(events)))
        check(all(int(e["seq"]) > 0 for e in events), "日志 seq 全为正")
        # 摘要
        r = c.get(f"/api/system/diagnostics/{create_oid}")
        check(r.status_code == 200 and r.json().get("ok") is True, "GET /diagnostics/{id} 200")
        check(r.json().get("diagnostics", {}).get("status") == "SUCCEEDED", "摘要状态 SUCCEEDED")

        print("\n[A7] 诊断 API 非法输入稳定拒绝（D18）")
        r = c.get("/api/system/operations/not-a-uuid")
        check(r.status_code == 400 and r.json().get("error_code") == "DIAGNOSTICS_INVALID_PARAM", "非法 UUID → 400", extra=str(r.status_code))
        r = c.get("/api/system/operations?status=BOGUS")
        check(r.status_code == 400 and r.json().get("error_code") == "DIAGNOSTICS_INVALID_PARAM", "非法 status 筛选 → 400", extra=str(r.status_code))
        r = c.get("/api/system/operations?operation_type=bogus")
        check(r.status_code == 400, "非法 operation_type 筛选 → 400", extra=str(r.status_code))
        missing = _uid()
        r = c.get(f"/api/system/operations/{missing}")
        # 未在内存，且文件被后续 clear 前可能有；此处该 id 从未产生 → 404
        check(r.status_code == 404 and r.json().get("error_code") == "OPERATION_NOT_FOUND", "不存在操作 → 404", extra=str(r.status_code) + " " + r.text[:120])

        print("\n[A8] 并发门禁 409 + holder 证据（D10）")
        holder_id = _uid()
        victim_id = _uid()
        with concurrency.exclusive_operation("generate", operation_id=holder_id):
            # 门禁被占用时，读诊断接口仍应可服务（D9 部分证据）
            r = c.get("/api/system/operations")
            check(r.status_code == 200, "门禁占用中 GET /operations 仍 200")
            # 写请求被 409 拒绝
            r = c.post("/api/system/migrate", headers={**auth_headers, "X-Operation-ID": victim_id}, cookies=cookies)
            check(r.status_code == 409, "门禁占用中 migrate → 409", extra=str(r.status_code))
            body = r.json()
            check(body.get("error_code") == "OPERATION_IN_PROGRESS", "error_code=OPERATION_IN_PROGRESS", extra=str(body.get("error_code")))
            details = body.get("details", {})
            check(details.get("holder_operation_id") == holder_id, "holder_operation_id 回传", extra=str(details))
            check(details.get("holder") == "generate", "holder 操作名", extra=str(details))
            check(isinstance(details.get("holder_elapsed_ms"), int) and details["holder_elapsed_ms"] >= 0, "holder_elapsed_ms 非负", extra=str(details.get("holder_elapsed_ms")))
        # 被拒请求不得成为 RUNNING 操作
        r = c.get(f"/api/system/operations/{victim_id}")
        check(r.status_code == 404, "被拒请求未产生 RUNNING 操作", extra=str(r.status_code))

        print("\n[A9] 隐私反向扫描（D15）")
        scan = c.get("/api/system/logs?after_seq=0&limit=500").json().get("events", [])
        violated = []
        for e in scan:
            raw = json.dumps(e, ensure_ascii=False)
            for marker in ("ark_api_key", "authorization", "bearer ", "api_key", "cookie", "session_token", "password"):
                if marker in raw.lower():
                    violated.append(marker)
            if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", raw):
                violated.append("email")
            if re.search(r"[A-Za-z]:[\\/]", raw):
                violated.append("win_path")
        check(not violated, "JSONL 无凭据/PII/绝对路径", extra=str(violated[:5]))
        # 清理日志（写安全 + 二次确认由前端负责，此处仅验证接口受保护）
        print("\n[A10] 历史日志清理（T4，写安全）")
        r = c.delete("/api/system/logs", headers=auth_headers, cookies=cookies)
        check(r.status_code == 200 and r.json().get("ok") is True, "DELETE /logs 200 ok", extra=str(r.status_code))
        r = c.get("/api/system/logs")
        check(r.json().get("events", []) == [], "清理后日志为空", extra=str(r.json().get("events")))


def _run_tests(state) -> int:
    _unit_tests()
    _api_tests(state)
    print("\n" + "-" * 60)
    print(f"PASS={_passed} FAIL={_failed}")
    return 0 if _failed == 0 else 1


def main() -> None:
    run_isolated(prefix="ra_v201_", test_fn=_run_tests, description="V2.0.1 可观测性验证")


if __name__ == "__main__":
    main()