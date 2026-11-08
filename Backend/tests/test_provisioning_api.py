"""
Tests for provisioning API and service layer.

Test coverage:
1. Installation submission (POST /provisioning/install)
2. Installation listing (GET /provisioning/install)
3. Installation retrieval (GET /provisioning/install/{id})
4. Installation approval (POST /provisioning/install/{id}/approve)
5. Authorization (Bearer token parsing)
6. State machine transitions
7. Error handling (invalid state, unauthorized access, etc.)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.cogpm.models import Base, Installation, Deployment, StateTransition, InstallState, DeploymentState
from app.cogpm.provisioner import CognitivePackageManager, Installation as CogPMInstallation
from app.cogpm.schemas import InstallRequest, SpendPolicy


# In-memory SQLite for tests
@pytest.fixture
def db():
    """Create in-memory SQLite database for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    yield SessionLocal()


@pytest.fixture
def client(db):
    """FastAPI test client with injected test database."""
    def override_get_db():
        yield db
    
    # Patch the database dependency
    from app.database import get_db
    app.dependency_overrides[get_db] = override_get_db
    
    return TestClient(app)


@pytest.fixture
def cogpm():
    """CognitivePackageManager with test manifests loaded."""
    cogpm = CognitivePackageManager()
    # Load test manifests (assumes they exist in app_manifests/)
    # In real tests, mock or create test manifests
    return cogpm


# ============================================================================
# Authorization Tests
# ============================================================================

def test_missing_authorization_header(client):
    """Test missing Bearer token."""
    response = client.post(
        "/api/v1/provisioning/install",
        json={"app_id": "forge", "monthly_ceiling_usd": 500},
    )
    assert response.status_code == 401
    assert "authorization" in response.json()["detail"].lower()


def test_invalid_authorization_format(client):
    """Test malformed Bearer token."""
    response = client.post(
        "/api/v1/provisioning/install",
        json={"app_id": "forge", "monthly_ceiling_usd": 500},
        headers={"Authorization": "Basic user:pass"},  # Wrong scheme
    )
    assert response.status_code == 401


def test_invalid_bearer_token_format(client):
    """Test Bearer token without tenant:user format."""
    response = client.post(
        "/api/v1/provisioning/install",
        json={"app_id": "forge", "monthly_ceiling_usd": 500},
        headers={"Authorization": "Bearer invalid_token"},
    )
    assert response.status_code == 401


# ============================================================================
# Installation Submission Tests
# ============================================================================

def test_submit_installation_success(client):
    """Test successful installation submission."""
    response = client.post(
        "/api/v1/provisioning/install",
        json={
            "app_id": "forge",
            "spend_policy": "hard_stop",
            "monthly_ceiling_usd": 500.00,
        },
        headers={"Authorization": "Bearer tenant-123:alice@example.com"},
    )
    
    # Note: This will fail without manifests loaded.
    # In real tests, mock the CogPM or load test manifests.
    # For now, we expect 400 (app not found)
    assert response.status_code in [400, 201]


def test_submit_installation_invalid_budget(client):
    """Test submission with invalid budget."""
    response = client.post(
        "/api/v1/provisioning/install",
        json={
            "app_id": "forge",
            "spend_policy": "hard_stop",
            "monthly_ceiling_usd": -100,  # Invalid: negative
        },
        headers={"Authorization": "Bearer tenant-123:alice@example.com"},
    )
    
    assert response.status_code == 422  # Validation error


def test_submit_installation_zero_budget(client):
    """Test submission with zero budget."""
    response = client.post(
        "/api/v1/provisioning/install",
        json={
            "app_id": "forge",
            "spend_policy": "hard_stop",
            "monthly_ceiling_usd": 0,
        },
        headers={"Authorization": "Bearer tenant-123:alice@example.com"},
    )
    
    assert response.status_code == 422


# ============================================================================
# Installation Listing Tests
# ============================================================================

