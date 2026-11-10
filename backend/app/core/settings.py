"""公共基础设施：加载TALENT_环境配置并校验生产环境约束。"""
from typing import Literal
from pydantic import SecretStr, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Settings：公共基础设施中的协作类型。"""
    model_config = SettingsConfigDict(env_prefix='TALENT_', extra='ignore')
    environment: Literal['dev','test','production'] = 'dev'
    database_url: SecretStr
    redis_url: SecretStr
    allowed_smtp_hosts: list[str] = ['mailpit']
    deepseek_api_key: SecretStr | None = None
    dashscope_api_key: SecretStr | None = None
    encryption_key: SecretStr | None = None
    milvus_uri: str = 'http://milvus:19530'
    semantic_top_k: int = Field(default=200,ge=1,le=1000)
    semantic_min_relevance: float = Field(default=0.0,ge=-1,le=1)
    minio_endpoint: str = 'minio:9000'
    minio_user: SecretStr | None = None
    minio_password: SecretStr | None = None
    minio_bucket: str = 'talent-business'
    minio_secure: bool = False
    max_file_bytes: int = 20*1024*1024
    max_file_pages: int = 100
    session_namespace: str = 'talent:staff'
    trusted_origins: list[str] = ['http://localhost:13000','http://127.0.0.1:13000']
    monitor_token: SecretStr

    @model_validator(mode='after')
    def validate_production(self):
        """校验生产监控令牌与HTTPS来源约束。"""
        if self.environment == 'production' and len(self.monitor_token.get_secret_value()) < 32:
            raise ValueError('Production monitor token must contain at least 32 characters')
        if self.environment == 'production' and any(not origin.startswith('https://') for origin in self.trusted_origins):
            raise ValueError('Production origins must use HTTPS')
        return self

    @classmethod
    def load(cls) -> 'Settings':
        """从进程环境加载并校验应用配置。"""
        return cls()
