"""add general_analysis to deal_reasoning_method enum

Revision ID: cfc32b16d78d
Revises: 44ce8a40ba59
Create Date: 2026-08-28 02:26:31.045642

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cfc32b16d78d'
down_revision: Union[str, Sequence[str], None] = '44ce8a40ba59'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Postgres 12+ allows ADD VALUE inside a transaction (the new value just
    # can't be used in the same transaction it's added in, which we don't
    # need to do here). IF NOT EXISTS makes this safe to re-run.
    op.execute("ALTER TYPE deal_reasoning_method ADD VALUE IF NOT EXISTS 'general_analysis'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no DROP VALUE for enum types -- removing one requires
    # rebuilding the type (rename old, create new without the value, alter
    # every column using it, drop old) and touching any rows already using
    # this value. Not worth the complexity for a downgrade path unlikely to
    # ever run; left as a deliberate no-op.
    pass
