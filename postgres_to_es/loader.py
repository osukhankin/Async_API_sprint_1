from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch, helpers

from backoff import backoff


class ElasticsearchLoader:
    """Загрузка документов в Elasticsearch."""

    def __init__(
        self,
        es_url: str,
        index_name: str = "movies",
    ) -> None:
        """
        Args:
            es_url: Базовый URL Elasticsearch (например http://localhost:9200).
            index_name: Имя индекса для загрузки документов.
        """
        self.es_url = es_url
        self.index_name = index_name
        self.client: Elasticsearch | None = None

    @backoff()
    def connect(self) -> None:
        """Создать клиент Elasticsearch."""
        self.client = Elasticsearch(hosts=[self.es_url])
        if not self.client.ping():
            raise ConnectionError(f"Elasticsearch is unavailable: {self.es_url}")

    def close(self) -> None:
        """Закрыть клиент Elasticsearch."""
        if self.client is not None:
            self.client.close()
            self.client = None

    def _reconnect(self) -> None:
        """Переподключиться к Elasticsearch перед повтором запроса."""
        self.close()
        self.connect()

    def __enter__(self) -> ElasticsearchLoader:
        """Открыть соединение при входе в контекстный менеджер."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Закрыть соединение при выходе из контекстного менеджера."""
        self.close()

    @backoff(before_retry=lambda self, *_a, **_k: self._reconnect())
    def index_exists(self) -> bool:
        """
        Проверить, существует ли индекс.

        Returns:
            True, если индекс уже создан.
        """
        if self.client is None:
            raise RuntimeError("Elasticsearch client is not connected")
        return bool(self.client.indices.exists(index=self.index_name))

    @backoff(before_retry=lambda self, *_a, **_k: self._reconnect())
    def create_index(self, schema: dict[str, Any]) -> None:
        """
        Создать индекс по схеме, если его ещё нет.

        Args:
            schema: Тело настроек и mappings индекса
                (settings + mappings).
        """
        if self.client is None:
            raise RuntimeError("Elasticsearch client is not connected")
        if self.index_exists():
            return
        self.client.indices.create(
            index=self.index_name,
            settings=schema.get("settings"),
            mappings=schema.get("mappings"),
        )

    @backoff(before_retry=lambda self, *_a, **_k: self._reconnect())
    def bulk_load(self, documents: list[dict[str, Any]]) -> None:
        """
        Загрузить пачку документов в Elasticsearch.

        Args:
            documents: Документы для bulk-загрузки.
        """
        if not documents:
            return
        if self.client is None:
            raise RuntimeError("Elasticsearch client is not connected")

        actions = (
            {
                "_index": self.index_name,
                "_id": document["id"],
                "_source": document,
            }
            for document in documents
        )
        helpers.bulk(self.client, actions)
