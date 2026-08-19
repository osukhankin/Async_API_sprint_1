from logging import config as logging_config
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from core.logger import LOGGING

logging_config.dictConfig(LOGGING)

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR.parent / '.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    project_name: str = 'movies'
    redis_host: str = '127.0.0.1'
    redis_port: int = 6379
    elastic_host: str = '127.0.0.1'
    elastic_port: int = 9200
    elastic_schema: str = 'http://'
    cache_expire_in_seconds: int = 60 * 5


settings = Settings()
