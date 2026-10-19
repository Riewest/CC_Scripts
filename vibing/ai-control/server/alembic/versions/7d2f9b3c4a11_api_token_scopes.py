"""Add API token scopes and resource restrictions.

Revision ID: 7d2f9b3c4a11
Revises: 2c8d3a1e9f40
Create Date: 2026-10-19
"""

import sqlalchemy as sa

from alembic import op

revision: str = "7d2f9b3c4a11"
down_revision: str | None = "2c8d3a1e9f40"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("api_tokens", sa.Column("last_used_ip", sa.String(length=64), nullable=True))
    op.add_column("api_tokens", sa.Column("token_prefix", sa.String(length=16), nullable=True))
    op.add_column("api_tokens", sa.Column("scopes", sa.JSON(), nullable=True))
    op.add_column("api_tokens", sa.Column("computer_ids", sa.JSON(), nullable=True))
    op.add_column("api_tokens", sa.Column("group_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("api_tokens", "group_ids")
    op.drop_column("api_tokens", "computer_ids")
    op.drop_column("api_tokens", "scopes")
    op.drop_column("api_tokens", "token_prefix")
    op.drop_column("api_tokens", "last_used_ip")
