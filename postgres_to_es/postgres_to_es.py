import logging
import time

from config import get_settings
from extractor import PostgresExtractor
from loader import ElasticsearchLoader
from state_storage import JsonFileStorage, State
from transformer import Transformer

logger = logging.getLogger(__name__)


def _load_films(
    extractor: PostgresExtractor,
    loader: ElasticsearchLoader,
    state: State,
    batch_size: int,
) -> None:
    """Инкрементально загрузить изменённые фильмы в индекс movies."""
    while True:
        batch = extractor.extract_changed_films(
            film_work_modified=state.get_state("film_work_modified"),
            person_modified=state.get_state("person_modified"),
            genre_modified=state.get_state("genre_modified"),
            limit=batch_size,
        )
        if not batch.has_changes:
            logger.info("No more film changes to process")
            break

        logger.info("Films to upsert: %s", len(batch.film_ids))
        for offset in range(0, len(batch.film_ids), batch_size):
            chunk_ids = batch.film_ids[offset:offset + batch_size]
            films = extractor.extract_films_by_ids(chunk_ids)
            if not films:
                continue
            documents = Transformer.transform_bulk(films)
            loader.bulk_load(documents)
            logger.info("Loaded %s film documents to Elasticsearch", len(documents))

        for key, value in batch.state_updates.items():
            state.set_state(key, value)
        logger.info("Film state updated: %s", list(batch.state_updates))


def _load_genres(
    extractor: PostgresExtractor,
    loader: ElasticsearchLoader,
    state: State,
    batch_size: int,
) -> None:
    """Инкрементально загрузить изменённые жанры в индекс genres."""
    while True:
        batch = extractor.extract_changed_genres(
            genres_index_modified=state.get_state("genres_index_modified"),
            limit=batch_size,
        )
        if not batch.has_changes:
            logger.info("No more genre changes to process")
            break

        logger.info("Genres to upsert: %s", len(batch.genre_ids))
        for offset in range(0, len(batch.genre_ids), batch_size):
            chunk_ids = batch.genre_ids[offset:offset + batch_size]
            genres = extractor.extract_genres_by_ids(chunk_ids)
            if not genres:
                continue
            documents = Transformer.transform_genres_bulk(genres)
            loader.bulk_load(documents)
            logger.info("Loaded %s genre documents to Elasticsearch", len(documents))

        for key, value in batch.state_updates.items():
            state.set_state(key, value)
        logger.info("Genre state updated: %s", list(batch.state_updates))


def _load_persons(
    extractor: PostgresExtractor,
    loader: ElasticsearchLoader,
    state: State,
    batch_size: int,
) -> None:
    """Инкрементально загрузить изменённых персон в индекс persons."""
    while True:
        batch = extractor.extract_changed_persons(
            persons_index_modified=state.get_state("persons_index_modified"),
            limit=batch_size,
        )
        if not batch.has_changes:
            logger.info("No more person changes to process")
            break

        logger.info("Persons to upsert: %s", len(batch.person_ids))
        for offset in range(0, len(batch.person_ids), batch_size):
            chunk_ids = batch.person_ids[offset:offset + batch_size]
            persons = extractor.extract_persons_by_ids(chunk_ids)
            if not persons:
                continue
            documents = Transformer.transform_persons_bulk(persons)
            loader.bulk_load(documents)
            logger.info("Loaded %s person documents to Elasticsearch", len(documents))

        for key, value in batch.state_updates.items():
            state.set_state(key, value)
        logger.info("Person state updated: %s", list(batch.state_updates))


def postgres_to_es() -> None:
    """Main process function."""
    settings = get_settings()
    extractor = PostgresExtractor(dsn=settings.dsl, batch_size=settings.batch_size)
    films_loader = ElasticsearchLoader(settings.es_url, index_name="movies")
    genres_loader = ElasticsearchLoader(settings.es_url, index_name="genres")
    persons_loader = ElasticsearchLoader(settings.es_url, index_name="persons")
    state = State(JsonFileStorage(settings.state_file_path))

    logger.info("ETL iteration started")
    with extractor, films_loader, genres_loader, persons_loader:
        films_loader.create_index(settings.schema)
        genres_loader.create_index(settings.genres_schema)
        persons_loader.create_index(settings.persons_schema)
        logger.info("Elasticsearch indexes are ready")

        _load_films(extractor, films_loader, state, settings.batch_size)
        _load_genres(extractor, genres_loader, state, settings.batch_size)
        _load_persons(extractor, persons_loader, state, settings.batch_size)

    logger.info("ETL iteration finished")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s:%(funcName)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("elastic_transport").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    settings = get_settings()
    logger.info(
        "ETL service started (poll_interval=%ss, batch_size=%s)",
        settings.poll_interval,
        settings.batch_size,
    )
    while True:
        postgres_to_es()
        logger.info("Sleeping for %s seconds", settings.poll_interval)
        time.sleep(settings.poll_interval)
