# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir 打包配置（PLAN §3.4 / §6 T7）。

- 入口：packaging/launcher.py（图形启动器，loopback 起 FastAPI + 打开浏览器 + 退出）。
- 目录型 onedir：便携目录含后端运行时、前端静态资源、系统模板与必要依赖，
  不含 .env / API Key / 真实数据库 / 输出 / 缓存（runtime 一律在源码与便携目录外）。
- 静态/数据资产以 datas 打进 _MEIPASS（冻结时后端 config.py 的 BASE_DIR 即 _MEIPASS）：
    frontend/dist  → frontend/dist
    backend/templates  → templates（含已固化的 pm_template.docx / pm_template.json）
    backend/config     → config（template_mapping.json）
- handler 动态 import 的 uvicorn 协议/事件循环、langchain/openai/tiktoken 子模块与
  数据文件（tiktoken bpe、certifi 证书）不依赖子进程/交互构建，静态分析无法覆盖，
  统一走 collect_all / collect_submodules。
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

project_root = Path(SPECPATH).resolve().parent
backend_dir = project_root / "backend"
packaging_dir = project_root / "packaging"
frontend_dist = project_root / "frontend" / "dist"

datas = []
binaries = []
hiddenimports = []

# ── 前端生产构建产物 ─────────────────────────────────────────── #
datas.append((str(frontend_dist), "frontend/dist"))

# ── 只读源码资产（模板 / 映射 config；prompts 以 Python 模块随代码打包） ── #
# 只打包运行时已固化的模板文件；不整目录拷贝，避免把 git 忽略的 __pycache__
# （.pyc 内嵌开发机绝对路径）与构建脚本 _build_templates.py 带进便携包。
datas.append((str(backend_dir / "templates" / "pm_template.docx"), "templates"))
datas.append((str(backend_dir / "templates" / "pm_template.json"), "templates"))
datas.append((str(backend_dir / "config"), "config"))

# ── AI 栈动态子模块/数据文件（含 cacert 证书、tiktoken bpe 编码） ── #
for pkg in ("langchain", "langchain_core", "langchain_openai", "openai", "tiktoken", "certifi"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# ── uvicorn 动态加载（http 协议 / websocket / 事件循环 / lifespan） ── #
hiddenimports += collect_submodules("uvicorn")

# ── 后端自身模块（薄 API 路由 + core/database/models/prompts/services） ── #
hiddenimports += ["main"]
for pkg in ("api", "core", "database", "models", "prompts", "services"):
    hiddenimports += collect_submodules(pkg)

a = Analysis(
    [str(packaging_dir / "launcher.py")],
    pathex=[str(backend_dir), str(packaging_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ResumeAssistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # 图形启动器：不显示要求用户操作的控制台窗口（PLAN §3.4）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ResumeAssistant",
)