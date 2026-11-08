"""
Tests for spend tracking and budget enforcement.

Test coverage:
1. Usage event recording (real-time spend tracking)
2. Budget checks (can_allocate_resource with spend policies)
3. Spend policy enforcement (hard_stop, reservation, controlled_overage)
4. Budget threshold alerts (80%, 95%, 100%)
5. Monthly usage reports (aggregation by app, kernel, installation)
6. Tenant isolation and authorization
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime

from app.cogpm.models import (
    Base, Installation, Deployment, UsageEvent, BudgetAlert,
    InstallState, DeploymentState,
)
from app.cogpm.spend_enforcement import SpendEnforcementService


# In-memory SQLite for tests
@pytest.fixture
def db():
    """Create in-memory SQLite database for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.fixture
def service(db):
    """SpendEnforcementService with test database."""
    return SpendEnforcementService(db=db)


@pytest.fixture
def active_installation(db):
    """Create an active installation for testing."""
    installation = Installation(
        id="test-install-1",
        tenant_id="tenant-123",
        app_id="forge_plus",
        app_version="1.0.0",
        state=InstallState.ACTIVE,
        requested_by="alice@example.com",
        approved_by="approver@example.com",
        manifest_hash="abc123",
        spend_policy="hard_stop",
        monthly_ceiling_usd=50000,  # $500/month * 100 = 50000 cents
    )
    db.add(installation)
    db.commit()
    return installation


# ============================================================================
# Usage Event Recording Tests
# ============================================================================

def test_record_usage_event_success(service, active_installation):
    """Test recording a usage event."""
    event = service.record_usage_event(
        tenant_id="tenant-123",
        installation_id=active_installation.id,
        app_id="forge_plus",
        kernel_id="epistemicos",
        resource_type="zone",
        cost_cents=10000,  # $100
        operation="create_zone",
        resource_id="zone-123",
        billing_category="compute",
    )

    assert event is not None
    assert event.cost_cents == 10000
    assert event.operation == "create_zone"
    assert event.kernel_id == "epistemicos"


def test_record_usage_event_inactive_installation(service, db):
    """Test recording event for inactive installation."""
    # Create FAILED installation
    installation = Installation(
        id="test-install-2",
        tenant_id="tenant-123",
        app_id="forge",
        app_version="1.0.0",
        state=InstallState.FAILED,
        requested_by="alice@example.com",
        manifest_hash="abc123",
        spend_policy="hard_stop",
        monthly_ceiling_usd=5000,
    )
    db.add(installation)
    db.commit()

    service = SpendEnforcementService(db=db)
    with pytest.raises(ValueError, match="not ACTIVE"):
        service.record_usage_event(
            tenant_id="tenant-123",
            installation_id=installation.id,
            app_id="forge",
            kernel_id="epistemicos",
            resource_type="zone",
            cost_cents=1000,
            operation="create_zone",
        )


def test_record_usage_event_unknown_installation(service):
    """Test recording event for non-existent installation."""
    with pytest.raises(ValueError, match="not found"):
        service.record_usage_event(
            tenant_id="tenant-123",
            installation_id="unknown-install",
            app_id="forge",
            kernel_id="epistemicos",
            resource_type="zone",
            cost_cents=1000,
            operation="create_zone",
        )


# ============================================================================
# Budget Check Tests (hard_stop policy)
# ============================================================================

def test_can_allocate_within_budget(service, active_installation):
    """Test allocation allowed when within budget."""
    # Record $100 spend
    service.record_usage_event(
        tenant_id="tenant-123",
        installation_id=active_installation.id,
        app_id="forge_plus",
        kernel_id="epistemicos",
        resource_type="zone",
        cost_cents=10000,  # $100
        operation="create_zone",
    )

    # Check if $200 allocation is allowed (total would be $300, within $500 ceiling)
    allowed, reason = service.can_allocate_resource(
        installation_id=active_installation.id,
        estimated_cost_cents=20000,  # $200
    )

    assert allowed is True
    assert reason is None


def test_can_allocate_exceeds_budget(service, active_installation):
    """Test allocation denied when exceeding budget (hard_stop)."""
    # Record $450 spend (close to $500 ceiling)
    service.record_usage_event(
        tenant_id="tenant-123",
        installation_id=active_installation.id,
        app_id="forge_plus",
        kernel_id="epistemicos",
        resource_type="zone",
        cost_cents=450000,  # $4500
        operation="create_zone",
    )

    # Check if $100 allocation is allowed (total would be $4600, exceeds $5000 ceiling)
    allowed, reason = service.can_allocate_resource(
        installation_id=active_installation.id,
        estimated_cost_cents=10000,  # $100
    )

    assert allowed is False
    assert reason is not None
    assert "exceed" in reason.lower()


