"""Store one external video-file path per Library recording.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from alembic import op
import sqlalchemy as sa

revision = "2_1_video_file"
down_revision = "1_3_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add an optional path without modifying archived recording bytes."""
    op.add_column("recordings", sa.Column("video_file_path", sa.Text()))


def downgrade() -> None:
    """Reject schema downgrades to preserve saved Library data.

    Raises:
        RuntimeError: Library schema downgrades are unsupported.
    """
    raise RuntimeError("Library schema downgrades are unsupported")
