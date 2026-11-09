"""
SpendEnforcementService: Real-time budget checks and quota enforcement.

Responsibilities:
1. Record UsageEvents when resources are consumed (real-time)
2. Check budget before allowing new resource allocation
3. Enforce spend ceilings based on spend_policy (hard_stop, reservation, controlled_overage)
4. Track budget alerts and thresholds (80%, 95%, 100%)
5. Handle policy-specific actions (reject, flag, allow+notify)
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.cogpm.models import (
    Installation, UsageEvent, BudgetAlert,
    InstallState,
)


class SpendEnforcementService:
    """
    Service layer for spend tracking and budget enforcement.
    """

    def __init__(self, db: Session):
        self.db = db

    def record_usage_event(
        self,
        tenant_id: str,
        installation_id: str,
        app_id: str,
        kernel_id: str,
        resource_type: str,
        cost_cents: int,
        operation: str,
        resource_id: Optional[str] = None,
        billing_category: Optional[str] = None,
        metadata: Optional[str] = None,
    ) -> UsageEvent:
        """
        Record a real-time usage event (e.g., zone creation, inference call).
        
        Args:
            tenant_id: Tenant identifier
            installation_id: Which installation this event belongs to
            app_id: App being used (forge, forge_plus, chronothera)
            kernel_id: Which kernel (epistemicos, synapticaos)
            resource_type: Type of resource (zone, swarm, inference, storage, etc.)
            cost_cents: Cost in cents USD
            operation: Operation name (create_zone, allocate_swarm, inference_call, etc.)
            resource_id: Optional reference to created resource (zone_id, swarm_id, etc.)
            billing_category: Optional billing category for cost allocation
            metadata: Optional JSON metadata (duration, tokens used, parameters, etc.)
        
        Returns:
            UsageEvent record created
        
        Raises:
            ValueError: If installation not found or already failed
        """
        # Validate installation exists and is ACTIVE
        installation = self.db.query(Installation).filter(
            Installation.id == installation_id
        ).first()
        if not installation:
            raise ValueError(f"Installation '{installation_id}' not found")
        
        # Verify tenant ownership
        if installation.tenant_id != tenant_id:
            raise ValueError(f"Unauthorized: Installation does not belong to tenant '{tenant_id}'")

        if installation.state != InstallState.ACTIVE:
            raise ValueError(
                f"Cannot record usage for installation in state '{installation.state}'. "
                f"Must be '{InstallState.ACTIVE}'"
            )

        # Create usage event
        event = UsageEvent(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            installation_id=installation_id,
            app_id=app_id,
            kernel_id=kernel_id,
            resource_type=resource_type,
            cost_cents=cost_cents,
            operation=operation,
            resource_id=resource_id,
            billing_category=billing_category or "compute",
            metadata=metadata,
            created_at=datetime.utcnow(),
            month_year=datetime.utcnow().strftime("%Y-%m"),
        )
        self.db.add(event)
        self.db.commit()

        return event

    def can_allocate_resource(
        self,
        tenant_id: str,
        installation_id: str,
        estimated_cost_cents: int,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a resource allocation should be allowed based on budget.
        
        Args:
            tenant_id: Tenant making the request (for ownership verification)
            installation_id: Installation to check
            estimated_cost_cents: Estimated cost of new allocation
        
        Returns:
            Tuple of (allowed: bool, reason: str or None)
            - (True, None): Allocation allowed
            - (False, reason): Allocation rejected with reason
        """
        # Fetch installation
        installation = self.db.query(Installation).filter(
            Installation.id == installation_id
        ).first()
        if not installation:
            return False, f"Installation '{installation_id}' not found"
        
        # Verify tenant ownership
        if installation.tenant_id != tenant_id:
            return False, f"Unauthorized: Installation does not belong to tenant '{tenant_id}'"

        if installation.state != InstallState.ACTIVE:
            return False, f"Installation is in '{installation.state}' state, not ACTIVE"

        # Calculate current month spend
        current_month = datetime.utcnow().strftime("%Y-%m")
        current_spent = self.db.query(func.sum(UsageEvent.cost_cents)).filter(
            UsageEvent.installation_id == installation_id,
            UsageEvent.month_year == current_month,
        ).scalar() or 0

        # Get ceiling (already in cents)
        ceiling_cents = installation.monthly_ceiling_cents

        # Calculate if allocation would exceed ceiling
        total_after = current_spent + estimated_cost_cents

        # Apply spend policy
        if installation.spend_policy == "hard_stop":
            if total_after > ceiling_cents:
                return False, (
                    f"Allocation would exceed budget ceiling: "
                    f"${current_spent/100:.2f} + ${estimated_cost_cents/100:.2f} "
                    f"> ${ceiling_cents/100:.2f}"
                )
            return True, None

        elif installation.spend_policy == "reservation":
            # Allow allocation but flag it (warn, but don't reject)
            if total_after > ceiling_cents:
                # Still allow but log alert
                self._create_budget_alert(
                    installation=installation,
                    monthly_spent_cents=current_spent,
                    alert_type="overage",
                    percentage=int((total_after / ceiling_cents) * 100),
                    action_taken="reservation_exceeded",
                    action_details=f"Allowed allocation exceeding reservation: ${estimated_cost_cents/100:.2f}",
                )
                return True, None  # Allow but flagged
            return True, None

        elif installation.spend_policy == "controlled_overage":
            # Always allow, but track spend
            if total_after > ceiling_cents:
                self._create_budget_alert(
                    installation=installation,
                    monthly_spent_cents=current_spent,
                    alert_type="overage",
                    percentage=int((total_after / ceiling_cents) * 100),
                    action_taken="controlled_overage_allowed",
                    action_details=f"Allocation allowed with overage: ${estimated_cost_cents/100:.2f}",
                )
            return True, None

        return True, None

    def check_budget_threshold(self, installation_id: str) -> Optional[BudgetAlert]:
        """
        Check if current spend crosses a threshold (80%, 95%, 100%).
        Create alert if threshold is reached.
        
        Args:
            installation_id: Installation to check
        
        Returns:
            BudgetAlert if a new threshold is crossed, None otherwise
        """
        # Fetch installation
        installation = self.db.query(Installation).filter(
            Installation.id == installation_id
        ).first()
        if not installation:
            return None

        # Calculate current spend
        current_month = datetime.utcnow().strftime("%Y-%m")
        current_spent = self.db.query(func.sum(UsageEvent.cost_cents)).filter(
            UsageEvent.installation_id == installation_id,
            UsageEvent.month_year == current_month,
        ).scalar() or 0

        ceiling_cents = installation.monthly_ceiling_cents
        percentage = int((current_spent / ceiling_cents) * 100) if ceiling_cents > 0 else 0

        # Check if threshold crossed
        threshold_type = None
        if percentage >= 100:
            threshold_type = "limit_reached"
        elif percentage >= 95:
            threshold_type = "threshold_95"
        elif percentage >= 80:
            threshold_type = "threshold_80"

        if threshold_type:
            # Check if we already alerted for this threshold this month
            existing_alert = self.db.query(BudgetAlert).filter(
                BudgetAlert.installation_id == installation_id,
                BudgetAlert.alert_type == threshold_type,
                BudgetAlert.monthly_spent_cents >= (ceiling_cents * 0.8),  # Same month
            ).first()
            if not existing_alert:
                alert = self._create_budget_alert(
                    installation=installation,
                    monthly_spent_cents=current_spent,
                    alert_type=threshold_type,
                    percentage=percentage,
                    action_taken=None,  # Will be set by handler
                )
                return alert

        return None

    def get_monthly_usage(
        self,
        tenant_id: str,
        month_year: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Get aggregated monthly usage for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            month_year: YYYY-MM format (default: current month)
        
        Returns:
            Dict with usage summary and per-installation breakdown
        """
        if not month_year:
            month_year = datetime.utcnow().strftime("%Y-%m")

        # Get total spend this month
        total_spent = self.db.query(func.sum(UsageEvent.cost_cents)).filter(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.month_year == month_year,
        ).scalar() or 0

        # Get by app
        by_app = self.db.query(
            UsageEvent.app_id,
            func.sum(UsageEvent.cost_cents).label("total"),
            func.count(UsageEvent.id).label("count"),
        ).filter(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.month_year == month_year,
        ).group_by(UsageEvent.app_id).all()

        # Get by kernel
        by_kernel = self.db.query(
            UsageEvent.kernel_id,
            func.sum(UsageEvent.cost_cents).label("total"),
            func.count(UsageEvent.id).label("count"),
        ).filter(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.month_year == month_year,
        ).group_by(UsageEvent.kernel_id).all()

        # Get installations and their ceilings
        installations = self.db.query(Installation).filter(
            Installation.tenant_id == tenant_id,
        ).all()

        installation_spend = {}
        for inst in installations:
            inst_spent = self.db.query(func.sum(UsageEvent.cost_cents)).filter(
                UsageEvent.installation_id == inst.id,
                UsageEvent.month_year == month_year,
            ).scalar() or 0
            percentage = int((inst_spent / inst.monthly_ceiling_cents) * 100) if inst.monthly_ceiling_cents > 0 else 0
            installation_spend[inst.id] = {
                "app_id": inst.app_id,
                "spent_cents": inst_spent,
                "ceiling_cents": inst.monthly_ceiling_cents,
                "percentage": percentage,
            }

        return {
            "month_year": month_year,
            "total_spent_cents": total_spent,
            "total_spent_usd": total_spent / 100,
            "by_app": [
                {
                    "app_id": app,
                    "spent_cents": total,
                    "spent_usd": total / 100,
                    "event_count": count,
                }
                for app, total, count in by_app
            ],
            "by_kernel": [
                {
                    "kernel_id": kernel,
                    "spent_cents": total,
                    "spent_usd": total / 100,
                    "event_count": count,
                }
                for kernel, total, count in by_kernel
            ],
            "installations": installation_spend,
        }

    def _create_budget_alert(
        self,
        installation: Installation,
        monthly_spent_cents: int,
        alert_type: str,
        percentage: int,
        action_taken: Optional[str] = None,
        action_details: Optional[str] = None,
    ) -> BudgetAlert:
        """Helper: Create a BudgetAlert record."""
        alert = BudgetAlert(
            id=str(uuid.uuid4()),
            tenant_id=installation.tenant_id,
            installation_id=installation.id,
            alert_type=alert_type,
            monthly_spent_cents=monthly_spent_cents,
            monthly_ceiling_cents=installation.monthly_ceiling_cents,
            percentage=percentage,
            action_taken=action_taken,
            action_details=action_details,
            created_at=datetime.utcnow(),
        )
        self.db.add(alert)
        self.db.commit()
        return alert
