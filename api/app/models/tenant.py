"""
Modèle Tenant (organisation cliente)
"""
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from ..database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    meta_user_id = Column(String(64), unique=True, nullable=True)  # Meta/Facebook User ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="tenant", cascade="all, delete-orphan")
    ad_accounts = relationship("AdAccount", back_populates="tenant", cascade="all, delete-orphan")
    oauth_tokens = relationship("OAuthToken", back_populates="tenant", cascade="all, delete-orphan")
    refresh_jobs = relationship("RefreshJob", back_populates="tenant", cascade="all, delete-orphan")
    naming_overrides = relationship("NamingOverride", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant {self.name}>"
