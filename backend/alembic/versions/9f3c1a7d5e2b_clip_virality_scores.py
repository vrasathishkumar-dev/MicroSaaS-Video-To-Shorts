"""clip virality scores

Adds real, server-computed scoring fields to `clips`, replacing the
frontend-only fake score (`computeViralityInsights()` in
`frontend/src/lib/virality.ts`) with columns the backend scoring service
(separate story work, not this migration) populates:

- `virality_score` (0-100 final score)
- `hook_score` (hook-strength sub-score)
- `completeness_score` (sentence-boundary sub-score; net-new column -- there
  is no live `engagement_score` column in this table to rename, the
  frontend's dead `engagement_score` field was never backed by a database
  column)
- `framing_score` (pass/fail speaker-framing signal: null = not yet
  checked, 0.0 = checked/no confident subject, 1.0 = checked/confident
  subject -- see `app/models/clip.py`'s Clip model docstring)
- `virality_reason` (short string naming the actual weak/strong sub-signals)

All five are nullable with no `server_default` -- NULL is the correct,
intentional state for every pre-migration row (backfilling a fake value
would repeat the exact problem this story exists to fix) and for any
newly-created row until the scoring service runs. No index: nothing reads
these columns via a WHERE/ORDER BY today, only per-clip display.

Hand-written for the same reason as the prior migrations in this repo: no
reachable local Postgres to autogenerate against.

Revision ID: 9f3c1a7d5e2b
Revises: e276d71b9110
Create Date: 2026-09-06 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f3c1a7d5e2b"
down_revision: Union[str, Sequence[str], None] = "e276d71b9110"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clips", sa.Column("virality_score", sa.Float(), nullable=True))
    op.add_column("clips", sa.Column("hook_score", sa.Float(), nullable=True))
    op.add_column("clips", sa.Column("completeness_score", sa.Float(), nullable=True))
    op.add_column("clips", sa.Column("framing_score", sa.Float(), nullable=True))
    op.add_column("clips", sa.Column("virality_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("clips", "virality_reason")
    op.drop_column("clips", "framing_score")
    op.drop_column("clips", "completeness_score")
    op.drop_column("clips", "hook_score")
    op.drop_column("clips", "virality_score")
