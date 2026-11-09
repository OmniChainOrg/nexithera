"""
REST API routes for spend tracking and budget enforcement.

Endpoints:
  POST   /api/v1/spend/usage               - Record usage event
  POST   /api/v1/spend/allocate            - Check if allocation allowed
  GET    /api/v1/spend/report              - Monthly usage report
  GET    /api/v1/spend/alerts              - List budget alerts
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.cogpm.spend_enforcement import SpendEnforcementService
from app.cogpm.spend_schemas import (
    UsageEventRequest, UsageEventResponse,
    AllocationRequest, AllocationResponse,
    UsageReportResponse, BudgetAlertResponse,
)
from app.cogpm.models import BudgetAlert
from app.database import get_db


# Initialize router
router = APIRouter(prefix="/spend", tags=["spend"])


def get_spend_service(db: Session = Depends(get_db)) -> SpendEnforcementService:
    """Dependency: Get SpendEnforcementService instance."""
    return SpendEnforcementService(db=db)


def get_tenant_from_auth(authorization: Optional[str] = Header(None)) -> str:
    """Extract tenant_id from Bearer token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    try:
        tenant_id, user_email = parts[1].split(":")
        return tenant_id
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token format. Expected 'Bearer tenant_id:user_email'"
        )


# ============================================================================
# Routes
# ============================================================================

@router.post("/usage", response_model=UsageEventResponse, status_code=201)
def record_usage_event(
    installation_id: str,
    app_id: str,
    kernel_id: str,
    request: UsageEventRequest,
    tenant_id: str = Depends(get_tenant_from_auth),
    service: SpendEnforcementService = Depends(get_spend_service),
) -> UsageEventResponse:
    """
    Record a real-time usage event (resource consumption).
    
    Called by kernel backends or CXU zone handlers when:
    - CXU zone created (epistemicos zone cost)
    - Swarm allocated (synapticaos swarm cost)
    - Inference call made (per-token cost)
    - Storage provisioned (monthly/GB cost)
    
    Args:
        installation_id: Which app installation
        app_id: Which app (forge, forge_plus, chronothera)
        kernel_id: Which kernel (epistemicos, synapticaos)
        request: UsageEventRequest with resource type and cost
        tenant_id: From Bearer token
        service: SpendEnforcementService dependency
    
    Returns:
        UsageEventResponse confirming event was recorded
    
    Raises:
        400: Invalid request or installation not ACTIVE
        401: Missing or invalid authorization
    """
    try:
        event = service.record_usage_event(
            tenant_id=tenant_id,
            installation_id=installation_id,
            app_id=app_id,
            kernel_id=kernel_id,
            resource_type=request.resource_type,
            cost_cents=request.cost_cents,
            operation=request.operation,
            resource_id=request.resource_id,
            billing_category=request.billing_category,
            metadata=request.metadata,
        )
        return UsageEventResponse.from_orm(event)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/allocate", response_model=AllocationResponse, status_code=200)
def check_allocation(
    installation_id: str,
    request: AllocationRequest,
    tenant_id: str = Depends(get_tenant_from_auth),
    service: SpendEnforcementService = Depends(get_spend_service),
) -> AllocationResponse:
    """
    Check if resource allocation is allowed based on current budget.
    
    Called by resource managers before creating:
    - CXU zones
    - Swarm allocations
    - Storage volumes
    
    Returns allowed/denied based on:
    1. Installation spend_policy (hard_stop, reservation, controlled_overage)
    2. Current month spend + estimated_cost vs. ceiling
    3. Budget alerts and thresholds
    
    Args:
        installation_id: Installation to check
        request: AllocationRequest with resource type and estimated cost
        tenant_id: From Bearer token
        service: SpendEnforcementService dependency
    
    Returns:
        AllocationResponse with allowed flag and reason if denied
    
    Raises:
        404: Installation not found
    """
    try:
        allowed, reason = service.can_allocate_resource(
            tenant_id=tenant_id,
            installation_id=installation_id,
            estimated_cost_cents=request.estimated_cost_cents,
        )
        
        # Check if denial is due to unauthorized access
        if not allowed and "Unauthorized" in (reason or ""):
            raise HTTPException(status_code=401, detail=reason)
        
        return AllocationResponse(allowed=allowed, reason=reason)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report", response_model=UsageReportResponse, status_code=200)
def get_usage_report(
    month_year: Optional[str] = Query(None, description="YYYY-MM format, default: current month"),
    tenant_id: str = Depends(get_tenant_from_auth),
    service: SpendEnforcementService = Depends(get_spend_service),
) -> UsageReportResponse:
    """
    Get monthly usage report for a tenant.
    
    Shows aggregated spend by:
    - App (Forge, Forge Plus, ChronoThera)
    - Kernel (EpistemicOS, SynapticaOS)
    - Installation (with spend vs. ceiling)
    
    Useful for:
    - Billing & invoicing
    - Cost analysis & forecasting
    - Usage optimization
    
    Args:
        month_year: YYYY-MM format (default: current month)
        tenant_id: From Bearer token
        service: SpendEnforcementService dependency
    
    Returns:
        UsageReportResponse with aggregated spend data
    """
    try:
        report = service.get_monthly_usage(
            tenant_id=tenant_id,
            month_year=month_year,
        )
        return UsageReportResponse(**report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts", response_model=list[BudgetAlertResponse], status_code=200)
def list_budget_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    resolved: Optional[str] = Query(None, description="pending, acknowledged, resolved, or all"),
    tenant_id: str = Depends(get_tenant_from_auth),
    db: Session = Depends(get_db),
) -> list[BudgetAlertResponse]:
    """
    List budget alerts for tenant.
    
    Shows threshold alerts (80%, 95%, 100%) and actions taken.
    
    Args:
        skip: Offset for pagination
        limit: Max results per page
        resolved: Filter by resolution status
        tenant_id: From Bearer token
        db: Database dependency
    
    Returns:
        List of BudgetAlertResponse (paginated)
    """
    query = db.query(BudgetAlert).filter(BudgetAlert.tenant_id == tenant_id)

    if resolved and resolved != "all":
        query = query.filter(BudgetAlert.resolved == resolved)

    total = query.count()
    alerts = query.order_by(BudgetAlert.created_at.desc()).offset(skip).limit(limit).all()

    return [BudgetAlertResponse.from_orm(alert) for alert in alerts]
