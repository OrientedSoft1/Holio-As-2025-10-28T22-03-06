"""Database connection helper."""

import os
import asyncpg


async def get_db_connection():
    """Get database connection."""
    return await asyncpg.connect(os.environ.get("DATABASE_URL"))
