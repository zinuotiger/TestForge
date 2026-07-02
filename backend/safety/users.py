"""用户管理 + RBAC 角色权限体系

设计文档第十三节：
  角色:
    - Admin:  全部权限（用户管理、项目创建/删除、全局配置）
    - Editor: 测试用例CRUD、执行测试、查看报告、修改项目配置
    - Viewer: 只读（查看测试用例、执行结果、报告）

  认证方式:
    - 本地账号+密码 (PBKDF2)
    - JWT Token (24h，可刷新)
    - API Token (长期有效，可限作用域)

  安全:
    - 登录失败速率限制 (5次/分钟封IP 15分钟)
    - 敏感操作二次确认
    - 用户管理仅 Admin 可访问
"""

import json
import time
import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from backend.safety.passwords import hash_password, verify_password
from backend.models.store import _get_backend

logger = logging.getLogger("testforge")


class UserRole(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


# 权限矩阵: role → set(permissions)
PERMISSIONS = {
    UserRole.ADMIN: {
        "test:read", "test:write", "test:delete",
        "exec:run", "exec:read",
        "report:read", "report:export",
        "settings:read", "settings:write",
        "user:manage", "project:manage",
        "heal:run", "analyze:run",
    },
    UserRole.EDITOR: {
        "test:read", "test:write", "test:delete",
        "exec:run", "exec:read",
        "report:read", "report:export",
        "settings:read",
        "heal:run", "analyze:run",
    },
    UserRole.VIEWER: {
        "test:read", "exec:read",
        "report:read",
        "settings:read",
    },
}


@dataclass
class User:
    username: str
    password_hash: str
    role: UserRole = UserRole.VIEWER
    email: str = ""
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    last_login: float = 0.0
    api_token: str = ""           # 长期 API Token（用于 CI/CD）
    api_token_scope: list[str] = field(default_factory=list)  # API Token 作用域


# ============ 登录失败速率限制 ============

class LoginRateLimiter:
    """登录失败速率限制：5 次失败/分钟 → 封 IP 15 分钟"""

    def __init__(self, max_attempts: int = 5, window: int = 60, ban_duration: int = 900):
        self.max_attempts = max_attempts
        self.window = window
        self.ban_duration = ban_duration
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._banned: dict[str, float] = {}  # ip → ban_until

    def is_banned(self, ip: str) -> bool:
        ban_until = self._banned.get(ip, 0)
        if time.time() < ban_until:
            return True
        if ban_until and time.time() >= ban_until:
            del self._banned[ip]
        return False

    def record_failure(self, ip: str):
        now = time.time()
        # 清理过期记录
        self._failures[ip] = [t for t in self._failures[ip] if now - t < self.window]
        self._failures[ip].append(now)
        if len(self._failures[ip]) >= self.max_attempts:
            self._banned[ip] = now + self.ban_duration
            logger.warning("IP %s 因连续登录失败被封禁 %d 分钟", ip, self.ban_duration // 60)

    def record_success(self, ip: str):
        self._failures.pop(ip, None)
        self._banned.pop(ip, None)

    def remaining_attempts(self, ip: str) -> int:
        now = time.time()
        failures = [t for t in self._failures.get(ip, []) if now - t < self.window]
        return max(0, self.max_attempts - len(failures))


login_rate_limiter = LoginRateLimiter()


# ============ 用户存储 ============

_users_initialized = False


async def init_users_table():
    """初始化用户表"""
    global _users_initialized
    if _users_initialized:
        return
    db = await _get_backend()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'viewer',
            email TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at REAL DEFAULT 0,
            last_login REAL DEFAULT 0,
            api_token TEXT DEFAULT '',
            api_token_scope TEXT DEFAULT '[]'
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_users_api_token ON users(api_token)")
    await db.commit()

    # 确保默认 admin 存在
    from backend.config import settings
    from backend.safety.security_checks import get_admin_credentials
    
    admin_username, admin_password_hash = get_admin_credentials()
    admin = await get_user(admin_username)
    if not admin:
        await create_user(
            username=admin_username,
            password="",  # 使用 hash
            password_hash=admin_password_hash,
            role=UserRole.ADMIN,
        )
        logger.info("默认管理员用户已创建: %s", admin_username)

    _users_initialized = True


async def create_user(
    username: str,
    password: str = "",
    password_hash: str = "",
    role: UserRole = UserRole.VIEWER,
    email: str = "",
) -> User:
    """创建用户"""
    if not password_hash and password:
        password_hash = hash_password(password)

    user = User(
        username=username,
        password_hash=password_hash,
        role=role,
        email=email,
    )
    db = await _get_backend()
    await db.execute(
        """INSERT OR REPLACE INTO users
           (username, password_hash, role, email, is_active, created_at, last_login, api_token, api_token_scope)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [username, password_hash, role.value, email, 1, user.created_at, 0, "", "[]"],
    )
    await db.commit()
    logger.info("用户已创建: %s (role=%s)", username, role.value)
    return user


async def get_user(username: str) -> Optional[User]:
    """获取用户"""
    db = await _get_backend()
    row = await db.fetchone(
        "SELECT username, password_hash, role, email, is_active, created_at, last_login, api_token, api_token_scope "
        "FROM users WHERE username = ?",
        [username],
    )
    if not row:
        return None
    return _row_to_user(row)


async def get_user_by_token(api_token: str) -> Optional[User]:
    """通过 API Token 获取用户（CI/CD 场景）"""
    if not api_token:
        return None
    db = await _get_backend()
    row = await db.fetchone(
        "SELECT username, password_hash, role, email, is_active, created_at, last_login, api_token, api_token_scope "
        "FROM users WHERE api_token = ? AND api_token != ''",
        [api_token],
    )
    if not row:
        return None
    return _row_to_user(row)


async def list_users() -> list[dict]:
    """列出所有用户（Admin）"""
    db = await _get_backend()
    rows = await db.fetchall(
        "SELECT username, role, email, is_active, created_at, last_login "
        "FROM users ORDER BY created_at"
    )
    return [
        {
            "username": r[0], "role": r[1], "email": r[2],
            "is_active": bool(r[3]), "created_at": r[4], "last_login": r[5],
        }
        for r in rows
    ]


async def update_user(username: str, **fields):
    """更新用户信息"""
    allowed = {"password_hash", "role", "email", "is_active", "last_login", "api_token", "api_token_scope"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return

    set_clauses = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [username]

    db = await _get_backend()
    await db.execute(f"UPDATE users SET {set_clauses} WHERE username = ?", params)
    await db.commit()


async def delete_user(username: str) -> bool:
    """删除用户（不能删除自己/admin）"""
    from backend.config import settings
    if username == settings.admin_username:
        return False
    db = await _get_backend()
    await db.execute("DELETE FROM users WHERE username = ?", [username])
    await db.commit()
    return True


async def update_last_login(username: str):
    """更新最后登录时间"""
    await update_user(username, last_login=time.time())


async def authenticate(username: str, password: str) -> Optional[User]:
    """认证用户（用户名+密码）"""
    user = await get_user(username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    await update_last_login(username)
    return user


async def generate_api_token(username: str, scope: list[str] = None) -> str:
    """为用户生成 API Token（长期有效，用于 CI/CD）"""
    import secrets
    token = f"tf_{secrets.token_urlsafe(32)}"
    await update_user(username, api_token=token, api_token_scope=json.dumps(scope or []))
    return token


def has_permission(role: UserRole, permission: str) -> bool:
    """检查角色是否有某权限"""
    return permission in PERMISSIONS.get(role, set())


def _row_to_user(row) -> User:
    return User(
        username=row[0],
        password_hash=row[1],
        role=UserRole(row[2]) if row[2] else UserRole.VIEWER,
        email=row[3] or "",
        is_active=bool(row[4]),
        created_at=row[5] or 0,
        last_login=row[6] or 0,
        api_token=row[7] or "",
        api_token_scope=json.loads(row[8] or "[]"),
    )
