"""Add audit log table

Revision ID: mem_003
Revises: mem_002
Create Date: 2026-05-31 18:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "mem_003"
down_revision = "mem_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mem_audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("chat_id", sa.String(), nullable=True),
        sa.Column("memory_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_timestamp", "mem_audit_log", ["timestamp"])
    op.create_index("idx_audit_user_event", "mem_audit_log", ["user_id", "event_type"])
    op.create_index("idx_audit_chat", "mem_audit_log", ["chat_id"])
    op.create_index("idx_audit_memory", "mem_audit_log", ["memory_id"])


def downgrade() -> None:
    op.drop_index("idx_audit_memory", table_name="mem_audit_log")
    op.drop_index("idx_audit_chat", table_name="mem_audit_log")
    op.drop_index("idx_audit_user_event", table_name="mem_audit_log")
    op.drop_index("idx_audit_timestamp", table_name="mem_audit_log")
    op.drop_table("mem_audit_log")
