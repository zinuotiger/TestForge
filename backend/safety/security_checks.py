"""安全检查和环境验证"""

import logging
import secrets
import string
from typing import Optional

from backend.config import settings
from backend.safety.passwords import hash_password

logger = logging.getLogger("testforge")


def validate_security_config() -> None:
    """验证安全相关配置"""
    
    # 检查密钥安全性
    if settings.secret_key == "change-me-in-production":
        if settings.debug:
            logger.warning(
                "⚠️ DEBUG模式使用了默认SECRET_KEY，仅限本地开发使用。"
            )
        else:
            logger.critical(
                "❌ 生产环境使用了默认SECRET_KEY，存在严重安全风险！"
                "请设置TESTFORGE_SECRET_KEY环境变量。"
            )
    
    # 检查管理员密码
    if not settings.admin_password_hash:
        if settings.debug:
            logger.warning(
                "⚠️ 未配置管理员密码哈希，DEBUG模式下使用默认密码'testforge'。"
            )
        else:
            logger.warning(
                "⚠️ 未配置管理员密码哈希，已自动生成随机密码。"
            )
    
    # 检查SMTP配置
    if settings.is_smtp_configured:
        logger.info("✅ SMTP邮件服务已配置")
    else:
        logger.info("ℹ️ SMTP邮件服务未配置，邮件通知功能不可用")
    
    # 检查LLM配置
    if settings.is_llm_configured:
        logger.info("✅ LLM服务已配置")
    else:
        logger.warning("⚠️ LLM服务未配置，AI相关功能将受限")


def get_admin_credentials() -> tuple[str, str]:
    """获取管理员凭据（用户名和密码哈希）
    
    Returns:
        tuple: (username, password_hash)
    """
    username = settings.admin_username
    
    if settings.admin_password_hash:
        return username, settings.admin_password_hash
    
    if settings.debug:
        # DEBUG模式使用固定密码
        default_password = "testforge"
        password_hash = hash_password(default_password)
        logger.warning(
            f"⚠️ DEBUG模式：管理员用户 '{username}' 密码为 '{default_password}'，请勿用于生产"
        )
        return username, password_hash
    
    # 生产模式生成随机密码
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    random_password = ''.join(secrets.choice(alphabet) for _ in range(16))
    password_hash = hash_password(random_password)
    
    print(
        f"\n{'=' * 60}\n"
        f"  生产模式：已生成随机管理员密码\n"
        f"  用户名: {username}\n"
        f"  密码:   {random_password}\n"
        f"  请妥善保存，建议尽快通过 TESTFORGE_ADMIN_PASSWORD_HASH 配置固定哈希。\n"
        f"{'=' * 60}\n"
    )
    
    return username, password_hash


def check_debug_mode_warnings() -> None:
    """检查并输出DEBUG模式警告"""
    if settings.debug:
        logger.warning("⚠️ DEBUG模式已启用 - 认证已跳过，仅供本地开发！")
        
        # 输出所有DEBUG模式相关的警告
        warnings = [
            "调试模式启用了简化认证",
            "使用了默认或弱安全性配置",
            "部分安全检查被禁用",
            "生产环境请确保DEBUG=false"
        ]
        
        for warning in warnings:
            logger.warning(f"  - {warning}")


def validate_cors_config() -> list[str]:
    """验证并返回CORS配置列表"""
    origins = settings.cors_origin_list
    
    if not origins:
        logger.warning("⚠️ CORS配置为空，将使用默认值")
        return ["http://localhost:3000", "http://localhost:9876", "http://127.0.0.1:3000"]
    
    # 检查是否有通配符（生产环境不推荐）
    if "*" in origins and not settings.debug:
        logger.warning("⚠️ 生产环境中使用CORS通配符(*)存在安全风险")
    
    logger.info(f"✅ CORS配置: {len(origins)}个来源")
    return origins


def get_secure_random_string(length: int = 32) -> str:
    """生成安全的随机字符串"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))