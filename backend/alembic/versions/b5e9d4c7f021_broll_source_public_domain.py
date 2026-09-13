"""Extend broll_source enum with wikimedia and internet_archive values.

Revision ID: b5e9d4c7f021
Revises: a3f8c2d1e047
Create Date: 2026-09-11

Adds two public-domain/CC-licensed B-roll source providers to the
broll_source Postgres enum. Postgres requires ALTER TYPE ... ADD VALUE
for enum extensions; the operation is irreversible without dropping the
type, so downgrade drops any rows using the new values first (there will
be none in practice — this migration runs before any new sources are used).
"""

from __future__ import annotations

from alembic import op

revision = "b5e9d4c7f021"
down_revision = "a3f8c2d1e047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD VALUE is not transactional in Postgres — it cannot run inside a
    # transaction block. Alembic wraps migrations in transactions by default,
    # so we must disable that for this specific migration.
    op.execute("COMMIT")
    op.execute("ALTER TYPE broll_source ADD VALUE IF NOT EXISTS 'wikimedia'")
    op.execute("ALTER TYPE broll_source ADD VALUE IF NOT EXISTS 'internet_archive'")


def downgrade() -> None:
    # Postgres cannot remove enum values. The cleanest downgrade is to delete
    # any rows using the new values (there should be none if this was only
    # just applied) and recreate the enum without them. In practice, just
    # deleting rows is sufficient for personal-use.
    op.execute(
        "DELETE FROM broll_assets WHERE source IN ('wikimedia', 'internet_archive')"
    )
    # The enum type itself cannot be shrunk without dropping and recreating it,
    # which would cascade to the column. For safety we leave the type intact
    # (harmless extra values in an enum are non-breaking) and only clean up data.
