"""Tests for CogPM REST API and provisioning service."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.provisioning import get_provisioning_service, router
from app.cogpm.manifest import load_manifests
from app.cogpm.models import Base, Installation, InstallState
from app.cogpm.provisioner import CognitivePackageManager
from app.cogpm.service import ProvisioningService
from app.cogpm.validator import KernelInfo, PlatformContext, TenantContext
from app.main import app


# Use in-memory SQLite for tests
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class FakeKernel:
    def __init__(self, name, fail=False):
        self.name = name
        self.fail = fail
        self.live = {}

    async def provision(self, tenant_id, manifest, linked_to):
        if self.fail:
            raise RuntimeError(f"{self.name} unavailable")
        dep_id = f"{self.name}:{tenant_id}-{manifest.name}"
        self.live[dep_id] = True
        return dep_id

    async def deprovision(self, deployment_id):
        self.live.pop(deployment_id, None)


@pytest.fixture
def platform():
    return PlatformContext(
        publisher_keys={"nexithera": b"nexithera-test-key"},
        kernels={
            "epistemicos": KernelInfo("0.1.0", {
                "cxu_zone", "guardian", "semantic_search",
                "single_zone_simulation", "governed_knowledge_commit"
            }),
            "synapticaos": KernelInfo("0.1.0", {
                "swarm_resource_group", "ctu_binding", "execution_lease", "sparse_execution"
            }),
        },
        hosting_services={"protein_folding"},
    )


@pytest.fixture
def cogpm(platform):
    ep = FakeKernel("epistemicos")
    sy = FakeKernel("synapticaos")
    return CognitivePackageManager(platform, {"epistemicos": ep, "synapticaos": sy})


@pytest.fixture
def manifests():
    return load_manifests("app_manifests")


@pytest.fixture
def provisioning_svc(db_session, platform, cogpm):
    return ProvisioningService(db_session, platform, cogpm)


@pytest.fixture
def client(db_session):
    """Override dependency for testing."""
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_provisioning_service] = lambda: ProvisioningService(
        db_session,
        PlatformContext(
            publisher_keys={"nexithera": b"nexithera-test-key"},
            kernels={
                "epistemicos": KernelInfo("0.1.0", {
                    "cxu_zone", "guardian", "semantic_search",
                    "single_zone_simulation", "governed_knowledge_commit"
                }),
                "synapticaos": KernelInfo("0.1.0", {
                    "swarm_resource_group", "ctu_binding", "execution_lease", "sparse_execution"
                }),
            },
            hosting_services={"protein_folding"},
        ),
        CognitivePackageManager(
            PlatformContext(
                publisher_keys={"nexithera": b"nexithera-test-key"},
                kernels={
                    "epistemicos": KernelInfo("0.1.0", {
                        "cxu_zone", "guardian", "semantic_search",
                        "single_zone_simulation", "governed_knowledge_commit"
                    }),
                    "synapticaos": KernelInfo("0.1.0", {
                        "swarm_resource_group", "ctu_binding", "execution_lease", "sparse_execution"
                    }),
                },
                hosting_services={"protein_folding"},
            ),
            {"epistemicos": FakeKernel("epistemicos"), "synapticaos": FakeKernel("synapticaos")}
        )
    )
    return TestClient(app)


def test_submit_forge_installation(provisioning_svc, manifests):
    """Submit a Forge manifest."""
    m = manifests["forge"]
    inst = provisioning_svc.submit_installation(m, m.sign(b"nexithera-test-key"), "acme", "admin")
    
    assert inst.id
    assert inst.state == InstallState.PENDING_APPROVAL
    assert inst.manifest_name == "forge"
    assert not inst.errors


def test_submit_with_bad_signature(provisioning_svc, manifests):
    """Submit with wrong signature fails validation."""
    m = manifests["forge"]
    inst = provisioning_svc.submit_installation(m, "bad-sig", "acme", "admin")
    
    assert inst.state == InstallState.FAILED
    assert any("signature" in e.lower() for e in inst.errors)


async def test_approve_forge(provisioning_svc, manifests):
    """Submit then approve a Forge installation."""
    m = manifests["forge"]
    inst = provisioning_svc.submit_installation(m, m.sign(b"nexithera-test-key"), "acme", "admin")
    
    inst = await provisioning_svc.approve_installation(inst.id)
    assert inst.state == InstallState.ACTIVE
    assert "epistemicos" in inst.deployments


async def test_approve_forge_plus_creates_linked_deployments(provisioning_svc, manifests):
    """Forge Plus creates two linked deployments."""
    m = manifests["forge-plus"]
    inst = provisioning_svc.submit_installation(m, m.sign(b"nexithera-test-key"), "acme", "admin")
    
    inst = await provisioning_svc.approve_installation(inst.id)
    assert inst.state == InstallState.ACTIVE
    assert set(inst.deployments.keys()) == {"epistemicos", "synapticaos"}
    
    # Fetch the DB records
    sy_dep = [d for d in inst.deployments if d.kernel_name == "synapticaos"][0]
    assert sy_dep.linked_to is not None  # synapticaos is linked to epistemicos


def test_get_installation(provisioning_svc, manifests):
    """Fetch installation details."""
    m = manifests["forge"]
    inst = provisioning_svc.submit_installation(m, m.sign(b"nexithera-test-key"), "acme", "admin")
    
    fetched = provisioning_svc.get_installation(inst.id)
    assert fetched.id == inst.id
    assert fetched.manifest_name == "forge"


def test_list_installations(provisioning_svc, manifests):
    """List installations for a tenant."""
    m1 = manifests["forge"]
    m2 = manifests["chronothera"]
    
    inst1 = provisioning_svc.submit_installation(m1, m1.sign(b"nexithera-test-key"), "acme", "admin")
    inst2 = provisioning_svc.submit_installation(m2, m2.sign(b"nexithera-test-key"), "acme", "admin")
    
    installs, total = provisioning_svc.list_installations("acme")
    assert total >= 2
    assert any(i.manifest_name == "forge" for i in installs)
    assert any(i.manifest_name == "chronothera" for i in installs)


def test_list_installations_filter_by_state(provisioning_svc, manifests):
    """Filter installations by state."""
    m = manifests["forge"]
    provisioning_svc.submit_installation(m, m.sign(b"nexithera-test-key"), "acme", "admin")
    
    installs, total = provisioning_svc.list_installations("acme", state="PENDING_APPROVAL")
    assert total >= 1


def test_chronothera_requires_forge(provisioning_svc, manifests):
    """ChronoThera install fails if Forge not installed."""
    m = manifests["chronothera"]
    inst = provisioning_svc.submit_installation(m, m.sign(b"nexithera-test-key"), "acme", "admin")
    
    # Should fail validation
    assert inst.state == InstallState.FAILED
    assert any("requires one of installed apps" in e for e in inst.errors)


def test_state_transitions_persisted(provisioning_svc, manifests):
    """State transitions are audited in DB."""
    m = manifests["forge"]
    inst = provisioning_svc.submit_installation(m, m.sign(b"nexithera-test-key"), "acme", "admin")
    
    transitions = provisioning_svc.db.query("state_transitions").all()
    # At minimum: submitted
    assert len(transitions) >= 1
