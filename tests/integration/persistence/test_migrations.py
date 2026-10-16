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
            assert set(inspector.get_table_names()) == {
                "users",
                "files",
                "notes",
                "alembic_version",
            }
            for table in ("users", "files", "notes"):
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
            assert inspector.get_pk_constraint("notes")["constrained_columns"] == ["id"]
            assert inspector.get_unique_constraints("notes") == []
            (note_fk,) = inspector.get_foreign_keys("notes")
            assert note_fk["constrained_columns"] == ["user_id"]
            assert note_fk["referred_table"] == "users"
            assert note_fk["options"]["ondelete"] == "RESTRICT"
            assert {check["name"] for check in inspector.get_check_constraints("notes")} == {
                "ck_notes_title_length",
                "ck_notes_body_length",
            }
            (note_index,) = inspector.get_indexes("notes")
            assert note_index["name"] == "ix_notes_owner_created_id"
            assert note_index["column_names"] == ["user_id", "created_at", "id"]
            columns = {column["name"]: column for column in inspector.get_columns("notes")}
            assert columns["title"]["type"].length == 200
            assert columns["created_at"]["type"].timezone
            assert columns["updated_at"]["type"].timezone

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
            "notes",
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


async def test_notes_upgrade_and_rollback_preserve_existing_users_and_files(blank_database):
    from datetime import UTC, datetime
    from uuid import uuid4

    from sqlalchemy import text

    from app.domain.entities import File, Note, User
    from app.infrastructure.persistence.file_repository import SqlAlchemyFileRepository
    from app.infrastructure.persistence.note_repository import SqlAlchemyNoteRepository
    from app.infrastructure.persistence.user_repository import SqlAlchemyUserRepository
    from tests.integration.helpers import migrate

    now = datetime(2026, 1, 1, tzinfo=UTC)
    owner = User(uuid4(), "Alice", "alice@example.com", "hash", now)
    file = File(uuid4(), owner.id, "sample.txt", "private/sample", "text/plain", 4, now)
    note = Note(uuid4(), owner.id, "Private", "content", now, now)
    await migrate(blank_database, "upgrade", "0001")
    async with blank_database.session() as session:
        await SqlAlchemyUserRepository(session).add(owner)
        await SqlAlchemyFileRepository(session).add(file)

    await migrate(blank_database, "upgrade", "head")
    async with blank_database.session() as session:
        assert await SqlAlchemyUserRepository(session).get_by_id(owner.id) == owner
        assert await SqlAlchemyFileRepository(session).get_owned(file.id, owner.id) == file
        await SqlAlchemyNoteRepository(session).add(note)

    await migrate(blank_database, "downgrade", "0001")
    async with blank_database.engine.connect() as connection:
        assert set(await connection.run_sync(lambda sync: inspect(sync).get_table_names())) == {
            "users",
            "files",
            "alembic_version",
        }
    async with blank_database.session() as session:
        assert await SqlAlchemyUserRepository(session).get_by_id(owner.id) == owner
        assert await SqlAlchemyFileRepository(session).get_owned(file.id, owner.id) == file

    await migrate(blank_database, "upgrade", "head")
    async with blank_database.session() as session:
        assert await SqlAlchemyNoteRepository(session).list_by_owner(owner.id) == []
        assert await SqlAlchemyUserRepository(session).get_by_id(owner.id) == owner
        assert await SqlAlchemyFileRepository(session).get_owned(file.id, owner.id) == file
        assert (
            await session.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one() == "0002"
