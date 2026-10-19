"""Add audit actor and computer context.

Revision ID: b3c7e91a4d20
Revises: 9a1b4c7d2e60
Create Date: 2026-10-19
"""

import sqlalchemy as sa

from alembic import op

revision: str = "b3c7e91a4d20"
down_revision: str | None = "9a1b4c7d2e60"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("actor_token_id", sa.String(length=36), nullable=True))
    op.add_column("audit_events", sa.Column("actor_type", sa.String(length=24), server_default="user", nullable=False))
    op.add_column("audit_events", sa.Column("computer_id", sa.String(length=36), nullable=True))
    op.add_column("audit_events", sa.Column("outcome", sa.String(length=24), server_default="success", nullable=False))
    op.add_column("audit_events", sa.Column("source_ip", sa.String(length=64), nullable=True))
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.create_foreign_key("fk_audit_events_actor_token", "api_tokens", ["actor_token_id"], ["id"], ondelete="SET NULL")
        batch_op.create_foreign_key("fk_audit_events_computer", "computers", ["computer_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_audit_events_computer_created", "audit_events", ["computer_id", "created_at"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_computer_created", table_name="audit_events")
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_constraint("fk_audit_events_computer", type_="foreignkey")
        batch_op.drop_constraint("fk_audit_events_actor_token", type_="foreignkey")
    op.drop_column("audit_events", "source_ip")
    op.drop_column("audit_events", "outcome")
    op.drop_column("audit_events", "computer_id")
    op.drop_column("audit_events", "actor_type")
    op.drop_column("audit_events", "actor_token_id")
