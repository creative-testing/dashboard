"""
Modèle User (utilisateur avec rôles)
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
import enum

from ..database import Base


class UserRole(str, enum.Enum):
    """Rôles disponibles"""
    OWNER = "owner"           # Propriétaire du tenant (accès total)
    ADMIN = "admin"           # Admin (gestion users + comptes)
    MANAGER = "manager"       # Account manager (accès sous-portefeuille)
    VIEWER = "viewer"         # Client final (lecture seule)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "meta_user_id", name="uq_users_tenant_meta"),
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False, index=True)  # Email unique par tenant (pas globalement)
    name = Column(String(255), nullable=True)  # User display name (from OAuth)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.VIEWER)
    meta_user_id = Column(String(64), nullable=True)  # Meta/Facebook User ID (pour OAuth)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    tenant = relationship("Tenant", back_populates="users")
    naming_overrides_created = relationship("NamingOverride", back_populates="updated_by_user")

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
