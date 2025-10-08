"""
Modèle RefreshJob (suivi des jobs de rafraîchissement)
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
import enum

from ..database import Base


class JobStatus(str, enum.Enum):
    """États d'un job de refresh"""
    QUEUED = "queued"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"


class RefreshJob(Base):
    __tablename__ = "refresh_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    ad_account_id = Column(UUID(as_uuid=True), ForeignKey("ad_accounts.id", ondelete="CASCADE"), nullable=False)

    # Status
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.QUEUED)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    # Errors
    error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    tenant = relationship("Tenant", back_populates="refresh_jobs")
    ad_account = relationship("AdAccount", back_populates="refresh_jobs")

    def __repr__(self):
        return f"<RefreshJob {self.status} - account={self.ad_account_id}>"
