"""TestForge 配置管理 — 集中式环境变量配置"""

import logging
import os
import sys
from typing import Optional, List, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import field_validator, ConfigDict

logger = logging.getLogger("testforge")

_DEFAULT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    """TestForge 全局配置，所有环境变量统一在此管理"""
    
    model_config = ConfigDict(
        env_prefix="TESTFORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # ===== 应用配置 =====
    app_name: str = "TestForge"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 9876

    # ===== LLM 配置 =====
    llm_provider: str = "dashscope"      # LiteLLM provider
    llm_model: str = "qwen-plus"
    llm_api_key: Optional[str] = None
    llm_api_base: Optional[str] = None
    llm_fallback_chain: str = "deepseek-chat,gpt-4o-mini"
    llm_temperature_code: float = 0.1
    llm_temperature_design: float = 0.3
    llm_max_tokens_code: int = 4096
    llm_max_tokens_design: int = 8192

    # ===== 本地 LLM (Ollama) =====
    ollama_enabled: bool = True
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3-coder:7b"

    # ===== 数据库配置 =====
    database_url: str = "sqlite+aiosqlite:///testforge.db"

    # ===== 安全配置 =====
    secret_key: str = _DEFAULT_SECRET
    sandbox_enabled: bool = True
    admin_username: str = "admin"
    admin_password_hash: str = ""        # PBKDF2 哈希；为空时启动自动生成随机密码并打印
    jwt_access_token_expire_minutes: int = 1440  # 24小时
    jwt_refresh_token_expire_days: int = 7       # 7天
    rate_limit_max_requests: int = 200           # 每分钟最大请求数
    rate_limit_window_seconds: int = 60          # 限流窗口时间

    # ===== CORS 配置 =====
    cors_origins: str = "http://localhost:3000,http://localhost:9876,http://127.0.0.1:3000"

    # ===== 执行配置 =====
    max_workers: int = 4
    timeout_per_test: int = 30
    timeout_total: int = 1800
    http_test_max_concurrency: int = 10    # HTTP 测试并发数
    http_test_max_tests: int = 30          # HTTP 测试最大执行数
    http_test_timeout: int = 8             # 单个 HTTP 请求超时（秒）

    # ===== 质量门禁 =====
    coverage_threshold: float = 80.0
    mutation_threshold: float = 80.0
    flaky_rerun_count: int = 5

    # ===== 通知配置 =====
    slack_webhook_url: Optional[str] = None
    dingtalk_webhook_url: Optional[str] = None

    # ===== 邮件配置 (SMTP) =====
    smtp_host: Optional[str] = None         # 如 smtp.qq.com / smtp.gmail.com
    smtp_port: int = 465
    smtp_use_tls: bool = True
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_timeout: int = 30                  # SMTP 连接超时

    # ===== 日志配置 =====
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_date_format: str = "%Y-%m-%d %H:%M:%S"

    # ===== RAG 配置 =====
    rag_embedding_model: str = "BAAI/bge-small-zh-v1.5"  # 中文embedding模型
    rag_top_k: int = 5                                   # 检索top K结果
    rag_similarity_threshold: float = 0.7                # 相似度阈值

    # ===== Agent 配置 =====
    agent_max_iterations: int = 8                        # Agent最大迭代次数
    agent_timeout_seconds: int = 300                     # Agent超时时间
    agent_temperature: float = 0.2                       # Agent推理温度

    # ===== 性能配置 =====
    cache_enabled: bool = True                           # 是否启用缓存
    cache_ttl_seconds: int = 300                         # 缓存过期时间
    db_pool_size: int = 5                               # 数据库连接池大小
    db_max_overflow: int = 10                           # 最大溢出连接数

    @field_validator("secret_key")
    @classmethod
    def _validate_secret_key(cls, v: str) -> str:
        """验证密钥安全性"""
        if v == _DEFAULT_SECRET:
            is_debug = os.getenv("TESTFORGE_DEBUG", "").lower() in ("true", "1", "yes")
            if is_debug:
                logger.warning(
                    "⚠️ debug 模式使用默认 SECRET_KEY，仅限本地开发，"
                    "生产环境必须设置 TESTFORGE_SECRET_KEY。"
                )
                return v
            logger.error(
                "生产环境必须设置 TESTFORGE_SECRET_KEY 环境变量，"
                "不得使用默认密钥。"
            )
            sys.exit(1)
        return v

    @field_validator("cors_origins")
    @classmethod
    def _validate_cors_origins(cls, v: str) -> str:
        """验证CORS配置"""
        origins = [o.strip() for o in v.split(",") if o.strip()]
        if not origins:
            return "http://localhost:3000,http://localhost:9876,http://127.0.0.1:3000"
        return v

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, v: str) -> str:
        """验证数据库URL格式"""
        if not v:
            return "sqlite+aiosqlite:///testforge.db"
        return v

    @property
    def cors_origin_list(self) -> List[str]:
        """CORS 允许来源列表"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        """判断是否为生产环境"""
        return not self.debug

    @property
    def llm_fallback_list(self) -> List[str]:
        """LLM降级链列表"""
        return [m.strip() for m in self.llm_fallback_chain.split(",") if m.strip()]

    @property
    def is_smtp_configured(self) -> bool:
        """检查SMTP是否配置"""
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    @property
    def is_llm_configured(self) -> bool:
        """检查LLM是否配置"""
        return bool(self.llm_api_key or self.ollama_enabled)

    def get_llm_config(self) -> Dict[str, Any]:
        """获取LLM配置字典"""
        return {
            "provider": self.llm_provider,
            "model": self.llm_model,
            "api_key": self.llm_api_key,
            "api_base": self.llm_api_base,
            "temperature_code": self.llm_temperature_code,
            "temperature_design": self.llm_temperature_design,
            "max_tokens_code": self.llm_max_tokens_code,
            "max_tokens_design": self.llm_max_tokens_design,
            "ollama_enabled": self.ollama_enabled,
            "ollama_host": self.ollama_host,
            "ollama_model": self.ollama_model,
        }

    def get_smtp_config(self) -> Dict[str, Any]:
        """获取SMTP配置字典"""
        return {
            "host": self.smtp_host,
            "port": self.smtp_port,
            "use_tls": self.smtp_use_tls,
            "user": self.smtp_user,
            "password": self.smtp_password,
            "timeout": self.smtp_timeout,
        }

    def get_execution_config(self) -> Dict[str, Any]:
        """获取执行配置字典"""
        return {
            "max_workers": self.max_workers,
            "timeout_per_test": self.timeout_per_test,
            "timeout_total": self.timeout_total,
            "http_test_max_concurrency": self.http_test_max_concurrency,
            "http_test_max_tests": self.http_test_max_tests,
            "http_test_timeout": self.http_test_timeout,
        }


# 全局配置实例
settings = Settings()

# 配置验证日志
if settings.debug:
    logger.warning("⚠️ DEBUG模式已启用 - 仅限本地开发环境使用")
    
if settings.secret_key == _DEFAULT_SECRET and not settings.debug:
    logger.critical("❌ 生产环境使用了默认SECRET_KEY，存在安全风险！")

if not settings.is_llm_configured:
    logger.warning("⚠️ LLM未配置，AI相关功能可能受限")

if settings.is_smtp_configured:
    logger.info("📧 SMTP邮件服务已配置")
else:
    logger.info("📧 SMTP邮件服务未配置，邮件通知功能不可用")
