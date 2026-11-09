"""
ProvisioningService: Bridge between in-memory CogPM and persistent database.

Responsibilities:
1. Accept installation requests, validate via CogPM manifests
2. Persist installation & deployment records to database
3. Trigger async provisioning via kernel backends
4. Sync deployment status & state transitions back to database
5. Handle rollback on failure (reverse-order kernel cleanup)
"""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.cogpm.provisioner import CognitivePackageManager, Installation as CogPMInstallation
from app.cogpm.manifest import AppManifest
from app.cogpm.models import (
    Installation, Deployment, StateTransition,
    InstallState, DeploymentState,
)
from app.cogpm.schemas import InstallRequest, InstallationResponse


class ProvisioningService:
    """
    Service layer for provisioning.
    Translates between FastAPI requests, CogPM orchestration, and database persistence.
    """

    def __init__(self, db: Session, cogpm: CognitivePackageManager):
        self.db = db
        self.cogpm = cogpm

    async def submit_installation(
        self,
        tenant_id: str,
        request: InstallRequest,
        requested_by: str,
    ) -> InstallationResponse:
        """
        Submit a new installation request.
        
        1. Validate app manifest exists and is compatible
        2. Create Installation record in PENDING_APPROVAL state
        3. Create Deployment record(s) for each kernel
        4. Record initial state transition
        5. Return installation details to tenant
        
        Args:
            tenant_id: Tenant identifier
            request: InstallRequest (app_id, spend_policy, monthly_ceiling_usd)
            requested_by: Email/user ID of requester
        
        Returns:
            InstallationResponse with full installation details
        """
        # Validate manifest exists for this app
        manifest = self.cogpm.get_manifest(request.app_id)
        if not manifest:
            raise ValueError(f"App '{request.app_id}' manifest not found")

        # Create Installation record
        installation_id = str(uuid.uuid4())
        installation = Installation(
            id=installation_id,
            tenant_id=tenant_id,
            app_id=request.app_id,
            app_version=manifest.version,
            state=InstallState.PENDING_APPROVAL,
            requested_by=requested_by,
            requested_at=datetime.utcnow(),
            manifest_hash=manifest.manifest_hash,
            spend_policy=request.spend_policy.value,
            monthly_ceiling_cents=int(request.monthly_ceiling_usd * 100),  # Convert USD to cents
        )
        self.db.add(installation)
        self.db.flush()  # Get installation.id in DB

        # Create Deployment records for each kernel requirement
        for kernel_spec in manifest.kernels:
            deployment_id = str(uuid.uuid4())
            deployment = Deployment(
                id=deployment_id,
                installation_id=installation_id,
                kernel_id=kernel_spec.name,
                kernel_version=kernel_spec.min_version or "0.1.0",
                state=DeploymentState.PENDING,
            )
            self.db.add(deployment)
        self.db.flush()

        # Record initial state transition
        transition = StateTransition(
            id=str(uuid.uuid4()),
            installation_id=installation_id,
            from_state=None,  # Initial state has no 'from'
            to_state=InstallState.PENDING_APPROVAL,
            triggered_by=requested_by,
            reason="Installation submitted",
            transitioned_at=datetime.utcnow(),
        )
        self.db.add(transition)

        self.db.commit()

        # Return full response
        self.db.refresh(installation)
        return self._installation_to_response(installation)

    async def approve_installation(
        self,
        installation_id: str,
        approved_by: str,
        reason: Optional[str] = None,
    ) -> InstallationResponse:
        """
        Approve a pending installation and trigger provisioning.
        
        1. Fetch Installation from database
        2. Validate state is PENDING_APPROVAL
        3. Transition to PROVISIONING
        4. Reconstruct in-memory CogPM Installation object
        5. Trigger async provisioning via kernel backends
        6. Sync deployments & state transitions back to database
        7. On success: transition to ACTIVE
        8. On failure: transition to FAILED, record error, may trigger ROLLING_BACK
        
        Args:
            installation_id: UUID of installation to approve
            approved_by: Email/user ID of approver
            reason: Optional approval reason
        
        Returns:
            InstallationResponse with updated state
        
        Raises:
            ValueError: If installation not found or state is invalid
        """
        # Fetch installation
        installation = self.db.query(Installation).filter(
            Installation.id == installation_id
        ).first()
        if not installation:
            raise ValueError(f"Installation '{installation_id}' not found")

        if installation.state != InstallState.PENDING_APPROVAL:
            raise ValueError(
                f"Cannot approve installation in state '{installation.state}'. "
                f"Must be '{InstallState.PENDING_APPROVAL}'"
            )

        # Update approval timestamp
        installation.approved_by = approved_by
        installation.approved_at = datetime.utcnow()

        # Transition to PROVISIONING
        installation.state = InstallState.PROVISIONING
        self.db.add(installation)
        self.db.flush()

        # Record approval transition
        transition = StateTransition(
            id=str(uuid.uuid4()),
            installation_id=installation_id,
            from_state=InstallState.PENDING_APPROVAL,
            to_state=InstallState.PROVISIONING,
            triggered_by=approved_by,
            reason=reason or "Installation approved",
            transitioned_at=datetime.utcnow(),
        )
        self.db.add(transition)
        self.db.commit()

        # Reconstruct in-memory CogPM Installation for provisioning orchestration
        manifest = self.cogpm.get_manifest(installation.app_id)
        cogpm_install = CogPMInstallation(
            install_id=installation_id,
            tenant_id=installation.tenant_id,
            app_id=installation.app_id,
            manifest=manifest,
        )

        # Trigger async provisioning
        try:
            await self.cogpm.approve(cogpm_install)

            # If we get here, provisioning succeeded
            installation.state = InstallState.ACTIVE
            installation.completed_at = datetime.utcnow()

            # Record deployments' final state & zone IDs from cogpm_install
            deployments = self.db.query(Deployment).filter(
                Deployment.installation_id == installation_id
            ).all()
            for deployment in deployments:
                # Find matching deployment in CogPM result
                for cogpm_dep in cogpm_install.deployments:
                    if cogpm_dep.kernel_id == deployment.kernel_id:
                        deployment.state = DeploymentState.ACTIVE
                        deployment.zone_id = getattr(cogpm_dep, "zone_id", None)
                        deployment.swarm_id = getattr(cogpm_dep, "swarm_id", None)
                        deployment.provisioned_at = datetime.utcnow()
                        self.db.add(deployment)
                        break

            # Record ACTIVE transition
            active_transition = StateTransition(
                id=str(uuid.uuid4()),
                installation_id=installation_id,
                from_state=InstallState.PROVISIONING,
                to_state=InstallState.ACTIVE,
                triggered_by="system",
                reason="Provisioning successful",
                transitioned_at=datetime.utcnow(),
            )
            self.db.add(active_transition)
            self.db.commit()

        except Exception as e:
            # Provisioning failed: record error and transition to FAILED
            installation.state = InstallState.FAILED
            installation.error_message = str(e)
            installation.completed_at = datetime.utcnow()

            # Mark all deployments as FAILED
            deployments = self.db.query(Deployment).filter(
                Deployment.installation_id == installation_id
            ).all()
            for deployment in deployments:
                deployment.state = DeploymentState.FAILED
                deployment.error_message = str(e)
                self.db.add(deployment)

            # Record FAILED transition
            failed_transition = StateTransition(
                id=str(uuid.uuid4()),
                installation_id=installation_id,
                from_state=InstallState.PROVISIONING,
                to_state=InstallState.FAILED,
                triggered_by="system",
                reason=f"Provisioning failed: {str(e)}",
                transitioned_at=datetime.utcnow(),
            )
            self.db.add(failed_transition)
            self.db.commit()

        # Fetch and return updated installation
        self.db.refresh(installation)
        return self._installation_to_response(installation)

    def get_installation(self, installation_id: str) -> Optional[InstallationResponse]:
        """
        Fetch a single installation by ID.
        
        Args:
            installation_id: UUID of installation
        
        Returns:
            InstallationResponse or None if not found
        """
        installation = self.db.query(Installation).filter(
            Installation.id == installation_id
        ).first()
        if installation:
            return self._installation_to_response(installation)
        return None

    def list_installations(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[InstallationResponse], int]:
        """
        List all installations for a tenant (paginated).
        
        Args:
            tenant_id: Filter by tenant
            skip: Offset for pagination
            limit: Max results per page
        
        Returns:
            Tuple of (list of InstallationResponse, total count)
        """
        query = self.db.query(Installation).filter(Installation.tenant_id == tenant_id)
        total = query.count()

        installations = query.order_by(desc(Installation.requested_at)).offset(skip).limit(limit).all()
        return [self._installation_to_response(inst) for inst in installations], total

    def _installation_to_response(self, installation: Installation) -> InstallationResponse:
        """Helper: Convert ORM Installation to Pydantic response."""
        return InstallationResponse(
            id=installation.id,
            tenant_id=installation.tenant_id,
            app_id=installation.app_id,
            app_version=installation.app_version,
            state=installation.state,
            requested_by=installation.requested_by,
            approved_by=installation.approved_by,
            requested_at=installation.requested_at,
            approved_at=installation.approved_at,
            completed_at=installation.completed_at,
            spend_policy=installation.spend_policy,
            monthly_ceiling_usd=installation.monthly_ceiling_usd / 100,  # Convert from cents
            error_message=installation.error_message,
            deployments=[
                {
                    "id": d.id,
                    "kernel_id": d.kernel_id,
                    "kernel_version": d.kernel_version,
                    "state": d.state,
                    "zone_id": d.zone_id,
                    "swarm_id": d.swarm_id,
                    "linked_to": d.linked_to,
                    "provisioned_at": d.provisioned_at,
                    "error_message": d.error_message,
                }
                for d in installation.deployments
            ],
            state_transitions=[
                {
                    "id": st.id,
                    "from_state": st.from_state,
                    "to_state": st.to_state,
                    "triggered_by": st.triggered_by,
                    "reason": st.reason,
                    "transitioned_at": st.transitioned_at,
                }
                for st in installation.state_transitions
            ],
        )
