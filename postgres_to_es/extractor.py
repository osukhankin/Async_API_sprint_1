from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from backoff import backoff


@dataclass(frozen=True)
class ExtractBatch:
    """Результат одной пачки инкрементальной выгрузки фильмов."""

    film_ids: list[UUID] = field(default_factory=list)
    state_updates: dict[str, str] = field(default_factory=dict)

    @property
    def has_changes(self) -> bool:
        """Есть ли изменения по film_work / person / genre."""
        return bool(self.state_updates)


@dataclass(frozen=True)
class GenreExtractBatch:
    """Результат одной пачки инкрементальной выгрузки жанров."""

    genre_ids: list[UUID] = field(default_factory=list)
    state_updates: dict[str, str] = field(default_factory=dict)

    @property
    def has_changes(self) -> bool:
        """Есть ли изменения по жанрам в фильмах."""
        return bool(self.state_updates)


class PostgresExtractor:
    """Извлечение данных из PostgreSQL для ETL Postgres → Elasticsearch."""

    def __init__(self, dsn: dict[str, Any], batch_size: int = 100) -> None:
        """
        Args:
            dsn: Параметры подключения к Postgres
                (dbname, user, password, host, port).
            batch_size: Размер пачки при инкрементальном чтении.
        """
        self.dsn = dsn
        self.batch_size = batch_size
        self.conn = None

    @backoff()
    def connect(self) -> None:
        """Открыть соединение с PostgreSQL."""
        self.conn = psycopg.connect(
            **self.dsn,
            row_factory=dict_row,
            options="-c search_path=public,content",
        )

    def close(self) -> None:
        """Закрыть соединение с PostgreSQL."""
        if self.conn and not self.conn.closed:
            self.conn.close()
            self.conn = None

    def _reconnect(self) -> None:
        """Переподключиться к PostgreSQL перед повтором запроса."""
        self.close()
        self.connect()

    def __enter__(self) -> PostgresExtractor:
        """Открыть соединение при входе в контекстный менеджер."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Закрыть соединение при выходе из контекстного менеджера."""
        self.close()

    @backoff(before_retry=lambda self, *_a, **_k: self._reconnect())
    def _extract_modified(
        self,
        table: str,
        modified_after: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Выбрать записи таблицы, изменённые после указанного момента.

        Args:
            table: Имя таблицы (film_work / person / genre).
            modified_after: Курсор из state (значение modified).
            limit: Максимум строк в пачке; по умолчанию self.batch_size.
        """
        allowed_tables = {"film_work", "person", "genre"}
        if table not in allowed_tables:
            raise ValueError(f"Unsupported table: {table}")

        batch_limit = limit or self.batch_size
        query = f"""
            SELECT id, modified
            FROM {table}
            WHERE modified > %s
            ORDER BY modified, id
            LIMIT %s;
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query, (modified_after, batch_limit))
            return cursor.fetchall()

    def extract_modified_film_works(
        self,
        modified_after: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Выбрать кинопроизведения, изменённые после указанного момента.

        Args:
            modified_after: Курсор из state (значение modified).
            limit: Максимум строк в пачке; по умолчанию self.batch_size.

        Returns:
            Список словарей с полями film_work (как минимум id, modified).
        """
        return self._extract_modified("film_work", modified_after, limit)

    def extract_modified_persons(
        self,
        modified_after: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Выбрать персон, изменённых после указанного момента.

        Args:
            modified_after: Курсор из state (значение modified).
            limit: Максимум строк в пачке; по умолчанию self.batch_size.

        Returns:
            Список словарей с полями person (как минимум id, modified).
        """
        return self._extract_modified("person", modified_after, limit)

    def extract_modified_genres(
        self,
        modified_after: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Выбрать жанры, изменённые после указанного момента.

        Args:
            modified_after: Курсор из state (значение modified).
            limit: Максимум строк в пачке; по умолчанию self.batch_size.

        Returns:
            Список словарей с полями genre (как минимум id, modified).
        """
        return self._extract_modified("genre", modified_after, limit)

    @backoff(before_retry=lambda self, *_a, **_k: self._reconnect())
    def _extract_film_ids_by_related(
        self,
        related_table: str,
        fk_column: str,
        ids: list[UUID],
    ) -> list[UUID]:
        """
        Найти id фильмов по связанным сущностям (персоны или жанры).

        Args:
            related_table: Таблица связи (person_film_work / genre_film_work).
            fk_column: Колонка внешнего ключа (person_id / genre_id).
            ids: Идентификаторы связанных сущностей.
        """
        if not ids:
            return []

        allowed = {
            "person_film_work": "person_id",
            "genre_film_work": "genre_id",
        }
        if related_table not in allowed or allowed[related_table] != fk_column:
            raise ValueError(f"Unsupported relation: {related_table}.{fk_column}")

        query = f"""
            SELECT DISTINCT film_work_id
            FROM {related_table}
            WHERE {fk_column} = ANY(%s);
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query, (list(ids),))
            return [row["film_work_id"] for row in cursor.fetchall()]

    def extract_film_ids_by_person_ids(
        self,
        person_ids: list[UUID],
    ) -> list[UUID]:
        """
        Найти id фильмов, связанных с указанными персонами.

        Нужен для каскада: изменилась персона → обновить связанные фильмы в ES.

        Args:
            person_ids: Идентификаторы персон.

        Returns:
            Список id кинопроизведений без дубликатов.
        """
        return self._extract_film_ids_by_related(
            "person_film_work",
            "person_id",
            person_ids,
        )

    def extract_film_ids_by_genre_ids(
        self,
        genre_ids: list[UUID],
    ) -> list[UUID]:
        """
        Найти id фильмов, связанных с указанными жанрами.

        Нужен для каскада: изменился жанр → обновить связанные фильмы в ES.

        Args:
            genre_ids: Идентификаторы жанров.

        Returns:
            Список id кинопроизведений без дубликатов.
        """
        return self._extract_film_ids_by_related(
            "genre_film_work",
            "genre_id",
            genre_ids,
        )

    @backoff(before_retry=lambda self, *_a, **_k: self._reconnect())
    def extract_films_by_ids(
        self,
        film_ids: list[UUID],
    ) -> list[dict[str, Any]]:
        """
        Получить полные данные фильмов для загрузки в Elasticsearch.

        Ожидается обогащение: жанры, актёры, сценаристы, режиссёры и т.п.

        Args:
            film_ids: Идентификаторы кинопроизведений.

        Returns:
            Список словарей с данными, достаточными для Transformer.
        """
        if not film_ids:
            return []

        query = """
            SELECT
                fw.id,
                fw.title,
                fw.description,
                fw.rating,
                fw.type,
                fw.created,
                fw.modified,
                COALESCE(
                    json_agg(DISTINCT jsonb_build_object(
                        'id', g.id,
                        'name', g.name
                    )) FILTER (WHERE g.id IS NOT NULL),
                    '[]'
                ) AS genres,
                COALESCE(
                    json_agg(DISTINCT jsonb_build_object(
                        'id', p.id,
                        'name', p.full_name,
                        'role', pfw.role
                    )) FILTER (WHERE p.id IS NOT NULL),
                    '[]'
                ) AS persons
            FROM film_work AS fw
            LEFT JOIN genre_film_work AS gfw ON fw.id = gfw.film_work_id
            LEFT JOIN genre AS g ON gfw.genre_id = g.id
            LEFT JOIN person_film_work AS pfw ON fw.id = pfw.film_work_id
            LEFT JOIN person AS p ON pfw.person_id = p.id
            WHERE fw.id = ANY(%s)
            GROUP BY fw.id;
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query, (list(film_ids),))
            return cursor.fetchall()

    def extract_changed_films(
        self,
        film_work_modified: str,
        person_modified: str,
        genre_modified: str,
        limit: int | None = None,
    ) -> ExtractBatch:
        """
        Собрать пачку фильмов, затронутых изменениями в PG.

        Учитывает изменения film_work, person и genre (с каскадом),
        возвращает id затронутых фильмов и новые курсоры для state.

        Args:
            film_work_modified: Курсор modified для film_work.
            person_modified: Курсор modified для person.
            genre_modified: Курсор modified для genre.
            limit: Размер пачки; по умолчанию self.batch_size.

        Returns:
            ExtractBatch с film_ids и state_updates.
        """
        modified_films = self.extract_modified_film_works(
            film_work_modified,
            limit=limit,
        )
        modified_persons = self.extract_modified_persons(
            person_modified,
            limit=limit,
        )
        modified_genres = self.extract_modified_genres(
            genre_modified,
            limit=limit,
        )

        if not (modified_films or modified_persons or modified_genres):
            return ExtractBatch()

        film_ids = {row["id"] for row in modified_films}
        film_ids.update(
            self.extract_film_ids_by_person_ids(
                [row["id"] for row in modified_persons],
            ),
        )
        film_ids.update(
            self.extract_film_ids_by_genre_ids(
                [row["id"] for row in modified_genres],
            ),
        )

        state_updates: dict[str, str] = {}
        if modified_films:
            state_updates["film_work_modified"] = max(
                row["modified"] for row in modified_films
            ).isoformat()
        if modified_persons:
            state_updates["person_modified"] = max(
                row["modified"] for row in modified_persons
            ).isoformat()
        if modified_genres:
            state_updates["genre_modified"] = max(
                row["modified"] for row in modified_genres
            ).isoformat()

        return ExtractBatch(film_ids=list(film_ids), state_updates=state_updates)

    @backoff(before_retry=lambda self, *_a, **_k: self._reconnect())
    def extract_genres_by_ids(
        self,
        genre_ids: list[UUID],
    ) -> list[dict[str, Any]]:
        """
        Получить полные данные жанров для загрузки в Elasticsearch.

        Берёт только жанры, связанные хотя бы с одним фильмом.

        Args:
            genre_ids: Идентификаторы жанров.

        Returns:
            Список словарей с данными, достаточными для Transformer.
        """
        if not genre_ids:
            return []

        query = """
            SELECT g.id, g.name, g.description
            FROM genre AS g
            INNER JOIN genre_film_work AS gfw ON g.id = gfw.genre_id
            WHERE g.id = ANY(%s)
            GROUP BY g.id;
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query, (list(genre_ids),))
            return cursor.fetchall()

    def extract_changed_genres(
        self,
        genres_index_modified: str,
        limit: int | None = None,
    ) -> GenreExtractBatch:
        """
        Собрать пачку жанров, затронутых изменениями в PG.

        Args:
            genres_index_modified: Курсор modified для индекса genres.
            limit: Размер пачки; по умолчанию self.batch_size.

        Returns:
            GenreExtractBatch с genre_ids и state_updates.
        """
        modified_genres = self.extract_modified_genres(
            genres_index_modified,
            limit=limit,
        )
        if not modified_genres:
            return GenreExtractBatch()

        return GenreExtractBatch(
            genre_ids=[row["id"] for row in modified_genres],
            state_updates={
                "genres_index_modified": max(
                    row["modified"] for row in modified_genres
                ).isoformat(),
            },
        )
