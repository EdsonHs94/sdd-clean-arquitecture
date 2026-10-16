"""Migration SQL checks that need no database connection."""

from io import StringIO
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.schema import CreateIndex, CreateTable

from alembic import command
from app.infrastructure.persistence.models import Base


def config_with_output(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://unused:unused@localhost/unused")
    output = StringIO()
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"), output_buffer=output)
    return config, output


def assert_notes_schema(sql):
    assert "CREATE TABLE notes (" in sql
    assert "title VARCHAR(200) NOT NULL" in sql
    assert "body TEXT NOT NULL" in sql
    assert "created_at TIMESTAMP WITH TIME ZONE NOT NULL" in sql
    assert "updated_at TIMESTAMP WITH TIME ZONE NOT NULL" in sql
    assert "PRIMARY KEY (id)" in sql
    assert "FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT" in sql
    assert "CHECK (char_length(title) BETWEEN 1 AND 200)" in sql
    assert "CHECK (char_length(body) <= 10000)" in sql
    assert "CREATE INDEX ix_notes_owner_created_id ON notes (user_id, created_at, id)" in sql


def test_offline_upgrade_adds_private_notes_without_replacing_existing_tables(monkeypatch):
    config, output = config_with_output(monkeypatch)
    command.upgrade(config, "head", sql=True)
    assert_notes_schema(output.getvalue())
    assert "DROP TABLE" not in output.getvalue()
    assert ScriptDirectory.from_config(config).get_heads() == ["0002"]


def test_offline_notes_rollback_drops_only_notes(monkeypatch):
    config, output = config_with_output(monkeypatch)
    command.downgrade(config, "0002:0001", sql=True)
    sql = output.getvalue()
    assert "DROP INDEX ix_notes_owner_created_id" in sql
    assert "DROP TABLE notes" in sql
    assert "DROP TABLE users" not in sql
    assert "DROP TABLE files" not in sql


def test_orm_emits_notes_constraints_and_owner_listing_index():
    from sqlalchemy.dialects.postgresql import dialect

    assert "notes" in Base.metadata.tables
    table = Base.metadata.tables["notes"]
    sql = str(CreateTable(table).compile(dialect=dialect()))
    sql += "\n".join(str(CreateIndex(index).compile(dialect=dialect())) for index in table.indexes)
    assert_notes_schema(sql)
    assert all(not column.nullable for column in table.columns)
