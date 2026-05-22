"""Tests for data collectors with mocked HTTP responses."""

import asyncio
import os
import json
import pytest

os.environ["DB_PATH"] = "test_discourse.db"

from collectors.base import BaseCollector
from collectors.fourchan import FourChanCollector
from collectors.mastodon import MastodonCollector
from collectors.truthsocial import TruthSocialCollector


def test_html_stripping():
    """Test HTML to plain text conversion."""

    class TestCollector(BaseCollector):
        async def collect(self):
            return 0

    c = TestCollector()

    assert c.strip_html("<p>Hello <b>world</b></p>") == "Hello world"
    assert c.strip_html('Test <a href="url">link</a> here') == "Test link here"
    assert c.strip_html('<span class="quote">&gt;greentext</span>') == ">greentext"
    assert c.strip_html("") == ""
    assert c.strip_html(None) == ""
    assert "newline" in c.strip_html("before<br>newline")


def test_fourchan_post_parsing():
    """Test 4chan post parsing."""
    collector = FourChanCollector()

    raw_post = {
        "no": 12345,
        "com": '<a href="#p12340" class="quotelink">&gt;&gt;12340</a><br>This is a test post',
        "time": 1705312800,
        "name": "Anonymous",
        "resto": 12340,
        "tim": 1705312800123,
        "ext": ".jpg",
    }

    parsed = collector._parse_post(raw_post, "pol")

    assert parsed["platform"] == "4chan"
    assert parsed["external_id"] == "pol-12345"
    assert parsed["board_or_feed"] == "pol"
    assert parsed["thread_id"] == "12340"
    assert parsed["author"] == "Anonymous"
    assert "test post" in parsed["content_text"].lower()
    assert len(parsed["media_urls"]) == 1
    assert "4cdn.org" in parsed["media_urls"][0]


def test_mastodon_status_parsing():
    """Test Mastodon status parsing."""
    collector = MastodonCollector()

    raw_status = {
        "id": "109876543210",
        "content": "<p>This is a post about the <a href='#'>#economy</a></p>",
        "created_at": "2024-01-15T10:00:00.000Z",
        "account": {
            "username": "testuser",
            "acct": "testuser",
            "display_name": "Test User",
            "followers_count": 100,
        },
        "media_attachments": [
            {"url": "https://media.mastodon.social/image.jpg"}
        ],
        "reblogs_count": 5,
        "favourites_count": 10,
        "replies_count": 3,
        "in_reply_to_id": None,
        "language": "en",
        "tags": [{"name": "economy"}],
    }

    parsed = collector._parse_status(raw_status, "public_timeline")

    assert parsed["platform"] == "mastodon"
    assert parsed["external_id"] == "109876543210"
    assert parsed["author"] == "testuser"
    assert "economy" in parsed["content_text"].lower()
    assert len(parsed["media_urls"]) == 1
    assert parsed["metadata"]["followers_count"] == 100


def test_truthsocial_status_parsing():
    """Test Truth Social status parsing."""
    collector = TruthSocialCollector()

    raw_status = {
        "id": "109999888777",
        "content": "<p>This is a Truth Social post about #politics</p>",
        "created_at": "2024-06-15T14:00:00.000Z",
        "account": {
            "username": "truthuser",
            "acct": "truthuser",
            "display_name": "Truth User",
            "followers_count": 500,
        },
        "media_attachments": [],
        "reblogs_count": 12,
        "favourites_count": 30,
        "replies_count": 8,
        "in_reply_to_id": None,
        "language": "en",
    }

    parsed = collector._parse_status(raw_status, "trending")

    assert parsed["platform"] == "truthsocial"
    assert parsed["external_id"] == "109999888777"
    assert parsed["author"] == "truthuser"
    assert "politics" in parsed["content_text"].lower()
    assert parsed["board_or_feed"] == "trending"
    assert parsed["metadata"]["followers_count"] == 500
