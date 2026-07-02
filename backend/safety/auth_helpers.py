"""认证辅助函数"""

import logging
from typing import Optional

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.config import settings

logger = logging.getLogger("testforge")


def is_debug_mode() -> bool:
    """检查是否为调试模式"""
    return settings.debug


def get_debug_user_info() -> tuple[str, str]:
    """获取调试模式用户信息
    
    Returns:
        tuple: (username, role)
    """
    if not is_debug_mode():
        return "", ""
    
    logger.debug("DEBUG模式：使用开发用户身份")
    return "dev_user", "admin"


def should_skip_auth() -> bool:
    """是否跳过认证检查"""
    return is_debug_mode()


def validate_auth_in_debug(
    credentials: Optional[HTTPAuthorizationCredentials] = None
) -> Optional[str]:
    """在调试模式下验证认证
    
    Returns:
        str: 用户名（调试模式返回dev_user），None表示需要正常认证
    """
    if not is_debug_mode():
        return None
    
    # 调试模式：如果有有效凭证，使用它；否则返回dev_user
    if credentials:
        try:
            from backend.safety.auth import validate_token
            payload = validate_token(credentials.credentials)
            if payload and payload.get("type") == "access":
                return payload.get("sub", "dev_user")
        except HTTPException:
            pass  # Token无效，降级到dev_user
    
    return "dev_user"


def get_debug_role() -> str:
    """获取调试模式默认角色"""
    return "admin" if is_debug_mode() else "viewer"