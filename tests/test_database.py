"""Tests for database operations."""

"""Tests for database operations.

NOTE: These tests were originally written for SQLite. The project now uses
PostgreSQL (asyncpg). To run these tests you need a running Postgres instance
and a test database configured via environment variables.
"""

import asyncio
import pytest

from database.connection import init_db, close_db
from database.queries import insert_posts, search_posts, get_stats, get_post_volume


@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup and teardown test database."""
    loop = asyncio.new_event_loop()
    loop.run_until_complete(init_db())
    yield loop
    loop.run_until_complete(close_db())
    loop.close()


def test_init_db(setup_teardown):
    """DB init sanity check."""
    # If init_db() didn't raise, schema creation worked.
    assert setup_teardown is not None


def test_insert_and_search(setup_teardown):
    """Test inserting posts and searching them."""
    loop = setup_teardown

    async def _test():
        posts = [
            {
                "platform": "4chan",
                "external_id": "pol-12345",
                "board_or_feed": "pol",
                "thread_id": "12340",
                "author": "Anonymous",
                "content_raw": "<p>Test post about immigration policy</p>",
                "content_text": "Test post about immigration policy",
                "media_urls": [],
                "posted_at": "2024-01-15T10:00:00",
                "metadata": {"post_no": 12345},
            },
            {
                "platform": "truthsocial",
                "external_id": "ts-67890",
                "board_or_feed": "public_timeline",
                "author": "testuser",
                "content_raw": "<p>Discussion about economy trends</p>",
                "content_text": "Discussion about economy trends",
                "media_urls": [],
                "posted_at": "2024-01-15T11:00:00",
                "metadata": {},
            },
        ]

        count = await insert_posts(posts)
        assert count >= 1

        # Search by keyword
        results, total = await search_posts(query="immigration")
        assert total >= 1
        assert any("immigration" in p["content_text"] for p in results)

        # Search by platform
        results, total = await search_posts(platform="4chan")
        assert total >= 1
        assert all(p["platform"] == "4chan" for p in results)

        # Stats
        stats = await get_stats()
        assert len(stats) >= 1

    loop.run_until_complete(_test())


def test_duplicate_handling(setup_teardown):
    """Test that duplicate posts are ignored."""
    loop = setup_teardown

    async def _test():
        post = {
            "platform": "4chan",
            "external_id": "pol-99999",
            "board_or_feed": "pol",
            "author": "Anonymous",
            "content_raw": "Duplicate test",
            "content_text": "Duplicate test",
            "posted_at": "2024-01-15T12:00:00",
        }

        count1 = await insert_posts([post])
        count2 = await insert_posts([post])
        # Second insert should not increase count (duplicate ignored)
        results, total = await search_posts(query="Duplicate")
        assert total == 1

    loop.run_until_complete(_test())
