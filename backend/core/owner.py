"""V2.2.0 P0：本地单用户 owner 契约（PLAN Revision 3）。

本 Revision 的 owner 是「本地单用户」契约，不是登录/服务器化多用户。

- 唯一当前身份的**真源**是 `settings.DEFAULT_USER_ID`（backend/core/config.py 硬编码
  "demo-user"），**不来自任何请求体**（`task_id` 与 `user_id` 语义严格分离）。
- `current_user_id()` 返回当前本地身份（任何 owner 限定查询/写入都以它作为第一过滤）。
- 旧任务（无 owner，`user_id IS NULL`）保持为空并视为 `LEGACY_UNOWNED` 隔离态：
  不被列选、列表、下载与清理触碰，仅在报告/保护计数中体现。
- 其余身份（stub-user / other-user / test-user 等）在**隔离副本**中用于越权测试，
  真实 runtime 不允许通过本契约修改/清理它们。
"""
from __future__ import annotations

from core.config import settings


# 当前本地身份真源（硬编码于 config；本地单用户，不来自请求体）
DEFAULT_USER_ID: str = settings.DEFAULT_USER_ID


def current_user_id() -> str:
    """返回当前本地用户标识。

    所有 owner 限定（Experience/Fact/Task 查询、列表、清理、装配归主）统一从这里取，
    绝不从请求体取 user_id 覆盖。
    """
    return DEFAULT_USER_ID


class LocalOwnerContext:
    """反映当前本地单用户 owner 的只读上下文。

    使用示例:
        owner = LocalOwnerContext.current()
        experiences = ...filter(Experience.user_id == owner.user_id)
    """

    def __init__(self, user_id: str | None = None) -> None:
        # 显式传入仅用于越权测试的隔离副本；生产默认取 current_user_id()。
        self.user_id: str = user_id or current_user_id()

    @classmethod
    def current(cls) -> "LocalOwnerContext":
        return cls(current_user_id())

    @property
    def is_owned(self) -> bool:
        return bool(self.user_id)

    def owns(self, owner: str | None) -> bool:
        """某条记录是否属于当前 owner。

        None（LEGACY_UNOWNED）或异主一律视为不拥有（isolation）。
        """
        return owner is not None and owner == self.user_id