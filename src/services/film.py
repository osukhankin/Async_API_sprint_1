from functools import lru_cache
from typing import Optional

from elasticsearch import AsyncElasticsearch, NotFoundError
from fastapi import Depends
from pydantic import TypeAdapter
from redis.asyncio import Redis

from db.elastic import get_elastic
from db.redis import get_redis
from models.film import Film, FilmShort

FILM_CACHE_EXPIRE_IN_SECONDS = 60 * 5  # 5 минут
FILMS_LIST_ADAPTER = TypeAdapter(list[FilmShort])


class FilmService:
    def __init__(self, redis: Redis, elastic: AsyncElasticsearch):
        self.redis = redis
        self.elastic = elastic

    async def get_by_id(self, film_id: str) -> Optional[Film]:
        cache_key = self._film_cache_key(film_id)
        data = await self._get_cache(cache_key)
        if data:
            return Film.model_validate_json(data)

        film = await self._get_film_from_elastic(film_id)
        if not film:
            return None

        await self._set_cache(cache_key, film.model_dump_json())
        return film

    async def get_films(
        self,
        page_number: int,
        page_size: int,
        sort: str,
        genre: str | None = None,
    ) -> list[FilmShort]:
        cache_key = self._films_list_cache_key(
            page_number=page_number,
            page_size=page_size,
            sort=sort,
            genre=genre,
        )
        cached = await self._get_cache(cache_key)
        if cached:
            return FILMS_LIST_ADAPTER.validate_json(cached)

        films = await self._get_films_from_elastic(
            from_=(page_number - 1) * page_size,
            size=page_size,
            sort=sort,
            genre=genre,
        )
        await self._set_cache(cache_key, FILMS_LIST_ADAPTER.dump_json(films))
        return films

    async def _get_film_from_elastic(self, film_id: str) -> Optional[Film]:
        try:
            doc = await self.elastic.get(index='movies', id=film_id)
        except NotFoundError:
            return None
        return Film(**doc['_source'])

    async def _get_films_from_elastic(
        self,
        from_: int,
        size: int,
        sort: str,
        genre: str | None = None,
    ) -> list[FilmShort]:
        source_includes = ['id', 'title', 'imdb_rating']
        docs = await self.elastic.search(
            index='movies',
            query=self._build_query(genre),
            source_includes=source_includes,
            from_=from_,
            size=size,
            sort=self._build_sort(sort),
        )
        return [FilmShort(**hit['_source']) for hit in docs['hits']['hits']]

    @staticmethod
    def _build_query(genre: str | None) -> dict:
        if not genre:
            return {'match_all': {}}
        return {
            'bool': {
                'filter': [
                    {'term': {'genres': genre}},
                ],
            },
        }

    @staticmethod
    def _build_sort(sort: str) -> list[dict]:
        order = 'desc' if sort.startswith('-') else 'asc'
        field = sort.lstrip('-')
        return [{field: {'order': order}}]

    @staticmethod
    def _film_cache_key(film_id: str) -> str:
        return f'film:{film_id}'

    @staticmethod
    def _films_list_cache_key(
        page_number: int,
        page_size: int,
        sort: str,
        genre: str | None,
    ) -> str:
        return (
            f'films:list:genre={genre or ""}'
            f':sort={sort}'
            f':page_number={page_number}'
            f':page_size={page_size}'
        )

    async def _get_cache(self, key: str) -> bytes | None:
        return await self.redis.get(key)

    async def _set_cache(self, key: str, value: str | bytes) -> None:
        await self.redis.set(key, value, FILM_CACHE_EXPIRE_IN_SECONDS)


@lru_cache()
def get_film_service(
        redis: Redis = Depends(get_redis),
        elastic: AsyncElasticsearch = Depends(get_elastic),
) -> FilmService:
    return FilmService(redis, elastic)
