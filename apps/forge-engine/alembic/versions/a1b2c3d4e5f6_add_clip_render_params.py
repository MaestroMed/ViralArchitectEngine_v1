"""add clip_queue.render_params

Stores the render parameters (trim window + caption preset + intro/jump-cut
config) used to produce each queued clip, so the in-app editor can re-render with
one tweak and reuse the exact same window. Null on clips rendered before this.

Revision ID: a1b2c3d4e5f6
Revises: 203248308398
Create Date: 2026-06-22 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "203248308398"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("clip_queue", schema=None) as batch_op:
        batch_op.add_column(sa.Column("render_params", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("clip_queue", schema=None) as batch_op:
        batch_op.drop_column("render_params")
