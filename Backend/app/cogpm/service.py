"""Provisioning service: bridges in-memory CogPM with SQLAlchemy persistence."""
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from .manifest import AppManifest, load_manifests
from .models import Deployment, Installation, InstallState, StateTransition
from .provisioner import CognitivePackageManager, Installation as MemoryInstallation
from .validator import PlatformContext, TenantContext, validate_install


class ProvisioningService:
    """Stateful provisioning orchestrator with database persistence."""

    def __init__(self, db: Session, platform: PlatformContext, cogpm: CognitivePackageManager):
        self.db = db
        self.platform = platform
        self.cogpm = cogpm

    def submit_installation(
        self,
        manifest: AppManifest,
        signature: str,
        tenant_id: str,
        requested_by: str,
    ) -> Installation:
        """Submit a manifest for installation and persist it."""
        errors = validate_install(manifest, signature, requested_by, self._load_tenant(tenant_id), self.platform)

        inst_id = f"inst-{manifest.name}-{tenant_id}"[:36]
        db_inst = Installation(
            id=inst_id,
            tenant_id=tenant_id,
            manifest_name=manifest.name,
            manifest_digest=manifest.digest(),
            manifest_json=manifest.model_dump(mode="json"),
            requested_by=requested_by,
            publisher_signature=signature,
            state=InstallState.FAILED if errors else InstallState.PENDING_APPROVAL,
            errors=errors,
        )

        # Audit trail
        transition = StateTransition(
            installation_id=inst_id,
            from_state=None,
            to_state=db_inst.state,
            note="submitted" if not errors else "validation failed",
        )

        self.db.add(db_inst)
        self.db.add(transition)
        self.db.commit()
        self.db.refresh(db_inst)
        return db_inst

    async def approve_installation(self, installation_id: str) -> Installation:
        """Approve a pending installation and begin provisioning."""
        db_inst = self.db.query(Installation).filter_by(id=installation_id).first()
        if not db_inst:
            raise ValueError(f"Installation {installation_id} not found")

        if db_inst.state != InstallState.PENDING_APPROVAL:
            raise ValueError(f"Cannot approve from state {db_inst.state.value}")

        # Reload tenant for quota checks
        tenant = self._load_tenant(db_inst.tenant_id)

        # Use in-memory CogPM for orchestration
        mem_inst = self.cogpm.installations.get(installation_id)
        if not mem_inst:
            # Recreate from DB
            manifest = AppManifest.model_validate(db_inst.manifest_json)
            mem_inst = self.cogpm.submit(manifest, db_inst.publisher_signature, db_inst.requested_by, tenant)
            self.cogpm.installations[installation_id] = mem_inst

        # Approve and provision
        await self.cogpm.approve(installation_id, tenant)
        mem_result = self.cogpm.installations[installation_id]

        # Sync back to DB
        db_inst.state = InstallState[mem_result.state.value]
        db_inst.updated_at = datetime.utcnow()
        db_inst.approved_at = datetime.utcnow()

        if mem_result.state == InstallState.ACTIVE:
            db_inst.activated_at = datetime.utcnow()
        elif mem_result.state == InstallState.FAILED:
            db_inst.failed_at = datetime.utcnow()
            db_inst.errors = mem_result.errors

        # Persist deployments (skip if already exists from prior attempts)
        existing_deps = self.db.query(Deployment).filter_by(installation_id=installation_id).all()
        existing_kernels = {d.kernel_name for d in existing_deps}
        
        for kname, dep_id in mem_result.deployments.items():
            if kname in existing_kernels:
                continue
            linked = None
            if kname == "synapticaos" and "epistemicos" in mem_result.deployments:
                linked = mem_result.deployments["epistemicos"]
            dep = Deployment(
                installation_id=installation_id,
                kernel_name=kname,
                deployment_id=dep_id,
                linked_to=linked,
            )
            self.db.add(dep)

        # Persist new state transitions (skip already recorded)
        existing_transitions = self.db.query(StateTransition).filter_by(installation_id=installation_id).count()
        for i, (state, note) in enumerate(mem_result.history):
            if i < existing_transitions:
                continue
            from_state = None
            if i > 0:
                prev_state = mem_result.history[i - 1][0]
                from_state = prev_state

            trans = StateTransition(
                installation_id=installation_id,
                from_state=from_state,
                to_state=state,
                note=note,
            )
            self.db.add(trans)

        self.db.commit()
        self.db.refresh(db_inst)
        return db_inst

    def get_installation(self, installation_id: str) -> Optional[Installation]:
        """Fetch installation details with full history."""
        return self.db.query(Installation).filter_by(id=installation_id).first()

    def list_installations(
        self, tenant_id: str, state: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> tuple[List[Installation], int]:
        """List installations for a tenant, optionally filtered by state."""
        query = self.db.query(Installation).filter_by(tenant_id=tenant_id)
        if state:
            try:
                state_enum = InstallState[state]
                query = query.filter_by(state=state_enum)
            except KeyError:
                pass
        total = query.count()
        installs = query.order_by(Installation.created_at.desc()).limit(limit).offset(offset).all()
        return installs, total

    def _load_tenant(self, tenant_id: str) -> TenantContext:
        """Load tenant context from config or database.
        
        For now, use dummy data. In production, fetch from tenant registry.
        """
        return TenantContext(
            tenant_id=tenant_id,
            entitlements={"forge", "forge-plus", "chronothera"},
            authorized_installers={"admin", "operator"},
            domains={"therapeutic"},
            installed_apps=set(),
            max_monthly_ceiling_usd=float("inf"),
        )
