from functools import lru_cache
from logging import getLogger
from typing import TypeVar

from fastapi import Depends
from pydantic import BaseModel, TypeAdapter
from redis.asyncio import Redis
from redis.exceptions import RedisError

from core.config import settings
from db.redis import get_redis

logger = getLogger(__name__)

T = TypeVar('T')
ModelT = TypeVar('ModelT', bound=BaseModel)


class CacheService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def get(self, key: str) -> bytes | None:
        try:
            return await self.redis.get(key)
        except RedisError as exc:
            logger.error('Redis unavailable on get(%s): %s', key, exc)
            return None

    async def set(self, key: str, value: str | bytes) -> None:
        try:
            await self.redis.set(key, value, settings.cache_expire_in_seconds)
        except RedisError as exc:
            logger.error('Redis unavailable on set(%s): %s', key, exc)

    async def get_model(self, key: str, model: type[ModelT]) -> ModelT | None:
        data = await self.get(key)
        if not data:
            return None
        return model.model_validate_json(data)

    async def set_model(self, key: str, value: BaseModel) -> None:
        await self.set(key, value.model_dump_json())

    async def get_typed(self, key: str, adapter: TypeAdapter[T]) -> T | None:
        data = await self.get(key)
        if not data:
            return None
        return adapter.validate_json(data)

    async def set_typed(self, key: str, adapter: TypeAdapter[T], value: T) -> None:
        await self.set(key, adapter.dump_json(value))


@lru_cache()
def get_cache_service(redis: Redis = Depends(get_redis)) -> CacheService:
    return CacheService(redis)
