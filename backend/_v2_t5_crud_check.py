"""V2.0.0 T5 前置：验证 Experience 薄 API CRUD + 同源写安全（正反路径）。

隔离 RESUME_DATA_DIR，走 TestClient 生命周期（触发 init_db 建表）。
退出码 0 = 业务断言通过且临时 runtime 清理干净；非 0 = 有失败、异常或清理失败。

资源语义（§11.1）：模块导入无副作用；临时 runtime 建立、环境保存/覆盖/恢复、产品模块
延迟导入、engine/TestClient 取得即登记与唯一退出码仲裁统一由 `_v2_test_runner.run_isolated`
收口；仅在业务断言与资源后置条件同时通过时才以 0 退出。
"""
from __future__ import annotations

import sys
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


def _run_tests(state) -> int:
    """执行全部 CRUD 断言，返回业务退出码（0=通过）。延迟导入处于隔离环境与 cleanup 保护内。"""
    import main  # noqa: E402
    from core import security  # noqa: E402
    from database.session import engine  # noqa: E402
    state.register_engine(engine)
    from fastapi.testclient import TestClient  # noqa: E402

    cookies = {security.SESSION_COOKIE_NAME: security.SESSION_TOKEN}
    auth_headers = {"Host": "127.0.0.1:8000"}

    c = TestClient(main.app)
    state.register_client(c)

    with c:
        print("=" * 60)
        print("V2.0.0 T5 CRUD 正向路径验证（隔离 runtime）")
        print("=" * 60)

        print("\n[1] 写安全：错误 Host 被拒")
        r = c.post("/api/experience/", json={"type": "work"})
        check(r.status_code == 403, "无 Host + 无 Cookie → 403", extra=str(r.status_code))

        payload = {
            "type": "work", "title": "后端工程师", "company": "某厂",
            "time": "2020-2023", "role": "后端", "description": "负责订单系统",
            "skills": ["Python", "SQL"], "achievements": ["QPS 提升 30%"],
            "raw_text": "",
        }

        print("\n[2] 创建（正确 Host + Cookie）")
        r = c.post("/api/experience/", json=payload, headers=auth_headers, cookies=cookies)
        check(r.status_code == 200, "create 200", extra=str(r.status_code) + " " + r.text[:200])
        created = r.json()
        check(created.get("id"), "返回含 id")
        check(created.get("title") == "后端工程师", "title 回读一致")
        check(created.get("skills") == ["Python", "SQL"], "skills 数组回读一致")
        check(created.get("fact_count", 0) >= 1, "fact_count 已聚合 >=1", extra=str(created.get("fact_count")))
        check(created.get("summary_status") == "pending", "新创建 summary_status=pending", extra=str(created.get("summary_status")))
        exp_id = created.get("id")

        print("\n[3] 列表（ORM 序列化 + 字段完整）")
        r = c.get("/api/experience/", headers={"Host": "127.0.0.1:8000"}, cookies=cookies)
        check(r.status_code == 200, "list 200", extra=str(r.status_code))
        items = r.json()
        check(isinstance(items, list) and len(items) == 1, "列表 1 项", extra=str(len(items) if isinstance(items, list) else items))
        if items:
            check(items[0].get("id") == exp_id, "列表项含正确 id")
            check("description" in items[0], "列表项含 description 字段")

        print("\n[4] 更新")
        upd = dict(payload)
        upd["description"] = "负责订单系统与风控"
        r = c.put(f"/api/experience/{exp_id}", json=upd, headers=auth_headers, cookies=cookies)
        check(r.status_code == 200, "update 200", extra=str(r.status_code) + " " + r.text[:200])
        check(r.json().get("description") == "负责订单系统与风控", "description 更新回读")

        print("\n[5] 删除")
        r = c.delete(f"/api/experience/{exp_id}", headers=auth_headers, cookies=cookies)
        check(r.status_code == 200 and r.json().get("ok") is True, "delete 200 ok", extra=str(r.status_code))

        print("\n[6] 列表为空")
        r = c.get("/api/experience/", headers={"Host": "127.0.0.1:8000"}, cookies=cookies)
        check(r.status_code == 200 and r.json() == [], "删除后列表为空")

    print("\n" + "-" * 60)
    print(f"PASS={_passed} FAIL={_failed}")

    return 0 if _failed == 0 else 1


def main() -> None:
    run_isolated(prefix="ra_v2_t5_", test_fn=_run_tests, description="CRUD 验证")


if __name__ == "__main__":
    main()