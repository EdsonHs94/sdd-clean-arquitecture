"""Async database resource lifecycle; mutations commit inside repositories."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class Database:
    def __init__(self, url: str, **engine_options: Any) -> None:
        self.engine = create_async_engine(url, hide_parameters=True, **engine_options)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        # Closing the session releases connections and rolls back any unfinished work.
        # Do not auto-commit after an HTTP response.
        async with self.session_factory() as session:
            yield session

    async def close(self) -> None:
        await self.engine.dispose()
