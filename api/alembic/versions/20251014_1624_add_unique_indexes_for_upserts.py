"""add unique indexes for upserts

Revision ID: ab7b593bfa67
Revises: 5d5e6e73a0ec
Create Date: 2025-10-14 16:24:15.063417

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'ab7b593bfa67'
down_revision = '5d5e6e73a0ec'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_oauth_tokens_user_provider
        ON oauth_tokens (user_id, provider)
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_ad_accounts_tenant_fb
        ON ad_accounts (tenant_id, fb_account_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_oauth_tokens_user_provider")
    op.execute("DROP INDEX IF EXISTS ux_ad_accounts_tenant_fb")
