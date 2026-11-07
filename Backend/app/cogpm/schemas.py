"""Pydantic schemas for CogPM REST API requests and responses."""
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .models import InstallState


class InstallRequest(BaseModel):
    """Submit an app manifest for installation."""

    manifest_name: str = Field(..., description="App name (forge, forge-plus, chronothera)")
    manifest_digest: str = Field(..., description="SHA256 digest of canonical manifest JSON")
    publisher_signature: str = Field(..., description="HMAC or asymmetric signature")
    tenant_id: str = Field(..., description="Tenant identifier")
    requested_by: str = Field(..., description="User/service requesting the install")


class ApproveRequest(BaseModel):
    """Approve a pending installation for provisioning."""

    pass  # No body needed; auth & tenant context from headers


class DeploymentResponse(BaseModel):
    """Kernel deployment record."""

    kernel_name: str
    deployment_id: str
    linked_to: Optional[str] = None
    provisioned_at: str
    deprovisioned_at: Optional[str] = None


class StateTransitionResponse(BaseModel):
    """State machine transition record."""

    from_state: Optional[str] = None
    to_state: str
    note: Optional[str] = None
    transitioned_at: str


class InstallationResponse(BaseModel):
    """Full installation state and history."""

    id: str
    tenant_id: str
    manifest_name: str
    manifest_digest: str
    requested_by: str
    state: str
    created_at: str
    updated_at: str
    approved_at: Optional[str] = None
    activated_at: Optional[str] = None
    failed_at: Optional[str] = None
    errors: List[str] = []
    deployments: Dict[str, str] = {}
    history: Optional[List[StateTransitionResponse]] = None


class InstallationListResponse(BaseModel):
    """Summary list of installations for a tenant."""

    installations: List[InstallationResponse]
    total: int
    limit: int
    offset: int