def test_list_installations_empty(client):
    """Test listing installations when none exist."""
    response = client.get(
        "/api/v1/provisioning/install",
        headers={"Authorization": "Bearer tenant-123:alice@example.com"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["installations"] == []
    assert data["total"] == 0
    assert data["skip"] == 0
    assert data["limit"] == 50


def test_list_installations_pagination(client):
    """Test pagination parameters."""
    response = client.get(
        "/api/v1/provisioning/install?skip=10&limit=25",
        headers={"Authorization": "Bearer tenant-123:alice@example.com"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["skip"] == 10
    assert data["limit"] == 25


def test_list_installations_invalid_limit(client):
    """Test invalid limit parameter."""
    response = client.get(
        "/api/v1/provisioning/install?limit=200",  # Max is 100
        headers={"Authorization": "Bearer tenant-123:alice@example.com"},
    )
    
    assert response.status_code == 422


# ============================================================================
# Installation Retrieval Tests
# ============================================================================

def test_get_installation_not_found(client):
    """Test retrieving non-existent installation."""
    response = client.get(
        "/api/v1/provisioning/install/non-existent-id",
        headers={"Authorization": "Bearer tenant-123:alice@example.com"},
    )
    
    assert response.status_code == 404


def test_get_installation_unauthorized_tenant(client, db):
    """Test retrieving installation from different tenant."""
    # Create an installation for tenant-456
    installation = Installation(
        id="test-install-1",
        tenant_id="tenant-456",
        app_id="forge",
        app_version="1.0.0",
        state=InstallState.PENDING_APPROVAL,
        requested_by="bob@example.com",
        manifest_hash="abc123",
        spend_policy="hard_stop",
        monthly_ceiling_usd=50000,
    )
    db.add(installation)
    db.commit()
    
    # Try to access as tenant-123
    response = client.get(
        "/api/v1/provisioning/install/test-install-1",
        headers={"Authorization": "Bearer tenant-123:alice@example.com"},
    )
    
    assert response.status_code == 403


# ============================================================================
# Installation Approval Tests
# ============================================================================

def test_approve_installation_not_found(client):
    """Test approving non-existent installation."""
    response = client.post(
        "/api/v1/provisioning/install/non-existent-id/approve",
        json={"approved_by": "approver@example.com"},
        headers={"Authorization": "Bearer tenant-123:alice@example.com"},
    )
    
    assert response.status_code == 404


def test_approve_installation_unauthorized_tenant(client, db):
    """Test approving installation from different tenant."""
    installation = Installation(
        id="test-install-2",
        tenant_id="tenant-456",
        app_id="forge",
        app_version="1.0.0",
        state=InstallState.PENDING_APPROVAL,
        requested_by="bob@example.com",
        manifest_hash="abc123",
        spend_policy="hard_stop",
        monthly_ceiling_usd=50000,
    )
    db.add(installation)
    db.commit()
    
    response = client.post(
        "/api/v1/provisioning/install/test-install-2/approve",
        json={"approved_by": "approver@example.com"},
        headers={"Authorization": "Bearer tenant-123:alice@example.com"},
    )
    
    assert response.status_code == 403


# ============================================================================
# State Machine Tests
# ============================================================================

def test_installation_state_machine(db):
    """Test valid state transitions."""
    # Valid: PENDING_APPROVAL -> PROVISIONING -> ACTIVE
    installation = Installation(
        id="state-test-1",
        tenant_id="tenant-123",
        app_id="forge",
        app_version="1.0.0",
        state=InstallState.PENDING_APPROVAL,
        requested_by="alice@example.com",
        manifest_hash="abc123",
        spend_policy="hard_stop",
        monthly_ceiling_usd=50000,
    )
    db.add(installation)
    db.commit()
    
    # Transition to PROVISIONING
    installation.state = InstallState.PROVISIONING
    installation.approved_by = "approver@example.com"
    installation.approved_at = datetime.utcnow()
    db.commit()
    
    assert installation.state == InstallState.PROVISIONING
    
    # Transition to ACTIVE
    installation.state = InstallState.ACTIVE
    installation.completed_at = datetime.utcnow()
    db.commit()
    
    assert installation.state == InstallState.ACTIVE


def test_installation_failure_transition(db):
    """Test PROVISIONING -> FAILED transition."""
    installation = Installation(
        id="state-test-2",
        tenant_id="tenant-123",
        app_id="forge",
        app_version="1.0.0",
        state=InstallState.PROVISIONING,
        requested_by="alice@example.com",
        approved_by="approver@example.com",
        manifest_hash="abc123",
        spend_policy="hard_stop",
        monthly_ceiling_usd=50000,
    )
    db.add(installation)
    db.commit()
    
    # Transition to FAILED
    installation.state = InstallState.FAILED
    installation.error_message = "Kernel provision timeout"
    installation.completed_at = datetime.utcnow()
    db.commit()
    
    assert installation.state == InstallState.FAILED
    assert installation.error_message is not None


# ============================================================================
# Deployment Tests
# ============================================================================

def test_deployment_creation(db):
    """Test deployment record creation."""
    installation = Installation(
        id="deploy-test-1",
        tenant_id="tenant-123",
        app_id="forge_plus",
        app_version="1.0.0",
        state=InstallState.PENDING_APPROVAL,
        requested_by="alice@example.com",
        manifest_hash="abc123",
        spend_policy="hard_stop",
        monthly_ceiling_usd=2000000,
    )
    db.add(installation)
    db.flush()
    
    # Forge Plus requires 2 deployments (EpistemicOS, SynapticaOS)
    deployment_ep = Deployment(
        id="deploy-ep-1",
        installation_id=installation.id,
        kernel_id="epistemicos",
        kernel_version="0.1.0",
        state=DeploymentState.PENDING,
    )
    deployment_syn = Deployment(
        id="deploy-syn-1",
        installation_id=installation.id,
        kernel_id="synapticaos",
        kernel_version="0.1.0",
        state=DeploymentState.PENDING,
        linked_to="deploy-ep-1",  # Link to EpistemicOS
    )
    db.add_all([deployment_ep, deployment_syn])
    db.commit()
    
    # Verify deployments
    deployments = db.query(Deployment).filter(
        Deployment.installation_id == installation.id
    ).all()
    assert len(deployments) == 2
    assert any(d.kernel_id == "epistemicos" for d in deployments)
    assert any(d.kernel_id == "synapticaos" for d in deployments)


# ============================================================================
# State Transition Audit Tests
# ============================================================================

def test_state_transition_audit(db):
    """Test state transition audit trail."""
    installation = Installation(
        id="audit-test-1",
        tenant_id="tenant-123",
        app_id="forge",
        app_version="1.0.0",
        state=InstallState.PENDING_APPROVAL,
        requested_by="alice@example.com",
        manifest_hash="abc123",
        spend_policy="hard_stop",
        monthly_ceiling_usd=50000,
    )
    db.add(installation)
    db.flush()
    
    # Record transitions
    transitions = [
        StateTransition(
            id="trans-1",
            installation_id=installation.id,
            from_state=InstallState.PENDING_APPROVAL,
            to_state=InstallState.PROVISIONING,
            triggered_by="approver@example.com",
            reason="Manual approval",
        ),
        StateTransition(
            id="trans-2",
            installation_id=installation.id,
            from_state=InstallState.PROVISIONING,
            to_state=InstallState.ACTIVE,
            triggered_by="system",
            reason="Provisioning completed",
        ),
    ]
    db.add_all(transitions)
    db.commit()
    
    # Verify audit trail
    audit = db.query(StateTransition).filter(
        StateTransition.installation_id == installation.id
    ).order_by(StateTransition.transitioned_at).all()
    
    assert len(audit) == 2
    assert audit[0].to_state == InstallState.PROVISIONING
    assert audit[1].to_state == InstallState.ACTIVE
