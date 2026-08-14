from functools import lru_cache
from typing import TypeVar

from fastapi import Depends
from pydantic import BaseModel, TypeAdapter
from redis.asyncio import Redis

from db.redis import get_redis

CACHE_EXPIRE_IN_SECONDS = 60 * 5  # 5 минут

T = TypeVar('T')
ModelT = TypeVar('ModelT', bound=BaseModel)


class CacheService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def get(self, key: str) -> bytes | None:
        return await self.redis.get(key)

    async def set(self, key: str, value: str | bytes) -> None:
        await self.redis.set(key, value, CACHE_EXPIRE_IN_SECONDS)

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
