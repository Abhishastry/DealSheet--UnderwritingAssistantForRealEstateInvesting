"""add fixer tier and neighborhood pricing fields

Revision ID: a264982074d0
Revises: cfc32b16d78d
Create Date: 2026-08-28 02:34:22.261527

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a264982074d0'
down_revision: Union[str, Sequence[str], None] = 'cfc32b16d78d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# New enum type. deal_reasoning_confidence already exists (created in the
# initial migration) and is reused as-is for fixer_tier_confidence.
fixer_tier_enum = postgresql.ENUM(
    'light_fixer', 'medium_fixer', 'deep_fixer', 'full_build', name='fixer_tier', create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    fixer_tier_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('properties', sa.Column('fixer_tier', fixer_tier_enum, nullable=True))
    op.add_column(
        'properties',
        sa.Column(
            'fixer_tier_confidence',
            postgresql.ENUM('verified', 'likely', 'unconfirmed', name='deal_reasoning_confidence', create_type=False),
            nullable=True,
        ),
    )
    op.add_column('properties', sa.Column('pct_below_neighborhood_avg', sa.Numeric(precision=6, scale=2), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('properties', 'pct_below_neighborhood_avg')
    op.drop_column('properties', 'fixer_tier_confidence')
    op.drop_column('properties', 'fixer_tier')
    fixer_tier_enum.drop(op.get_bind(), checkfirst=True)
