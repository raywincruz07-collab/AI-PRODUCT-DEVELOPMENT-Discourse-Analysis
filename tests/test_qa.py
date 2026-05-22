"""Tests for Evidence-Based QA features."""

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Set test DB path before importing app
os.environ["DB_PATH"] = "test_qa.db"

from api.main import app
from database.connection import init_db, close_db
from database.queries import insert_posts

client = TestClient(app, raise_server_exceptions=False)


from api.routes_analytics import _request_counts


@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup and teardown for each test."""
    _request_counts.clear()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())
    yield
    loop.run_until_complete(close_db())
    loop.close()
    if os.path.exists("test_qa.db"):
        os.remove("test_qa.db")


@pytest.mark.asyncio
async def test_qa_positive_case():
    """Test 1 — Positive case: insert 10 posts mentioning 'immigration', assert response fields."""
    posts = []
    for i in range(10):
        posts.append({
            "platform": "truthsocial",
            "external_id": f"qa-pos-{i}",
            "author": "tester",
            "content_text": f"Discussing immigration reform and borders {i}",
            "posted_at": "2026-05-13T10:00:00",
            "likes": i,
            "replies": 0,
            "shares": 0
        })
    await insert_posts(posts)

    mock_response = {
        "answer": "YES",
        "why": "Multiple posts discuss immigration reform.",
        "confidence": 85,
        "platforms_found": ["truthsocial"],
        "total_posts_analyzed": 10,
        "supporting_snippets": [
            {"platform": "truthsocial", "author": "tester", "posted_at": "2026-05-13T10:00:00", "content": "Discussing immigration reform and borders 0"}
        ],
        "limitation_note": "This answer is based solely on posts collected by Discourse Analyzer."
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=lambda: {
                "content": [{"text": '{"answer": "YES", "why": "Multiple posts discuss immigration reform.", "confidence": 85, "platforms_found": ["truthsocial"], "total_posts_analyzed": 10, "supporting_snippets": [{"platform": "truthsocial", "author": "tester", "posted_at": "2026-05-13T10:00:00", "content": "Discussing immigration reform and borders 0"}], "limitation_note": "This answer is based solely on posts collected by Discourse Analyzer."}'}]
            }
        )
        
        response = client.post("/api/qa/answer", json={"question": "Are people discussing immigration?"})
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert isinstance(data["supporting_snippets"], list)
        assert isinstance(data["confidence"], int)
        assert isinstance(data["limitation_note"], str)


@pytest.mark.asyncio
async def test_qa_insufficient_data():
    """Test 2 — Insufficient data: insert zero posts, assert INSUFFICIENT DATA."""
    # Database is empty by default in each test due to fixture
    response = client.post("/api/qa/answer", json={"question": "What is happening with taxes?"})
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "INSUFFICIENT DATA"
    assert "Not enough collected posts" in data["why"]


def test_qa_validation_empty():
    """Test 3 — Validation empty: POST with empty question string, assert 400."""
    response = client.post("/api/qa/answer", json={"question": ""})
    assert response.status_code == 400
    assert "Question too short" in response.json()["detail"]


def test_qa_validation_short():
    """Test 4 — Validation short: POST with question 'Hi', assert 400."""
    response = client.post("/api/qa/answer", json={"question": "Hi"})
    assert response.status_code == 400
    assert "Question too short" in response.json()["detail"]


def test_qa_rate_limit():
    """Test 5 — Rate limit: POST 11 requests, 11th returns 429."""
    # We use a unique IP or reset the rate limiter state if needed.
    # Since it's in-memory and static, it might be affected by previous tests.
    # However, 'client' in TestClient typically uses a mock address.
    
    # Clear previous counts if necessary (accessing private var for testing)
    from api.routes_analytics import _request_counts
    _request_counts.clear()

    for i in range(10):
        resp = client.post("/api/qa/answer", json={"question": "Valid question number " + str(i)})
        assert resp.status_code != 429
    
    # 11th request
    resp = client.post("/api/qa/answer", json={"question": "One too many questions"})
    assert resp.status_code == 429
    assert "Too many requests" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_qa_api_failure():
    """Test 6 — API failure: mock httpx exception, assert INSUFFICIENT DATA."""
    # Ensure there are enough posts to trigger the API call
    posts = []
    for i in range(5):
        posts.append({
            "platform": "mastodon",
            "external_id": f"qa-fail-{i}",
            "author": "tester",
            "content_text": "keyword match content",
            "posted_at": "2026-05-13T10:00:00"
        })
    await insert_posts(posts)

    with patch("httpx.AsyncClient.post", side_effect=Exception("API Down")):
        response = client.post("/api/qa/answer", json={"question": "Triggering keyword match?"})
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "INSUFFICIENT DATA"
        assert "internal error" in data["why"].lower()
