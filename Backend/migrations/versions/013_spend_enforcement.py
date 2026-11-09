"""create spend tracking and budget alerts

Revision ID: 013_spend_enforcement
Revises: 012_cogpm_provisioning
Create Date: 2026-11-08 00:00:00.000000

Creates two tables for spend tracking and budget enforcement:
1. cogpm_usage_events: Real-time usage event recording
   - Tracks every resource consumption (zone, swarm, inference, storage)
   - Cost in cents, with billing category and operation type
   - Indexed by tenant, month_year for efficient monthly aggregation

2. cogpm_budget_alerts: Budget threshold alerts
   - Tracks when tenants hit 80%, 95%, 100%, and overage
   - Records action taken (hard_stop: reject, reservation: flag, controlled_overage: allow+notify)
   - Indexed by tenant and alert type for efficient retrieval

Foreign key relationships with CASCADE DELETE:
  UsageEvent.installation_id -> Installation.id
  BudgetAlert.installation_id -> Installation.id
"""

from alembic import op
import sqlalchemy as sa


revision = '013_spend_enforcement'
down_revision = '012_cogpm_provisioning'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create usage_events table
    op.create_table(
        'cogpm_usage_events',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(255), nullable=False),
        sa.Column('installation_id', sa.String(36), nullable=False),
        sa.Column('app_id', sa.String(255), nullable=False),
        sa.Column('kernel_id', sa.String(20), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.String(255), nullable=True),
        sa.Column('cost_cents', sa.Integer, nullable=False),
        sa.Column('billing_category', sa.String(50), nullable=False),
        sa.Column('operation', sa.String(100), nullable=False),
        sa.Column('metadata', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('month_year', sa.String(7), nullable=False),
        sa.Column('billed', sa.String(20), nullable=False, server_default='pending'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['installation_id'], ['cogpm_installations.id'], ondelete='CASCADE'),
        sa.Index('idx_tenant_month', 'tenant_id', 'month_year'),
        sa.Index('idx_tenant_created_at', 'tenant_id', 'created_at'),
        sa.Index('idx_installation_id', 'installation_id'),
        sa.Index('idx_kernel_resource', 'kernel_id', 'resource_type'),
    )

    # Create budget_alerts table
    op.create_table(
        'cogpm_budget_alerts',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(255), nullable=False),
        sa.Column('installation_id', sa.String(36), nullable=False),
        sa.Column('alert_type', sa.String(50), nullable=False),
        sa.Column('monthly_spent_cents', sa.Integer, nullable=False),
        sa.Column('monthly_ceiling_cents', sa.Integer, nullable=False),
        sa.Column('percentage', sa.Integer, nullable=False),
        sa.Column('action_taken', sa.String(100), nullable=True),
        sa.Column('action_details', sa.Text, nullable=True),
        sa.Column('resolved', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('acknowledged_at', sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['installation_id'], ['cogpm_installations.id'], ondelete='CASCADE'),
        sa.Index('idx_tenant_alert_type', 'tenant_id', 'alert_type'),
        sa.Index('idx_created_at', 'created_at'),
    )


def downgrade() -> None:
    op.drop_table('cogpm_budget_alerts')
    op.drop_table('cogpm_usage_events')
