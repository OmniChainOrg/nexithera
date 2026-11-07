"""add cogpm provisioning tables

Revision ID: 012
Revises: 011
Create Date: 2026-11-07 23:30:00.000000

Adds tables for Cognitive Package Manager (CogPM) installation lifecycle:
  * installations         -- app manifest submissions with state machine
  * deployments           -- per-kernel deployment records (epistemicos, synapticaos)
  * state_transitions     -- audit trail of state machine transitions

All statements are idempotent.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "installations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("manifest_name", sa.String(128), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("requested_by", sa.String(128), nullable=False),
        sa.Column("publisher_signature", sa.String(256), nullable=False),
        sa.Column("state", sa.Enum("PENDING_APPROVAL", "PROVISIONING", "ACTIVE", "FAILED", "ROLLING_BACK", name="installstate"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manifest_digest"),
    )
    op.create_index("ix_installations_tenant_id", "installations", ["tenant_id"])
    op.create_index("ix_installations_state", "installations", ["state"])

    op.create_table(
        "deployments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("installation_id", sa.String(36), nullable=False),
        sa.Column("kernel_name", sa.String(64), nullable=False),
        sa.Column("deployment_id", sa.String(256), nullable=False),
        sa.Column("linked_to", sa.String(256), nullable=True),
        sa.Column("provisioned_at", sa.DateTime(), nullable=False),
        sa.Column("deprovisioned_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["installation_id"], ["installations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deployments_installation_id", "deployments", ["installation_id"])

    op.create_table(
        "state_transitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("installation_id", sa.String(36), nullable=False),
        sa.Column("from_state", sa.Enum("PENDING_APPROVAL", "PROVISIONING", "ACTIVE", "FAILED", "ROLLING_BACK", name="installstate"), nullable=True),
        sa.Column("to_state", sa.Enum("PENDING_APPROVAL", "PROVISIONING", "ACTIVE", "FAILED", "ROLLING_BACK", name="installstate"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("transitioned_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["installation_id"], ["installations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_state_transitions_installation_id", "state_transitions", ["installation_id"])


def downgrade() -> None:
    op.drop_index("ix_state_transitions_installation_id", "state_transitions")
    op.drop_table("state_transitions")
    op.drop_index("ix_deployments_installation_id", "deployments")
    op.drop_table("deployments")
    op.drop_index("ix_installations_state", "installations")
    op.drop_index("ix_installations_tenant_id", "installations")
    op.drop_table("installations")
