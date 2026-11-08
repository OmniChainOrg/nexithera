"""
Pydantic schemas for provisioning API contract.

Request schemas (from tenant):
- InstallRequest: Submit new installation

Response schemas (to tenant):
- InstallationResponse: Full installation details
- DeploymentResponse: Per-kernel deployment details
- StateTransitionResponse: Audit trail entry
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class InstallState(str, Enum):
    """Installation state machine."""
    PENDING_APPROVAL = "pending_approval"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"


class DeploymentState(str, Enum):
    """Per-kernel deployment state."""
    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    FAILED = "failed"


class SpendPolicy(str, Enum):
    """Spend enforcement policy."""
    HARD_STOP = "hard_stop"
    RESERVATION = "reservation"
    CONTROLLED_OVERAGE = "controlled_overage"


# ============================================================================
# Request Schemas
# ============================================================================

class InstallRequest(BaseModel):
    """
    Request to install an app.
    
    Tenant provides:
    - app_id: which app to install (forge, forge_plus, chronothera)
    - spend_policy: how to enforce budget (hard_stop, reservation, controlled_overage)
    - monthly_ceiling_usd: budget ceiling in USD (multiply by 100 for cents in DB)
    """
    app_id: str = Field(..., description="App to install: forge, forge_plus, chronothera")
    spend_policy: SpendPolicy = Field(default=SpendPolicy.HARD_STOP)
    monthly_ceiling_usd: float = Field(..., ge=0, description="Monthly budget in USD")

    @validator("monthly_ceiling_usd")
    def validate_ceiling(cls, v):
        if v < 1:
            raise ValueError("monthly_ceiling_usd must be at least $1.00")
        return v


# ============================================================================
# Response Schemas
# ============================================================================

class DeploymentResponse(BaseModel):
    """Per-kernel deployment details."""
    id: str
    kernel_id: str
    kernel_version: str
    state: DeploymentState
    zone_id: Optional[str] = None
    swarm_id: Optional[str] = None
    linked_to: Optional[str] = None  # For Forge Plus SynapticaOS linking
    provisioned_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class StateTransitionResponse(BaseModel):
    """State transition audit entry."""
    id: str
    from_state: InstallState
    to_state: InstallState
    triggered_by: str
    reason: Optional[str] = None
    transitioned_at: datetime

    class Config:
        from_attributes = True


class InstallationResponse(BaseModel):
    """
    Full installation details (response to tenant).
    
    Includes:
    - Installation state and metadata
    - Per-kernel deployments
    - State transition audit trail
    """
    id: str
    tenant_id: str
    app_id: str
    app_version: str
    state: InstallState
    
    # Audit
    requested_by: str
    approved_by: Optional[str] = None
    requested_at: datetime
    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Budget
    spend_policy: str
    monthly_ceiling_usd: float
    
    # Status
    error_message: Optional[str] = None
    
    # Relationships
    deployments: List[DeploymentResponse] = []
    state_transitions: List[StateTransitionResponse] = []

    class Config:
        from_attributes = True


class InstallationListResponse(BaseModel):
    """Paginated list of installations."""
    installations: List[InstallationResponse]
    total: int
    skip: int
    limit: int


class ApprovalRequest(BaseModel):
    """
    Request to approve a pending installation.
    """
    approved_by: str = Field(..., description="Email or user ID approving this installation")
    reason: Optional[str] = Field(None, description="Optional approval reason")
