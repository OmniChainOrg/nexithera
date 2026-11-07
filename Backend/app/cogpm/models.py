"""SQLAlchemy models for CogPM installation lifecycle persistence."""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Column, Enum as SQLEnum, ForeignKey, String, Text, DateTime, Integer
from sqlalchemy.orm import relationship

from app.core.database import Base


class InstallState(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    PROVISIONING = "PROVISIONING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    ROLLING_BACK = "ROLLING_BACK"


class Installation(Base):
    """Persisted installation record with full state machine lifecycle."""

    __tablename__ = "installations"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    manifest_name = Column(String(128), nullable=False)
    manifest_digest = Column(String(64), nullable=False, unique=True)
    manifest_json = Column(JSON, nullable=False)  # Full manifest for audit
    requested_by = Column(String(128), nullable=False)
    publisher_signature = Column(String(256), nullable=False)  # HMAC or asymmetric sig

    state = Column(SQLEnum(InstallState), default=InstallState.PENDING_APPROVAL, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    activated_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)

    # JSON array of error messages if state == FAILED
    errors = Column(JSON, default=list, nullable=False)

    # Relationships
    deployments = relationship("Deployment", back_populates="installation", cascade="all, delete-orphan")
    history = relationship("StateTransition", back_populates="installation", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "manifest_name": self.manifest_name,
            "manifest_digest": self.manifest_digest,
            "requested_by": self.requested_by,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "errors": self.errors,
            "deployments": {d.kernel_name: d.deployment_id for d in self.deployments},
        }


class Deployment(Base):
    """Per-kernel deployment linked to an installation."""

    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    installation_id = Column(String(36), ForeignKey("installations.id"), nullable=False, index=True)
    kernel_name = Column(String(64), nullable=False)  # epistemicos, synapticaos
    deployment_id = Column(String(256), nullable=False)  # e.g., "epistemicos:zone-123"
    linked_to = Column(String(256), nullable=True)  # deployment ID this is linked to (for synapticaos)
    provisioned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    deprovisioned_at = Column(DateTime, nullable=True)

    installation = relationship("Installation", back_populates="deployments")

    def to_dict(self):
        return {
            "kernel_name": self.kernel_name,
            "deployment_id": self.deployment_id,
            "linked_to": self.linked_to,
            "provisioned_at": self.provisioned_at.isoformat(),
            "deprovisioned_at": self.deprovisioned_at.isoformat() if self.deprovisioned_at else None,
        }


class StateTransition(Base):
    """Audit trail: every state transition with timestamp and note."""

    __tablename__ = "state_transitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    installation_id = Column(String(36), ForeignKey("installations.id"), nullable=False, index=True)
    from_state = Column(SQLEnum(InstallState), nullable=True)  # None for initial
    to_state = Column(SQLEnum(InstallState), nullable=False)
    note = Column(Text, nullable=True)  # e.g., "signature verified", "kernel unavailable"
    transitioned_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    installation = relationship("Installation", back_populates="history")

    def to_dict(self):
        return {
            "from_state": self.from_state.value if self.from_state else None,
            "to_state": self.to_state.value,
            "note": self.note,
            "transitioned_at": self.transitioned_at.isoformat(),
        }
