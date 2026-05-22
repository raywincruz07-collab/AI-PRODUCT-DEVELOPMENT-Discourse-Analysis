"""Evidence-based question answering from collected posts using Claude API."""

from __future__ import annotations

import json
import logging

import httpx

import config
from analysis.keywords import tokenize
from database.queries import search_posts

logger = logging.getLogger(__name__)

_INSUFFICIENT_DATA = {
    "answer": "INSUFFICIENT DATA",
    "why": "Not enough collected posts found to answer this question reliably.",
    "confidence": 0,
    "platforms_found": [],
    "total_posts_analyzed": 0,
    "supporting_snippets": [],
    "limitation_note": (
        "This answer is based solely on posts collected by Discourse Analyzer. "
        "Collection gaps may affect results."
    ),
}

_ERROR_RESPONSE = {
    "answer": "INSUFFICIENT DATA",
    "why": "Analysis could not be completed due to an internal error.",
    "confidence": 0,
    "platforms_found": [],
    "total_posts_analyzed": 0,
    "supporting_snippets": [],
    "limitation_note": (
        "This answer is based solely on posts collected by Discourse Analyzer. "
        "Collection gaps may affect results."
    ),
}

_TIMEOUT_RESPONSE = {
    "answer": "INSUFFICIENT DATA",
    "why": "Analysis could not be completed due to an internal error.",
    "confidence": 0,
    "platforms_found": [],
    "total_posts_analyzed": 0,
    "supporting_snippets": [],
    "limitation_note": "Request timed out.",
}

_SYSTEM_PROMPT = """\
You are an evidence analyzer for a journalism research tool.
You will be given a question and a set of social media posts
collected from 4chan, Mastodon, and Truth Social.

Rules you must follow strictly:
- Answer ONLY based on the posts provided below
- Never use outside knowledge
- Never guess or predict
- Never infer beyond what posts explicitly say
- If evidence is weak, mixed, or missing return INSUFFICIENT DATA

Return ONLY valid JSON in this exact format, nothing else,
no markdown, no explanation, no code blocks:
{
  "answer": "YES" or "NO" or "INSUFFICIENT DATA",
  "why": "plain English explanation based only on the posts provided",
  "confidence": integer 0 to 100,
  "platforms_found": ["4chan", "mastodon", "truthsocial"],
  "total_posts_analyzed": integer,
  "supporting_snippets": [
    {
      "platform": "...",
      "author": "...",
      "posted_at": "...",
      "content": "..."
    }
  ],
  "limitation_note": "This answer is based solely on posts collected by Discourse Analyzer. Collection gaps may affect results."
}"""


async def answer_from_posts(
    question: str,
    platform: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """Answer a question using evidence from collected posts.

    Steps:
      1. Extract keywords from the question via tokenize().
      2. Search posts for each keyword; deduplicate and score.
      3. Gate on QA_MIN_RELEVANT_POSTS — return INSUFFICIENT DATA early if not met.
      4. Build prompt and call Claude API.
      5. Parse JSON response; return INSUFFICIENT DATA on any failure.
    """

    # ── Step 1: Keyword extraction ──────────────────────────────────────────
    keywords = tokenize(question)
    if not keywords:
        return dict(_INSUFFICIENT_DATA)

    # ── Step 2: Search and score collected posts ─────────────────────────────
    # When no filters are applied, fetch a much larger pool so Claude sees
    # the full breadth of what has been collected. With filters, stay focused.
    no_filters = not platform and not start and not end
    db_limit_per_kw = 1000 if no_filters else 300
    claude_max_posts = 150 if no_filters else config.QA_MAX_POSTS

    seen_ids: set = set()
    all_posts: list[dict] = []

    for kw in keywords:
        try:
            posts, _ = await search_posts(
                query=kw,
                platform=platform or None,
                start=start or None,
                end=end or None,
                limit=db_limit_per_kw,
            )
        except Exception as exc:
            logger.debug("search_posts failed for keyword %r: %s", kw, exc)
            continue

        for post in posts:
            pid = post.get("id")
            if pid is not None and pid not in seen_ids:
                seen_ids.add(pid)
                all_posts.append(post)

    # Score each post by counting how many question keywords appear in content_text
    kw_set = set(keywords)
    for post in all_posts:
        text = (post.get("content_text") or "").lower()
        post["_score"] = sum(1 for kw in kw_set if kw in text)

    # Sort descending by score, take top posts for Claude
    all_posts.sort(key=lambda p: p["_score"], reverse=True)
    top_posts = all_posts[:claude_max_posts]

    # ── Step 3: Insufficient data gate ──────────────────────────────────────
    if len(top_posts) < config.QA_MIN_RELEVANT_POSTS:
        return {
            "answer": "INSUFFICIENT DATA",
            "why": "Not enough collected posts found to answer this question reliably.",
            "confidence": 0,
            "platforms_found": [],
            "total_posts_analyzed": 0,
            "supporting_snippets": [],
            "limitation_note": (
                "This answer is based solely on posts collected by Discourse Analyzer. "
                "Collection gaps may affect results."
            ),
        }

    # ── Step 4: Build prompt ─────────────────────────────────────────────────
    post_lines = []
    for p in top_posts:
        plat = p.get("platform", "unknown")
        author = p.get("author") or "Anonymous"
        date = str(p.get("posted_at", ""))[:10]
        board = p.get("board_or_feed") or ""
        content = (p.get("content_text") or "").strip()
        post_lines.append(f"[{plat} | {author} | {date} | {board}] {content}")

    user_message = (
        f"QUESTION: {question}\n\nCOLLECTED POSTS:\n" + "\n".join(post_lines)
    )

    # ── Step 5: Call Claude API ──────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": config.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 1500,
                    "system": _SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_message}],
                },
            )
    except httpx.TimeoutException:
        logger.warning("Claude API request timed out")
        return dict(_TIMEOUT_RESPONSE)
    except Exception as exc:
        logger.warning("Claude API request failed: %s", exc)
        return dict(_ERROR_RESPONSE)

    # ── Step 6: Parse response ───────────────────────────────────────────────
    try:
        raw = response.json()["content"][0]["text"]
        # Strip any markdown code fences if present
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        # Always ensure the limitation_note is present
        result.setdefault(
            "limitation_note",
            "This answer is based solely on posts collected by Discourse Analyzer. "
            "Collection gaps may affect results.",
        )
        return result
    except Exception as exc:
        logger.warning("Failed to parse Claude response: %s", exc)
        return dict(_ERROR_RESPONSE)
