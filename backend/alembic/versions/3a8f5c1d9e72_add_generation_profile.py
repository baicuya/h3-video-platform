"""add generation profile

Revision ID: 3a8f5c1d9e72
Revises: 707a748fc7ac
Create Date: 2026-08-10 07:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3a8f5c1d9e72"
down_revision: Union[str, None] = "707a748fc7ac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "video_jobs",
        sa.Column(
            "generation_profile",
            sa.String(length=16),
            nullable=False,
            server_default="quality",
        ),
    )
    op.alter_column(
        "video_jobs",
        "generation_profile",
        server_default="turbo",
    )


def downgrade() -> None:
    op.drop_column("video_jobs", "generation_profile")
