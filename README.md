# Movies Async API

Асинхронный API онлайн-кинотеатра: фильмы, жанры и персоны.

Клиенты ходят только в FastAPI. Данные читаются из Elasticsearch, ответы кешируются в Redis. PostgreSQL используется как источник для ETL, который наполняет индексы `movies`, `genres` и `persons`.

## Стек

- Python, FastAPI, uvicorn
- Elasticsearch
- Redis
- PostgreSQL + ETL (`postgres_to_es/`)
- Docker Compose

## Запуск

```bash
cp .env.example .env
docker compose up -d --build
```

Поднимаются API, Redis, Elasticsearch, PostgreSQL (дамп `database_dump.sql`) и ETL.

После первой итерации ETL:

- API: http://localhost:8000
- OpenAPI: http://localhost:8000/api/openapi
- Elasticsearch: http://localhost:9200

Логи ETL:

```bash
docker compose logs -f etl
```

Полный сброс данных:

```bash
docker compose down -v
docker compose up -d --build
```

### API локально, инфраструктура в Docker

```bash
docker compose up -d redis elasticsearch theatre-db etl
cd src
fastapi dev main.py
```

В `.env` для этого режима: `REDIS_HOST=127.0.0.1`, `ELASTIC_HOST=127.0.0.1`.

## Эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/v1/films/` | Список фильмов (`sort`, `genre`, пагинация) |
| GET | `/api/v1/films/search/` | Поиск фильмов |
| GET | `/api/v1/films/{uuid}/` | Карточка фильма |
| GET | `/api/v1/genres/` | Список жанров |
| GET | `/api/v1/genres/{uuid}/` | Карточка жанра |
| GET | `/api/v1/persons/search/` | Поиск персон |
| GET | `/api/v1/persons/{uuid}/` | Карточка персоны |
| GET | `/api/v1/persons/{uuid}/film/` | Фильмы персоны |

Примеры:

```bash
curl "http://localhost:8000/api/v1/films/?sort=-imdb_rating&page_size=5"
curl "http://localhost:8000/api/v1/films/search/?query=star&page_size=5"
curl "http://localhost:8000/api/v1/genres/"
curl "http://localhost:8000/api/v1/persons/search/?query=lucas&page_size=5"
```

## Структура

```
src/                 # FastAPI-приложение
  api/v1/            # Роутеры
  services/          # Бизнес-логика, Elasticsearch, кеш
  models/            # Доменные модели
  schemas/           # DTO ответов API
  db/                # Клиенты Redis и Elasticsearch
postgres_to_es/      # ETL Postgres → Elasticsearch
docker-compose.yml
```
