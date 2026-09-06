"""clip broll placement

Adds `broll_placement` to clips -- the editor's choice of where B-roll
sits (a small bottom-right PIP card, a full-width top or bottom band, or
an even split-screen with the main video) instead of the single hardcoded
top-right PIP the renderer used before.

`bottom_right` is the server default so every existing clip keeps
rendering with a small corner card, the closest match to the old
hardcoded behaviour.

Hand-written for the same reason as the earlier migrations: no reachable
local Postgres to autogenerate against.

Revision ID: e276d71b9110
Revises: 2c98d61a2ef4
Create Date: 2026-09-06 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e276d71b9110"
down_revision: Union[str, Sequence[str], None] = "2c98d61a2ef4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    placement_enum = sa.Enum(
        "bottom_right", "top", "bottom", "split", name="broll_placement"
    )
    placement_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "clips",
        sa.Column(
            "broll_placement",
            placement_enum,
            nullable=False,
            server_default="bottom_right",
        ),
    )


def downgrade() -> None:
    op.drop_column("clips", "broll_placement")
    sa.Enum(name="broll_placement").drop(op.get_bind(), checkfirst=True)
