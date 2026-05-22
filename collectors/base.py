"""Abstract base collector."""

import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import warnings

from bs4 import BeautifulSoup
from bs4 import MarkupResemblesLocatorWarning
from database.queries import insert_posts
import config


class BaseCollector(ABC):
    """Base class for platform data collectors."""

    platform: str = ""
    post_counts: dict[str, int] = {}

    def strip_html(self, html: str) -> str:
        """Convert HTML content to plain text."""
        if not html:
            return ""
        # Replace <br> with newlines before stripping
        html = re.sub(r"<br\s*/?>", "\n", html)
        # BeautifulSoup emits a warning if the input resembles a URL.
        warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _to_utc(dt: datetime) -> datetime:
        """Normalize naive/aware datetimes to UTC-aware."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    async def filter_and_limit_posts(self, posts: list[dict]) -> list[dict]:
        """Filter posts by date and limit the number of posts per day."""
        filtered_posts = []
        start_date = self._to_utc(datetime.fromisoformat(config.START_DATE))

        for post in posts:
            # Accept Z or offset formats
            posted_at_str = str(post["posted_at"]).replace("Z", "+00:00")
            posted_at = self._to_utc(datetime.fromisoformat(posted_at_str))
            if posted_at < start_date:
                continue

            day_str = posted_at.strftime("%Y-%m-%d")
            if day_str not in self.post_counts:
                self.post_counts[day_str] = 0

            if self.post_counts[day_str] < config.DAILY_POST_LIMIT:
                filtered_posts.append(post)
                self.post_counts[day_str] += 1
            else:
                # Stop collecting for this day if the limit is reached
                continue

        return filtered_posts

    async def save_posts(self, posts: list[dict]) -> int:
        """Save collected posts to the database after filtering and limiting."""
        filtered_posts = await self.filter_and_limit_posts(posts)
        if not filtered_posts:
            return 0
        return await insert_posts(filtered_posts)

    @abstractmethod
    async def collect(self) -> int:
        """Run one collection cycle. Return number of posts collected."""
        pass