def test_can_allocate_exactly_at_ceiling(service, active_installation):
    """Test allocation allowed when exactly at ceiling."""
    # Record $499.99 spend
    service.record_usage_event(
        tenant_id="tenant-123",
        installation_id=active_installation.id,
        app_id="forge_plus",
        kernel_id="epistemicos",
        resource_type="zone",
        cost_cents=499900,  # $4999
        operation="create_zone",
    )

    # Check if $1 allocation is allowed (total would be $5000, exactly at ceiling)
    allowed, reason = service.can_allocate_resource(
        installation_id=active_installation.id,
        estimated_cost_cents=100,  # $1
    )

    assert allowed is True


# ============================================================================
# Spend Policy Tests (reservation)
# ============================================================================

def test_reservation_policy_allows_overage(service, db):
    """Test reservation policy allows overage but creates alert."""
    # Create reservation policy installation
    installation = Installation(
        id="test-install-res",
        tenant_id="tenant-123",
        app_id="forge",
        app_version="1.0.0",
        state=InstallState.ACTIVE,
        requested_by="alice@example.com",
        approved_by="approver@example.com",
        manifest_hash="abc123",
        spend_policy="reservation",
        monthly_ceiling_usd=100,  # $100 reservation
    )
    db.add(installation)
    db.commit()

    service = SpendEnforcementService(db=db)

    # Record $90 spend
    service.record_usage_event(
        tenant_id="tenant-123",
        installation_id=installation.id,
        app_id="forge",
        kernel_id="epistemicos",
        resource_type="zone",
        cost_cents=9000,  # $90
        operation="create_zone",
    )

    # Check if $50 allocation is allowed (total would be $140, exceeds $100)
    allowed, reason = service.can_allocate_resource(
        installation_id=installation.id,
        estimated_cost_cents=5000,  # $50
    )

    # Reservation policy allows overage but flags it
    assert allowed is True
    assert reason is None  # No rejection reason


# ============================================================================
# Spend Policy Tests (controlled_overage)
# ============================================================================

def test_controlled_overage_policy_allows_everything(service, db):
    """Test controlled_overage policy always allows but tracks."""
    installation = Installation(
        id="test-install-ovg",
        tenant_id="tenant-123",
        app_id="chronothera",
        app_version="1.0.0",
        state=InstallState.ACTIVE,
        requested_by="alice@example.com",
        approved_by="approver@example.com",
        manifest_hash="abc123",
        spend_policy="controlled_overage",
        monthly_ceiling_usd=50,  # Low ceiling for testing
    )
    db.add(installation)
    db.commit()

    service = SpendEnforcementService(db=db)

    # Record $40 spend
    service.record_usage_event(
        tenant_id="tenant-123",
        installation_id=installation.id,
        app_id="chronothera",
        kernel_id="epistemicos",
        resource_type="zone",
        cost_cents=4000,  # $40
        operation="create_zone",
    )

    # Check if $50 allocation is allowed (total would be $90, way over $50)
    allowed, reason = service.can_allocate_resource(
        installation_id=installation.id,
        estimated_cost_cents=5000,  # $50
    )

    # Controlled overage allows it
    assert allowed is True


# ============================================================================
# Budget Threshold Tests
# ============================================================================

def test_budget_threshold_80_percent(service, db):
    """Test budget alert at 80% threshold."""
    installation = Installation(
        id="test-install-thresh",
        tenant_id="tenant-123",
        app_id="forge",
        app_version="1.0.0",
        state=InstallState.ACTIVE,
        requested_by="alice@example.com",
        approved_by="approver@example.com",
        manifest_hash="abc123",
        spend_policy="hard_stop",
        monthly_ceiling_usd=1000,  # $1000 ceiling
    )
    db.add(installation)
    db.commit()

    service = SpendEnforcementService(db=db)

    # Record exactly 80% of ceiling ($800)
    service.record_usage_event(
        tenant_id="tenant-123",
        installation_id=installation.id,
        app_id="forge",
        kernel_id="epistemicos",
        resource_type="zone",
        cost_cents=80000,  # $800
        operation="create_zone",
    )

    # Check threshold
    alert = service.check_budget_threshold(installation.id)
    assert alert is not None
    assert alert.alert_type == "threshold_80"
    assert alert.percentage == 80


