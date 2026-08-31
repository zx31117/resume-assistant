"""本地管理接口安全边界（PLAN §3.3）。

- loopback 绑定：settings.APP_HOST 默认 127.0.0.1（由启动器/uvicorn 保证）；
- 写操作（POST/PUT/PATCH/DELETE）校验 Host / Origin / 启动会话 Cookie；
- 生产不启用任意来源 CORS（本模块不加 CORS 头，浏览器同源策略默认阻止跨源读）；
- 启动会话令牌在进程启动时生成，写入 HttpOnly + SameSite=Strict Cookie，
  前端同源请求自动携带，其他网页无法跨源窃取或伪造。

会话令牌不通过 URL 传输（PLAN §3.4：不以可复制敏感 Token URL 暴露）。
"""
from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Request
from fastapi.responses import Response

SESSION_COOKIE_NAME = "ra_session"
# V2.0.0 单用户本地应用：进程级会话令牌，启动即生成，进程结束即失效。
SESSION_TOKEN: str = secrets.token_urlsafe(32)

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# 允许的 loopback Host（不含端口与时戳），Origins 允许 loopback 前缀。
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}


def is_write_request(request: Request) -> bool:
    return request.method.upper() in _WRITE_METHODS


def _host_name(host_header: Optional[str]) -> str:
    if not host_header:
        return ""
    # 去掉端口与首尾空白 / IPv6 括号
    name = host_header.strip()
    if name.startswith("["):
        name = name[1:].split("]", 1)[0]
    else:
        name = name.split(":", 1)[0]
    return name.lower()


def is_loopback_host(host_header: Optional[str]) -> bool:
    return _host_name(host_header) in _LOOPBACK_HOSTS


def _origin_host(origin: Optional[str]) -> str:
    """从 Origin 头提取 host（协议与端口外的主机名）。"""
    if not origin:
        return ""
    try:
        from urllib.parse import urlparse
        return (urlparse(origin).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return ""


def is_allowed_origin(origin: Optional[str]) -> bool:
    """Origin 缺失（同源导航/非浏览器）或无跨源意图时允许；否则必须为 loopback。"""
    if not origin:
        return True
    host = _origin_host(origin)
    return host in _LOOPBACK_HOSTS


def session_valid(request: Request) -> bool:
    """校验启动会话 Cookie 是否匹配进程令牌。"""
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    return bool(cookie) and secrets.compare_digest(cookie, SESSION_TOKEN)


def set_session_cookie(response: Response) -> None:
    """在响应中种下启动会话 Cookie（HttpOnly + SameSite=Strict）。"""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=SESSION_TOKEN,
        httponly=True,
        samesite="strict",
        path="/",
    )


def validate_write_request(request: Request) -> Optional[str]:
    """校验写请求；返回 None 表示通过，否则返回拒绝原因。"""
    if not is_loopback_host(request.headers.get("host")):
        return "非 loopback Host"
    if not is_allowed_origin(request.headers.get("origin")):
        return "跨来源 Origin"
    if not session_valid(request):
        return "缺失或错误的启动会话令牌"
    return None