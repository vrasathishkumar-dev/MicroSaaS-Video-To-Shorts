"""video project submission options

Adds what the submit form asks for -- target short length, framing,
caption style, and whether to auto-source B-roll -- to video_projects, so
the choices made at upload actually shape the shorts that come out.

`clip_framing` and `clip_caption_style` already exist as types from the
previous revision, so only `clip_length` is created here. Every column
carries a server default matching today's behaviour, leaving existing
projects untouched.

Hand-written for the same reason as the earlier migrations: no reachable
local Postgres to autogenerate against.

Revision ID: d4a92c17e6b3
Revises: c31f8a5d0b42
Create Date: 2026-09-01 00:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a92c17e6b3"
down_revision: Union[str, Sequence[str], None] = "c31f8a5d0b42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    clip_length_enum = sa.Enum("auto", "fast", "in_depth", name="clip_length")
    clip_length_enum.create(op.get_bind(), checkfirst=True)

    # Already created with the clips columns; referenced, not created.
    framing_enum = sa.Enum(
        "speaker_focus", "dynamic_blur", "fit", name="clip_framing", create_type=False
    )
    caption_style_enum = sa.Enum(
        "hormozi",
        "neon",
        "bold_box",
        "karaoke",
        "minimal",
        name="clip_caption_style",
        create_type=False,
    )

    op.add_column(
        "video_projects",
        sa.Column(
            "target_clip_length",
            clip_length_enum,
            nullable=False,
            server_default="auto",
        ),
    )
    op.add_column(
        "video_projects",
        sa.Column(
            "framing_mode",
            framing_enum,
            nullable=False,
            server_default="speaker_focus",
        ),
    )
    op.add_column(
        "video_projects",
        sa.Column(
            "caption_style",
            caption_style_enum,
            nullable=False,
            server_default="hormozi",
        ),
    )
    op.add_column(
        "video_projects",
        sa.Column("auto_broll", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("video_projects", "auto_broll")
    op.drop_column("video_projects", "caption_style")
    op.drop_column("video_projects", "framing_mode")
    op.drop_column("video_projects", "target_clip_length")
    sa.Enum(name="clip_length").drop(op.get_bind(), checkfirst=True)
