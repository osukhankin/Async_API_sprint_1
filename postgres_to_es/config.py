from functools import lru_cache
from pathlib import Path
import json
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация ETL-сервиса Postgres → Elasticsearch."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_name: str
    db_user: str
    db_password: str
    db_host: str
    db_port: int

    batch_size: int
    state_file_path: str
    poll_interval: int

    es_host: str
    es_port: int

    @property
    def dsl(self) -> dict[str, str | int]:
        """Параметры подключения для psycopg.connect(**dsl)."""
        return {
            "dbname": self.db_name,
            "user": self.db_user,
            "password": self.db_password,
            "host": self.db_host,
            "port": self.db_port,
        }

    @property
    def es_url(self) -> str:
        """Базовый URL Elasticsearch."""
        return f"http://{self.es_host}:{self.es_port}"

    def _load_schema(self, filename: str) -> dict[str, Any]:
        """Загрузить схему индекса Elasticsearch из JSON-файла."""
        schema_path = Path(__file__).resolve().parent / filename
        if not schema_path.exists():
            raise FileNotFoundError(f"ES schema file not found: {schema_path}")
        with schema_path.open(encoding="utf-8") as file:
            return json.load(file)

    @property
    def schema(self) -> dict[str, Any]:
        """Схема индекса movies для Elasticsearch."""
        return self._load_schema("es_schema.json")

    @property
    def genres_schema(self) -> dict[str, Any]:
        """Схема индекса genres для Elasticsearch."""
        return self._load_schema("es_genres_schema.json")

    @property
    def persons_schema(self) -> dict[str, Any]:
        """Схема индекса persons для Elasticsearch."""
        return self._load_schema("es_persons_schema.json")


@lru_cache
def get_settings() -> Settings:
    """Вернуть закэшированный экземпляр настроек."""
    return Settings()
