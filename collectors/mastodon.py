"""Mastodon data collector using the Mastodon-compatible API."""

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx

import config
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class MastodonCollector(BaseCollector):
    platform = "mastodon"

    def __init__(self):
        self.base_url = config.MASTODON_API_BASE
        self.token = config.MASTODON_ACCESS_TOKEN
        self.hashtags = config.MASTODON_HASHTAGS
        self.search_keywords = config.MASTODON_SEARCH_KEYWORDS
        headers = {"User-Agent": "DiscourseAnalyzer/1.0 (Academic Research)"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self.client = httpx.AsyncClient(timeout=30.0, headers=headers)

    def _parse_status(self, status: dict, feed: str = "public") -> dict:
        """Parse a Mastodon status into our standard format."""
        content_raw = status.get("content", "")
        media_urls = [m.get("url", "") for m in status.get("media_attachments", [])]
        account = status.get("account", {})
        in_reply_to = status.get("in_reply_to_id")

        return {
            "platform": "mastodon",
            "external_id": str(status["id"]),
            "board_or_feed": feed,
            "thread_id": str(in_reply_to) if in_reply_to else None,
            "author": account.get("username", account.get("acct", "unknown")),
            "content_raw": content_raw,
            "content_text": self.strip_html(content_raw),
            "media_urls": media_urls,
            "posted_at": status.get(
                "created_at", datetime.now(timezone.utc).isoformat()
            ),
            "likes": status.get("favourites_count", 0),
            "replies": status.get("replies_count", 0),
            "shares": status.get("reblogs_count", 0),
            "metadata": {
                "display_name": account.get("display_name", ""),
                "followers_count": account.get("followers_count", 0),
                "language": status.get("language", ""),
                "tags": [t.get("name", "") for t in status.get("tags", [])],
            },
        }

    async def _fetch_endpoint(
        self, path: str, feed_label: str, params: dict = None
    ) -> list[dict]:
        """Fetch and parse posts from a Mastodon-compatible endpoint."""
        url = f"{self.base_url}{path}"
        all_posts = []

        try:
            resp = await self.client.get(url, params=params or {})
            if resp.status_code == 401:
                logger.warning(
                    "Mastodon endpoint requires authentication. Set MASTODON_TOKEN env var."
                )
                return []
            if resp.status_code == 429:
                logger.warning("Mastodon rate limit hit. Backing off.")
                return []
            if resp.status_code != 200:
                logger.warning(f"Mastodon returned {resp.status_code} for {url}")
                return []

            statuses = resp.json()
            if isinstance(statuses, list):
                for status in statuses:
                    # Only collect English posts
                    if status.get("language") and status["language"] != "en":
                        continue
                    all_posts.append(self._parse_status(status, feed_label))

            # Follow pagination (max 2 pages to stay within rate limits)
            link_header = resp.headers.get("Link", "")
            next_url = None
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip().strip("<>")
                    break

            if next_url:
                await asyncio.sleep(1)
                resp2 = await self.client.get(next_url)
                if resp2.status_code == 200:
                    statuses2 = resp2.json()
                    if isinstance(statuses2, list):
                        for status in statuses2:
                            if status.get("language") and status["language"] != "en":
                                continue
                            all_posts.append(self._parse_status(status, feed_label))

        except Exception as e:
            logger.error(f"Mastodon fetch failed for {path}: {e}")

        return all_posts

    async def collect(self) -> int:
        """Collect from public timeline, hashtags, and keyword searches."""
        total = 0

        # Public timeline
        posts = await self._fetch_endpoint(
            "/api/v1/timelines/public",
            "public_timeline",
            {"limit": "40"},
        )
        if posts:
            count = await self.save_posts(posts)
            total += count

        await asyncio.sleep(1)

        # Hashtag timelines
        for tag in self.hashtags:
            posts = await self._fetch_endpoint(
                f"/api/v1/timelines/tag/{tag}",
                f"hashtag_{tag}",
                {"limit": "40"},
            )
            if posts:
                count = await self.save_posts(posts)
                total += count
            await asyncio.sleep(1)

        return total

    async def close(self):
        await self.client.aclose()
