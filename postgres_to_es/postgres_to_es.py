import logging
import time

from config import get_settings
from extractor import PostgresExtractor
from loader import ElasticsearchLoader
from state_storage import JsonFileStorage, State
from transformer import Transformer

logger = logging.getLogger(__name__)


def postgres_to_es() -> None:
    """Main process function."""
    settings = get_settings()
    extractor = PostgresExtractor(dsn=settings.dsl, batch_size=settings.batch_size)
    loader = ElasticsearchLoader(settings.es_url)
    state = State(JsonFileStorage(settings.state_file_path))

    logger.info("ETL iteration started")
    with extractor, loader:
        loader.create_index(settings.schema)
        logger.info("Elasticsearch index is ready")

        while True:
            batch = extractor.extract_changed_films(
                film_work_modified=state.get_state("film_work_modified"),
                person_modified=state.get_state("person_modified"),
                genre_modified=state.get_state("genre_modified"),
                limit=settings.batch_size,
            )
            if not batch.has_changes:
                logger.info("No more changes to process")
                break

            logger.info("Films to upsert: %s", len(batch.film_ids))
            for offset in range(0, len(batch.film_ids), settings.batch_size):
                chunk_ids = batch.film_ids[offset:offset + settings.batch_size]
                films = extractor.extract_films_by_ids(chunk_ids)
                if not films:
                    continue
                documents = Transformer.transform_bulk(films)
                loader.bulk_load(documents)
                logger.info("Loaded %s documents to Elasticsearch", len(documents))

            for key, value in batch.state_updates.items():
                state.set_state(key, value)
            logger.info("State updated: %s", list(batch.state_updates))

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
