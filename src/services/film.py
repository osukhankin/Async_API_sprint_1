from functools import lru_cache
from typing import Optional

from elasticsearch import AsyncElasticsearch, NotFoundError
from fastapi import Depends
from redis.asyncio import Redis

from db.elastic import get_elastic
from db.redis import get_redis
from models.film import Film

FILM_CACHE_EXPIRE_IN_SECONDS = 60 * 5  # 5 минут


class FilmService:
    def __init__(self, redis: Redis, elastic: AsyncElasticsearch):
        self.redis = redis
        self.elastic = elastic

    async def get_by_id(self, film_id: str) -> Optional[Film]:
        film = await self._film_from_cache(film_id)
        if not film:
            film = await self._get_film_from_elastic(film_id)
            if not film:
                return None
            await self._put_film_to_cache(film)
        return film

    async def get_films(
        self,
        page_number: int,
        page_size: int,
        sort: str,
        genre: str | None = None,
    ) -> list[Film]:
        offset = (page_number - 1) * page_size
        return await self._get_films_from_elastic(
            from_=offset,
            size=page_size,
            sort=sort,
            genre=genre,
        )

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
    ) -> list[Film]:
        source_includes = ['id', 'title', 'imdb_rating']
        docs = await self.elastic.search(
            index='movies',
            query=self._build_query(genre),
            source_includes=source_includes,
            from_=from_,
            size=size,
            sort=self._build_sort(sort),
        )
        return [Film(**hit['_source']) for hit in docs['hits']['hits']]

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

    async def _film_from_cache(self, film_id: str) -> Optional[Film]:
        data = await self.redis.get(film_id)
        if not data:
            return None
        film = Film.model_validate_json(data)
        return film

    async def _put_film_to_cache(self, film: Film):
        await self.redis.set(film.id, film.model_dump_json(), FILM_CACHE_EXPIRE_IN_SECONDS)


@lru_cache()
def get_film_service(
        redis: Redis = Depends(get_redis),
        elastic: AsyncElasticsearch = Depends(get_elastic),
) -> FilmService:
    return FilmService(redis, elastic)
