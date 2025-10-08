"""
Modèle OAuthToken (tokens Facebook chiffrés)
⚠️ SÉCURITÉ: Les tokens sont chiffrés en base avec pgcrypto
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, LargeBinary, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from ..database import Base


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Provider (meta, google, tiktok, etc.)
    provider = Column(String(32), nullable=False, default="meta")

    # Facebook User
    fb_user_id = Column(String(255), nullable=True)

    # Token CHIFFRÉ (bytea)
    # ⚠️ Utilisez utils/security.py encrypt_token/decrypt_token
    access_token = Column(LargeBinary, nullable=False)

    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Scopes accordés
    scopes = Column(ARRAY(String), nullable=True)  # ex: ['ads_read', 'business_management']

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    tenant = relationship("Tenant", back_populates="oauth_tokens")

    def __repr__(self):
        return f"<OAuthToken fb_user={self.fb_user_id}>"
