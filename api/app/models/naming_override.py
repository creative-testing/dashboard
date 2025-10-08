"""
Modèle NamingOverride (corrections manuelles nomenclature)
"""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from ..database import Base


class NamingOverride(Base):
    __tablename__ = "naming_overrides"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    # Ad ID Meta
    ad_id = Column(String(255), nullable=False, index=True)

    # Nomenclature corrigée (5 champs)
    type = Column(String(100), nullable=True)      # ex: "Nuevo"
    angle = Column(String(255), nullable=True)     # ex: "Picazón"
    creator = Column(String(255), nullable=True)   # ex: "Maria"
    age = Column(String(50), nullable=True)        # ex: "25-30"
    hook = Column(String(100), nullable=True)      # ex: "H1"

    # Audit
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    tenant = relationship("Tenant", back_populates="naming_overrides")
    updated_by_user = relationship("User", back_populates="naming_overrides_created")

    def __repr__(self):
        return f"<NamingOverride ad={self.ad_id}>"
