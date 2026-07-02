"""认证与用户管理 API

端点:
  POST /api/auth/login          — 登录（用户名+密码 → JWT）
  POST /api/auth/refresh        — 刷新 Token
  POST /api/auth/logout         — 登出（客户端清除 token）
  GET  /api/auth/me             — 获取当前用户信息
  POST /api/auth/api-token      — 生成 API Token（CI/CD）
  GET  /api/auth/users          — 用户列表（Admin）
  POST /api/auth/users          — 创建用户（Admin）
  PUT  /api/auth/users/{username} — 更新用户（Admin）
  DELETE /api/auth/users/{username} — 删除用户（Admin）
  GET  /api/auth/resilience     — 熔断器/吞吐量监控状态
"""

import time
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from backend.config import settings
from backend.safety.auth_helpers import is_debug_mode
from backend.safety.auth import (
    create_token, create_refresh_token, validate_token,
    get_current_user, get_current_user_role, require_permission, require_role,
)
from backend.safety.users import (
    UserRole, User, authenticate, get_user, list_users, create_user,
    update_user, delete_user, generate_api_token, init_users_table,
    login_rate_limiter, PERMISSIONS,
)
from backend.safety.resilience import list_circuit_breakers, list_monitors
from backend.config import settings

logger = logging.getLogger("testforge")

router = APIRouter()


# ============ 请求模型 ============

class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "viewer"            # admin | editor | viewer
    email: str = ""


class UpdateUserRequest(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None


class ApiTokenRequest(BaseModel):
    scope: list[str] = []


# ============ 认证端点 ============

@router.post("/login")
async def login(req: LoginRequest, request: Request):
    """登录获取 JWT token"""
    client_ip = request.client.host if request.client else "unknown"

    # 检查 IP 是否被封禁
    if login_rate_limiter.is_banned(client_ip):
        raise HTTPException(429, "登录失败次数过多，IP 已被封禁 15 分钟")

    # 认证
    user = await authenticate(req.username, req.password)
    if not user:
        login_rate_limiter.record_failure(client_ip)
        remaining = login_rate_limiter.remaining_attempts(client_ip)
        raise HTTPException(
            401,
            f"用户名或密码错误，剩余尝试次数: {remaining}"
        )

    login_rate_limiter.record_success(client_ip)

    access_token = create_token(user.username, user.role.value)
    refresh_token = create_refresh_token(user.username, user.role.value)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 86400,
        "user": {
            "username": user.username,
            "role": user.role.value,
            "email": user.email,
        },
    }


@router.post("/refresh")
async def refresh_token(req: RefreshRequest):
    """用 refresh_token 刷新 access_token"""
    payload = validate_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(401, "Refresh token 无效或已过期")

    username = payload.get("sub", "")
    role = payload.get("role", "viewer")

    # 确认用户仍存在且活跃
    user = await get_user(username)
    if not user or not user.is_active:
        raise HTTPException(401, "用户不存在或已禁用")

    new_access_token = create_token(username, role)
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": 86400,
    }


@router.post("/logout")
async def logout(user: str = Depends(get_current_user)):
    """登出（JWT 无状态，客户端清除 token 即可）"""
    return {"status": "ok", "message": "已登出，请清除本地 token"}


@router.get("/me")
async def get_me(user: str = Depends(get_current_user)):
    """获取当前用户信息"""
    user_obj = await get_user(user)
    if not user_obj:
        # debug 模式下的 dev_user
        debug_role = UserRole.ADMIN if is_debug_mode() else UserRole.VIEWER
        return {
            "username": user,
            "role": debug_role.value,
            "permissions": list(PERMISSIONS.get(debug_role, set())),
        }
    return {
        "username": user_obj.username,
        "role": user_obj.role.value,
        "email": user_obj.email,
        "is_active": user_obj.is_active,
        "last_login": user_obj.last_login,
        "permissions": list(PERMISSIONS.get(user_obj.role, set())),
    }


@router.post("/api-token")
async def create_api_token(
    req: ApiTokenRequest,
    user: str = Depends(get_current_user),
):
    """生成 API Token（用于 CI/CD 自动化调用）"""
    token = await generate_api_token(user, req.scope)
    return {"api_token": token, "scope": req.scope}


# ============ 用户管理端点（仅 Admin）============

@router.get("/users")
async def api_list_users(admin: str = Depends(require_role(UserRole.ADMIN))):
    """用户列表（仅 Admin）"""
    return {"users": await list_users()}


@router.post("/users")
async def api_create_user(
    req: CreateUserRequest,
    admin: str = Depends(require_role(UserRole.ADMIN)),
):
    """创建用户（仅 Admin）"""
    try:
        role = UserRole(req.role)
    except ValueError:
        raise HTTPException(400, f"无效的角色: {req.role}（可选: admin/editor/viewer）")

    existing = await get_user(req.username)
    if existing:
        raise HTTPException(409, f"用户 {req.username} 已存在")

    user = await create_user(
        username=req.username,
        password=req.password,
        role=role,
        email=req.email,
    )
    return {"status": "created", "username": user.username, "role": user.role.value}


@router.put("/users/{username}")
async def api_update_user(
    username: str,
    req: UpdateUserRequest,
    admin: str = Depends(require_role(UserRole.ADMIN)),
):
    """更新用户（仅 Admin）"""
    user = await get_user(username)
    if not user:
        raise HTTPException(404, f"用户 {username} 不存在")

    fields = {}
    if req.password is not None:
        from backend.safety.passwords import hash_password
        fields["password_hash"] = hash_password(req.password)
    if req.role is not None:
        try:
            fields["role"] = UserRole(req.role).value
        except ValueError:
            raise HTTPException(400, f"无效的角色: {req.role}")
    if req.email is not None:
        fields["email"] = req.email
    if req.is_active is not None:
        fields["is_active"] = 1 if req.is_active else 0

    if fields:
        await update_user(username, **fields)

    return {"status": "updated", "username": username}


@router.delete("/users/{username}")
async def api_delete_user(
    username: str,
    admin: str = Depends(require_role(UserRole.ADMIN)),
):
    """删除用户（仅 Admin，不能删除 admin）"""
    if username == settings.admin_username:
        raise HTTPException(403, "不能删除管理员账户")
    if username == admin:
        raise HTTPException(403, "不能删除自己")

    success = await delete_user(username)
    if not success:
        raise HTTPException(400, "删除失败")
    return {"status": "deleted", "username": username}


# ============ 弹性监控端点 ============

@router.get("/resilience")
async def resilience_status(user: str = Depends(get_current_user)):
    """获取熔断器和吞吐量监控状态"""
    return {
        "circuit_breakers": list_circuit_breakers(),
        "throughput_monitors": list_monitors(),
    }
