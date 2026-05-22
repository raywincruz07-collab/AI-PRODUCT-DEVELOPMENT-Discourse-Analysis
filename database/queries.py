"""Reusable database query functions.

Supports PostgreSQL (asyncpg) and SQLite (aiosqlite).

The app prefers Postgres, but will fall back to SQLite automatically when
Postgres is not installed/running.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from database.connection import get_backend, get_conn

logger = logging.getLogger(__name__)


def _parse_dt(value: Any) -> datetime:
    """Parse an ISO datetime string to a naive UTC-ish datetime.

    Posts can come with timezone offsets (e.g., 2024-01-01T10:00:00Z).
    We convert to datetime; asyncpg will handle tz-aware values too.
    """
    if value is None:
        raise ValueError("posted_at is required")
    if isinstance(value, datetime):
        return value
    # Handle trailing Z
    s = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(s)


async def insert_posts(posts: list[dict]) -> int:
    """Insert posts, ignoring duplicates. Returns count of newly inserted posts."""
    if not posts:
        return 0

    inserted = 0
    backend = get_backend()

    if backend == "sqlite":
        sql = """
        INSERT OR IGNORE INTO posts (
            platform, external_id, board_or_feed, thread_id, author,
            content_raw, content_text, media_urls, posted_at, metadata_json,
            likes, replies, shares
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """

        async with get_conn() as conn:
            for post in posts:
                try:
                    cur = await conn.execute(
                        sql,
                        (
                            post["platform"],
                            post["external_id"],
                            post.get("board_or_feed"),
                            post.get("thread_id"),
                            post.get("author"),
                            post.get("content_raw", ""),
                            post.get("content_text", ""),
                            json.dumps(post.get("media_urls", [])),
                            str(post.get("posted_at")),
                            json.dumps(post.get("metadata", {})),
                            int(post.get("likes", 0) or 0),
                            int(post.get("replies", 0) or 0),
                            int(post.get("shares", 0) or 0),
                        ),
                    )
                    if cur.rowcount and cur.rowcount > 0:
                        inserted += 1
                except Exception as e:
                    logger.debug(
                        f"insert_posts(sqlite): skipping post due to error: {e}"
                    )
                    continue
            await conn.commit()
        return inserted

    # Postgres
    sql = """
    INSERT INTO posts (
        platform, external_id, board_or_feed, thread_id, author,
        content_raw, content_text, media_urls, posted_at, metadata_json,
        likes, replies, shares
    )
    VALUES (
        $1,$2,$3,$4,$5,
        $6,$7,$8,$9,$10,
        $11,$12,$13
    )
    ON CONFLICT (platform, external_id) DO NOTHING
    """

    async with get_conn() as conn:
        for post in posts:
            try:
                result = await conn.execute(
                    sql,
                    post["platform"],
                    post["external_id"],
                    post.get("board_or_feed"),
                    post.get("thread_id"),
                    post.get("author"),
                    post.get("content_raw", ""),
                    post.get("content_text", ""),
                    json.dumps(post.get("media_urls", [])),
                    _parse_dt(post.get("posted_at")),
                    json.dumps(post.get("metadata", {})),
                    int(post.get("likes", 0) or 0),
                    int(post.get("replies", 0) or 0),
                    int(post.get("shares", 0) or 0),
                )
                # asyncpg returns e.g. "INSERT 0 1" when inserted, "INSERT 0 0" on conflict.
                if result.endswith(" 1"):
                    inserted += 1
            except Exception as e:
                logger.debug(f"insert_posts: skipping post due to error: {e}")
                continue
    return inserted


async def search_posts(
    query: str | None = None,
    platform: str | None = None,
    author: str | None = None,
    board: str | None = None,
    start: str | None = None,
    end: str | None = None,
    page: int = 1,
    limit: int = 50,
):
    """Search posts with filters. Returns (posts, total_count)."""
    offset = (page - 1) * limit
    backend = get_backend()

    if backend == "sqlite":
        where: list[str] = []
        params: list[Any] = []

        if query:
            for word in query.split():
                where.append("content_text LIKE ?")
                params.append(f"%{word}%")
        if platform:
            where.append("platform = ?")
            params.append(platform)
        if author:
            where.append("author = ?")
            params.append(author)
        if board:
            where.append("board_or_feed = ?")
            params.append(board)
        if start:
            where.append("posted_at >= ?")
            params.append(start)
        if end:
            where.append("posted_at <= ?")
            params.append(end)

        where_sql = " AND ".join(where) if where else "1=1"
        logger.info("search_posts SQL: WHERE %s | params: %s", where_sql, params)

        async with get_conn() as conn:
            cur = await conn.execute(
                f"SELECT COUNT(*) FROM posts WHERE {where_sql}", params
            )
            total_row = await cur.fetchone()
            total = int(total_row[0]) if total_row else 0

            cur = await conn.execute(
                f"""SELECT * FROM posts
                    WHERE {where_sql}
                    ORDER BY posted_at DESC
                    LIMIT ? OFFSET ?""",
                params + [limit, offset],
            )
            rows = await cur.fetchall()
            posts = [dict(r) for r in rows]
            return posts, total

    # Postgres
    where: list[str] = []
    params: list[Any] = []
    i = 1

    if query:
        for word in query.split():
            where.append(f"content_text ILIKE ${i}")
            params.append(f"%{word}%")
            i += 1
    if platform:
        where.append(f"platform = ${i}")
        params.append(platform)
        i += 1
    if author:
        where.append(f"author = ${i}")
        params.append(author)
        i += 1
    if board:
        where.append(f"board_or_feed = ${i}")
        params.append(board)
        i += 1
    if start:
        where.append(f"posted_at >= ${i}")
        params.append(_parse_dt(start))
        i += 1
    if end:
        where.append(f"posted_at <= ${i}")
        params.append(_parse_dt(end))
        i += 1

    where_sql = " AND ".join(where) if where else "TRUE"

    async with get_conn() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM posts WHERE {where_sql}", *params
        )

        rows = await conn.fetch(
            f"""
            SELECT *
            FROM posts
            WHERE {where_sql}
            ORDER BY posted_at DESC
            LIMIT ${i} OFFSET ${i + 1}
            """,
            *params,
            limit,
            offset,
        )

        posts = [dict(r) for r in rows]
        return posts, int(total or 0)


async def get_post_by_id(post_id: int):
    """Get a single post by ID."""
    backend = get_backend()
    async with get_conn() as conn:
        if backend == "sqlite":
            cur = await conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
            row = await cur.fetchone()
            return dict(row) if row else None
        row = await conn.fetchrow("SELECT * FROM posts WHERE id = $1", post_id)
        return dict(row) if row else None


async def get_stats():
    """Get collection statistics."""
    backend = get_backend()
    async with get_conn() as conn:
        if backend == "sqlite":
            cur = await conn.execute("""
                SELECT
                    platform,
                    COUNT(*) as total_posts,
                    COUNT(DISTINCT author) as unique_authors,
                    COUNT(DISTINCT board_or_feed) as boards,
                    MIN(posted_at) as earliest,
                    MAX(posted_at) as latest
                FROM posts
                GROUP BY platform
                ORDER BY platform
                """)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

        rows = await conn.fetch("""
            SELECT
                platform,
                COUNT(*) as total_posts,
                COUNT(DISTINCT author) as unique_authors,
                COUNT(DISTINCT board_or_feed) as boards,
                MIN(posted_at) as earliest,
                MAX(posted_at) as latest
            FROM posts
            GROUP BY platform
            ORDER BY platform
            """)
        return [dict(r) for r in rows]


def _period_expr(granularity: str) -> str:
    # Returned string is embedded in SQL; only allow known values.
    if granularity == "hour":
        return "date_trunc('hour', posted_at)"
    if granularity == "day":
        return "date_trunc('day', posted_at)"
    if granularity == "week":
        return "date_trunc('week', posted_at)"
    return "date_trunc('hour', posted_at)"


async def get_post_volume(
    platform: str | None = None,
    granularity: str = "hour",
    start: str | None = None,
    end: str | None = None,
):
    """Get post volume over time."""
    backend = get_backend()

    if backend == "sqlite":
        fmt_map = {"hour": "%Y-%m-%d %H:00", "day": "%Y-%m-%d", "week": "%Y-%W"}
        fmt = fmt_map.get(granularity, "%Y-%m-%d")
        where: list[str] = []
        params: list[Any] = []
        if platform:
            where.append("platform = ?")
            params.append(platform)
        if start:
            where.append("posted_at >= ?")
            params.append(start)
        if end:
            where.append("posted_at <= ?")
            params.append(end)
        where_sql = " AND ".join(where) if where else "1=1"

        async with get_conn() as conn:
            cur = await conn.execute(
                f"""
                SELECT strftime('{fmt}', posted_at) as period, COUNT(*) as count
                FROM posts
                WHERE {where_sql}
                GROUP BY period
                ORDER BY period
                """,
                params,
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    # Postgres
    period = _period_expr(granularity)

    where: list[str] = []
    params: list[Any] = []
    i = 1

    if platform:
        where.append(f"platform = ${i}")
        params.append(platform)
        i += 1
    if start:
        where.append(f"posted_at >= ${i}")
        params.append(_parse_dt(start))
        i += 1
    if end:
        where.append(f"posted_at <= ${i}")
        params.append(_parse_dt(end))
        i += 1

    where_sql = " AND ".join(where) if where else "TRUE"

    async with get_conn() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                {period} AS period,
                COUNT(*)::int AS count
            FROM posts
            WHERE {where_sql}
            GROUP BY period
            ORDER BY period
            """,
            *params,
        )

    # Convert datetime period to string for frontend
    out = []
    for r in rows:
        p = r["period"]
        out.append(
            {
                "period": p.isoformat(sep=" ") if isinstance(p, datetime) else str(p),
                "count": r["count"],
            }
        )
    return out


