"""broll asset auto_generated flag

Adds `auto_generated` to broll_assets so a re-click of "Auto-insert B-roll"
can replace its own previous batch instead of piling duplicates on top of
it (auto_source_broll had no way to tell its own rows apart from ones the
user added manually via search, so every click just inserted another
batch on top of whatever was already there).

Server default `false` so every existing row -- auto-sourced or manual,
indistinguishable before this column existed -- is left alone rather than
risk deleting something a user added by hand.

Hand-written for the same reason as the earlier migrations: no reachable
local Postgres to autogenerate against.

Revision ID: 2c98d61a2ef4
Revises: d4a92c17e6b3
Create Date: 2026-09-05 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2c98d61a2ef4"
down_revision: Union[str, Sequence[str], None] = "d4a92c17e6b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "broll_assets",
        sa.Column(
            "auto_generated", sa.Boolean(), nullable=False, server_default="false"
        ),
    )


def downgrade() -> None:
    op.drop_column("broll_assets", "auto_generated")
