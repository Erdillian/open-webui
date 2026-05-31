"""Add onboarding_done flag to mem_profile

Revision ID: mem_002
Revises: mem_001
Create Date: 2026-05-31 15:45:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "mem_002"
down_revision: Union[str, None] = "mem_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("mem_profile", schema=None) as batch_op:
        batch_op.add_column(sa.Column("onboarding_done", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("mem_profile", schema=None) as batch_op:
        batch_op.drop_column("onboarding_done")
