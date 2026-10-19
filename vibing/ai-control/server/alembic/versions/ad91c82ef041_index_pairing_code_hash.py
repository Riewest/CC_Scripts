"""Index hashed pairing codes for lookup.

Revision ID: ad91c82ef041
Revises: 9f56e595c85a
Create Date: 2026-10-18
"""

from alembic import op

revision: str = "ad91c82ef041"
down_revision: str | None = "9f56e595c85a"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_index(
        "ix_pairing_codes_code_hash",
        "pairing_codes",
        ["code_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_pairing_codes_code_hash", table_name="pairing_codes")
