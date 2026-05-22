"""Central configuration for the Discourse Analyzer."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Always load .env from the project root (this file's directory), regardless of CWD.
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

# Database backend
# - "postgres" (default) uses asyncpg + PostgreSQL
# - "sqlite" uses aiosqlite and a local file
DB_BACKEND = os.getenv("DB_BACKEND", "postgres").lower()
DB_PATH = os.getenv("DB_PATH", "discourse.db")

# Database
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "discourse")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))

# 4chan API (free, no auth required)
FOURCHAN_API_BASE = "https://a.4cdn.org"
FOURCHAN_BOARDS = os.getenv("FOURCHAN_BOARDS", "pol,news,biz").split(",")
FOURCHAN_RATE_LIMIT_SECONDS = 1.1
FOURCHAN_COLLECT_INTERVAL_MINUTES = 5

# Mastodon-compatible platform (Mastodon.social as alternative social platform)
MASTODON_API_BASE = "https://mastodon.social"
# Support both variable names (older README/.env used MASTODON_ACCESS_TOKEN)
MASTODON_ACCESS_TOKEN = (
    os.getenv("MASTODON_TOKEN")
    or os.getenv("MASTODON_ACCESS_TOKEN")
    or os.getenv("MASTODON_TOKEN_ACCESS")
    or None
)
MASTODON_HASHTAGS = os.getenv(
    "MASTODON_HASHTAGS", "politics,news,election,media"
).split(",")
MASTODON_SEARCH_KEYWORDS = os.getenv(
    "MASTODON_KEYWORDS", "immigration,economy,climate"
).split(",")
MASTODON_COLLECT_INTERVAL_MINUTES = 10

# Truth Social (via truthbrush - Stanford Internet Observatory)
TRUTHSOCIAL_USERNAME = os.getenv("TRUTHSOCIAL_USERNAME", None)
TRUTHSOCIAL_PASSWORD = os.getenv("TRUTHSOCIAL_PASSWORD", None)
TRUTHSOCIAL_TOKEN = os.getenv("TRUTHSOCIAL_TOKEN", None)
TRUTHSOCIAL_HASHTAGS = os.getenv(
    "TRUTHSOCIAL_HASHTAGS", "politics,news,election,media"
).split(",")
TRUTHSOCIAL_COLLECT_INTERVAL_MINUTES = 3

# Server
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# Data Collection
START_DATE = os.getenv("START_DATE", "2024-02-01")
DAILY_POST_LIMIT = int(os.getenv("DAILY_POST_LIMIT", "200"))

# Velocity Alerts
ALERT_SPIKE_THRESHOLD = float(os.getenv("ALERT_SPIKE_THRESHOLD", "3.0"))
ALERT_MIN_MENTIONS = int(os.getenv("ALERT_MIN_MENTIONS", "5"))
ALERT_WINDOW_HOURS = int(os.getenv("ALERT_WINDOW_HOURS", "1"))
ALERT_BASELINE_HOURS = int(os.getenv("ALERT_BASELINE_HOURS", "24"))
ALERT_MAX_AGE_HOURS = int(os.getenv("ALERT_MAX_AGE_HOURS", "2"))

# Evidence-Based QA
QA_MAX_POSTS = int(os.getenv("QA_MAX_POSTS", "20"))
QA_MIN_RELEVANT_POSTS = int(os.getenv("QA_MIN_RELEVANT_POSTS", "5"))
QA_CONFIDENCE_THRESHOLD = int(os.getenv("QA_CONFIDENCE_THRESHOLD", "40"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
