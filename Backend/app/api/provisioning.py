"""
REST API routes for Cognitive Package Manager provisioning.

Endpoints:
  POST   /api/v1/provisioning/install           - Submit new installation
  GET    /api/v1/provisioning/install           - List tenant's installations
  GET    /api/v1/provisioning/install/{id}      - Get installation details
  POST   /api/v1/provisioning/install/{id}/approve - Approve pending installation
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional

from app.cogpm.provisioner import CognitivePackageManager
from app.cogpm.service import ProvisioningService
from app.cogpm.schemas import (
    InstallRequest, InstallationResponse, InstallationListResponse, ApprovalRequest
)
from app.database import get_db


# Initialize router
router = APIRouter(prefix="/provisioning", tags=["provisioning"])

# Load app manifests (relative to project root)
MANIFEST_DIR = Path(__file__).resolve().parents[3] / 'app_manifests'


def get_cogpm() -> CognitivePackageManager:
    """Dependency: Get CogPM instance with manifests loaded."""
    cogpm = CognitivePackageManager()
    for manifest_file in MANIFEST_DIR.glob("*.yaml"):
        cogpm.load_manifest(str(manifest_file))
    return cogpm


def get_provisioning_service(
    db: Session = Depends(get_db),
    cogpm: CognitivePackageManager = Depends(get_cogpm),
) -> ProvisioningService:
    """Dependency: Get ProvisioningService instance."""
    return ProvisioningService(db=db, cogpm=cogpm)


def get_tenant_from_auth(authorization: Optional[str] = Header(None)) -> str:
    """
    Extract tenant_id from Bearer token.
    
    Format: "Bearer tenant_id:user_email"
    Example: "Bearer tenant-123:alice@example.com"
    
    Production: Replace with JWT validation (PyJWT, python-jose, etc.)
    """
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


def get_user_from_auth(authorization: Optional[str] = Header(None)) -> str:
    """Extract user email from Bearer token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    try:
        tenant_id, user_email = parts[1].split(":")
        return user_email
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token format. Expected 'Bearer tenant_id:user_email'"
        )


# ============================================================================
# Routes
# ============================================================================

@router.post("/install", response_model=InstallationResponse, status_code=201)
async def submit_installation(
    request: InstallRequest,
    tenant_id: str = Depends(get_tenant_from_auth),
    user_email: str = Depends(get_user_from_auth),
    service: ProvisioningService = Depends(get_provisioning_service),
) -> InstallationResponse:
    """
    Submit a new app installation request.
    
    The installation starts in PENDING_APPROVAL state and requires
    explicit approval before provisioning begins.
    
    Args:
        request: InstallRequest (app_id, spend_policy, monthly_ceiling_usd)
        tenant_id: From Bearer token (tenant_id:user_email)
        user_email: From Bearer token
        service: ProvisioningService dependency
    
    Returns:
        InstallationResponse with installation ID and initial state
    
    Raises:
        400: Invalid request (app not found, invalid budget, etc.)
        401: Missing or invalid authorization
    """
    try:
        return await service.submit_installation(
            tenant_id=tenant_id,
            request=request,
            requested_by=user_email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/install", response_model=InstallationListResponse, status_code=200)
def list_installations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    tenant_id: str = Depends(get_tenant_from_auth),
    service: ProvisioningService = Depends(get_provisioning_service),
) -> InstallationListResponse:
    """
    List all installations for a tenant (paginated).
    
    Args:
        skip: Offset for pagination (default 0)
        limit: Max results per page (default 50, max 100)
        tenant_id: From Bearer token
        service: ProvisioningService dependency
    
    Returns:
        InstallationListResponse with paginated list of installations
    """
    installations, total = service.list_installations(
        tenant_id=tenant_id,
        skip=skip,
        limit=limit,
    )
    return InstallationListResponse(
        installations=installations,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/install/{installation_id}", response_model=InstallationResponse, status_code=200)
def get_installation(
    installation_id: str,
    tenant_id: str = Depends(get_tenant_from_auth),
    service: ProvisioningService = Depends(get_provisioning_service),
) -> InstallationResponse:
    """
    Get details of a single installation by ID.
    
    Returns full installation state, deployments, and audit trail.
    
    Args:
        installation_id: Installation UUID
        tenant_id: From Bearer token (used to verify ownership)
        service: ProvisioningService dependency
    
    Returns:
        InstallationResponse with full installation details
    
    Raises:
        404: Installation not found or tenant mismatch
    """
    installation = service.get_installation(installation_id)
    if not installation:
        raise HTTPException(status_code=404, detail="Installation not found")

    # Verify tenant ownership
    if installation.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Unauthorized: Installation belongs to different tenant")

    return installation


@router.post("/install/{installation_id}/approve", response_model=InstallationResponse, status_code=200)
async def approve_installation(
    installation_id: str,
    request: ApprovalRequest,
    tenant_id: str = Depends(get_tenant_from_auth),
    user_email: str = Depends(get_user_from_auth),
    service: ProvisioningService = Depends(get_provisioning_service),
) -> InstallationResponse:
    """
    Approve a pending installation and trigger provisioning.
    
    Transitions installation from PENDING_APPROVAL to PROVISIONING.
    Kernel backends are invoked asynchronously to provision zones/swarms.
    
    On success: transitions to ACTIVE.
    On failure: transitions to FAILED and may trigger ROLLING_BACK.
    
    Args:
        installation_id: Installation UUID to approve
        request: ApprovalRequest (approved_by, optional reason)
        tenant_id: From Bearer token
        user_email: From Bearer token
        service: ProvisioningService dependency
    
    Returns:
        InstallationResponse with updated state (PROVISIONING or ACTIVE)
    
    Raises:
        400: Invalid state transition or validation error
        403: Unauthorized (tenant mismatch)
        404: Installation not found
    """
    # Verify installation exists and belongs to tenant
    installation = service.get_installation(installation_id)
    if not installation:
        raise HTTPException(status_code=404, detail="Installation not found")

    if installation.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Unauthorized: Installation belongs to different tenant")

    try:
        return await service.approve_installation(
            installation_id=installation_id,
            approved_by=request.approved_by,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
