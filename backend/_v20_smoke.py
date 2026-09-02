"""V2.0.0 冒烟测试：薄 API 路由 + 安全中间件 + 同源托管。

退出码 0 = 业务断言通过且临时 runtime 清理干净；非 0 = 有失败、异常或清理失败（打印明细）。

资源语义（§11.1）：模块导入无副作用；临时 runtime 建立、环境保存/覆盖/恢复、产品模块
延迟导入、engine/TestClient 取得即登记、断言执行与唯一退出码仲裁统一由
`_v2_test_runner.run_isolated` 收口，确保依赖导入失败 / lifespan 初始化失败 / 断言失败 /
业务异常 / 提前退出等任何路径都能释放 SQLite 句柄并删除临时 runtime。
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


def check(cond: bool, name: str, extra: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [PASS] {name}")
    else:
        _failed += 1
        print(f"  [FAIL] {name} {extra}")


def _run_tests(state) -> int:
    """执行全部冒烟断言，返回业务退出码（0=通过）。延迟导入处于隔离环境与 cleanup 保护内。"""
    import main  # noqa: E402
    from database.session import engine  # noqa: E402
    state.register_engine(engine)
    from fastapi.testclient import TestClient  # noqa: E402

    c = TestClient(main.app)
    state.register_client(c)

    # 进入上下文管理触发 lifespan -> init_db() 建表，避免全新库下
    # /api/system/status 因表不存在而 500。
    with c:
        print("=" * 60)
        print("V2.0.0 冒烟测试（隔离 runtime）")
        print("=" * 60)

        print("\n[1] 同源健康检查")
        r = c.get("/api/health")
        check(r.status_code == 200, "/api/health 200")
        body = r.json()
        check(body.get("status") == "ok", "health status=ok")
        check(body.get("version") == "2.0.1", "版本元数据 = 2.0.1", extra=str(body.get('version')))

        print("\n[2] 配置快照（脱敏）")
        r = c.get("/api/config")
        check(r.status_code == 200, "/api/config 200")
        snap = r.json()
        check("ARK_API_KEY" in snap, "快照含 ARK_API_KEY 元数据")
        key_meta = snap.get("ARK_API_KEY", {})
        check("masked" in key_meta, "ARKEY 返回 masked 而非明文")
        check("source" in key_meta, "ARKEY 含 source")
        # 快照永不返回完整 key（此处只确认无明文字段名泄漏，具体 key 值由 cred 库决定）
        check("value" not in key_meta, "ARKEY 元数据不含 value 明文")

        print("\n[3] 系统状态")
        r = c.get("/api/system/status")
        check(r.status_code == 200, "/api/system/status 200")
        st = r.json()
        for k in ("version", "migrations", "counts", "embeddings", "ready", "next_steps"):
            check(k in st, f"status 含 {k}")

        print("\n[4] 模板列表")
        r = c.get("/api/template/list")
        check(r.status_code == 200, "/api/template/list 200")
        check("templates" in r.json(), "templates 列表存在")

        print("\n[5] 写操作安全边界（无 session cookie 应被拒绝）")
        # 不携带 cookie：session_valid 应为 False → 403
        r = c.post("/api/config/test", json={
            "ark_base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "ark_api_key": "test-key",
            "llm_model": "m",
            "embedding_model": "e",
        })
        check(r.status_code == 403, "无会话令牌写请求被拒 403", extra=str(r.status_code))
        check(r.json().get("error_code") == "FORBIDDEN", "拒绝原因 error_code=FORBIDDEN")

        print("\n[6] 同源托管（生产构建产物）")
        # 未构建 dist 时根路由应回退 JSON；此处只验证不崩溃
        r = c.get("/")
        check(r.status_code in (200, 404), "/ 返回 200 或 404（未构建回退）", extra=str(r.status_code))

        print("\n" + "-" * 60)
        print(f"PASS={_passed} FAIL={_failed}")

    return 0 if _failed == 0 else 1


def main() -> None:
    run_isolated(prefix="ra_v20_smoke_", test_fn=_run_tests, description="冒烟测试")


if __name__ == "__main__":
    main()