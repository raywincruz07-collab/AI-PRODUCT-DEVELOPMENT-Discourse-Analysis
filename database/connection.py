"""Database connection and initialization.

Supports two backends:
- PostgreSQL via asyncpg (preferred)
- SQLite via aiosqlite (fallback for easier local runs)

If configured for Postgres but the server is not reachable, the module will
automatically fall back to SQLite so the web app can still run.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging

import aiosqlite
import asyncpg

import config

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
_sqlite: aiosqlite.Connection | None = None
_backend_effective: str = config.DB_BACKEND


def get_backend() -> str:
    """Return the effective backend in use ("postgres" or "sqlite")."""
    return _backend_effective


def _set_backend(backend: str) -> None:
    global _backend_effective
    _backend_effective = backend


async def get_pool() -> asyncpg.Pool:
    """Get or create the database connection pool."""
    global _pool
    if _pool is None:
        try:
            # Small pool is enough for this app; avoids too many open connections.
            _pool = await asyncpg.create_pool(
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME,
                host=config.DB_HOST,
                port=config.DB_PORT,
                min_size=1,
                max_size=5,
                timeout=10,
            )
        except Exception as e:
            raise RuntimeError(
                "Cannot connect to PostgreSQL. "
                f"Host={config.DB_HOST} Port={config.DB_PORT} DB={config.DB_NAME} User={config.DB_USER}. "
                "Make sure PostgreSQL is installed and running, and your .env credentials are correct."
            ) from e
    return _pool


async def get_sqlite() -> aiosqlite.Connection:
    """Get or create a SQLite connection."""
    global _sqlite
    if _sqlite is None:
        _sqlite = await aiosqlite.connect(config.DB_PATH)
        _sqlite.row_factory = aiosqlite.Row
        # Better concurrency defaults
        await _sqlite.execute("PRAGMA journal_mode=WAL;")
        await _sqlite.execute("PRAGMA synchronous=NORMAL;")
        await _sqlite.execute("PRAGMA foreign_keys=ON;")
    return _sqlite


@asynccontextmanager
async def get_conn():
    """Get a connection for the configured backend.

    If Postgres is configured but unreachable, automatically fall back to SQLite.
    """
    global _backend_effective

    if _backend_effective == "sqlite":
        conn = await get_sqlite()
        yield conn
        return

    # Try Postgres
    try:
        pool = await get_pool()
        conn = await pool.acquire()
        try:
            yield conn
        finally:
            await pool.release(conn)
    except Exception as e:
        # One-time automatic fallback
        logger.warning(
            "PostgreSQL is not reachable (%s). Falling back to SQLite (%s).",
            e,
            config.DB_PATH,
        )
        _set_backend("sqlite")
        conn = await get_sqlite()
        yield conn


async def close_db():
    """Close the database connection pool."""
    global _pool, _sqlite
    if _pool is not None:
        await _pool.close()
        _pool = None
    if _sqlite is not None:
        await _sqlite.close()
        _sqlite = None


async def init_db():
    """Create tables and indexes if they don't exist."""
    async with get_conn() as conn:
        if get_backend() == "sqlite":
            await conn.executescript("""
                CREATE TABLE IF NOT EXISTS posts (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform      TEXT NOT NULL,
                    external_id   TEXT NOT NULL,
                    board_or_feed TEXT,
                    thread_id     TEXT,
                    author        TEXT,
                    content_raw   TEXT NOT NULL,
                    content_text  TEXT NOT NULL,
                    media_urls    TEXT,
                    posted_at     TEXT NOT NULL,
                    collected_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                    metadata_json TEXT,
                    likes         INTEGER DEFAULT 0,
                    replies       INTEGER DEFAULT 0,
                    shares        INTEGER DEFAULT 0,
                    UNIQUE(platform, external_id)
                );

                CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts(platform);
                CREATE INDEX IF NOT EXISTS idx_posts_posted_at ON posts(posted_at);
                CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author);
                CREATE INDEX IF NOT EXISTS idx_posts_board ON posts(board_or_feed);
                """)
            await conn.commit()
            return

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id              SERIAL PRIMARY KEY,
                platform        TEXT NOT NULL CHECK(platform IN ('4chan', 'mastodon', 'truthsocial')),
                external_id     TEXT NOT NULL,
                board_or_feed   TEXT,
                thread_id       TEXT,
                author          TEXT,
                content_raw     TEXT NOT NULL,
                content_text    TEXT NOT NULL,
                media_urls      JSONB,
                posted_at       TIMESTAMPTZ NOT NULL,
                collected_at    TIMESTAMPTZ DEFAULT NOW(),
                metadata_json   JSONB,
                likes           INTEGER DEFAULT 0,
                replies         INTEGER DEFAULT 0,
                shares          INTEGER DEFAULT 0,
                UNIQUE(platform, external_id)
            );

            CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts(platform);
            CREATE INDEX IF NOT EXISTS idx_posts_posted_at ON posts(posted_at);
            CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author);
            CREATE INDEX IF NOT EXISTS idx_posts_board ON posts(board_or_feed);

            -- If table was previously created with TIMESTAMP (no tz), upgrade it.
            DO $$
            BEGIN
                ALTER TABLE posts ALTER COLUMN posted_at TYPE TIMESTAMPTZ USING posted_at;
            EXCEPTION WHEN others THEN
                -- ignore if already correct or table doesn't exist yet
            END $$;

            ALTER TABLE posts ADD COLUMN IF NOT EXISTS content_tsvector TSVECTOR;
            CREATE INDEX IF NOT EXISTS content_tsvector_idx ON posts USING GIN(content_tsvector);

            CREATE OR REPLACE FUNCTION update_tsvector() RETURNS TRIGGER AS $$
            BEGIN
                NEW.content_tsvector := to_tsvector('english', COALESCE(NEW.content_text, ''));
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS tsvector_update ON posts;
            CREATE TRIGGER tsvector_update BEFORE INSERT OR UPDATE
            ON posts FOR EACH ROW EXECUTE PROCEDURE update_tsvector();
            """)
