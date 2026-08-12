import logging
import time
from functools import wraps

import psycopg
from elastic_transport import TransportError

logger = logging.getLogger(__name__)


def backoff(
    start_sleep_time=0.1,
    factor=2,
    border_sleep_time=10,
    max_retries=10,
    before_retry=None,
):
    """
    Функция для повторного выполнения функции через некоторое время, если возникла ошибка.
    Использует наивный экспоненциальный рост времени повтора (factor)
    до граничного времени ожидания (border_sleep_time)
    """

    def func_wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            n = 0
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (
                    ConnectionError,
                    TimeoutError,
                    psycopg.OperationalError,
                    psycopg.InterfaceError,
                    TransportError,
                ) as exc:
                    if attempt == max_retries:
                        raise

                    if before_retry is not None:
                        before_retry(*args, **kwargs)

                    sleep_time = start_sleep_time * (factor ** n)
                    if sleep_time >= border_sleep_time:
                        sleep_time = border_sleep_time
                    else:
                        n += 1

                    logger.warning(
                        f"Backoff for {func.__name__}: {exc}. Retry in {sleep_time:.1f}s"
                    )
                    time.sleep(sleep_time)

        return inner

    return func_wrapper
