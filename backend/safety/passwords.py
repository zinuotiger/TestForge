"""密码哈希工具 — PBKDF2-SHA256（标准库实现，无需额外依赖）"""

import hashlib
import hmac
import os
import secrets

_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    """生成 PBKDF2 哈希，格式: pbkdf2_sha256$iterations$salt_hex$hash_hex"""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """验证密码是否匹配哈希（时间安全比较）"""
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(dk, expected)
    except (ValueError, AttributeError):
        return False


def generate_random_password(length: int = 20) -> str:
    """生成随机密码"""
    return secrets.token_urlsafe(length)
