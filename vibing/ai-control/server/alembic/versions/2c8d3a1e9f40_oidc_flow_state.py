"""Persist short-lived OIDC state and PKCE data.

Revision ID: 2c8d3a1e9f40
Revises: 85da299674ca
Create Date: 2026-10-19
"""

import sqlalchemy as sa

from alembic import op

revision: str = "2c8d3a1e9f40"
down_revision: str | None = "85da299674ca"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "oidc_flows",
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("browser_hash", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("code_verifier", sa.String(length=128), nullable=False),
        sa.Column("link_user_id", sa.String(length=36), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["link_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("state_hash"),
    )
    op.create_index("ix_oidc_flows_expires_at", "oidc_flows", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_oidc_flows_expires_at", table_name="oidc_flows")
    op.drop_table("oidc_flows")
