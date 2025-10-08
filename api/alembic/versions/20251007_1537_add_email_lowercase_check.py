"""add_email_lowercase_check

Revision ID: 035e17324270
Revises: 2f94505c3fa4
Create Date: 2025-10-07 15:37:47.057674

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '035e17324270'
down_revision = '2f94505c3fa4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add CHECK constraint to ensure email is always lowercase
    This guard-rail prevents inconsistencies at the database level
    """
    conn = op.get_bind()

    # Add CHECK constraint: email must be NULL or lowercase
    conn.execute(sa.text("""
    ALTER TABLE users
    ADD CONSTRAINT users_email_lowercase_chk
    CHECK (email IS NULL OR email = lower(email));
    """))


def downgrade() -> None:
    """
    Remove CHECK constraint on email
    """
    conn = op.get_bind()

    conn.execute(sa.text("""
    ALTER TABLE users
    DROP CONSTRAINT IF EXISTS users_email_lowercase_chk;
    """))
