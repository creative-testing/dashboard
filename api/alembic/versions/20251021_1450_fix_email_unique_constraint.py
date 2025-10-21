"""fix email unique constraint to be per-tenant

Revision ID: c8f9a2b3d4e5
Revises: ab7b593bfa67
Create Date: 2025-10-21 14:50:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'c8f9a2b3d4e5'
down_revision = 'ab7b593bfa67'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Supprimer les doublons d'email (garde le plus récent par email)
    op.execute(
        """
        DELETE FROM users
        WHERE id IN (
            SELECT id
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (PARTITION BY email ORDER BY created_at DESC) as rn
                FROM users
            ) t
            WHERE rn > 1
        )
        """
    )

    # 2. Supprimer la contrainte UNIQUE sur email seul
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key")

    # 3. Créer un index simple sur email (pour performance)
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")

    # 4. Créer une contrainte UNIQUE sur (tenant_id, email)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_users_tenant_email
        ON users (tenant_id, email)
        """
    )


def downgrade() -> None:
    # Retour en arrière (si besoin)
    op.execute("DROP INDEX IF EXISTS ux_users_tenant_email")
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)
        """
    )
