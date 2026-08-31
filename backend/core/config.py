"""全局配置：源码资产与运行数据按 D-020 物理解耦（V1.5.0：Chroma 退出）。

- BASE_DIR：backend/ 根目录（不可变源码资产，如模板/config/prompts/.env.example）
- RESUME_DATA_DIR：统一运行数据根目录（默认位于 Git checkout 外）
  - Windows: %LOCALAPPDATA%/ResumeAssistant
  - macOS:   ~/Library/Application Support/ResumeAssistant
  - Linux:   ~/.local/share/resume-assistant
  - 可通过环境变量 RESUME_DATA_DIR 显式覆盖（绝对路径或相对 cwd 均可）
- 所有可变数据（SQLite/output/logs/cache）默认从 RESUME_DATA_DIR 派生；
  用户显式设置 SQLITE_PATH/DOCX_OUTPUT_DIR 时仍使用原值并解析为绝对路径，
  以便迁移期保留旧路径作为回滚开关。
- V1.5.0：Chroma 已退出活动配置；向量持久化统一走 SQLite BLOB 派生表（见
  services/embedding_service.py 与 database.models.FactEmbedding）。CHROMA_PATH
  配置项不再存在；numpy 仅作计算库，不承担 JSON 向量持久化或 fallback 后端。
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# backend/ 根目录：不可变源码资产根（模板/config/prompts/docs 示例）
# V2.0.0：PyInstaller 冻结时源码资产被打进 _MEIPASS 包内，BASE_DIR 指向解包根，
# 保证 templates/config/prompts/frontend 等在打包后仍可定位（PLAN §3.4 T7）。
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
# .env 仍优先从 BASE_DIR（本地开发者）读取；干净 clone 用户需复制 .env.example 并自行放好
load_dotenv(BASE_DIR / ".env")


def _default_runtime_root() -> Path:
    """默认位于 Git checkout 外的用户级数据目录，跨平台遵循 XDG/Apple/Windows 约定。"""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "ResumeAssistant"
        return Path.home() / "AppData" / "Local" / "ResumeAssistant"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ResumeAssistant"
    return Path.home() / ".local" / "share" / "resume-assistant"


def _resolve_abs(path: str | os.PathLike[str]) -> Path:
    """把输入路径转为绝对路径。相对路径按 cwd 解释（调用方显式传值时）。"""
    p = Path(os.fspath(path)).expanduser()
    return p if p.is_absolute() else (Path.cwd() / p).resolve()


# V1.4 新增：统一 runtime data root
_DATA_ROOT_ENV = os.getenv("RESUME_DATA_DIR")
if _DATA_ROOT_ENV:
    RESUME_DATA_DIR: Path = _resolve_abs(_DATA_ROOT_ENV)
else:
    RESUME_DATA_DIR = _default_runtime_root()

# runtime 子目录（全部位于 RESUME_DATA_DIR 下）
DATABASE_DIR = RESUME_DATA_DIR / "database"
DOCX_OUTPUT_DIR_DEFAULT = RESUME_DATA_DIR / "output"
LOGS_DIR = RESUME_DATA_DIR / "logs"
CACHE_DIR = RESUME_DATA_DIR / "cache"


def _setting_resolve(user_value: str | None, runtime_default: Path, *, as_dir: bool = False) -> str:
    """用户显式传值时解析为绝对路径，否则使用 runtime 派生默认值并保证父目录可写。

    - as_dir=False（默认）：runtime_default 表示**文件路径**，只保证父目录存在。
      例：SQLITE_PATH = <runtime>/database/app.db — 只 mkdir(<runtime>/database)。
    - as_dir=True：runtime_default 表示**目录**，会把自身及父目录都建好。
      例：DOCX_OUTPUT_DIR / LOGS_DIR / CACHE_DIR。

    迁移期兼容：用户可继续设置旧变量 SQLITE_PATH / DOCX_OUTPUT_DIR
    作为"旧路径回滚开关"；未设置则走 runtime 统一目录。
    V1.5.0：CHROMA_PATH 已退出活动配置（向量持久化统一走 SQLite BLOB）。
    """
    if user_value:
        return str(_resolve_abs(user_value))
    runtime_default.parent.mkdir(parents=True, exist_ok=True)
    if as_dir:
        runtime_default.mkdir(parents=True, exist_ok=True)
    return str(runtime_default)


class Settings:
    # 豆包 / 火山方舟
    ARK_API_KEY: str = os.getenv("ARK_API_KEY", "")
    ARK_BASE_URL: str = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "doubao-seed-evolving")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "doubao-embedding-vision-251215")

    # V1.4：源码资产根（只读使用，内部 modules 取模板/config/prompts 等用它）
    BASE_DIR: Path = BASE_DIR
    # V1.4：统一运行数据根（对外暴露便于诊断与下载接口基于它重算前缀）
    RESUME_DATA_DIR: Path = RESUME_DATA_DIR

    # 存储：未显式配置时默认走 runtime root 下子目录
    # V1.5.0：CHROMA_PATH 已移除（向量持久化统一走 SQLite BLOB 派生表）
    SQLITE_PATH: str = _setting_resolve(os.getenv("SQLITE_PATH"), DATABASE_DIR / "app.db")

    # 应用
    APP_HOST: str = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))

    # V1 单用户简化：默认用户标识
    DEFAULT_USER_ID: str = "demo-user"

    # DOCX 输出目录（典型是目录）
    DOCX_OUTPUT_DIR: str = _setting_resolve(os.getenv("DOCX_OUTPUT_DIR"), DOCX_OUTPUT_DIR_DEFAULT, as_dir=True)

    # 预留 logs/cache 路径（类体外按模块级 Path 重新赋值，避免类体遮蔽同名变量）
    LOGS_DIR: str = ""
    CACHE_DIR: str = ""


# 类体中无法直接引用模块级同名 Path 变量（会被类变量遮蔽），所以在类定义后显式赋值。
_RT_LOGS_DIR = LOGS_DIR  # 模块级 Path: <RESUME_DATA_DIR>/logs
_RT_CACHE_DIR = CACHE_DIR  # 模块级 Path: <RESUME_DATA_DIR>/cache
Settings.LOGS_DIR = _setting_resolve(os.getenv("LOGS_DIR"), _RT_LOGS_DIR, as_dir=True)
Settings.CACHE_DIR = _setting_resolve(os.getenv("CACHE_DIR"), _RT_CACHE_DIR, as_dir=True)

settings = Settings()

# 初始化时确保 runtime root 自身创建（避免后续写任何文件时父目录不存在）
RESUME_DATA_DIR.mkdir(parents=True, exist_ok=True)
