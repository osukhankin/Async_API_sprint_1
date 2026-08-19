from http import HTTPStatus

from fastapi import HTTPException, Query

ELASTIC_MAX_RESULT_WINDOW = 10_000
MAX_PAGE_SIZE = 100


class Pagination:
    def __init__(
        self,
        page_number: int = Query(1, ge=1, description='Номер страницы'),
        page_size: int = Query(
            50,
            ge=1,
            le=MAX_PAGE_SIZE,
            description='Размер страницы',
        ),
    ):
        if page_number * page_size > ELASTIC_MAX_RESULT_WINDOW:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail=(
                    'page_number * page_size must not exceed '
                    f'{ELASTIC_MAX_RESULT_WINDOW}'
                ),
            )
        self.page_number = page_number
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page_number - 1) * self.page_size
