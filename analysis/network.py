"""Network relationship analysis — reply chains, co-posting, author interactions."""

from collections import Counter, defaultdict
from database.connection import get_backend, get_conn


async def get_reply_network(
    platform: str = None,
    board: str = None,
    limit: int = 100,
) -> dict:
    """Build a reply network from thread relationships.

    Returns nodes (authors) and edges (reply connections between authors
    who participate in the same threads).
    """
    backend = get_backend()

    if backend == "sqlite":
        where = ["thread_id IS NOT NULL", "author IS NOT NULL"]
        params = []
        if platform:
            where.append("platform = ?")
            params.append(platform)
        if board:
            where.append("board_or_feed = ?")
            params.append(board)
        where_sql = " AND ".join(where)

        async with get_conn() as conn:
            cur = await conn.execute(
                f"""SELECT thread_id, author, platform, board_or_feed
                    FROM posts
                    WHERE {where_sql}
                    ORDER BY posted_at DESC
                    LIMIT 5000""",
                params,
            )
            rows = await cur.fetchall()
    else:
        where = ["thread_id IS NOT NULL", "author IS NOT NULL"]
        params = []
        i = 1
        if platform:
            where.append(f"platform = ${i}")
            params.append(platform)
            i += 1
        if board:
            where.append(f"board_or_feed = ${i}")
            params.append(board)
            i += 1

        where_sql = " AND ".join(where)

        async with get_conn() as conn:
            rows = await conn.fetch(
                f"""SELECT thread_id, author, platform, board_or_feed
                    FROM posts
                    WHERE {where_sql}
                    ORDER BY posted_at DESC
                    LIMIT 5000""",
                *params,
            )

    # Group authors by thread
    thread_authors = defaultdict(set)
    author_platforms = {}
    author_post_counts = Counter()

    for row in rows:
        thread_id = row[0]
        author = row[1]
        plat = row[2]
        board_name = row[3]
        thread_authors[thread_id].add(author)
        author_platforms[author] = plat
        author_post_counts[author] += 1

    # Build edges: authors who co-occur in the same thread interact
    edge_weights = Counter()
    for thread_id, authors in thread_authors.items():
        authors_list = sorted(authors)
        for i in range(len(authors_list)):
            for j in range(i + 1, len(authors_list)):
                edge_key = (authors_list[i], authors_list[j])
                edge_weights[edge_key] += 1

    # Filter to top edges by weight
    top_edges = edge_weights.most_common(limit)

    # Collect all authors involved in top edges
    involved_authors = set()
    for (a, b), _ in top_edges:
        involved_authors.add(a)
        involved_authors.add(b)

    # Build node list
    nodes = []
    for author in involved_authors:
        nodes.append(
            {
                "id": author,
                "platform": author_platforms.get(author, "unknown"),
                "posts": author_post_counts.get(author, 0),
            }
        )

    # Build edge list
    edges = []
    for (source, target), weight in top_edges:
        edges.append(
            {
                "source": source,
                "target": target,
                "weight": weight,
            }
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "total_threads": len(thread_authors),
        "total_authors": len(author_post_counts),
    }


async def get_top_authors(
    platform: str = None,
    limit: int = 20,
) -> list[dict]:
    """Get most active authors with their thread participation stats."""
    backend = get_backend()

    if backend == "sqlite":
        where = ["author IS NOT NULL"]
        params = []
        if platform:
            where.append("platform = ?")
            params.append(platform)
        where_sql = " AND ".join(where) if where else "1=1"

        async with get_conn() as conn:
            cur = await conn.execute(
                f"""SELECT
                        author,
                        platform,
                        COUNT(*) as post_count,
                        COUNT(DISTINCT thread_id) as thread_count,
                        COUNT(DISTINCT board_or_feed) as board_count,
                        MIN(posted_at) as first_seen,
                        MAX(posted_at) as last_seen
                    FROM posts
                    WHERE {where_sql}
                    GROUP BY author, platform
                    ORDER BY post_count DESC
                    LIMIT ?""",
                params + [limit],
            )
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    where = ["author IS NOT NULL"]
    params = []
    i = 1
    if platform:
        where.append(f"platform = ${i}")
        params.append(platform)
        i += 1

    where_sql = " AND ".join(where) if where else "TRUE"

    async with get_conn() as conn:
        rows = await conn.fetch(
            f"""SELECT
                    author,
                    platform,
                    COUNT(*)::int as post_count,
                    COUNT(DISTINCT thread_id)::int as thread_count,
                    COUNT(DISTINCT board_or_feed)::int as board_count,
                    MIN(posted_at) as first_seen,
                    MAX(posted_at) as last_seen
                FROM posts
                WHERE {where_sql}
                GROUP BY author, platform
                ORDER BY post_count DESC
                LIMIT ${i}""",
            *params,
            limit,
        )
    return [dict(r) for r in rows]


async def get_thread_activity(
    platform: str = None,
    limit: int = 20,
) -> list[dict]:
    """Get most active threads with participant counts."""
    backend = get_backend()

    if backend == "sqlite":
        where = ["thread_id IS NOT NULL"]
        params = []
        if platform:
            where.append("platform = ?")
            params.append(platform)
        where_sql = " AND ".join(where) if where else "1=1"

        async with get_conn() as conn:
            cur = await conn.execute(
                f"""SELECT
                        thread_id,
                        platform,
                        board_or_feed,
                        COUNT(*) as reply_count,
                        COUNT(DISTINCT author) as participants,
                        MIN(posted_at) as started,
                        MAX(posted_at) as latest_reply
                    FROM posts
                    WHERE {where_sql}
                    GROUP BY thread_id, platform, board_or_feed
                    HAVING COUNT(*) > 1
                    ORDER BY reply_count DESC
                    LIMIT ?""",
                params + [limit],
            )
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    where = ["thread_id IS NOT NULL"]
    params = []
    i = 1
    if platform:
        where.append(f"platform = ${i}")
        params.append(platform)
        i += 1

    where_sql = " AND ".join(where) if where else "TRUE"

    async with get_conn() as conn:
        rows = await conn.fetch(
            f"""SELECT
                    thread_id,
                    platform,
                    board_or_feed,
                    COUNT(*)::int as reply_count,
                    COUNT(DISTINCT author)::int as participants,
                    MIN(posted_at) as started,
                    MAX(posted_at) as latest_reply
                FROM posts
                WHERE {where_sql}
                GROUP BY thread_id, platform, board_or_feed
                HAVING COUNT(*) > 1
                ORDER BY reply_count DESC
                LIMIT ${i}""",
            *params,
            limit,
        )
    return [dict(r) for r in rows]
