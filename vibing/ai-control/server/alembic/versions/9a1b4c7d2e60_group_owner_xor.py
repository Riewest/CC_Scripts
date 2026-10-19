"""Require exactly one control group owner.

Revision ID: 9a1b4c7d2e60
Revises: 8f4a6d2c1b90
Create Date: 2026-10-19
"""

from alembic import op

revision: str = "9a1b4c7d2e60"
down_revision: str | None = "8f4a6d2c1b90"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("groups") as batch_op:
        batch_op.create_check_constraint(
            "ck_group_exactly_one_owner",
            "(owner_user_id IS NOT NULL AND owner_team_id IS NULL) OR "
            "(owner_user_id IS NULL AND owner_team_id IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("groups") as batch_op:
        batch_op.drop_constraint("ck_group_exactly_one_owner", type_="check")
