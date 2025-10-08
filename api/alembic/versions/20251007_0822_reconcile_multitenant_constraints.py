"""reconcile_multitenant_constraints

Revision ID: 2f94505c3fa4
Revises: c5f824415992
Create Date: 2025-10-07 08:22:48.331777

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f94505c3fa4'
down_revision = 'c5f824415992'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Reconciliation multi-tenant:
    1. Users: email unique global → UNIQUE(tenant_id, lower(email))
    2. OAuth tokens: add provider + UNIQUE(user_id, provider)
    3. Ad accounts: UNIQUE(tenant_id, fb_account_id)
    """
    conn = op.get_bind()

    # ===== 1. USERS: Email unique per tenant (case-insensitive) =====

    # 1a. Drop global unique constraint on email (if exists)
    conn.execute(sa.text("""
    DO $$
    BEGIN
      IF EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'users' AND c.conname = 'users_email_key'
      ) THEN
        ALTER TABLE users DROP CONSTRAINT users_email_key;
      END IF;
    END$$;
    """))

    # 1b. Create unique index on (tenant_id, lower(email))
    conn.execute(sa.text("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_users_tenant_email_lower
    ON users (tenant_id, lower(email));
    """))

    # ===== 2. OAUTH TOKENS: Add provider + unique constraint =====

    # 2a. Add provider column (if not exists)
    try:
        op.add_column("oauth_tokens", sa.Column("provider", sa.String(32), nullable=False, server_default="meta"))
    except Exception:
        pass  # Column already exists

    # 2b. Remove server_default (we only want it for existing rows)
    try:
        op.alter_column("oauth_tokens", "provider", server_default=None)
    except Exception:
        pass

    # 2c. Create unique constraint (user_id, provider)
    conn.execute(sa.text("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_oauth_tokens_user_provider'
      ) THEN
        ALTER TABLE oauth_tokens
        ADD CONSTRAINT uq_oauth_tokens_user_provider UNIQUE (user_id, provider);
      END IF;
    END$$;
    """))

    # ===== 3. AD ACCOUNTS: Unique constraint (tenant_id, fb_account_id) =====

    # Note: uq_ad_accounts_tenant_fb already created in previous migration
    # This is idempotent - will skip if exists
    conn.execute(sa.text("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_ad_accounts_tenant_fb'
      ) THEN
        ALTER TABLE ad_accounts
        ADD CONSTRAINT uq_ad_accounts_tenant_fb UNIQUE (tenant_id, fb_account_id);
      END IF;
    END$$;
    """))


def downgrade() -> None:
    """
    Rollback multi-tenant reconciliation
    """
    conn = op.get_bind()

    # 1. Restore global unique constraint on users.email
    conn.execute(sa.text("""
    DROP INDEX IF EXISTS uq_users_tenant_email_lower;
    """))

    conn.execute(sa.text("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'users_email_key'
      ) THEN
        ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email);
      END IF;
    END$$;
    """))

    # 2. Drop oauth_tokens constraints and column
    conn.execute(sa.text("""
    DO $$
    BEGIN
      IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_oauth_tokens_user_provider'
      ) THEN
        ALTER TABLE oauth_tokens DROP CONSTRAINT uq_oauth_tokens_user_provider;
      END IF;
    END$$;
    """))

    try:
        op.drop_column("oauth_tokens", "provider")
    except Exception:
        pass

    # 3. Ad accounts constraint stays (was created in previous migration)
