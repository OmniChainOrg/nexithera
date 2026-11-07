from pathlib import Path

import pytest

from app.cogpm.manifest import AppManifest, load_manifests
from app.cogpm.provisioner import CognitivePackageManager, InstallState
from app.cogpm.validator import KernelInfo, PlatformContext, TenantContext

MANIFEST_DIR = Path(__file__).resolve().parents[2] / "app_manifests"
KEY = b"nexithera-test-key"


class FakeKernel:
    def __init__(self, name, fail=False):
        self.name, self.fail = name, fail
        self.live, self.links = {}, []

    async def provision(self, tenant_id, manifest, linked_to):
        if self.fail:
            raise RuntimeError("boom")
        dep = f"{self.name}-{tenant_id}-{manifest.name}"
        self.live[dep] = True
        self.links.append(linked_to)
        return dep

    async def deprovision(self, deployment_id):
        self.live.pop(deployment_id, None)


@pytest.fixture
def manifests():
    return load_manifests(MANIFEST_DIR)


@pytest.fixture
def platform():
    return PlatformContext(
        publisher_keys={"nexithera": KEY},
        kernels={
            "epistemicos": KernelInfo("0.2.0", {"cxu_zone", "guardian", "semantic_search",
                                                "single_zone_simulation", "governed_knowledge_commit"}),
            "synapticaos": KernelInfo("0.1.0", {"swarm_resource_group", "ctu_binding",
                                                "execution_lease", "sparse_execution"}),
        },
        hosting_services={"protein_folding"},
    )


@pytest.fixture
def tenant():
    return TenantContext("acme", {"forge", "forge-plus", "chronothera"}, {"admin"})


def test_all_manifests_load(manifests):
    assert set(manifests) == {"forge", "forge-plus", "chronothera"}
    assert "synapticaos" not in manifests["forge"].kernels


def test_controlled_overage_requires_limit(manifests):
    data = manifests["forge"].model_dump(mode="json")
    data["spend_policy"]["enforcement"] = "controlled_overage"
    with pytest.raises(ValueError):
        AppManifest.model_validate(data)


async def test_forge_plus_creates_two_linked_deployments(manifests, platform, tenant):
    ep, sy = FakeKernel("ep"), FakeKernel("sy")
    pm = CognitivePackageManager(platform, {"epistemicos": ep, "synapticaos": sy})
    m = manifests["forge-plus"]
    inst = pm.submit(m, m.sign(KEY), "admin", tenant)
    assert inst.state == InstallState.PENDING_APPROVAL
    await pm.approve(inst.id, tenant)
    assert inst.state == InstallState.ACTIVE
    assert set(inst.deployments) == {"epistemicos", "synapticaos"}
    assert sy.links == [inst.deployments["epistemicos"]]
    assert "forge-plus" in tenant.installed_apps


async def test_forge_only_uses_epistemicos(manifests, platform, tenant):
    ep, sy = FakeKernel("ep"), FakeKernel("sy")
    pm = CognitivePackageManager(platform, {"epistemicos": ep, "synapticaos": sy})
    m = manifests["forge"]
    inst = pm.submit(m, m.sign(KEY), "admin", tenant)
    await pm.approve(inst.id, tenant)
    assert inst.state == InstallState.ACTIVE and not sy.live


async def test_failure_rolls_back_earlier_deployments(manifests, platform, tenant):
    ep, sy = FakeKernel("ep"), FakeKernel("sy", fail=True)
    pm = CognitivePackageManager(platform, {"epistemicos": ep, "synapticaos": sy})
    m = manifests["forge-plus"]
    inst = pm.submit(m, m.sign(KEY), "admin", tenant)
    await pm.approve(inst.id, tenant)
    assert inst.state == InstallState.FAILED
    assert not ep.live and not inst.deployments
    states = [s for s, _ in inst.history]
    assert InstallState.ROLLING_BACK in states and "forge-plus" not in tenant.installed_apps


def test_bad_signature_fails(manifests, platform, tenant):
    pm = CognitivePackageManager(platform, {})
    m = manifests["forge"]
    inst = pm.submit(m, "00", "admin", tenant)
    assert inst.state == InstallState.FAILED
    assert any("signature" in e for e in inst.errors)


def test_validation_catches_policy_issues(manifests, platform, tenant):
    platform.hosting_services.clear()
    platform.kernels["synapticaos"].capabilities.discard("execution_lease")
    tenant.entitlements.discard("forge-plus")
    m = manifests["forge-plus"]
    pm = CognitivePackageManager(platform, {})
    inst = pm.submit(m, m.sign(KEY), "intruder", tenant)
    joined = " | ".join(inst.errors)
    for needle in ("protein_folding", "execution_lease", "not entitled", "install authority"):
        assert needle in joined


def test_chronothera_requires_forge_family(manifests, platform, tenant):
    m = manifests["chronothera"]
    pm = CognitivePackageManager(platform, {})
    assert pm.submit(m, m.sign(KEY), "admin", tenant).state == InstallState.FAILED
    tenant.installed_apps.add("forge")
    assert pm.submit(m, m.sign(KEY), "admin", tenant).state == InstallState.PENDING_APPROVAL
