from functools import lru_cache
from typing import Optional

from elasticsearch import AsyncElasticsearch, NotFoundError
from fastapi import Depends
from pydantic import TypeAdapter

from db.elastic import get_elastic
from models.film import Film, FilmShort
from models.genre import Genre
from services.cache import CacheService, get_cache_service

FILMS_LIST_ADAPTER = TypeAdapter(list[FilmShort])


class FilmService:
    def __init__(self, cache: CacheService, elastic: AsyncElasticsearch):
        self.cache = cache
        self.elastic = elastic

    async def get_by_id(self, film_id: str) -> Optional[Film]:
        cache_key = self._film_cache_key(film_id)
        if cached := await self.cache.get_model(cache_key, Film):
            return cached

        film_data = await self._get_film_from_elastic(film_id)
        if not film_data:
            return None

        film, genre_names = film_data
        film.genres = await self._get_genres_from_elastic(genre_names)
        await self.cache.set_model(cache_key, film)
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
        if cached := await self._get_films_short_from_cache(cache_key):
            return cached

        genre_name: str | None = None
        if genre:
            genre_name = await self._get_genre_name_by_id(genre)
            if genre_name is None:
                await self._set_films_short_to_cache(cache_key, [])
                return []

        films = await self._search_films_short_from_elastic(
            from_=(page_number - 1) * page_size,
            size=page_size,
            genre=genre_name,
            sort=sort,
        )
        await self._set_films_short_to_cache(cache_key, films)
        return films

    async def search_films(
        self,
        page_number: int,
        page_size: int,
        query: str,
    ) -> list[FilmShort]:
        cache_key = self._films_search_cache_key(
            page_number=page_number,
            page_size=page_size,
            query=query,
        )
        if cached := await self._get_films_short_from_cache(cache_key):
            return cached

        films = await self._search_films_short_from_elastic(
            from_=(page_number - 1) * page_size,
            size=page_size,
            query=query,
        )
        await self._set_films_short_to_cache(cache_key, films)
        return films

    async def _get_film_from_elastic(self, film_id: str) -> tuple[Film, list[str]] | None:
        try:
            doc = await self.elastic.get(index='movies', id=film_id)
        except NotFoundError:
            return None

        source = dict(doc['_source'])
        genre_names = list(source.pop('genres', None) or [])
        return Film(**source, genres=[]), genre_names

    async def _get_genres_from_elastic(self, genre_names: list[str]) -> list[Genre]:
        if not genre_names:
            return []

        docs = await self.elastic.search(
            index='genres',
            query={
                'bool': {
                    'filter': [
                        {'terms': {'name.raw': genre_names}},
                    ],
                },
            },
            source_includes=['id', 'name'],
            size=len(genre_names),
        )
        genres_by_name = {
            genre.name: genre
            for genre in (Genre(**hit['_source']) for hit in docs['hits']['hits'])
        }
        return [
            genres_by_name[name]
            for name in genre_names
            if name in genres_by_name
        ]

    async def _get_genre_name_by_id(self, genre_id: str) -> str | None:
        try:
            doc = await self.elastic.get(
                index='genres',
                id=genre_id,
                source_includes=['name'],
            )
        except NotFoundError:
            return None
        return doc['_source'].get('name')

    async def _get_films_short_from_cache(self, cache_key: str) -> list[FilmShort] | None:
        return await self.cache.get_typed(cache_key, FILMS_LIST_ADAPTER)

    async def _set_films_short_to_cache(self, cache_key: str, films: list[FilmShort]) -> None:
        await self.cache.set_typed(cache_key, FILMS_LIST_ADAPTER, films)

    async def _search_films_short_from_elastic(
        self,
        from_: int,
        size: int,
        *,
        genre: str | None = None,
        query: str | None = None,
        sort: str | None = None,
    ) -> list[FilmShort]:
        search_kwargs: dict = {
            'index': 'movies',
            'query': self._build_query(genre, query),
            'source_includes': ['id', 'title', 'imdb_rating'],
            'from_': from_,
            'size': size,
        }
        if sort:
            search_kwargs['sort'] = self._build_sort(sort)

        docs = await self.elastic.search(**search_kwargs)
        return [FilmShort(**hit['_source']) for hit in docs['hits']['hits']]

    @staticmethod
    def _build_query(genre: str | None, query: str | None) -> dict:
        if genre:
            return {
                'bool': {
                    'filter': [
                        {'term': {'genres': genre}},
                    ],
                },
            }
        if query:
            return {
                'multi_match': {
                    'query': query,
                    'fields': ['title', 'description'],
                },
            }
        return {'match_all': {}}

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

    @staticmethod
    def _films_search_cache_key(
        page_number: int,
        page_size: int,
        query: str,
    ) -> str:
        return (
            f'films:search:query={query}'
            f':page_number={page_number}'
            f':page_size={page_size}'
        )


@lru_cache()
def get_film_service(
        cache: CacheService = Depends(get_cache_service),
        elastic: AsyncElasticsearch = Depends(get_elastic),
) -> FilmService:
    return FilmService(cache, elastic)
