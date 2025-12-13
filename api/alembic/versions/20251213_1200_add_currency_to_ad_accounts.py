"""Add currency column to ad_accounts

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2025-12-13

Stores the native currency of Meta ad accounts (USD, MXN, EUR, etc.)
to display monetary values in the correct currency in the dashboard.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ad_accounts', sa.Column('currency', sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column('ad_accounts', 'currency')
