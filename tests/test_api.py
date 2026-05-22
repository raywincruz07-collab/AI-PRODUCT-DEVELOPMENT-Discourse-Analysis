"""Tests for FastAPI endpoints."""

import asyncio
import os
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from api.main import app
from database.connection import init_db, close_db
from database.queries import insert_posts

client = TestClient(app, raise_server_exceptions=False)


class TestStandardAPI:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup test database with sample data."""
        os.environ["DB_PATH"] = "test_discourse.db"
        loop = asyncio.new_event_loop()

        async def setup():
            await init_db()
            await insert_posts([
                {
                    "platform": "4chan",
                    "external_id": "pol-11111",
                    "board_or_feed": "pol",
                    "author": "Anonymous",
                    "content_raw": "Discussion about immigration reform",
                    "content_text": "Discussion about immigration reform",
                    "posted_at": "2024-01-15T10:00:00",
                },
                {
                    "platform": "mastodon",
                    "external_id": "masto-22222",
                    "board_or_feed": "public_timeline",
                    "author": "user1",
                    "content_raw": "Economy is looking strong",
                    "content_text": "Economy is looking strong",
                    "posted_at": "2024-01-15T11:00:00",
                },
            ])

        loop.run_until_complete(setup())
        yield
        loop.run_until_complete(close_db())
        loop.close()
        if os.path.exists("test_discourse.db"):
            os.remove("test_discourse.db")

    def test_get_posts(self):
        """Test listing posts."""
        response = client.get("/api/posts")
        assert response.status_code == 200
        data = response.json()
        assert "posts" in data
        assert "total" in data

    def test_search_posts(self):
        """Test keyword search."""
        response = client.get("/api/posts?keyword=immigration")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 0

    def test_filter_by_platform(self):
        """Test platform filtering."""
        response = client.get("/api/posts?platform=4chan")
        assert response.status_code == 200
        data = response.json()
        for post in data["posts"]:
            assert post["platform"] == "4chan"

    def test_stats(self):
        """Test stats endpoint."""
        response = client.get("/api/stats")
        assert response.status_code == 200

    def test_trends_volume(self):
        """Test post volume endpoint."""
        response = client.get("/api/trends/volume?granularity=day")
        assert response.status_code == 200

    def test_top_keywords(self):
        """Test top keywords endpoint."""
        response = client.get("/api/keywords/top?n=10")
        assert response.status_code == 200

    def test_keyword_frequency(self):
        """Test keyword frequency endpoint."""
        response = client.get("/api/keywords/frequency?keyword=test")
        assert response.status_code == 200

    def test_cooccurrence(self):
        """Test narrative co-occurrence endpoint."""
        response = client.get("/api/narratives/cooccurrence?keyword=test")
        assert response.status_code == 200
        data = response.json()
        assert "seed_keyword" in data
        assert "co_occurring" in data

    def test_compare_narratives(self):
        """Test platform comparison endpoint."""
        response = client.get("/api/narratives/compare?keyword=test")
        assert response.status_code == 200
        data = response.json()
        assert "4chan" in data
        assert "mastodon" in data

    def test_network_graph(self):
        """Test network graph endpoint."""
        response = client.get("/api/network/graph")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert "total_threads" in data

    def test_network_authors(self):
        """Test top authors endpoint."""
        response = client.get("/api/network/authors")
        assert response.status_code == 200

    def test_network_threads(self):
        """Test active threads endpoint."""
        response = client.get("/api/network/threads")
        assert response.status_code == 200


class TestVelocityAPI:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        os.environ["DB_PATH"] = "test_velocity.db"
        loop = asyncio.new_event_loop()

        async def setup():
            await init_db()
            now = datetime.now(timezone.utc)
            
            posts = []
            # Baseline: 1 mention 20 hours ago
            posts.append({
                "platform": "4chan",
                "external_id": "pol-old",
                "board_or_feed": "pol",
                "author": "Anon-old",
                "thread_id": "thread-old",
                "content_raw": "SpikeTest",
                "content_text": "SpikeTest",
                "posted_at": (now - timedelta(hours=20)).isoformat(),
            })
            
            # Recent: 10 mentions in the last 30 minutes
            for i in range(10):
                posts.append({
                    "platform": "4chan",
                    "external_id": f"pol-new-{i}",
                    "board_or_feed": "pol",
                    "author": f"Anon-{i}",
                    "thread_id": f"thread-{i}",
                    "content_raw": "SpikeTest",
                    "content_text": "SpikeTest",
                    "posted_at": (now - timedelta(minutes=30)).isoformat(),
                })
                
            # Noise: A keyword with only 2 recent mentions
            for i in range(2):
                posts.append({
                    "platform": "4chan",
                    "external_id": f"pol-noise-{i}",
                    "board_or_feed": "pol",
                    "author": f"Anon-noise-{i}",
                    "thread_id": f"thread-noise-{i}",
                    "content_raw": "NoiseWord",
                    "content_text": "NoiseWord",
                    "posted_at": (now - timedelta(minutes=10)).isoformat(),
                })

            # Filler: Extra posts to pass the 20-post minimum data gate in velocity alerts
            filler_words = ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape", "honeydew", "kiwi", "lemon"]
            for i, word in enumerate(filler_words):
                posts.append({
                    "platform": "4chan",
                    "external_id": f"pol-filler-{i}",
                    "board_or_feed": "pol",
                    "author": f"Anon-filler-{i}",
                    "thread_id": f"thread-filler-{i}",
                    "content_raw": word,
                    "content_text": word,
                    "posted_at": (now - timedelta(minutes=10)).isoformat(),
                })

            await insert_posts(posts)

        loop.run_until_complete(setup())
        yield
        loop.run_until_complete(close_db())
        loop.close()
        if os.path.exists("test_velocity.db"):
            os.remove("test_velocity.db")

    def test_velocity_alerts(self):
        response = client.get("/api/alerts/velocity")
        assert response.status_code == 200
        data = response.json()
        
        # SpikeTest should be there
        spikes = [a for a in data if a.get('keyword', '').lower() == 'spiketest']
        assert len(spikes) > 0
        spike = spikes[0]
        assert spike['recent_count'] == 10
        assert spike['spike_ratio'] >= 3.0
        
        # NoiseWord should NOT be there (< 5 mentions)
        noise = [a for a in data if a.get('keyword', '').lower() == 'noiseword']
        assert len(noise) == 0
