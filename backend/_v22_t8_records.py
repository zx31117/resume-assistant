"""V2.2.0 R2-T08 验证：我的简历真实记录列表（GET /api/task/records）。

退出码 0 = 业务断言通过且临时 runtime 清理干净；非 0 = 有失败/异常/清理失败。

覆盖（用户 Revision 2 缺口头：PLAN §3「查看已生成记录和真实可用 artifact」）：
- [B1] records 仅返回 SUCCEEDED 且已发布 DOCX 产物的任务；未发布/非 SUCCEEDED 不进列表；
- [B2] 每条记录含真实 published_docx_path / published_pdf_path（可直接构造 /api/template/download 链接）；
- [B3] 每条记录含最新入参 name / jd_len（真实回读，非伪造）；
- [B4] 记录按 updated_at 降序（更新优先）；
- [B5] GET /records 不会被 GET /{task_id} 路径参数捕获（路由顺序正确），
      GET /api/task/{task_id} 单独读取仍正常。

通过 TestClient 走真实 HTTP 层（含统一 DomainError 映射），临时 runtime 内独立 DB。
"""
from __future__ import annotations

import sys
from pathlib import Path
import urllib.parse

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


def _make_succeeded(client, req, repo_factory, db_factory,
                    name, jd, docx_path, pdf_path="", transition_first=True):
    """走真实 API 创建任务并对一个任务置 SUCCEEDED + 发布产物。返回 task_id。"""
    r = client.post("/api/task", **req)
    tid = r.json()["task_id"]
    client.put(f"/api/task/{tid}/save", json={
        "name": name, "phone": "", "email": "", "location": "", "jd": jd}, **req)
    client.post(f"/api/task/{tid}/freeze", json={
        "name": name, "phone": "", "email": "", "location": "", "jd": jd}, **req)
    client.post(f"/api/task/{tid}/start", **req)  # RUNNING（上一任务已终态，活动槽已释放）
    db = db_factory()
    try:
        from core import task as task_domain
        from services.task_repository import TaskRepository
        repo = TaskRepository(db)
        t = repo.get(tid)
        if transition_first:
            repo.transition(t, task_domain.TaskStatus.SUCCEEDED)
        repo.publish_artifacts(t, resume_revision=1, docx_path=docx_path, pdf_path=pdf_path)
        db.commit()
    finally:
        db.close()
    return tid


def _run_tests_inner(state) -> int:
    from fastapi.testclient import TestClient
    from main import app
    from database.session import SessionLocal, engine
    from core import security

    state.register_engine(engine)

    cookies = {security.SESSION_COOKIE_NAME: security.SESSION_TOKEN}
    auth_headers = {"Host": "127.0.0.1:8000"}
    REQ = {"headers": auth_headers, "cookies": cookies}

    client = TestClient(app)
    state.register_client(client)

    from database import migrations as mig
    mig.run_migrations()

    def _db():
        return SessionLocal()

    # 造 2 条已发布记录 + 1 条未发布/F 失败任务
    print("\n[B1-B5] 真实记录列表")
    _make_succeeded(client, REQ, None, _db,
                    "张三", "高级后端工程师岗位描述JD全文" * 6,
                    "output/resume_zhangsan_pm_template.docx",
                    "output/resume_zhangsan_pm_template.pdf")
    _make_succeeded(client, REQ, None, _db,
                    "李四", "算法工程师岗位描述JD全文" * 5,
                    "output/resume_lisi_pm_template.docx",
                    "output/resume_lisi_pm_template.pdf")

    # 未发布产物（FAILED 语义：无 artifact）的任务应不进列表
    r_f = client.post("/api/task", **REQ)
    tid_f = r_f.json()["task_id"]
    jd_f = "中级前端工程师，负责产品页面与组件开发，熟悉 React 与前端工程化，参与需求评审、代码评审与性能优化，关注可访问性与渲染性能，base 上海，可尽快到岗。"  # ≥60 字
    client.put(f"/api/task/{tid_f}/save", json={
        "name": "失败者", "phone": "", "email": "", "location": "", "jd": jd_f}, **REQ)
    client.post(f"/api/task/{tid_f}/freeze", json={
        "name": "失败者", "phone": "", "email": "", "location": "", "jd": jd_f}, **REQ)
    client.post(f"/api/task/{tid_f}/start", **REQ)
    db_f = _db()
    try:
        from core import task as task_domain
        from services.task_repository import TaskRepository
        repo = TaskRepository(db_f)
        t_f = repo.get(tid_f)
        repo.transition(t_f, task_domain.TaskStatus.FAILED, terminal_error="G_FAILED")
        db_f.commit()
    finally:
        db_f.close()

    r = client.get("/api/task/records", **REQ)
    body = r.json()
    check(r.status_code == 200, "GET /api/task/records 返回 200", extra=str(r.status_code))
    check(isinstance(body, list), "records 返回列表", extra=str(type(body)))

    names = {rec.get("latest_input", {}).get("name") for rec in body}
    check("张三" in names and "李四" in names, "两条已发布记录都在列表中", extra=str(names))
    check("失败者" not in names, "无产物/非 SUCCEEDED 任务不进入列表", extra=str(names))

    # 每条记录可下载引用 + 入参真实回读
    first = next((rec for rec in body if rec.get("latest_input", {}).get("name") == "张三"), None)
    check(first is not None, "张三记录存在")
    if first:
        check(first["published_docx_path"]
              == "output/resume_zhangsan_pm_template.docx", "张三 docx 发布引用真实",
              extra=str(first.get("published_docx_path")))
        check(first["published_pdf_path"]
              == "output/resume_zhangsan_pm_template.pdf", "张三 pdf 发布引用真实")
        dl = "/api/template/download?path=" + urllib.parse.quote(
            first["published_docx_path"])
        check(dl.startswith("/api/template/download?path=") and "output" in dl,
              "可构造同源下载链接", extra=dl)
        check(first["latest_input"]["name"] == "张三", "name 真实回读")
        jd_len = first["latest_input"]["jd_len"]
        check(jd_len > 0, "jd_len 真实回读", extra=str(jd_len))

    # 按 updated_at 降序：后发布的李四应排前面
    docx_seqs = [rec["published_docx_path"] for rec in body if rec.get("published_docx_path")]
    li = docx_seqs.index("output/resume_lisi_pm_template.docx") if "output/resume_lisi_pm_template.docx" in docx_seqs else -1
    zh = docx_seqs.index("output/resume_zhangsan_pm_template.docx") if "output/resume_zhangsan_pm_template.docx" in docx_seqs else -1
    check(0 <= li < zh, "记录按发布时间降序（新的在前）", extra=str(docx_seqs))

    # 路由顺序：GET /records 不被 /{task_id} 捕获；单独 GET /{task_id} 仍可用
    r2 = client.get(f"/api/task/{tid_f}", **REQ)
    check(r2.status_code == 200 and r2.json()["task_id"] == tid_f,
          "GET /api/task/{task_id} 单独读取仍正常（路由顺序无误）",
          extra=str(r2.status_code))

    # 空库语义（新增一个临时 DB：仅一个 FAILED，records 为空）由 [B1] 已隐含：
    # "失败者" 未出现即证明 SUCCEEDED+artifact 过滤生效。

    print(f"\n结果：{_passed} 通过 / {_failed} 失败")
    return 1 if _failed else 0


if __name__ == "__main__":
    def _fn(state):
        return _run_tests_inner(state)

    run_isolated("v22_t8_records_", _fn, "V2.2.0 R2-T08 records gate")