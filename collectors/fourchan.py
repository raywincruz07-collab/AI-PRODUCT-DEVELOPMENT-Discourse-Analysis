"""4chan data collector using the official read-only JSON API."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx

import config
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class FourChanCollector(BaseCollector):
    platform = "4chan"

    def __init__(self):
        self.base_url = config.FOURCHAN_API_BASE
        self.boards = config.FOURCHAN_BOARDS
        self.rate_limit = config.FOURCHAN_RATE_LIMIT_SECONDS
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "DiscourseAnalyzer/1.0 (Academic Research)"},
        )

    async def _rate_limited_get(self, url: str) -> httpx.Response | None:
        """Make a rate-limited GET request."""
        try:
            await asyncio.sleep(self.rate_limit)
            response = await self.client.get(url)
            if response.status_code == 200:
                return response
            elif response.status_code == 304:
                return None  # Not modified
            else:
                logger.warning(f"4chan API returned {response.status_code} for {url}")
                return None
        except Exception as e:
            logger.error(f"4chan request failed for {url}: {e}")
            return None

    def _parse_post(self, post: dict, board: str) -> dict:
        """Parse a 4chan post into our standard format."""
        content_raw = post.get("com", "")
        media_urls = []
        if post.get("tim") and post.get("ext"):
            media_urls.append(f"https://i.4cdn.org/{board}/{post['tim']}{post['ext']}")

        return {
            "platform": "4chan",
            "external_id": f"{board}-{post['no']}",
            "board_or_feed": board,
            "thread_id": str(post.get("resto", post["no"])),
            "author": post.get("name", "Anonymous"),
            "content_raw": content_raw,
            "content_text": self.strip_html(content_raw),
            "media_urls": media_urls,
            "posted_at": datetime.fromtimestamp(post["time"], timezone.utc).isoformat(),
            "likes": 0,  # 4chan doesn't have likes
            "replies": post.get("replies", 0),
            "shares": 0,  # 4chan doesn't have shares
            "metadata": {
                "post_no": post["no"],
                "images": post.get("images", 0),
                "trip": post.get("trip", ""),
                "country": post.get("country", ""),
                "country_name": post.get("country_name", ""),
            },
        }

    async def _collect_board(self, board: str) -> int:
        """Collect posts from a single board's catalog and top threads."""
        total = 0

        # Fetch catalog
        resp = await self._rate_limited_get(f"{self.base_url}/{board}/catalog.json")
        if not resp:
            return 0

        catalog = resp.json()
        all_posts = []
        thread_nos = []

        # Parse catalog pages - each page has threads with OP posts
        for page in catalog:
            for thread in page.get("threads", []):
                all_posts.append(self._parse_post(thread, board))
                thread_nos.append(thread["no"])

        # Fetch top threads for replies (limit to most active threads)
        thread_nos_sorted = sorted(
            thread_nos,
            key=lambda n: next(
                (
                    t.get("replies", 0)
                    for page in catalog
                    for t in page.get("threads", [])
                    if t["no"] == n
                ),
                0,
            ),
            reverse=True,
        )[
            :10
        ]  # Top 10 most active threads

        for thread_no in thread_nos_sorted:
            resp = await self._rate_limited_get(
                f"{self.base_url}/{board}/thread/{thread_no}.json"
            )
            if not resp:
                continue

            thread_data = resp.json()
            for post in thread_data.get("posts", [])[
                1:
            ]:  # Skip OP (already in catalog)
                all_posts.append(self._parse_post(post, board))

        # Save to database
        if all_posts:
            total = await self.save_posts(all_posts)
            logger.info(
                f"4chan /{board}/: saved {total} new posts from {len(all_posts)} total"
            )

        return total

    async def collect(self) -> int:
        """Collect from all configured boards."""
        total = 0
        for board in self.boards:
            try:
                count = await self._collect_board(board)
                total += count
            except Exception as e:
                logger.error(f"Failed to collect 4chan /{board}/: {e}")
        return total

    async def close(self):
        await self.client.aclose()
