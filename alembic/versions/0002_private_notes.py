"""Add owner-scoped private notes."""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="ck_notes_title_length"),
        sa.CheckConstraint("char_length(body) <= 10000", name="ck_notes_body_length"),
    )
    op.create_index("ix_notes_owner_created_id", "notes", ["user_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_notes_owner_created_id", table_name="notes")
    op.drop_table("notes")
