from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from models.person import Person as PersonModel
from services.film import FilmService, get_film_service

router = APIRouter(tags=['Фильмы'])


class Person(BaseModel):
    uuid: str
    full_name: str


class FilmResponse(BaseModel):
    uuid: str
    title: str
    description: str | None = None
    imdb_rating: float | None = None
    genres: list[str] = Field(default_factory=list)
    actors: list[Person] = Field(default_factory=list)
    directors: list[Person] = Field(default_factory=list)
    writers: list[Person] = Field(default_factory=list)


class FilmListItem(BaseModel):
    uuid: str
    title: str
    imdb_rating: float | None = None


def _to_person_response(person: PersonModel) -> Person:
    """Доменная Person (id) → API Person (uuid)."""
    return Person(uuid=person.id, full_name=person.name)


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
        genres=film.genres,
        actors=[_to_person_response(person) for person in film.actors],
        directors=[_to_person_response(person) for person in film.directors],
        writers=[_to_person_response(person) for person in film.writers],
    )


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
        description='Фильтр по жанру (точное совпадение, например Action)',
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
