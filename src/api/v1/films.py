from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from services.film import FilmService, get_film_service

router = APIRouter(tags=['Фильмы'])


class Person(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    uuid: str = Field(validation_alias='id')
    full_name: str = Field(validation_alias='name')


class Genre(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    uuid: str = Field(validation_alias='id')
    name: str


class FilmResponse(BaseModel):
    uuid: str
    title: str
    description: str | None = None
    imdb_rating: float | None = None
    genre: list[Genre] = Field(default_factory=list)
    actors: list[Person] = Field(default_factory=list)
    directors: list[Person] = Field(default_factory=list)
    writers: list[Person] = Field(default_factory=list)


class FilmListItem(BaseModel):
    uuid: str
    title: str
    imdb_rating: float | None = None


@router.get(
    '/search/',
    response_model=list[FilmListItem],
    summary="Поиск по фильмам",
    description="Поиск фильмов по названию и описанию с пагинацией",
)
async def films_search(
    film_service: FilmService = Depends(get_film_service),
    page_number: int = Query(1, ge=1, description='Номер страницы'),
    page_size: int = Query(50, ge=1, le=100, description='Размер страницы'),
    query: str = Query(..., min_length=1, description='Поиск по частичному совпадению имени фильма'),
) -> list[FilmListItem]:
    items = await film_service.search_films(
        page_number=page_number,
        page_size=page_size,
        query=query,
    )
    return [
        FilmListItem(uuid=film.id, title=film.title, imdb_rating=film.imdb_rating)
        for film in items
    ]


@router.get(
    '/',
    response_model=list[FilmListItem],
    summary="Список фильмов",
    description="Список фильмов с пагинацией, сортировкой и фильтром по жанру",
)
async def films_list(
    film_service: FilmService = Depends(get_film_service),
    page_number: int = Query(1, ge=1, description='Номер страницы'),
    page_size: int = Query(50, ge=1, le=100, description='Размер страницы'),
    sort: str = Query(
        '-imdb_rating',
        description='Сортировка: imdb_rating (asc) или -imdb_rating (desc)',
        pattern=r'^-?imdb_rating$',
    ),
    genre: str | None = Query(
        None,
        description='Фильтр по UUID жанра',
    ),
) -> list[FilmListItem]:
    items = await film_service.get_films(
        page_number=page_number,
        page_size=page_size,
        sort=sort,
        genre=genre,
    )
    return [
        FilmListItem(uuid=film.id, title=film.title, imdb_rating=film.imdb_rating)
        for film in items
    ]


@router.get(
    '/{film_id}/',
    response_model=FilmResponse,
    summary="Детальная информация о фильме",
    description="Возвращает полную информацию о фильме по его UUID",
)
async def film_details(film_id: str, film_service: FilmService = Depends(get_film_service)) -> FilmResponse:
    film = await film_service.get_by_id(film_id)
    if not film:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail='film not found')
    return FilmResponse(
        uuid=film.id,
        title=film.title,
        description=film.description,
        imdb_rating=film.imdb_rating,
        genre=[Genre.model_validate(genre) for genre in film.genres],
        actors=[Person.model_validate(person) for person in film.actors],
        directors=[Person.model_validate(person) for person in film.directors],
        writers=[Person.model_validate(person) for person in film.writers],
    )
