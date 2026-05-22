"""Pydantic models for API request/response validation."""

from pydantic import BaseModel
from typing import Optional


class PostResponse(BaseModel):
    id: int
    platform: str
    external_id: str
    board_or_feed: Optional[str] = None
    thread_id: Optional[str] = None
    author: Optional[str] = None
    content_text: str
    media_urls: Optional[str] = None
    posted_at: str
    collected_at: Optional[str] = None
    likes: int
    replies: int
    shares: int


class PostListResponse(BaseModel):
    posts: list[PostResponse]
    total: int
    page: int
    limit: int


class TrendPoint(BaseModel):
    period: str
    count: int


class KeywordCount(BaseModel):
    keyword: str
    count: int


class TrendingKeyword(BaseModel):
    keyword: str
    count: int
    score: float


class NarrativeResponse(BaseModel):
    seed_keyword: str
    total_posts: int
    co_occurring: list[KeywordCount]


class PlatformStats(BaseModel):
    platform: str
    total_posts: int
    unique_authors: int
    boards: int
    earliest: Optional[str] = None
    latest: Optional[str] = None
