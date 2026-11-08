"""
SQLAlchemy ORM models for Cognitive Package Manager provisioning.

Persistent state machine for app installations:
- Installation: Root aggregate for a tenant's app deployment
- Deployment: Per-kernel deployment (1:1 for Forge, 2:1 for Forge Plus)
- StateTransition: Audit trail of all state changes

Foreign key relationships:
  Installation -> Deployment (1:N, cascade delete)
  Installation -> StateTransition (1:N, cascade delete)
"""

from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Enum, ForeignKey,
    Index, func, CheckConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class InstallState(str, enum.Enum):
    """Installation state machine states."""
    PENDING_APPROVAL = "pending_approval"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"


class DeploymentState(str, enum.Enum):
    """Per-kernel deployment states."""
    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    FAILED = "failed"


class Installation(Base):
    """
    Root aggregate for app installation.
    
    Represents a tenant's request to install an app (Forge, Forge Plus, ChronoThera).
    Moves through states: PENDING_APPROVAL -> PROVISIONING -> ACTIVE or FAILED.
    """
    __tablename__ = "cogpm_installations"

    id = Column(String(36), primary_key=True, index=True)  # UUID
    tenant_id = Column(String(255), nullable=False, index=True)
    app_id = Column(String(255), nullable=False)  # forge, forge_plus, chronothera
    app_version = Column(String(20), nullable=False)
    state = Column(Enum(InstallState), nullable=False, default=InstallState.PENDING_APPROVAL)
    
    # Audit trail
    requested_by = Column(String(255), nullable=False)  # email/user_id
    approved_by = Column(String(255), nullable=True)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Manifest & configuration
    manifest_hash = Column(String(64), nullable=False)  # SHA256 of app manifest
    spend_policy = Column(String(20), nullable=False)  # hard_stop, reservation, controlled_overage
    monthly_ceiling_usd = Column(Integer, nullable=False)  # Budget in cents
    
    # Metadata
    error_message = Column(Text, nullable=True)
    metadata = Column(Text, nullable=True)  # JSON string for extensibility

    # Relationships
    deployments = relationship(
        "Deployment",
        back_populates="installation",
        cascade="all, delete-orphan",
        foreign_keys="Deployment.installation_id"
    )
    state_transitions = relationship(
        "StateTransition",
        back_populates="installation",
        cascade="all, delete-orphan",
        foreign_keys="StateTransition.installation_id"
    )

    # Indexes
    __table_args__ = (
        Index("idx_tenant_id_state", "tenant_id", "state"),
        Index("idx_requested_at", "requested_at"),
        CheckConstraint("monthly_ceiling_usd > 0", name="ck_ceiling_positive"),
    )

    def __repr__(self):
        return f"<Installation(id={self.id}, tenant={self.tenant_id}, app={self.app_id}, state={self.state})>"


class Deployment(Base):
    """
    Per-kernel deployment record.
    
    Each kernel (EpistemicOS, SynapticaOS) gets one deployment record.
    For Forge: 1 deployment (EpistemicOS only)
    For Forge Plus: 2 deployments (EpistemicOS, SynapticaOS linked)
    """
    __tablename__ = "cogpm_deployments"

    id = Column(String(36), primary_key=True, index=True)  # UUID
    installation_id = Column(String(36), ForeignKey("cogpm_installations.id", ondelete="CASCADE"), nullable=False, index=True)
    kernel_id = Column(String(20), nullable=False)  # epistemicos, synapticaos
    kernel_version = Column(String(20), nullable=False)
    state = Column(Enum(DeploymentState), nullable=False, default=DeploymentState.PENDING)
    
    # Zone/swarm reference from kernel
    zone_id = Column(String(255), nullable=True)  # CXU zone ID from EpistemicOS
    swarm_id = Column(String(255), nullable=True)  # Swarm ID from SynapticaOS
    
    # For Forge Plus: SynapticaOS is linked to EpistemicOS zone
    linked_to = Column(String(36), nullable=True)  # FK to another Deployment (EpistemicOS), if SynapticaOS
    
    # Audit
    provisioned_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata = Column(Text, nullable=True)  # JSON: health status, resource usage, etc.

    # Relationship to Installation
    installation = relationship("Installation", back_populates="deployments")

    # Indexes
    __table_args__ = (
        Index("idx_installation_kernel", "installation_id", "kernel_id"),
        Index("idx_zone_id", "zone_id"),
    )

    def __repr__(self):
        return f"<Deployment(id={self.id}, kernel={self.kernel_id}, state={self.state}, zone={self.zone_id})>"


class StateTransition(Base):
    """
    Audit trail: Every state change is recorded.
    
    Examples:
    - PENDING_APPROVAL -> PROVISIONING (approved)
    - PROVISIONING -> ACTIVE (successful provision)
    - PROVISIONING -> FAILED (kernel error)
    - FAILED -> ROLLING_BACK (rollback initiated)
    """
    __tablename__ = "cogpm_state_transitions"

    id = Column(String(36), primary_key=True, index=True)  # UUID
    installation_id = Column(String(36), ForeignKey("cogpm_installations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    from_state = Column(Enum(InstallState), nullable=False)
    to_state = Column(Enum(InstallState), nullable=False)
    
    # Who triggered this transition
    triggered_by = Column(String(255), nullable=False)
    
    # Why (for failures, approvals, rejections)
    reason = Column(Text, nullable=True)
    
    # When
    transitioned_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationship to Installation
    installation = relationship("Installation", back_populates="state_transitions")

    # Indexes
    __table_args__ = (
        Index("idx_installation_transitioned_at", "installation_id", "transitioned_at"),
    )

    def __repr__(self):
        return f"<StateTransition(id={self.id}, {self.from_state} -> {self.to_state})>"
