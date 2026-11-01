"""Run Library migrations on the transaction supplied by LibraryStore.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from alembic import context
from sqlalchemy.engine import Connection

connection = context.config.attributes["connection"]
if not isinstance(connection, Connection):
    raise TypeError("Library migrations require the application's connection")
context.configure(connection=connection, transactional_ddl=True)
with context.begin_transaction():
    context.run_migrations()
