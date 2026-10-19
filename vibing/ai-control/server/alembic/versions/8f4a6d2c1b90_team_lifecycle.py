"""Add team default roles and invitations.

Revision ID: 8f4a6d2c1b90
Revises: 7d2f9b3c4a11
Create Date: 2026-10-19
"""

import sqlalchemy as sa

from alembic import op

revision: str = "8f4a6d2c1b90"
down_revision: str | None = "7d2f9b3c4a11"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column(
            "default_member_role",
            sa.Enum("VIEWER", "OPERATOR", "OWNER", name="sharerole"),
            server_default="OPERATOR",
            nullable=False,
        ),
    )
    op.create_table(
        "team_invites",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("team_id", sa.String(length=36), nullable=False),
        sa.Column("invited_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_team_invites_token_hash", "team_invites", ["token_hash"], unique=True)
    op.create_index("ix_team_invites_team_id", "team_invites", ["team_id"])
    op.create_index("ix_team_invites_username", "team_invites", ["username"])


def downgrade() -> None:
    op.drop_index("ix_team_invites_username", table_name="team_invites")
    op.drop_index("ix_team_invites_team_id", table_name="team_invites")
    op.drop_index("ix_team_invites_token_hash", table_name="team_invites")
    op.drop_table("team_invites")
    op.drop_column("teams", "default_member_role")
