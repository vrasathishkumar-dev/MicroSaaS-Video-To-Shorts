"""clip framing mode and caption style

Adds the two editor choices the export has to honour: how the clip fills
the 9:16 canvas, and which caption look burns in. Both carry a server
default so clips created before this migration keep rendering exactly as
they did (speaker focus, Hormozi captions).

Hand-written for the same reason as the initial migration: no reachable
local Postgres instance to run `alembic revision --autogenerate` against.

Revision ID: c31f8a5d0b42
Revises: be97e4a7ba79
Create Date: 2026-08-31 23:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c31f8a5d0b42"
down_revision: Union[str, Sequence[str], None] = "be97e4a7ba79"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    framing_enum = sa.Enum(
        "speaker_focus", "dynamic_blur", "fit", name="clip_framing"
    )
    caption_style_enum = sa.Enum(
        "hormozi", "neon", "bold_box", "karaoke", "minimal", name="clip_caption_style"
    )
    # create_type is a no-op outside Postgres; on Postgres the columns
    # below would otherwise fail on a type that doesn't exist yet.
    framing_enum.create(op.get_bind(), checkfirst=True)
    caption_style_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "clips",
        sa.Column(
            "framing_mode",
            framing_enum,
            nullable=False,
            server_default="speaker_focus",
        ),
    )
    op.add_column(
        "clips",
        sa.Column(
            "caption_style",
            caption_style_enum,
            nullable=False,
            server_default="hormozi",
        ),
    )


def downgrade() -> None:
    op.drop_column("clips", "caption_style")
    op.drop_column("clips", "framing_mode")
    sa.Enum(name="clip_caption_style").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="clip_framing").drop(op.get_bind(), checkfirst=True)
