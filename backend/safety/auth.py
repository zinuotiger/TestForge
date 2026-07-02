"""JWT 认证模块 — 无状态 JWT + RBAC 角色权限 + Token 刷新

增强点（对比旧版）：
  1. JWT payload 携带 role，支持角色权限检查
  2. Token 刷新机制（refresh_token，7天有效）
  3. API Token 认证（CI/CD 场景，长期有效）
  4. require_permission 依赖注入（按权限控制端点）
  5. require_role 依赖注入（按角色控制端点）
"""

import time
import jwt
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.config import settings
from backend.safety.auth_helpers import (
    is_debug_mode,
    get_debug_user_info,
    validate_auth_in_debug,
    get_debug_role,
)
from backend.safety.users import (
    UserRole, has_permission, get_user, get_user_by_token,
    authenticate, login_rate_limiter,
)

security = HTTPBearer(auto_error=False)

# Token 类型
ACCESS_TOKEN_TTL = 24 * 3600       # 24 小时
REFRESH_TOKEN_TTL = 7 * 24 * 3600  # 7 天


def create_token(username: str, role: str = "viewer", ttl_hours: int = 24) -> str:
    """创建 JWT access token（HS256，携带角色）"""
    now = time.time()
    payload = {
        "sub": username,
        "role": role,
        "type": "access",
        "iat": int(now),
        "exp": int(now + ttl_hours * 3600),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_refresh_token(username: str, role: str = "viewer") -> str:
    """创建 JWT refresh token（7 天有效）"""
    now = time.time()
    payload = {
        "sub": username,
        "role": role,
        "type": "refresh",
        "iat": int(now),
        "exp": int(now + REFRESH_TOKEN_TTL),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def validate_token(token: str) -> dict | None:
    """验证 JWT token，返回 payload 或 None"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        return None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """依赖注入：获取当前用户名

    支持三种认证方式（优先级从高到低）：
      1. debug 模式跳过认证（仅本地开发）
      2. Bearer JWT Token
      3. X-API-Token 头（API Token，CI/CD 场景）
    """
    # DEBUG 模式检查
    debug_user = validate_auth_in_debug(credentials)
    if debug_user:
        return debug_user

    # 1. JWT Token
    if credentials:
        payload = validate_token(credentials.credentials)
        if payload and payload.get("type") == "access":
            return payload.get("sub", "")
        raise HTTPException(401, "Token 无效或已过期")

    # 2. API Token
    api_token = request.headers.get("X-API-Token", "")
    if api_token:
        user = await get_user_by_token(api_token)
        if user and user.is_active:
            return user.username
        raise HTTPException(401, "API Token 无效")

    raise HTTPException(401, "需要认证")


async def get_current_user_role(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> UserRole:
    """依赖注入：获取当前用户角色"""
    # DEBUG 模式检查
    if is_debug_mode():
        return UserRole.ADMIN

    # JWT
    if credentials:
        payload = validate_token(credentials.credentials)
        if payload and payload.get("type") == "access":
            role_str = payload.get("role", "viewer")
            try:
                return UserRole(role_str)
            except ValueError:
                return UserRole.VIEWER

    # API Token
    api_token = request.headers.get("X-API-Token", "")
    if api_token:
        user = await get_user_by_token(api_token)
        if user and user.is_active:
            return user.role

    return UserRole.VIEWER


def require_permission(permission: str):
    """依赖注入工厂：要求当前用户有指定权限

    用法:
        @router.post("/tests", dependencies=[Depends(require_permission("test:write"))])
        async def create_test(...): ...
    """
    async def _checker(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
    ):
        # DEBUG 模式检查
        if is_debug_mode():
            debug_username, _ = get_debug_user_info()
            return debug_username

        # JWT
        role = UserRole.VIEWER
        username = ""
        if credentials:
            payload = validate_token(credentials.credentials)
            if payload and payload.get("type") == "access":
                username = payload.get("sub", "")
                role_str = payload.get("role", "viewer")
                try:
                    role = UserRole(role_str)
                except ValueError:
                    role = UserRole.VIEWER
            else:
                raise HTTPException(401, "Token 无效或已过期")
        else:
            # API Token
            api_token = request.headers.get("X-API-Token", "")
            if api_token:
                user = await get_user_by_token(api_token)
                if user and user.is_active:
                    username = user.username
                    role = user.role
                else:
                    raise HTTPException(401, "API Token 无效")
            else:
                raise HTTPException(401, "需要认证")

        if not has_permission(role, permission):
            raise HTTPException(403, f"权限不足，需要 {permission} 权限（当前角色: {role.value}）")

        return username

    return _checker


def require_role(min_role: UserRole):
    """依赖注入工厂：要求当前用户至少为指定角色

    角色层级: ADMIN > EDITOR > VIEWER
    """
    role_hierarchy = {UserRole.VIEWER: 0, UserRole.EDITOR: 1, UserRole.ADMIN: 2}
    min_level = role_hierarchy[min_role]

    async def _checker(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
    ):
        # DEBUG 模式检查
        if is_debug_mode():
            debug_username, _ = get_debug_user_info()
            return debug_username

        current_role = await get_current_user_role(request, credentials)
        if role_hierarchy.get(current_role, 0) < min_level:
            raise HTTPException(403, f"角色权限不足，需要 {min_role.value} 或更高")

        if credentials:
            payload = validate_token(credentials.credentials)
            if payload:
                return payload.get("sub", "")
        return ""

    return _checker


async def optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """可选认证（不强制要求登录）"""
    if not credentials:
        return "anonymous"
    payload = validate_token(credentials.credentials)
    if payload and payload.get("type") == "access":
        return payload.get("sub", "anonymous")
    return "anonymous"
