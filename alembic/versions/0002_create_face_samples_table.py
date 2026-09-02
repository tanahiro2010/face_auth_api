"""create face samples table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-02

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FACE_EMBEDDING_DIM = 512


def upgrade() -> None:
    op.create_table(
        "face_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("embedding", Vector(FACE_EMBEDDING_DIM), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_face_samples_person_id", "face_samples", ["person_id"])
    op.create_index(
        "ix_face_samples_embedding_cosine",
        "face_samples",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.execute(
        """
        INSERT INTO face_samples (id, person_id, embedding, source, created_at)
        SELECT id, id, embedding, 'migration', created_at
        FROM people
        """
    )


def downgrade() -> None:
    op.drop_index("ix_face_samples_embedding_cosine", table_name="face_samples")
    op.drop_index("ix_face_samples_person_id", table_name="face_samples")
    op.drop_table("face_samples")
