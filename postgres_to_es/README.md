# ETL: Postgres → Elasticsearch

Отказоустойчивый сервис синхронизации данных из PostgreSQL в Elasticsearch.

## Быстрый запуск (для ревью)

Из **корня репозитория**:

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f etl
```

Поднимаются:
- **theatre-db** — PostgreSQL с дампом `docker_compose/simple_project/database_dump.sql`
- **elasticsearch** — http://localhost:9200
- **etl** — фоновый перенос данных (ждёт готовности Postgres)

После первой итерации ETL проверьте Postman-коллекцию `ETLTests` против `http://localhost:9200`.

Полный сброс (перезалить БД и state с нуля):

```bash
docker compose down -v
docker compose up -d --build
```

## Структура

| Файл | Назначение |
|---|---|
| `postgres_to_es.py` | Точка входа, основной цикл |
| `extractor.py` | Извлечение из PostgreSQL |
| `transformer.py` | Преобразование в документ ES |
| `loader.py` | Загрузка в Elasticsearch |
| `state_storage.py` | Хранение курсоров синхронизации |
| `backoff.py` | Повтор при ошибках PG/ES |
| `config.py` | Настройки (pydantic) |
| `es_schema.json` | Схема индекса `movies` |
| `Dockerfile` | Образ ETL-сервиса |

## Локальный запуск без Docker

```bash
cd postgres_to_es
cp .env.example .env   # DB_HOST=localhost, ES_HOST=localhost
pip install -r requirements.txt
python postgres_to_es.py
```

PostgreSQL и Elasticsearch должны быть доступны локально (например, через `docker compose up theatre-db elasticsearch` из корня).
