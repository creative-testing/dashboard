"""
Modèle AdAccount (comptes publicitaires Meta connectés)
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
import enum

from ..database import Base


class AccountProfile(str, enum.Enum):
    """Types de profils (KPIs différents)"""
    ECOM = "ecom"    # E-commerce (ROAS, CPA)
    LEADS = "leads"  # Lead generation (CTR, CPL)


class AdAccount(Base):
    __tablename__ = "ad_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    # Meta Ad Account
    fb_account_id = Column(String(255), nullable=False, index=True)  # ex: "act_123456"
    name = Column(String(255), nullable=True)

    # Profile type (pour adapter les KPIs)
    profile = Column(Enum(AccountProfile), nullable=False, default=AccountProfile.ECOM)

    # Metadata
    last_refresh_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Auto-disable after repeated failures (403 errors)
    is_disabled = Column(Boolean, nullable=False, default=False)
    disabled_reason = Column(String(255), nullable=True)
    consecutive_errors = Column(Integer, nullable=False, default=0)

    # Relations
    tenant = relationship("Tenant", back_populates="ad_accounts")
    refresh_jobs = relationship("RefreshJob", back_populates="ad_account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AdAccount {self.fb_account_id} - {self.name}>"
