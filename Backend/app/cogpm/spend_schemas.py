"""
Pydantic schemas for spend tracking and usage reporting.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ============================================================================
# Usage Event Schemas
# ============================================================================

class UsageEventRequest(BaseModel):
    """
    Request to record a usage event (when resource is consumed).
    
    Sent by kernel backends or CXU zone handlers when:
    - New CXU zone is created
    - Swarm is allocated
    - Inference request is made
    - Storage is provisioned
    """
    resource_type: str = Field(..., description="zone, swarm, inference, storage, etc.")
    cost_cents: int = Field(..., ge=0, description="Cost in cents USD")
    operation: str = Field(..., description="create_zone, allocate_swarm, run_inference, etc.")
    resource_id: Optional[str] = Field(None, description="Created resource ID (zone_id, swarm_id)")
    billing_category: Optional[str] = Field("compute", description="Billing category for cost allocation")
    metadata: Optional[str] = Field(None, description="JSON metadata (duration, tokens, parameters)")


class UsageEventResponse(BaseModel):
    """Response confirming usage event was recorded."""
    id: str
    tenant_id: str
    installation_id: str
    app_id: str
    kernel_id: str
    resource_type: str
    cost_cents: int
    billing_category: str
    operation: str
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Budget Check Schemas
# ============================================================================

class AllocationRequest(BaseModel):
    """
    Request to allocate a new resource with cost check.
    
    Before creating a CXU zone or swarm, check if budget allows it.
    """
    resource_type: str = Field(..., description="zone, swarm, etc.")
    estimated_cost_cents: int = Field(..., ge=0, description="Estimated cost in cents")


class AllocationResponse(BaseModel):
    """
    Response to allocation request (allowed/denied).
    """
    allowed: bool
    reason: Optional[str] = None
    current_spent_usd: float
    ceiling_usd: float
    remaining_budget_usd: float


# ============================================================================
# Budget Alert Schemas
# ============================================================================

class BudgetAlertResponse(BaseModel):
    """Budget alert notification."""
    id: str
    alert_type: str  # threshold_80, threshold_95, limit_reached, overage
    percentage: int
    monthly_spent_cents: int
    monthly_ceiling_cents: int
    action_taken: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Usage Report Schemas
# ============================================================================

class AppUsageBreakdown(BaseModel):
    """Usage breakdown by app."""
    app_id: str
    spent_cents: int
    spent_usd: float
    event_count: int


class KernelUsageBreakdown(BaseModel):
    """Usage breakdown by kernel."""
    kernel_id: str
    spent_cents: int
    spent_usd: float
    event_count: int


class InstallationUsageSummary(BaseModel):
    """Usage summary for a single installation."""
    installation_id: str
    app_id: str
    spent_cents: int
    ceiling_cents: int
    percentage: int  # 0-100+


class UsageReportResponse(BaseModel):
    """
    Complete monthly usage report for a tenant.
    
    Shows spend aggregated by app, kernel, and installation.
    Useful for billing, forecasting, and cost analysis.
    """
    month_year: str  # YYYY-MM
    total_spent_cents: int
    total_spent_usd: float
    by_app: List[AppUsageBreakdown]
    by_kernel: List[KernelUsageBreakdown]
    installations: dict  # Dict[installation_id, InstallationUsageSummary]

    class Config:
        from_attributes = True
