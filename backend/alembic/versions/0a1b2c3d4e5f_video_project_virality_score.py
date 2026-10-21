"""Add virality_score to video_projects

Revision ID: 0a1b2c3d4e5f
Revises: f4a8b1c9d2e3
Create Date: 2026-10-21 21:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "f4a8b1c9d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "video_projects",
        sa.Column("virality_score", sa.Float(), nullable=True),
    )
    # Backfill virality_score from existing clips
    op.execute(
        """
        UPDATE video_projects vp
        SET virality_score = sub.max_score
        FROM (
            SELECT video_project_id, MAX(virality_score) AS max_score
            FROM clips
            WHERE virality_score IS NOT NULL
            GROUP BY video_project_id
        ) sub
        WHERE vp.id = sub.video_project_id;
        """
    )
    # Backfill virality_score from transcript segments for projects with no clips yet
    op.execute(
        """
        UPDATE video_projects vp
        SET virality_score = ROUND((sub.max_score * 100)::numeric, 1)::float
        FROM (
            SELECT video_project_id, MAX(highlight_score) AS max_score
            FROM transcript_segments
            WHERE highlight_score IS NOT NULL
            GROUP BY video_project_id
        ) sub
        WHERE vp.id = sub.video_project_id AND vp.virality_score IS NULL;
        """
    )


def downgrade() -> None:
    op.drop_column("video_projects", "virality_score")
