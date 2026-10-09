"""Composition root: concrete adapters are constructed only at the outer boundary."""

import asyncio
from contextlib import asynccontextmanager
from secrets import token_urlsafe

from fastapi import FastAPI

from app.infrastructure.persistence.file_repository import SqlAlchemyFileRepository
from app.infrastructure.persistence.session import Database
from app.infrastructure.persistence.user_repository import SqlAlchemyUserRepository
from app.infrastructure.security.passwords import Argon2PasswordHasher
from app.infrastructure.security.tokens import JwtTokenService
from app.infrastructure.settings import Settings
from app.infrastructure.storage.s3 import S3FileStorage, create_s3_client
from app.presentation.error_handlers import install_error_handlers
from app.presentation.routers import auth, files, users


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = Database(config.database_url.get_secret_value())
        s3_client = None
        try:
            hasher = Argon2PasswordHasher()
            app.state.database = database
            app.state.user_repository_factory = SqlAlchemyUserRepository
            app.state.password_hasher = hasher
            app.state.token_service = JwtTokenService(
                config.jwt_secret.get_secret_value(),
                issuer=config.jwt_issuer,
                audience=config.jwt_audience,
            )
            app.state.dummy_password_hash = await hasher.hash(token_urlsafe(32))
            s3_client = await asyncio.to_thread(
                create_s3_client, config.aws_region, config.s3_endpoint_url
            )
            app.state.file_repository_factory = SqlAlchemyFileRepository
            app.state.file_storage = S3FileStorage(s3_client, config.s3_bucket)
            yield
        finally:
            try:
                if s3_client is not None:
                    await asyncio.to_thread(s3_client.close)
            finally:
                await database.close()

    app = FastAPI(title="user-architecture-model", lifespan=lifespan)
    install_error_handlers(app)
    app.include_router(users.router)
    app.include_router(auth.router)
    app.include_router(files.router)
    return app
