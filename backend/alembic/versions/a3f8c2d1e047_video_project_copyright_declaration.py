"""Add copyright_declaration column to video_projects.

Revision ID: a3f8c2d1e047
Revises: 16715379e79b
Create Date: 2026-09-11

Adds a self-declared copyright basis field to every video project.
Nullable with no server default so pre-existing rows stay NULL rather
than being assigned a declaration the submitter never made.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a3f8c2d1e047"
down_revision = "16715379e79b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the enum type first, then the column.
    copyright_declaration_enum = sa.Enum(
        "own_content",
        "licensed",
        "public_domain",
        "fair_use",
        name="copyright_declaration",
    )
    copyright_declaration_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "video_projects",
        sa.Column(
            "copyright_declaration",
            sa.Enum(
                "own_content",
                "licensed",
                "public_domain",
                "fair_use",
                name="copyright_declaration",
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("video_projects", "copyright_declaration")
    op.execute("DROP TYPE IF EXISTS copyright_declaration")
