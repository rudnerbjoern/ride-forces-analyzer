"""Identify recordings across exports in the unreleased app 1.3 schema.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from alembic import op
import sqlalchemy as sa

from ride_forces_analyzer.importers import ImportSuccess, import_forces_bytes
from ride_forces_analyzer.importers.library_metadata import recording_uuid

revision = "1_3_identity"
down_revision = "1_3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Backfill UUIDs and merge existing duplicates into their earliest archive entry.

    The earliest entry retains its original bytes and Library choices; all export
    history and video links are reassigned before removing later duplicate rows.
    """
    op.add_column("recordings", sa.Column("source_uuid", sa.Text()))
    connection = op.get_bind()
    rows = connection.exec_driver_sql(
        "SELECT source_sha256, source_format FROM recordings "
        "ORDER BY imported_at_utc, source_sha256",
    ).fetchall()
    identities: dict[str, str] = {}
    for digest, source_format in rows:
        data = connection.exec_driver_sql(
            "SELECT source_bytes FROM recordings WHERE source_sha256=?",
            (digest,),
        ).scalar_one()
        source = import_forces_bytes(data, compressed=source_format == "zforces")
        if not isinstance(source, ImportSuccess):
            continue
        identity = recording_uuid(source.recording)
        if identity is None:
            continue
        previous = identities.get(identity)
        if previous is None:
            identities[identity] = digest
            connection.exec_driver_sql(
                "UPDATE recordings SET source_uuid=? WHERE source_sha256=?",
                (identity, digest),
            )
        else:
            for table in ("export_history", "video_links"):
                connection.exec_driver_sql(
                    f"UPDATE {table} SET recording_sha256=? WHERE recording_sha256=?",
                    (previous, digest),
                )
            connection.exec_driver_sql("DELETE FROM recordings WHERE source_sha256=?", (digest,))
    op.create_index("idx_recordings_uuid", "recordings", ["source_uuid"], unique=True)


def downgrade() -> None:
    """Reject automatic downgrades to preserve archived recordings.

    Raises:
        RuntimeError: Library schema downgrades are unsupported.
    """
    raise RuntimeError("Library schema downgrades are unsupported")
