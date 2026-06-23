"""Create memory layer tables

Revision ID: mem_001
Revises:
Create Date: 2026-05-31 14:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from open_webui.migrations.util import get_existing_tables

# revision identifiers, used by Alembic.
revision: str = "mem_001"
down_revision: Union[str, None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(get_existing_tables())

    if "mem_items" not in existing_tables:
        op.create_table(
            "mem_items",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("source_message_id", sa.String(), nullable=True),
            sa.Column("source_chat_id", sa.String(), nullable=True),
            sa.Column("source_document_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=True),
            sa.Column("timestamp_created", sa.BigInteger(), nullable=True),
            sa.Column("timestamp_event", sa.BigInteger(), nullable=True),
            sa.Column("speaker", sa.String(), nullable=True),
            sa.Column("category", sa.String(), nullable=True),
            sa.Column("importance", sa.Float(), nullable=True),
            sa.Column("sensitivity", sa.Float(), nullable=True),
            sa.Column("pinned", sa.Boolean(), nullable=True),
            sa.Column("archived", sa.Boolean(), nullable=True),
            sa.Column("superseded_by", sa.Integer(), nullable=True),
            sa.Column("related_to", sa.JSON(), nullable=True),
            sa.Column("chroma_id", sa.String(), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.Index("idx_mem_items_user_id", "user_id"),
            sa.Index("idx_mem_items_chat_id", "source_chat_id"),
            sa.Index("idx_mem_items_category", "category"),
            sa.Index("idx_mem_items_chroma_id", "chroma_id"),
        )

    if "mem_conflicts" not in existing_tables:
        op.create_table(
            "mem_conflicts",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("memory_a_id", sa.Integer(), nullable=False),
            sa.Column("memory_b_id", sa.Integer(), nullable=False),
            sa.Column("detected_at", sa.BigInteger(), nullable=True),
            sa.Column("similarity_score", sa.Float(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("resolution_memory_id", sa.Integer(), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.Index("idx_mem_conflicts_user_id", "user_id"),
            sa.Index("idx_mem_conflicts_status", "status"),
        )

    if "mem_profile" not in existing_tables:
        op.create_table(
            "mem_profile",
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("executive_summary", sa.Text(), nullable=False),
            sa.Column("full_profile_json", sa.JSON(), nullable=False),
            sa.Column("last_updated", sa.BigInteger(), nullable=True),
            sa.Column("last_full_regen", sa.BigInteger(), nullable=True),
            sa.Column("memories_since_regen", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("user_id"),
        )

    if "mem_profile_history" not in existing_tables:
        op.create_table(
            "mem_profile_history",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("executive_summary", sa.Text(), nullable=False),
            sa.Column("full_profile_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.BigInteger(), nullable=True),
            sa.Column("trigger", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.Index("idx_mem_profile_history_user_id", "user_id"),
        )

    if "mem_tags" not in existing_tables:
        op.create_table(
            "mem_tags",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("color", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "name"),
        )

    if "mem_item_tags" not in existing_tables:
        op.create_table(
            "mem_item_tags",
            sa.Column("memory_item_id", sa.Integer(), nullable=False),
            sa.Column("tag_id", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("memory_item_id", "tag_id"),
        )


def downgrade() -> None:
    existing_tables = set(get_existing_tables())

    if "mem_item_tags" in existing_tables:
        op.drop_table("mem_item_tags")
    if "mem_tags" in existing_tables:
        op.drop_table("mem_tags")
    if "mem_profile_history" in existing_tables:
        op.drop_table("mem_profile_history")
    if "mem_profile" in existing_tables:
        op.drop_table("mem_profile")
    if "mem_conflicts" in existing_tables:
        op.drop_table("mem_conflicts")
    if "mem_items" in existing_tables:
        op.drop_table("mem_items")
