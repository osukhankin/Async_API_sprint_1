from __future__ import annotations

from typing import Any


class Transformer:
    """Преобразование данных из Postgres в документы индекса movies."""

    @staticmethod
    def transform(film: dict[str, Any]) -> dict[str, Any]:
        """
        Преобразовать одну запись фильма в документ Elasticsearch.

        Ожидаемый вход — результат PostgresExtractor.extract_films_by_ids:
        id, title, description, rating, genres, persons и т.п.

        Args:
            film: Сырые данные фильма из Postgres.

        Returns:
            Документ для индекса movies
            (id, imdb_rating, genres, title, description,
             actors/writers/directors и соответствующие *_names).
        """
        roles = Transformer._split_persons_by_role(film.get("persons") or [])
        return {
            "id": str(film["id"]),
            "imdb_rating": film["rating"],
            "genres": Transformer._genre_names(film.get("genres") or []),
            "title": film["title"],
            "description": film["description"],
            "actors": roles["actors"],
            "actors_names": Transformer._person_names(roles["actors"]),
            "writers": roles["writers"],
            "writers_names": Transformer._person_names(roles["writers"]),
            "directors": roles["directors"],
            "directors_names": Transformer._person_names(roles["directors"]),
        }

    @staticmethod
    def transform_bulk(films: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Преобразовать пачку фильмов в документы Elasticsearch.

        Args:
            films: Список сырых записей из Postgres.

        Returns:
            Список документов для bulk-загрузки в ES.
        """
        return [Transformer.transform(film) for film in films]

    @staticmethod
    def transform_genre(genre: dict[str, Any]) -> dict[str, Any]:
        """
        Преобразовать одну запись жанра в документ Elasticsearch.

        Args:
            genre: Сырые данные жанра из Postgres.

        Returns:
            Документ для индекса genres (id, name, description).
        """
        return {
            "id": str(genre["id"]),
            "name": genre["name"],
            "description": genre["description"],
        }

    @staticmethod
    def transform_genres_bulk(genres: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Преобразовать пачку жанров в документы Elasticsearch.

        Args:
            genres: Список сырых записей из Postgres.

        Returns:
            Список документов для bulk-загрузки в ES.
        """
        return [Transformer.transform_genre(genre) for genre in genres]

    @staticmethod
    def transform_person(person: dict[str, Any]) -> dict[str, Any]:
        """
        Преобразовать одну запись персоны в документ Elasticsearch.

        Args:
            person: Сырые данные персоны из Postgres.

        Returns:
            Документ для индекса persons (id, full_name, films).
        """
        films_by_id: dict[str, list[str]] = {}
        for film in person.get("films") or []:
            film_id = str(film["id"])
            role = film["role"]
            roles = films_by_id.setdefault(film_id, [])
            if role not in roles:
                roles.append(role)

        return {
            "id": str(person["id"]),
            "full_name": person["full_name"],
            "films": [
                {"id": film_id, "roles": roles}
                for film_id, roles in films_by_id.items()
            ],
        }

    @staticmethod
    def transform_persons_bulk(persons: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Преобразовать пачку персон в документы Elasticsearch.

        Args:
            persons: Список сырых записей из Postgres.

        Returns:
            Список документов для bulk-загрузки в ES.
        """
        return [Transformer.transform_person(person) for person in persons]

    @staticmethod
    def _split_persons_by_role(
        persons: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, str]]]:
        """
        Разложить персон по ролям для полей actors / writers / directors.

        Args:
            persons: Список вида {"id", "name", "role"}.

        Returns:
            Словарь с ключами actors / writers / directors —
            списки {"id", "name"} без role.
        """
        result: dict[str, list[dict[str, str]]] = {
            "actors": [],
            "writers": [],
            "directors": [],
        }
        role_to_key = {
            "actor": "actors",
            "writer": "writers",
            "director": "directors",
        }
        for person in persons:
            key = role_to_key.get(person["role"])
            if key:
                result[key].append(
                    {"id": str(person["id"]), "name": person["name"]},
                )
        return result

    @staticmethod
    def _person_names(persons: list[dict[str, str]]) -> list[str]:
        """
        Получить список имён персон для полей *_names.

        Args:
            persons: Список {"id", "name"}.

        Returns:
            Список имён.
        """
        return [person["name"] for person in persons]

    @staticmethod
    def _genre_names(genres: list[dict[str, Any]]) -> list[str]:
        """
        Получить список названий жанров для поля genres в ES.

        Args:
            genres: Список вида {"id", "name"}.

        Returns:
            Список названий жанров.
        """
        return [genre["name"] for genre in genres]
