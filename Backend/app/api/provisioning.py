"""REST API for CogPM provisioning."""
import os
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from .manifest import load_manifests
from .models import Installation, InstallState
from .provisioner import CognitivePackageManager
from .schemas import (
    ApproveRequest,
    InstallRequest,
    InstallationListResponse,
    InstallationResponse,
    StateTransitionResponse,
)
from .service import ProvisioningService
from .validator import KernelInfo, PlatformContext

router = APIRouter(prefix="/api/v1/provisioning", tags=["provisioning"])

# Determine manifest directory (relative to project root)
MANIFEST_DIR = Path(os.getenv("MANIFEST_DIR", "app_manifests"))
if not MANIFEST_DIR.is_absolute():
    MANIFEST_DIR = Path(__file__).resolve().parents[3] / MANIFEST_DIR


def get_provisioning_service(db: Session = Depends(get_db)) -> ProvisioningService:
    """Dependency: instantiate provisioning service with platform context."""
    # In production, load from config/registry
    platform = PlatformContext(
        publisher_keys={"nexithera": b"nexithera-test-key"},  # Load from secure config
        kernels={
            "epistemicos": KernelInfo(
                "0.1.0",
                {
                    "cxu_zone",
                    "guardian",
                    "semantic_search",
                    "single_zone_simulation",
                    "governed_knowledge_commit",
                },
            ),
            "synapticaos": KernelInfo("0.1.0", {"swarm_resource_group", "ctu_binding", "execution_lease", "sparse_execution"}),
        },
        hosting_services={"protein_folding"},
    )

    # Kernel backends (injected from main.py)
    backends = {}  # Populated by app initialization

    cogpm = CognitivePackageManager(platform, backends)
    return ProvisioningService(db, platform, cogpm)


def extract_tenant(authorization: Annotated[str | None, Header()] = None) -> str:
    """Extract tenant ID from Bearer token or header.
    
    For now, use a simple header; in production, validate JWT.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    # In production: decode JWT, validate, return tenant_id
    return authorization[7:].split(":")[0] or "default-tenant"


@router.post("/install", status_code=202, response_model=InstallationResponse)
async def submit_installation(
    body: InstallRequest,
    svc: ProvisioningService = Depends(get_provisioning_service),
    tenant: str = Depends(extract_tenant),
):
    """Submit an app manifest for installation.
    
    Returns installation ID; client polls GET /provisioning/install/{id}.
    """
    if body.tenant_id != tenant:
        raise HTTPException(403, "Tenant mismatch")

    # Load manifest from app_manifests directory
    try:
        manifests = load_manifests(MANIFEST_DIR)
        manifest = manifests[body.manifest_name]
    except (FileNotFoundError, KeyError) as e:
        raise HTTPException(404, f"Manifest not found: {body.manifest_name}") from e

    # Verify digest
    if manifest.digest() != body.manifest_digest:
        raise HTTPException(400, "Manifest digest mismatch")

    # Submit to provisioning service
    try:
        db_inst = svc.submit_installation(manifest, body.publisher_signature, body.tenant_id, body.requested_by)
        return InstallationResponse(**db_inst.to_dict())
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@router.get("/install/{installation_id}", response_model=InstallationResponse)
async def get_installation(
    installation_id: str,
    svc: ProvisioningService = Depends(get_provisioning_service),
    tenant: str = Depends(extract_tenant),
):
    """Poll installation status."""
    db_inst = svc.get_installation(installation_id)
    if not db_inst:
        raise HTTPException(404, "Installation not found")
    if db_inst.tenant_id != tenant:
        raise HTTPException(403, "Access denied")

    response = db_inst.to_dict()
    response["history"] = [StateTransitionResponse(**t.to_dict()) for t in db_inst.history]
    return InstallationResponse(**response)


@router.post("/install/{installation_id}/approve", response_model=InstallationResponse)
async def approve_installation(
    installation_id: str,
    body: ApproveRequest,
    svc: ProvisioningService = Depends(get_provisioning_service),
    tenant: str = Depends(extract_tenant),
):
    """Approve a pending installation and begin provisioning."""
    db_inst = svc.get_installation(installation_id)
    if not db_inst:
        raise HTTPException(404, "Installation not found")
    if db_inst.tenant_id != tenant:
        raise HTTPException(403, "Access denied")
    if db_inst.state != InstallState.PENDING_APPROVAL:
        raise HTTPException(400, f"Cannot approve from state {db_inst.state.value}")

    try:
        db_inst = await svc.approve_installation(installation_id)
        response = db_inst.to_dict()
        response["history"] = [StateTransitionResponse(**t.to_dict()) for t in db_inst.history]
        return InstallationResponse(**response)
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@router.get("/install", response_model=InstallationListResponse)
async def list_installations(
    state: Optional[str] = Query(None, description="Filter by state"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    svc: ProvisioningService = Depends(get_provisioning_service),
    tenant: str = Depends(extract_tenant),
):
    """List installations for a tenant."""
    installations, total = svc.list_installations(tenant, state=state, limit=limit, offset=offset)
    return InstallationListResponse(
        installations=[InstallationResponse(**i.to_dict()) for i in installations],
        total=total,
        limit=limit,
        offset=offset,
    )