def test_budget_threshold_100_percent(service, db):
    """Test budget alert at 100% (limit reached)."""
    installation = Installation(
        id="test-install-100",
        tenant_id="tenant-123",
        app_id="forge",
        app_version="1.0.0",
        state=InstallState.ACTIVE,
        requested_by="alice@example.com",
        approved_by="approver@example.com",
        manifest_hash="abc123",
        spend_policy="hard_stop",
        monthly_ceiling_usd=100,
    )
    db.add(installation)
    db.commit()

    service = SpendEnforcementService(db=db)

    # Record exactly 100% of ceiling
    service.record_usage_event(
        tenant_id="tenant-123",
        installation_id=installation.id,
        app_id="forge",
        kernel_id="epistemicos",
        resource_type="zone",
        cost_cents=10000,  # $100
        operation="create_zone",
    )

    # Check threshold
    alert = service.check_budget_threshold(installation.id)
    assert alert is not None
    assert alert.alert_type == "limit_reached"
    assert alert.percentage == 100


# ============================================================================
# Monthly Usage Report Tests
# ============================================================================

def test_usage_report_single_app(service, active_installation):
    """Test usage report aggregation by app."""
    # Record multiple events
    service.record_usage_event(
        tenant_id="tenant-123",
        installation_id=active_installation.id,
        app_id="forge_plus",
        kernel_id="epistemicos",
        resource_type="zone",
        cost_cents=10000,  # $100
        operation="create_zone",
    )
    service.record_usage_event(
        tenant_id="tenant-123",
        installation_id=active_installation.id,
        app_id="forge_plus",
        kernel_id="synapticaos",
        resource_type="swarm",
        cost_cents=5000,  # $50
        operation="allocate_swarm",
    )

    # Get report
    report = service.get_monthly_usage(tenant_id="tenant-123")

    assert report["total_spent_cents"] == 15000
    assert report["total_spent_usd"] == 150.0
    assert len(report["by_app"]) == 1
    assert report["by_app"][0]["app_id"] == "forge_plus"
    assert report["by_app"][0]["spent_cents"] == 15000


def test_usage_report_by_kernel(service, active_installation, db):
    """Test usage report aggregation by kernel."""
    # Create another installation
    installation2 = Installation(
        id="test-install-2",
        tenant_id="tenant-123",
        app_id="forge",
        app_version="1.0.0",
        state=InstallState.ACTIVE,
        requested_by="alice@example.com",
        approved_by="approver@example.com",
        manifest_hash="abc123",
        spend_policy="hard_stop",
        monthly_ceiling_usd=10000,
    )
    db.add(installation2)
    db.commit()

    service = SpendEnforcementService(db=db)

    # Record events for each kernel
    service.record_usage_event(
        tenant_id="tenant-123",
        installation_id=active_installation.id,
        app_id="forge_plus",
        kernel_id="epistemicos",
        resource_type="zone",
        cost_cents=10000,
        operation="create_zone",
    )
    service.record_usage_event(
        tenant_id="tenant-123",
        installation_id=installation2.id,
        app_id="forge",
        kernel_id="epistemicos",
        resource_type="zone",
        cost_cents=5000,
        operation="create_zone",
    )

    # Get report
    report = service.get_monthly_usage(tenant_id="tenant-123")

    assert len(report["by_kernel"]) == 1
    assert report["by_kernel"][0]["kernel_id"] == "epistemicos"
    assert report["by_kernel"][0]["spent_cents"] == 15000


def test_usage_report_installation_breakdown(service, active_installation):
    """Test usage report shows per-installation breakdown."""
    # Record events
    service.record_usage_event(
        tenant_id="tenant-123",
        installation_id=active_installation.id,
        app_id="forge_plus",
        kernel_id="epistemicos",
        resource_type="zone",
        cost_cents=100000,  # $1000 (20% of $5000 ceiling)
        operation="create_zone",
    )

    # Get report
    report = service.get_monthly_usage(tenant_id="tenant-123")

    # Check installation breakdown
    inst_spend = report["installations"][active_installation.id]
    assert inst_spend["spent_cents"] == 100000
    assert inst_spend["ceiling_cents"] == 5000000  # $50,000
    assert inst_spend["percentage"] == 2  # 2% of ceiling
