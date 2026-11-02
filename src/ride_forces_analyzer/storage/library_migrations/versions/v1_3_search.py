"""Populate Library search projections in the unreleased app 1.3 schema.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from alembic import op

from ride_forces_analyzer.storage.library_search import library_search_values

revision = "1_3_search"
down_revision = "1_3_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Backfill effective-name projections using only existing metadata columns."""
    connection = op.get_bind()
    rows = connection.exec_driver_sql(
        "SELECT source_sha256, COALESCE(ride_name_override, source_ride_name), "
        "COALESCE(park_name_override, source_park_name) FROM recordings",
    ).fetchall()
    for digest, ride, park in rows:
        connection.exec_driver_sql(
            "UPDATE recordings SET park_key=?, search_text=? WHERE source_sha256=?",
            (*library_search_values(ride, park), digest),
        )


def downgrade() -> None:
    """Reject automatic downgrades to preserve archived recordings.

    Raises:
        RuntimeError: Library schema downgrades are unsupported.
    """
    raise RuntimeError("Library schema downgrades are unsupported")
