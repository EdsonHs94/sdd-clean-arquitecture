from pathlib import Path

from alembic.config import Config

from alembic import command


async def migrate(database, operation, revision):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    async with database.engine.begin() as connection:

        def run(sync):
            config.attributes["connection"] = sync
            getattr(command, operation)(config, revision)

        await connection.run_sync(run)
