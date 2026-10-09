import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect

from app.infrastructure.persistence.models import Base

pytestmark = pytest.mark.integration


async def test_blank_upgrade_has_constraints_and_owner_listing_index(blank_database):
    from tests.integration.helpers import migrate

    await migrate(blank_database, "upgrade", "head")
    async with blank_database.engine.connect() as connection:

        def inspect_schema(sync):
            inspector = inspect(sync)
            assert set(inspector.get_table_names()) == {"users", "files", "alembic_version"}
            for table in ("users", "files"):
                assert all(not column["nullable"] for column in inspector.get_columns(table))
            assert inspector.get_pk_constraint("users")["constrained_columns"] == ["id"]
            assert inspector.get_pk_constraint("files")["constrained_columns"] == ["id"]
            assert inspector.get_unique_constraints("users")[0]["column_names"] == ["email"]
            assert inspector.get_unique_constraints("files")[0]["column_names"] == ["storage_key"]
            (foreign_key,) = inspector.get_foreign_keys("files")
            assert foreign_key["referred_table"] == "users"
            assert foreign_key["options"]["ondelete"] == "RESTRICT"
            assert inspector.get_check_constraints("files")[0]["name"] == "ck_files_size"
            index = next(
                i
                for i in inspector.get_indexes("files")
                if i["name"] == "ix_files_owner_created_id"
            )
            assert index["column_names"] == ["user_id", "created_at", "id"]

        await connection.run_sync(inspect_schema)


async def test_downgrade_then_upgrade_recreates_schema(blank_database):
    from tests.integration.helpers import migrate

    await migrate(blank_database, "upgrade", "head")
    await migrate(blank_database, "downgrade", "base")
    async with blank_database.engine.connect() as connection:
        assert await connection.run_sync(lambda sync: inspect(sync).get_table_names()) == [
            "alembic_version"
        ]
    await migrate(blank_database, "upgrade", "head")
    async with blank_database.engine.connect() as connection:
        assert set(await connection.run_sync(lambda sync: inspect(sync).get_table_names())) == {
            "users",
            "files",
            "alembic_version",
        }


async def test_migrated_schema_matches_orm_metadata(blank_database):
    from tests.integration.helpers import migrate

    await migrate(blank_database, "upgrade", "head")
    async with blank_database.engine.connect() as connection:

        def differences(sync):
            return compare_metadata(MigrationContext.configure(sync), Base.metadata)

        assert await connection.run_sync(differences) == []


def test_revision_template_renders_valid_python():
    import ast
    from pathlib import Path

    from mako.template import Template

    template = Path(__file__).resolve().parents[3] / "alembic/script.py.mako"
    rendered = Template(filename=str(template)).render(
        message="next migration",
        imports="",
        up_revision="0002",
        down_revision="0001",
        branch_labels=None,
        depends_on=None,
        upgrades="pass",
        downgrades="pass",
    )
    ast.parse(rendered)
