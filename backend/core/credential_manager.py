"""Windows Credential Manager 封装（ctypes，无第三方依赖）。

PLAN §3.2 密钥边界：
- 便携版长期 API Key 必须进入 Windows Credential Manager（或等价系统凭据库）；
- 本模块用 advapi32 的 CredReadW / CredWriteW / CredDeleteW 落入 Windows
  凭据库（CRED_TYPE_GENERIC），避免 PyInstaller 打包第三方凭据库的风险；
- 不可用 / 写入失败 / 删除失败显式抛 CredentialError，绝不退回明文存储；
- 非 Windows 平台显式报告不可用（首版只验收 Windows；源码入口的**读取**
  不受影响，仅阻止**激活写入**）。
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

# ── 常量 ─────────────────────────────────────────────────────── #
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168

# 用不含反斜杠的 target 名（generic credential 的 target 建议不含 `\`）。
TARGET = "ResumeAssistant.ark_api_key"
USERNAME = "ark_api_key"


class CredentialError(Exception):
    """凭据库操作失败（不可用、读写删失败）。调用方据此显式失败，不退明文。"""


def is_supported() -> bool:
    """当前平台是否支持写入系统凭据库。"""
    return sys.platform.startswith("win")


# ── 结构体与函数签名（仅 Windows 需要） ────────────────────────── #

class _FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


class _CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", _FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", wintypes.LPBYTE),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


_PCREDENTIAL = ctypes.POINTER(_CREDENTIAL)

# WinDLL(use_last_error=True)：确保 CredXXXW 失败后 ctypes.get_last_error()
# 能取到真实错误码（否则 CredReadW 未找到凭据会误判为其它错误，无法返回 None）。
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True) if is_supported() else None


def _require_supported() -> None:
    if not is_supported() or _advapi32 is None:
        raise CredentialError("Credential Manager 仅支持 Windows；当前平台不可用")


# ── 读 / 写 / 删 ──────────────────────────────────────────────── #

def get_api_key() -> str | None:
    """读取长期 API Key；未设置返回 None；失败抛 CredentialError。"""
    _require_supported()
    pcred = _PCREDENTIAL()
    ok = _advapi32.CredReadW(TARGET, CRED_TYPE_GENERIC, 0, ctypes.byref(pcred))
    if not ok:
        err = ctypes.get_last_error()
        if err == ERROR_NOT_FOUND:
            return None
        raise CredentialError(_win_error("CredRead", err))
    try:
        cred = pcred.contents
        if not cred.CredentialBlob or cred.CredentialBlobSize == 0:
            return ""
        blob = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
        return blob.decode("utf-16-le")
    finally:
        _advapi32.CredFree(pcred)


def set_api_key(key: str) -> None:
    """写入长期 API Key（覆盖）。失败抛 CredentialError。"""
    _require_supported()
    blob = key.encode("utf-16-le")
    cred = _CREDENTIAL()
    cred.Type = CRED_TYPE_GENERIC
    cred.TargetName = TARGET
    cred.CredentialBlobSize = len(blob)
    cred.CredentialBlob = ctypes.cast(ctypes.create_string_buffer(blob), wintypes.LPBYTE)
    cred.Persist = CRED_PERSIST_LOCAL_MACHINE
    cred.UserName = USERNAME
    if not _advapi32.CredWriteW(ctypes.byref(cred), 0):
        err = ctypes.get_last_error()
        raise CredentialError(_win_error("CredWrite", err))


def delete_api_key() -> None:
    """删除长期 API Key；不存在视为成功；失败抛 CredentialError。"""
    _require_supported()
    if not _advapi32.CredDeleteW(TARGET, CRED_TYPE_GENERIC, 0):
        err = ctypes.get_last_error()
        if err == ERROR_NOT_FOUND:
            return
        raise CredentialError(_win_error("CredDelete", err))


def mask_key(key: str) -> str:
    """脱敏：只暴露末尾 4 位，前缀用星号；过短则返回固定占位。"""
    if not key:
        return "<未配置>"
    if len(key) <= 4:
        return "****"
    return "****" + key[-4:]


def _win_error(op: str, code: int) -> str:
    try:
        msg = ctypes.FormatError(code)
    except Exception:  # noqa: BLE001
        msg = f"errno={code}"
    return f"{op} 失败（{msg}）"