from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException

from schemas.genre import Genre
from services.genre import GenreService, get_genre_service

router = APIRouter(tags=['Жанры'])


@router.get(
    '/',
    response_model=list[Genre],
    summary="Список жанров",
    description="Список всех жанров",
)
async def genres_list(
    genre_service: GenreService = Depends(get_genre_service),
) -> list[Genre]:
    items = await genre_service.get_genres()
    return [Genre.model_validate(genre) for genre in items]


@router.get(
    '/{genre_id}/',
    response_model=Genre,
    summary="Детальная информация о жанре",
    description="Возвращает полную информацию о жанре по его UUID",
)
async def genre_details(genre_id: str, genre_service: GenreService = Depends(get_genre_service)) -> Genre:
    genre = await genre_service.get_by_id(genre_id)
    if not genre:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail='genre not found')
    return Genre.model_validate(genre)
