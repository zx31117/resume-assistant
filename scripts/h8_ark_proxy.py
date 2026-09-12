#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""H8 阻断项 B：ARK/豆包 Provider 边界**计数代理**（不读取、不记录任何 Key）。

用途：把应用侧 `ARK_BASE_URL` 指向本代理，代理原样转发到真实上游，并在 Provider 边界
统计每次 LLM/Embedding 调用 —— 用于机器断言「JD 分析恰 1 次」「rewrite 次数」「无输入页预分析」。

安全边界（硬约束）：
- **绝不**把 Authorization/任何请求头或请求/响应正文写入磁盘；只记录
  {ts, method, path, model, req_bytes, status, resp_bytes, dur_ms}。
- Key 仅在内存中随请求头透传，不落盘、不回显。
- 只监听 127.0.0.1。

用法：
  python ark_proxy.py --port 8787 --upstream https://ark.cn-beijing.volces.com --out counts.json
     └ 计数实时写入 --out（每次请求后覆盖写，便于外部轮询）
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_lock = threading.Lock()
_state: dict = {"calls": [], "by_path": {}, "total": 0}
_upstream = "https://ark.cn-beijing.volces.com"
_out = Path("counts.json")
# 只透传这些请求头（避免把无关头/连接头带过去；Authorization 必须透传但绝不落盘）
_PASS_HEADERS = ("authorization", "content-type", "accept", "openai-beta", "x-request-id")


def _record(entry: dict) -> None:
    with _lock:
        _state["calls"].append(entry)
        _state["total"] += 1
        p = entry["path"]
        _state["by_path"][p] = _state["by_path"].get(p, 0) + 1
        try:
            _out.write_text(json.dumps(_state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # 静默：绝不把含 Key 的原始请求行写日志
        return

    def _proxy(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        # 仅提取**非敏感请求形状**用于调用次数归因：model 名、是否带 tools / response_format、
        # temperature、消息条数。绝不记录任何正文、请求头或响应正文。
        model = ""
        has_tools = False
        has_response_format = False
        temperature = None
        msg_count = None
        if body:
            try:
                j = json.loads(body.decode("utf-8", "replace"))
                model = str(j.get("model") or "")
                has_tools = bool(j.get("tools"))
                has_response_format = bool(j.get("response_format"))
                temperature = j.get("temperature")
                msgs = j.get("messages")
                msg_count = len(msgs) if isinstance(msgs, list) else None
            except Exception:
                pass
        t0 = time.time()
        url = _upstream.rstrip("/") + self.path
        req = urllib.request.Request(url, data=body if body else None, method=method)
        for k, v in self.headers.items():
            if k.lower() in _PASS_HEADERS:
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = resp.read()
                status = resp.status
                ctype = resp.headers.get("Content-Type", "application/json")
        except urllib.error.HTTPError as e:
            data = e.read()
            status = e.code
            ctype = e.headers.get("Content-Type", "application/json") if e.headers else "application/json"
        except Exception as e:  # noqa: BLE001
            data = json.dumps({"error": {"message": f"proxy upstream error: {type(e).__name__}"}}).encode()
            status = 502
            ctype = "application/json"
        dur = int((time.time() - t0) * 1000)
        _record({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "method": method,
                 "path": self.path.split("?")[0], "model": model,
                 "has_tools": has_tools, "has_response_format": has_response_format,
                 "temperature": temperature, "msg_count": msg_count,
                 "req_bytes": len(body), "status": status, "resp_bytes": len(data),
                 "dur_ms": dur})
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        self._proxy("POST")

    def do_GET(self):
        self._proxy("GET")


def main() -> int:
    global _upstream, _out
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--upstream", default="https://ark.cn-beijing.volces.com")
    ap.add_argument("--out", default="counts.json")
    args = ap.parse_args()
    _upstream = args.upstream
    _out = Path(args.out)
    _out.write_text(json.dumps(_state, ensure_ascii=False), encoding="utf-8")
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"[ark-proxy] listening 127.0.0.1:{args.port} → {_upstream} (counts → {_out})", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
