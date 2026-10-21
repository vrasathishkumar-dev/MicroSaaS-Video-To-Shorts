"""Add broll_placement to video_projects

Revision ID: f4a8b1c9d2e3
Revises: b5e9d4c7f021
Create Date: 2026-10-21 17:19:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f4a8b1c9d2e3"
down_revision: Union[str, Sequence[str], None] = "b5e9d4c7f021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use existing postgresql enum 'broll_placement'
    broll_placement_enum = postgresql.ENUM(
        "bottom_right", "top", "bottom", "split",
        name="broll_placement",
        create_type=False,
    )
    op.add_column(
        "video_projects",
        sa.Column(
            "broll_placement",
            broll_placement_enum,
            server_default="bottom",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("video_projects", "broll_placement")
