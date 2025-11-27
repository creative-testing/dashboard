"""Add is_disabled column to ad_accounts

Revision ID: 20251127_1100
Revises: 20251021_1450
Create Date: 2025-11-27

Allows auto-disabling accounts that repeatedly fail (403 errors)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '20251127_1100'
down_revision = '20251021_1450'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ad_accounts', sa.Column('is_disabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('ad_accounts', sa.Column('disabled_reason', sa.String(255), nullable=True))
    op.add_column('ad_accounts', sa.Column('consecutive_errors', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('ad_accounts', 'consecutive_errors')
    op.drop_column('ad_accounts', 'disabled_reason')
    op.drop_column('ad_accounts', 'is_disabled')
