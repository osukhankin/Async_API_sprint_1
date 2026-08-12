from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException
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


def _to_person_response(person: PersonModel) -> Person:
    """Доменная Person (id) → API Person (uuid)."""
    return Person(uuid=person.id, full_name=person.name)


@router.get(
    '/{film_id}/',
    response_model=FilmResponse,
    summary="Фильмы",
    description="Список фильмов с пагинацией",
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
