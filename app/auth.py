"""管理接口的令牌校验。

PRD 4.2：所有页面公开只读，写操作凭 Admin-Token。
用 compare_digest 做常数时间比较，避免时序侧信道。
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from .config import ADMIN_TOKEN


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if not ADMIN_TOKEN or not x_admin_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "需要 Admin-Token")
    if not hmac.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Admin-Token 不正确")
