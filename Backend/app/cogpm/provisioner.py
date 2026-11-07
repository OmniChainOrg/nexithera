import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Protocol, Tuple

from .manifest import AppManifest
from .validator import PlatformContext, TenantContext, validate_install


class InstallState(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    PROVISIONING = "PROVISIONING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    ROLLING_BACK = "ROLLING_BACK"


ALLOWED_TRANSITIONS = {
    InstallState.PENDING_APPROVAL: {InstallState.PROVISIONING, InstallState.FAILED},
    InstallState.PROVISIONING: {InstallState.ACTIVE, InstallState.ROLLING_BACK},
    InstallState.ROLLING_BACK: {InstallState.FAILED},
    InstallState.ACTIVE: set(),
    InstallState.FAILED: set(),
}


class KernelBackend(Protocol):
    """Kernel-side provisioning surface (EpistemicOS or SynapticaOS)."""

    async def provision(self, tenant_id: str, manifest: AppManifest, linked_to: Optional[str]) -> str: ...

    async def deprovision(self, deployment_id: str) -> None: ...


class InstallError(Exception):
    pass


@dataclass
class Installation:
    id: str
    tenant_id: str
    manifest: AppManifest
    manifest_digest: str
    requested_by: str
    state: InstallState = InstallState.PENDING_APPROVAL
    deployments: Dict[str, str] = field(default_factory=dict)  # kernel name -> deployment id
    errors: List[str] = field(default_factory=list)
    history: List[Tuple[InstallState, str]] = field(default_factory=list)

    def _to(self, state: InstallState, note: str = "") -> None:
        if state not in ALLOWED_TRANSITIONS[self.state]:
            raise InstallError(f"illegal transition {self.state.value} -> {state.value}")
        self.state = state
        self.history.append((state, note))


class CognitivePackageManager:
    PROVISION_ORDER = ("epistemicos", "synapticaos")  # governance first, execution linked to it

    def __init__(self, platform: PlatformContext, backends: Dict[str, KernelBackend]):
        self.platform = platform
        self.backends = backends
        self.installations: Dict[str, Installation] = {}

    def submit(
        self, manifest: AppManifest, signature: str, requested_by: str, tenant: TenantContext
    ) -> Installation:
        inst = Installation(
            id=str(uuid.uuid4()),
            tenant_id=tenant.tenant_id,
            manifest=manifest,
            manifest_digest=manifest.digest(),
            requested_by=requested_by,
        )
        inst.history.append((InstallState.PENDING_APPROVAL, "submitted"))
        self.installations[inst.id] = inst
        errors = validate_install(manifest, signature, requested_by, tenant, self.platform)
        if errors:
            inst.errors = errors
            inst._to(InstallState.FAILED, "validation failed")
        return inst

    async def approve(self, installation_id: str, tenant: TenantContext) -> Installation:
        inst = self.installations[installation_id]
        if inst.state != InstallState.PENDING_APPROVAL:
            raise InstallError(f"cannot approve from {inst.state.value}")
        inst._to(InstallState.PROVISIONING, "approved")

        linked: Optional[str] = None
        try:
            for kname in self.PROVISION_ORDER:
                req = inst.manifest.kernels.get(kname)
                if req is None:
                    continue
                dep_id = await self.backends[kname].provision(inst.tenant_id, inst.manifest, linked)
                inst.deployments[kname] = dep_id
                linked = linked or dep_id
        except Exception as exc:  # any backend failure triggers full rollback
            inst.errors.append(f"provisioning error: {exc}")
            await self._rollback(inst)
            return inst

        inst._to(InstallState.ACTIVE, "provisioned")
        tenant.installed_apps.add(inst.manifest.name)
        return inst

    async def _rollback(self, inst: Installation) -> None:
        inst._to(InstallState.ROLLING_BACK, "rollback started")
        for kname in reversed(list(inst.deployments)):
            try:
                await self.backends[kname].deprovision(inst.deployments[kname])
            except Exception as exc:
                inst.errors.append(f"rollback of {kname} failed: {exc}")
        inst.deployments.clear()
        inst._to(InstallState.FAILED, "rolled back")
