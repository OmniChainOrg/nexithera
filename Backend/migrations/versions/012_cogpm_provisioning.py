"""create cogpm provisioning tables

Revision ID: 012_cogpm_provisioning
Revises: 011_*
Create Date: 2026-11-08 00:00:00.000000

Creates three tables for CogPM provisioning state machine:
1. cogpm_installations: Root aggregate for app installations
2. cogpm_deployments: Per-kernel deployment records (1 per kernel in manifest)
3. cogpm_state_transitions: Audit trail of all state changes

Foreign key relationships with CASCADE DELETE:
  Deployment.installation_id -> Installation.id
  StateTransition.installation_id -> Installation.id

Enums created:
  - install_state: PENDING_APPROVAL, PROVISIONING, ACTIVE, FAILED, ROLLING_BACK
  - deployment_state: PENDING, PROVISIONING, ACTIVE, FAILED

Indexes:
  - (tenant_id, state) for fast queries by tenant & current state
  - (requested_at) for timeline queries
  - (installation_id, kernel_id) for deployment lookups
  - (zone_id) for zone tracking
  - (installation_id, transitioned_at) for audit trail

Constraints:
  - monthly_ceiling_usd > 0 (positive spend ceiling)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '012_cogpm_provisioning'
down_revision = '011_*'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    install_state = postgresql.ENUM('pending_approval', 'provisioning', 'active', 'failed', 'rolling_back', name='install_state')
    deployment_state = postgresql.ENUM('pending', 'provisioning', 'active', 'failed', name='deployment_state')
    install_state.create(op.get_bind(), checkfirst=True)
    deployment_state.create(op.get_bind(), checkfirst=True)

    # Create installations table
    op.create_table(
        'cogpm_installations',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(255), nullable=False),
        sa.Column('app_id', sa.String(255), nullable=False),
        sa.Column('app_version', sa.String(20), nullable=False),
        sa.Column('state', sa.Enum('pending_approval', 'provisioning', 'active', 'failed', 'rolling_back', name='install_state'), nullable=False),
        sa.Column('requested_by', sa.String(255), nullable=False),
        sa.Column('approved_by', sa.String(255), nullable=True),
        sa.Column('requested_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('approved_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('manifest_hash', sa.String(64), nullable=False),
        sa.Column('spend_policy', sa.String(20), nullable=False),
        sa.Column('monthly_ceiling_cents', sa.Integer, nullable=False),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('metadata', sa.Text, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_tenant_id_state', 'tenant_id', 'state'),
        sa.Index('idx_requested_at', 'requested_at'),
        sa.CheckConstraint('monthly_ceiling_cents > 0', name='ck_ceiling_positive'),
    )

    # Create deployments table
    op.create_table(
        'cogpm_deployments',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('installation_id', sa.String(36), nullable=False),
        sa.Column('kernel_id', sa.String(20), nullable=False),
        sa.Column('kernel_version', sa.String(20), nullable=False),
        sa.Column('state', sa.Enum('pending', 'provisioning', 'active', 'failed', name='deployment_state'), nullable=False),
        sa.Column('zone_id', sa.String(255), nullable=True),
        sa.Column('swarm_id', sa.String(255), nullable=True),
        sa.Column('linked_to', sa.String(36), nullable=True),
        sa.Column('provisioned_at', sa.DateTime, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('metadata', sa.Text, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['installation_id'], ['cogpm_installations.id'], ondelete='CASCADE'),
        sa.Index('idx_installation_kernel', 'installation_id', 'kernel_id'),
        sa.Index('idx_zone_id', 'zone_id'),
    )

    # Create state_transitions table
    op.create_table(
        'cogpm_state_transitions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('installation_id', sa.String(36), nullable=False),
        sa.Column('from_state', sa.Enum('pending_approval', 'provisioning', 'active', 'failed', 'rolling_back', name='install_state'), nullable=False),
        sa.Column('to_state', sa.Enum('pending_approval', 'provisioning', 'active', 'failed', 'rolling_back', name='install_state'), nullable=False),
        sa.Column('triggered_by', sa.String(255), nullable=False),
        sa.Column('reason', sa.Text, nullable=True),
        sa.Column('transitioned_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['installation_id'], ['cogpm_installations.id'], ondelete='CASCADE'),
        sa.Index('idx_installation_transitioned_at', 'installation_id', 'transitioned_at'),
    )


def downgrade() -> None:
    # Drop tables in reverse order (respecting FK constraints)
    op.drop_table('cogpm_state_transitions')
    op.drop_table('cogpm_deployments')
    op.drop_table('cogpm_installations')

    # Drop enum types
    sa.Enum(name='deployment_state').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='install_state').drop(op.get_bind(), checkfirst=True)
