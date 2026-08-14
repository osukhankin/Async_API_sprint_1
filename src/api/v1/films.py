from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Query

from schemas.film import FilmListItem, FilmResponse
from services.film import FilmService, get_film_service

router = APIRouter(tags=['Фильмы'])


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
    return [FilmListItem.model_validate(film) for film in items]


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
    return [FilmListItem.model_validate(film) for film in items]


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
    return FilmResponse.model_validate(film)
