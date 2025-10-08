"""
Modèle Subscription (abonnements Stripe + quotas)
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
import enum

from ..database import Base


class SubscriptionPlan(str, enum.Enum):
    """Plans disponibles"""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    """États d'abonnement Stripe"""
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    # Stripe
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)

    # Plan & Status
    plan = Column(Enum(SubscriptionPlan), nullable=False, default=SubscriptionPlan.FREE)
    status = Column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.ACTIVE)

    # Quotas (selon le plan)
    quota_accounts = Column(Integer, nullable=False, default=3)           # Max comptes
    quota_refresh_per_day = Column(Integer, nullable=False, default=1)    # Max refresh/jour

    # Billing
    current_period_end = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    tenant = relationship("Tenant", back_populates="subscriptions")

    def __repr__(self):
        return f"<Subscription {self.plan} - {self.status}>"
