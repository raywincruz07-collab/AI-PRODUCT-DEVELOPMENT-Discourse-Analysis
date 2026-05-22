"""Database models / schema reference.

The actual schema creation happens in connection.py:init_db().
This module provides helper utilities for working with post data.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Post:
    id: int
    platform: str
    external_id: str
    board_or_feed: Optional[str]
    thread_id: Optional[str]
    author: Optional[str]
    content_raw: str
    content_text: str
    media_urls: Optional[str]
    posted_at: str
    collected_at: str
    metadata_json: Optional[str]
    likes: int
    replies: int
    shares: int
