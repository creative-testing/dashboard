"""add_oauth_fields_tenant_user

Revision ID: c5f824415992
Revises: f387507b488d
Create Date: 2025-10-06 15:28:02.057605

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5f824415992'
down_revision = 'f387507b488d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add OAuth-related fields to tenants and users tables:
    - tenants.meta_user_id (unique)
    - users.meta_user_id (renamed from fb_user_id)
    - users.name
    - Unique constraints for idempotent upserts
    """
    conn = op.get_bind()

    # 1. Add meta_user_id to tenants
    try:
        op.add_column("tenants", sa.Column("meta_user_id", sa.String(length=64), nullable=True))
    except Exception:
        pass  # Column already exists

    try:
        op.create_unique_constraint("uq_tenants_meta_user_id", "tenants", ["meta_user_id"])
    except Exception:
        pass  # Constraint already exists

    # 2. Rename users.fb_user_id -> users.meta_user_id (if fb_user_id exists)
    try:
        conn.execute(sa.text("ALTER TABLE users RENAME COLUMN fb_user_id TO meta_user_id"))
    except Exception:
        # Column doesn't exist or already renamed, try to add meta_user_id
        try:
            op.add_column("users", sa.Column("meta_user_id", sa.String(length=64), nullable=True))
        except Exception:
            pass  # Column already exists

    # 3. Add users.name
    try:
        op.add_column("users", sa.Column("name", sa.String(length=255), nullable=True))
    except Exception:
        pass  # Column already exists

    # 4. Add unique constraints for idempotent upserts
    try:
        op.create_unique_constraint("uq_users_tenant_meta", "users", ["tenant_id", "meta_user_id"])
    except Exception:
        pass  # Constraint already exists

    try:
        op.create_unique_constraint("uq_oauth_user_provider", "oauth_tokens", ["user_id", "provider"])
    except Exception:
        pass  # Constraint already exists

    try:
        op.create_unique_constraint("uq_ad_accounts_tenant_fb", "ad_accounts", ["tenant_id", "fb_account_id"])
    except Exception:
        pass  # Constraint already exists


def downgrade() -> None:
    """
    Rollback OAuth fields migration
    """
    conn = op.get_bind()

    # Drop unique constraints
    try:
        op.drop_constraint("uq_ad_accounts_tenant_fb", "ad_accounts", type_="unique")
    except Exception:
        pass

    try:
        op.drop_constraint("uq_oauth_user_provider", "oauth_tokens", type_="unique")
    except Exception:
        pass

    try:
        op.drop_constraint("uq_users_tenant_meta", "users", type_="unique")
    except Exception:
        pass

    # Drop users.name
    try:
        op.drop_column("users", "name")
    except Exception:
        pass

    # Rename users.meta_user_id -> users.fb_user_id
    try:
        conn.execute(sa.text("ALTER TABLE users RENAME COLUMN meta_user_id TO fb_user_id"))
    except Exception:
        pass

    # Drop tenants.meta_user_id
    try:
        op.drop_constraint("uq_tenants_meta_user_id", "tenants", type_="unique")
    except Exception:
        pass

    try:
        op.drop_column("tenants", "meta_user_id")
    except Exception:
        pass
