"""Create the initial Library schema introduced with app version 1.3.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words sqlalchemy DESC

from alembic import op
import sqlalchemy as sa

revision = "1_3"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Library tables, relationships, scalar constraints and query indexes."""
    op.create_table(
        "recordings",
        sa.Column("source_sha256", sa.Text(), primary_key=True, nullable=False),
        sa.Column("source_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("source_filename", sa.Text(), nullable=False),
        sa.Column("source_format", sa.Text(), nullable=False),
        sa.Column("source_byte_count", sa.Integer(), nullable=False),
        sa.Column("source_ride_name", sa.Text()),
        sa.Column("source_park_name", sa.Text()),
        sa.Column("recorded_at_utc", sa.Text()),
        sa.Column("recorded_day", sa.Text()),
        sa.Column("day_timezone", sa.Text()),
        sa.Column("imported_at_utc", sa.Text(), nullable=False),
        sa.Column("first_sample", sa.Integer(), nullable=False),
        sa.Column("last_sample", sa.Integer(), nullable=False),
        sa.Column("gravity_index", sa.Integer()),
        sa.Column("incline_index", sa.Integer()),
        sa.Column("calibration_algorithm_version", sa.Text(), nullable=False),
        sa.Column("calibration_window_samples", sa.Integer(), nullable=False),
        sa.Column("ride_name_override", sa.Text()),
        sa.Column("park_name_override", sa.Text()),
        sa.Column("row_override", sa.Text()),
        sa.Column("seat_override", sa.Text()),
        sa.Column("train_override", sa.Text()),
        sa.Column("riding_position_override", sa.Text()),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("workflow_status", sa.Text(), nullable=False, server_default="imported"),
        sa.Column("park_key", sa.Text()),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "length(source_sha256) = 64 AND source_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="ck_recordings_digest",
        ),
        sa.CheckConstraint("source_format IN ('forces', 'zforces')", name="ck_recordings_format"),
        sa.CheckConstraint(
            "source_byte_count >= 0 AND source_byte_count = length(source_bytes)",
            name="ck_recordings_bytes",
        ),
        sa.CheckConstraint(
            "first_sample >= 0 AND last_sample >= first_sample "
            "AND (gravity_index IS NULL OR gravity_index >= 0) "
            "AND (incline_index IS NULL OR incline_index >= 0) "
            "AND calibration_window_samples > 0",
            name="ck_recordings_markers",
        ),
        sa.CheckConstraint(
            "riding_position_override IS NULL OR riding_position_override IN ('Seated', 'Flying')",
            name="ck_recordings_position",
        ),
        sa.CheckConstraint(
            "workflow_status IN ('imported', 'markers_verified', 'overlays_created', "
            "'video_ready', 'uploaded', 'completed')",
            name="ck_recordings_workflow",
        ),
    )
    op.create_table(
        "export_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recording_sha256",
            sa.Text(),
            sa.ForeignKey("recordings.source_sha256"),
            nullable=False,
        ),
        sa.Column("export_kind", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("started_at_utc", sa.Text(), nullable=False),
        sa.Column("finished_at_utc", sa.Text()),
        sa.Column("duration_seconds", sa.Float()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("application_version", sa.Text(), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("export_snapshot_json", sa.Text()),
        sa.Column("output_path", sa.Text()),
        sa.Column("file_size_bytes", sa.Integer()),
        sa.Column("gpu_encoding", sa.Integer()),
        sa.Column("error", sa.Text()),
        sa.CheckConstraint(
            "export_kind IN ('video', 'csv', 'json', 'analyzer_json')",
            name="ck_export_history_kind",
        ),
        sa.CheckConstraint("origin IN ('single', 'batch')", name="ck_export_history_origin"),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled', 'interrupted')",
            name="ck_export_history_status",
        ),
        sa.CheckConstraint(
            "(duration_seconds IS NULL OR duration_seconds >= 0) "
            "AND (file_size_bytes IS NULL OR file_size_bytes >= 0) "
            "AND (gpu_encoding IS NULL OR gpu_encoding IN (0, 1))",
            name="ck_export_history_results",
        ),
    )
    op.create_table(
        "video_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recording_sha256",
            sa.Text(),
            sa.ForeignKey("recordings.source_sha256"),
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index(
        "idx_recordings_day",
        "recordings",
        [
            sa.text("recorded_day DESC"),
            sa.text("recorded_at_utc DESC"),
            sa.text("imported_at_utc DESC"),
            "source_sha256",
        ],
    )
    op.create_index(
        "idx_recordings_park_day",
        "recordings",
        [
            "park_key",
            sa.text("recorded_day DESC"),
            sa.text("recorded_at_utc DESC"),
            sa.text("imported_at_utc DESC"),
            "source_sha256",
        ],
    )
    op.create_index(
        "idx_export_history_recording",
        "export_history",
        ["recording_sha256", sa.text("started_at_utc DESC"), sa.text("id DESC")],
    )
    op.create_index("idx_video_links_recording", "video_links", ["recording_sha256", "id"])


def downgrade() -> None:
    """Reject automatic downgrades to preserve the Library's archived data.

    Raises:
        RuntimeError: Library schema downgrades are unsupported.
    """
    raise RuntimeError("Library schema downgrades are unsupported")
