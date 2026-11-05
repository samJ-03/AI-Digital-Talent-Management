from typing import Literal
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='TALENT_', extra='ignore')
    environment: Literal['dev','test','production'] = 'dev'
    database_url: SecretStr
    redis_url: SecretStr
    monitor_token: SecretStr

    @model_validator(mode='after')
    def validate_production(self):
        if self.environment == 'production' and len(self.monitor_token.get_secret_value()) < 32:
            raise ValueError('Production monitor token must contain at least 32 characters')
        return self

    @classmethod
    def load(cls) -> 'Settings':
        return cls()
