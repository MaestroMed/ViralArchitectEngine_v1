"""add device_tokens

Push (APNs) device-token registry. The iOS app POSTs its APNs token to
/v1/devices/register and we persist one row per device so the engine can wake a
backgrounded phone when clips are ready.

Revision ID: 203248308398
Revises: fca1c1626c2d
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '203248308398'
down_revision: Union[str, Sequence[str], None] = 'fca1c1626c2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('device_tokens',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('token', sa.String(length=200), nullable=False),
    sa.Column('platform', sa.String(length=20), nullable=False),
    sa.Column('bundle_id', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('device_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_device_tokens_token'), ['token'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('device_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_device_tokens_token'))

    op.drop_table('device_tokens')
