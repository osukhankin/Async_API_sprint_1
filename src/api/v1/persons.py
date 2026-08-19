from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Query

from core.pagination import Pagination
from schemas.film import FilmListItem
from schemas.person import PersonResponse
from services.person import PersonService, get_person_service

router = APIRouter(tags=['Персоны'])


@router.get(
    '/search/',
    response_model=list[PersonResponse],
    summary="Поиск по персонам",
    description="Поиск персон по имени с пагинацией",
)
async def persons_search(
    person_service: PersonService = Depends(get_person_service),
    pagination: Pagination = Depends(),
    query: str = Query(..., min_length=1, description='Поиск по частичному совпадению имени'),
) -> list[PersonResponse]:
    items = await person_service.search_persons(
        pagination=pagination,
        query=query,
    )
    return [PersonResponse.model_validate(person) for person in items]


@router.get(
    '/{person_id}/film/',
    response_model=list[FilmListItem],
    summary="Фильмы персоны",
    description="Список фильмов, в которых участвовала персона",
)
async def person_films(
    person_id: str,
    person_service: PersonService = Depends(get_person_service),
) -> list[FilmListItem]:
    films = await person_service.get_person_films(person_id)
    if films is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail='person not found')
    return [FilmListItem.model_validate(film) for film in films]


@router.get(
    '/{person_id}/',
    response_model=PersonResponse,
    summary="Детальная информация о персоне",
    description="Возвращает информацию о персоне и её ролях в фильмах",
)
async def person_details(
    person_id: str,
    person_service: PersonService = Depends(get_person_service),
) -> PersonResponse:
    person = await person_service.get_by_id(person_id)
    if not person:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail='person not found')
    return PersonResponse.model_validate(person)
