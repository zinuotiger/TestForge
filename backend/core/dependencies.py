"""核心依赖注入模块 — 统一管理所有依赖项"""

from typing import Optional

from backend.config import settings
from backend.safety.auth_helpers import is_debug_mode, get_debug_user_info


# ===== 配置相关依赖 =====
def get_config() -> settings:
    """获取配置实例"""
    return settings


def is_debug() -> bool:
    """检查是否为调试模式"""
    return is_debug_mode()


def get_llm_config() -> dict:
    """获取LLM配置"""
    return settings.get_llm_config()


def get_smtp_config() -> dict:
    """获取SMTP配置"""
    return settings.get_smtp_config()


def get_execution_config() -> dict:
    """获取执行配置"""
    return settings.get_execution_config()


# ===== 调试模式相关依赖 =====
def get_debug_info() -> tuple[str, str]:
    """获取调试模式信息"""
    return get_debug_user_info()


# ===== 数据库连接池配置 =====
def get_db_pool_config() -> dict:
    """获取数据库连接池配置"""
    return {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_pre_ping": True,
        "pool_recycle": 3600,  # 1小时回收连接
    }


# ===== 缓存配置 =====
def get_cache_config() -> dict:
    """获取缓存配置"""
    return {
        "enabled": settings.cache_enabled,
        "ttl_seconds": settings.cache_ttl_seconds,
    }


# ===== RAG配置 =====
def get_rag_config() -> dict:
    """获取RAG配置"""
    return {
        "embedding_model": settings.rag_embedding_model,
        "top_k": settings.rag_top_k,
        "similarity_threshold": settings.rag_similarity_threshold,
    }


# ===== Agent配置 =====
def get_agent_config() -> dict:
    """获取Agent配置"""
    return {
        "max_iterations": settings.agent_max_iterations,
        "timeout_seconds": settings.agent_timeout_seconds,
        "temperature": settings.agent_temperature,
    }


# ===== 质量门禁配置 =====
def get_quality_config() -> dict:
    """获取质量门禁配置"""
    return {
        "coverage_threshold": settings.coverage_threshold,
        "mutation_threshold": settings.mutation_threshold,
        "flaky_rerun_count": settings.flaky_rerun_count,
    }