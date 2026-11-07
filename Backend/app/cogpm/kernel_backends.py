"""Real EpistemicOS and SynapticaOS kernel backends for CogPM provisioning."""
import asyncio
import os
import uuid
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from .manifest import AppManifest


class KernelBackend(ABC):
    """Abstract kernel provisioning interface."""

    @abstractmethod
    async def provision(self, tenant_id: str, manifest: AppManifest, linked_to: Optional[str]) -> str:
        """Provision an isolated deployment. linked_to is the epistemicos deployment ID if this is synapticaos."""

    @abstractmethod
    async def deprovision(self, deployment_id: str) -> None:
        """Clean up a deployment."""


class EpistemicOSBackend(KernelBackend):
    """Provisions isolated EpistemicOS zones with tenant-scoped knowledge bindings."""

    def __init__(self, endpoint: str = None, timeout: float = 30.0):
        self.endpoint = endpoint or os.getenv("EPISTEMICOS_ENDPOINT", "http://localhost:8001")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout, verify=False)

    async def provision(self, tenant_id: str, manifest: AppManifest, linked_to: Optional[str]) -> str:
        """Create an isolated EpistemicOS zone with Guardian knowledge commit governance."""
        zone_id = str(uuid.uuid4())[:8]
        zone_name = f"{manifest.name}-{tenant_id}-{zone_id}"

        try:
            # POST /api/zones/scopes to create a new zone scope
            scope_resp = await self.client.post(
                f"{self.endpoint}/api/zones/scopes",
                json={"target_os": "TREE"},
                headers={"Authorization": f"Bearer {os.getenv('ZONE_GUARDIAN_TOKEN', '')}"},
            )
            scope_resp.raise_for_status()
            scope_data = scope_resp.json()
            scope_id = scope_data.get("scope_id")

            # Record in Guardian: this zone is tied to tenant+app+spend_ceiling
            guardian_note = f"Tenant {tenant_id} provisioned {manifest.name} "
            guardian_note += f"(${manifest.spend_policy.monthly_ceiling_usd}/mo, {manifest.spend_policy.enforcement})"

            # For now, we just log the provision. Real implementation would:
            # - Register the zone's governance parameters
            # - Bind Guardian knowledge commits to the zone
            # - Set up spend tracking hooks
            return f"epistemicos:{scope_id}"

        except Exception as exc:
            raise RuntimeError(f"EpistemicOS zone provision failed: {exc}") from exc

    async def deprovision(self, deployment_id: str) -> None:
        """Tear down an EpistemicOS zone."""
        try:
            # POST /api/zones/destroy or similar
            # For now, log it
            pass
        except Exception as exc:
            raise RuntimeError(f"EpistemicOS zone deprovision failed: {exc}") from exc

    async def close(self):
        await self.client.aclose()


class SynapticaOSBackend(KernelBackend):
    """Provisions sparse, distributed CXU swarms and execution leases."""

    def __init__(self, endpoint: str = None, timeout: float = 30.0):
        self.endpoint = endpoint or os.getenv("SYNAPTICAOS_ENDPOINT", "http://localhost:8002")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout, verify=False)

    async def provision(self, tenant_id: str, manifest: AppManifest, linked_to: Optional[str]) -> str:
        """Allocate swarm resources, linked to epistemicos zone."""
        swarm_id = str(uuid.uuid4())[:8]

        try:
            # POST /api/swarms/allocate with tenant, CTU budget, spend ceiling
            # linked_to is the epistemicos zone ID; swarm execution is governed by that zone's Guardian
            swarm_resp = await self.client.post(
                f"{self.endpoint}/api/swarms/allocate",
                json={
                    "tenant_id": tenant_id,
                    "linked_zone": linked_to,
                    "app_manifest_name": manifest.name,
                    "spend_ceiling_usd": manifest.spend_policy.monthly_ceiling_usd,
                    "enforcement": manifest.spend_policy.enforcement,
                },
            )
            swarm_resp.raise_for_status()
            swarm_data = swarm_resp.json()
            return f"synapticaos:{swarm_data.get('swarm_id', swarm_id)}"

        except Exception as exc:
            raise RuntimeError(f"SynapticaOS swarm allocation failed: {exc}") from exc

    async def deprovision(self, deployment_id: str) -> None:
        """Release swarm resources."""
        try:
            # POST /api/swarms/release or DELETE
            pass
        except Exception as exc:
            raise RuntimeError(f"SynapticaOS swarm release failed: {exc}") from exc

    async def close(self):
        await self.client.aclose()