async def get_posts_for_export(
    platform: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = 50000,
):
    """Fetch all posts for export without pagination."""
    backend = get_backend()
    where: list[str] = []
    params: list[Any] = []

    if platform and platform.lower() != "all":
        where.append("platform = ?" if backend == "sqlite" else "platform = $1")
        params.append(platform)

    p_idx = len(params) + 1
    if start:
        where.append(
            "posted_at >= ?" if backend == "sqlite" else f"posted_at >= ${p_idx}"
        )
        params.append(start if backend == "sqlite" else _parse_dt(start))
        p_idx += 1
    if end:
        where.append(
            "posted_at <= ?" if backend == "sqlite" else f"posted_at <= ${p_idx}"
        )
        params.append(end if backend == "sqlite" else _parse_dt(end))
        p_idx += 1

    where_sql = " AND ".join(where) if where else ("1=1" if backend == "sqlite" else "TRUE")

    async with get_conn() as conn:
        if backend == "sqlite":
            cur = await conn.execute(
                f"SELECT * FROM posts WHERE {where_sql} ORDER BY posted_at DESC LIMIT ?",
                params + [limit],
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        else:
            rows = await conn.fetch(
                f"SELECT * FROM posts WHERE {where_sql} ORDER BY posted_at DESC LIMIT ${p_idx}",
                *params,
                limit,
            )
            return [dict(r) for r in rows]
