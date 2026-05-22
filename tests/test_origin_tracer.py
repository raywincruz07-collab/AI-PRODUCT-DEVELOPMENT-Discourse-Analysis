import pytest
import json
import os
import asyncio
from datetime import datetime, timezone, timedelta
from database.connection import get_conn, get_backend, init_db, close_db
from analysis.origin_tracer import trace_narrative_origin

# Set test DB path
import config
config.DB_PATH = "test_origin.db"
config.DB_BACKEND = "sqlite" # ensure sqlite for tests

@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup and teardown for each test."""
    # Reset backend state to force sqlite with new path
    from database import connection
    connection._sqlite = None
    connection._backend_effective = "sqlite"
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())
    yield
    loop.run_until_complete(close_db())
    loop.close()
    if os.path.exists("test_origin.db"):
        try: os.remove("test_origin.db")
        except: pass

@pytest.mark.asyncio
async def test_origin_tracer_basic():
    """Test basic narrative tracing logic."""
    backend = get_backend()
    now = datetime.now(timezone.utc)
    
    # Insert posts spread over 3 days across 2 platforms
    posts = [
        # Day 1 - Origin
        ("4chan", "ext1", "auth1", "pol", now - timedelta(days=2), "raw", "Target keyword first appearance", None, 15),
        # Day 2
        ("4chan", "ext2", "auth2", "news", now - timedelta(days=1), "raw", "Target keyword second post", None, 0),
        # Day 3
        ("mastodon", "ext3", "auth3", "fed1", now, "raw", "Target keyword spread to mastodon", json.dumps({"followers_count": 1000}), 0),
        ("mastodon", "ext4", "auth4", "fed1", now + timedelta(minutes=10), "raw", "Target keyword amplifier", json.dumps({"followers_count": 500}), 0),
    ]
    
    async with get_conn() as conn:
        for p in posts:
            if backend == "sqlite":
                await conn.execute(
                    "INSERT INTO posts (platform, external_id, author, board_or_feed, posted_at, content_raw, content_text, metadata_json, replies) VALUES (?,?,?,?,?,?,?,?,?)",
                    p
                )
            else:
                await conn.execute(
                    "INSERT INTO posts (platform, external_id, author, board_or_feed, posted_at, content_raw, content_text, metadata_json, replies) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
                    *p
                )
        await conn.commit()

    result = await trace_narrative_origin("Target")
    
    assert "error" not in result
    assert result["keyword"] == "Target"
    assert result["origin"]["author"] == "auth1"
    assert len(result["spread_timeline"]) == 2
    assert result["total_posts_found"] == 4
    assert result["direct_reach"] == 1500
    assert result["data_quality"] in ["Strong", "Moderate", "Limited"]

@pytest.mark.asyncio
async def test_origin_tracer_insufficient_data():
    """Test response when fewer than 3 posts are found."""
    backend = get_backend()
    async with get_conn() as conn:
        if backend == "sqlite":
            await conn.execute("INSERT INTO posts (platform, external_id, content_raw, content_text, posted_at) VALUES ('mastodon', 'ext1', 'raw', 'Target', '2024-01-01')")
        else:
            await conn.execute("INSERT INTO posts (platform, external_id, content_raw, content_text, posted_at) VALUES ($1, $2, $3, $4, $5)", "mastodon", "ext1", "raw", "Target", "2024-01-01")
        await conn.commit()

    result = await trace_narrative_origin("Target")
    assert result["error"] == "INSUFFICIENT DATA"

@pytest.mark.asyncio
async def test_origin_tracer_coordination():
    """Test coordination detection logic."""
    backend = get_backend()
    now = datetime.now(timezone.utc)
    
    # 3 non-anon posts within 90 mins
    posts = [
        ("mastodon", "ext10", "user1", "feed", now, "raw", "coordinated target", None, 0),
        ("mastodon", "ext11", "user2", "feed", now + timedelta(minutes=30), "raw", "coordinated target", None, 0),
        ("truthsocial", "ext12", "user3", "feed", now + timedelta(minutes=80), "raw", "coordinated target", None, 0),
    ]
    
    async with get_conn() as conn:
        for p in posts:
            if backend == "sqlite":
                await conn.execute("INSERT INTO posts (platform, external_id, author, board_or_feed, posted_at, content_raw, content_text, metadata_json, replies) VALUES (?,?,?,?,?,?,?,?,?)", p)
            else:
                await conn.execute("INSERT INTO posts (platform, external_id, author, board_or_feed, posted_at, content_raw, content_text, metadata_json, replies) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)", *p)
        await conn.commit()

    result = await trace_narrative_origin("coordinated")
    assert result["coordination_signal"] == "POSSIBLE COORDINATED AMPLIFICATION"
    assert result["coordination_window_minutes"] == 80

@pytest.mark.asyncio
async def test_origin_tracer_organic():
    """Test organic spread detection."""
    backend = get_backend()
    now = datetime.now(timezone.utc)
    
    # Posts spread over 3 days
    posts = [
        ("mastodon", "ext20", "user1", "feed", now, "raw", "organic target", None, 0),
        ("mastodon", "ext21", "user2", "feed", now + timedelta(days=1), "raw", "organic target", None, 0),
        ("truthsocial", "ext22", "user3", "feed", now + timedelta(days=2), "raw", "organic target", None, 0),
    ]
    
    async with get_conn() as conn:
        for p in posts:
            if backend == "sqlite":
                await conn.execute("INSERT INTO posts (platform, external_id, author, board_or_feed, posted_at, content_raw, content_text, metadata_json, replies) VALUES (?,?,?,?,?,?,?,?,?)", p)
            else:
                await conn.execute("INSERT INTO posts (platform, external_id, author, board_or_feed, posted_at, content_raw, content_text, metadata_json, replies) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)", *p)
        await conn.commit()

    result = await trace_narrative_origin("organic")
    assert result["coordination_signal"] == "ORGANIC SPREAD"

@pytest.mark.asyncio
async def test_origin_tracer_anon_filter():
    """Test that Anonymous 4chan authors are filtered from amplifiers."""
    backend = get_backend()
    now = datetime.now(timezone.utc)
    
    posts = [
        ("4chan", "ext30", "Anonymous", "pol", now, "raw", "anon target", None, 0),
        ("4chan", "ext31", "Anonymous", "pol", now + timedelta(minutes=5), "raw", "anon target", None, 0),
        ("4chan", "ext32", "Anonymous", "pol", now + timedelta(minutes=10), "raw", "anon target", None, 0),
        ("mastodon", "ext33", "realuser", "feed", now + timedelta(minutes=15), "raw", "anon target", None, 0),
    ]
    
    async with get_conn() as conn:
        for p in posts:
            if backend == "sqlite":
                await conn.execute("INSERT INTO posts (platform, external_id, author, board_or_feed, posted_at, content_raw, content_text, metadata_json, replies) VALUES (?,?,?,?,?,?,?,?,?)", p)
            else:
                await conn.execute("INSERT INTO posts (platform, external_id, author, board_or_feed, posted_at, content_raw, content_text, metadata_json, replies) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)", *p)
        await conn.commit()

    result = await trace_narrative_origin("anon")
    # Only realuser should be in amplifiers
    assert len(result["top_amplifiers"]) == 1
    assert result["top_amplifiers"][0]["author"] == "realuser"

