"""公开版本元数据单一真源（V1.4.1 建立）。

所有对外暴露当前版本的位置统一从本模块导入 APP_VERSION，避免漂移：
- FastAPI app.version
- OpenAPI info.version
- GET / 响应 version
- Stub Demo 对外 banner
"""
from __future__ import annotations

APP_VERSION = "2.0.0"
