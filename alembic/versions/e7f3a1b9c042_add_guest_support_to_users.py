"""add guest support to users

Revision ID: e7f3a1b9c042
Revises: a1b2c3d4e5f6
Create Date: 2026-04-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7f3a1b9c042"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_guest",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "last_active_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_users_is_guest_last_active",
        "users",
        ["is_guest", "last_active_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_users_is_guest_last_active", table_name="users")
    op.drop_column("users", "last_active_at")
    op.drop_column("users", "is_guest")
