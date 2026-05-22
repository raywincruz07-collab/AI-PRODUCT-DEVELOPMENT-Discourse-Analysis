"""Journalist-ready public discourse report generation."""

from __future__ import annotations

import json
import logging
from datetime import datetime

import httpx

import config
from analysis.keywords import tokenize
from analysis.narratives import _extract_cooccurrence_terms
from database.queries import search_posts
from database.connection import get_backend, get_conn

logger = logging.getLogger(__name__)

_REPORT_SYSTEM_PROMPT = """\
You are a senior research analyst writing a detailed briefing for journalists and researchers.

You will receive:
- A focus question / topic
- A data-driven verdict (YES / NO / INSUFFICIENT DATA) with confidence score and explanation
- A sample of real public social media posts collected from 4chan, Mastodon, and Truth Social
- Platform statistics

Your task is to write a DETAILED, RICH narrative report. Think of it as a journalist briefing document.

CRITICAL RULES:
- These are public posts — opinions, claims, discussions. NOT verified facts.
- Always use careful language: "public discourse suggests", "posts indicate", "some users claim", "collected data shows".
- Never fabricate post content, statistics, or claims not in the provided data.
- Be thorough, specific, and analytical — not generic or vague.
- Each section should have real substance drawn from the actual posts provided.

Return ONLY valid JSON, no markdown, no code blocks:
{
  "title": "Specific descriptive report title starting with 'Public Discourse Report:'",
  "main_topic": "The core topic in 3-6 words",
  "narrative_overview": "4-6 sentences. Describe what is actually being said in the collected posts. What are the dominant claims? What is the general tone? Are views consistent or split across platforms? Ground everything in what the posts actually say.",
  "executive_summary": "2-3 sentences bottom line for a journalist: what does this discourse data tell us, and what does it NOT tell us?",
  "key_discussion_points": [
    "Full sentence point 1 — specific claim or pattern found in the posts",
    "Full sentence point 2",
    "Full sentence point 3 — at least 6 points, 8 preferred"
  ],
  "platform_observations": {
    "description": "2-3 sentences comparing how different platforms discuss this topic. What is unique to each platform? Are there any notable differences in framing or tone?"
  },
  "what_to_investigate": "3-4 sentences: what specific angles, claims, or patterns in this data should journalists follow up on? What questions does this discourse raise that deserve reporting?",
  "interpretation": "2-3 sentences on what these discourse patterns may indicate. Do not make factual claims — focus on what the patterns suggest and their limitations as evidence."
}"""


async def _fetch_posts_for_topic(
    question: str,
    platform: str | None,
    start: str | None,
    end: str | None,
) -> list[dict]:
    """Search posts by each keyword in the question, deduplicate, score by relevance.

    Without filters, fetches a large pool (1000/kw → top 120) for broad coverage.
    With filters, uses a tighter focused fetch (300/kw → top 60).
    """
    keywords = tokenize(question)
    if not keywords:
        keywords = [w for w in question.lower().split() if len(w) > 3][:5]

    no_filters = not platform and not start and not end
    db_limit_per_kw = 1000 if no_filters else 300
    max_posts = 120 if no_filters else 60

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
        except Exception:
            continue
        for post in posts:
            pid = post.get("id")
            if pid is not None and pid not in seen_ids:
                seen_ids.add(pid)
                all_posts.append(post)

    kw_set = set(keywords)
    for post in all_posts:
        text = (post.get("content_text") or "").lower()
        post["_score"] = sum(1 for kw in kw_set if kw in text)

    all_posts.sort(key=lambda p: p["_score"], reverse=True)
    return all_posts[:max_posts]


async def _get_related_keywords(question: str, platform: str | None, start: str | None, end: str | None) -> list[str]:
    """Get co-occurring terms for the first meaningful keyword in the question."""
    keywords = tokenize(question)
    if not keywords:
        return []
    seed = keywords[0]
    backend = get_backend()
    try:
        if backend == "sqlite":
            where = ["content_text LIKE ?"]
            params = [f"%{seed}%"]
            if platform:
                where.append("platform = ?")
                params.append(platform)
            if start:
                where.append("posted_at >= ?")
                params.append(start)
            if end:
                where.append("posted_at <= ?")
                params.append(end)
            where_sql = " AND ".join(where)
            async with get_conn() as conn:
                cur = await conn.execute(
                    f"SELECT content_text FROM posts WHERE {where_sql} LIMIT 500", params
                )
                rows = await cur.fetchall()
        else:
            where = [f"content_text ILIKE $1"]
            params = [f"%{seed}%"]
            i = 2
            if platform:
                where.append(f"platform = ${i}")
                params.append(platform)
                i += 1
            where_sql = " AND ".join(where)
            async with get_conn() as conn:
                rows = await conn.fetch(
                    f"SELECT content_text FROM posts WHERE {where_sql} LIMIT 500", *params
                )
        counter = _extract_cooccurrence_terms(rows, seed, min_bigram_count=3)
        return [k for k, _ in counter.most_common(20)]
    except Exception as e:
        logger.debug("Related keywords failed: %s", e)
        return []


async def generate_report(
    question: str,
    qa_answer: dict,
    platform: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """Generate a structured journalist-ready public discourse report."""

    # 1. Fetch relevant posts
    top_posts = await _fetch_posts_for_topic(question, platform, start, end)

    # 2. Platform breakdown
    platform_stats: dict[str, dict] = {}
    for post in top_posts:
        plat = post.get("platform", "unknown")
        if plat not in platform_stats:
            platform_stats[plat] = {"post_count": 0, "authors": set()}
        platform_stats[plat]["post_count"] += 1
        author = post.get("author")
        if author:
            platform_stats[plat]["authors"].add(author)

    platform_breakdown = {
        plat: {"post_count": d["post_count"], "unique_authors": len(d["authors"])}
        for plat, d in platform_stats.items()
    }

    # 3. Related keywords
    related_keywords = await _get_related_keywords(question, platform, start, end)

    # 4. Evidence posts — up to 4 per platform, 12 total
    evidence_posts: list[dict] = []
    per_platform: dict[str, int] = {}
    for post in top_posts:
        plat = post.get("platform", "unknown")
        if per_platform.get(plat, 0) >= 4:
            continue
        per_platform[plat] = per_platform.get(plat, 0) + 1
        evidence_posts.append({
            "platform": plat,
            "author": post.get("author") or "Anonymous",
            "posted_at": str(post.get("posted_at", ""))[:19].replace("T", " "),
            "content": (post.get("content_text") or "").strip()[:500],
            "post_id": post.get("external_id") or str(post.get("id", "")),
            "board_or_feed": post.get("board_or_feed") or "",
        })
        if len(evidence_posts) >= 12:
            break

    # 5. Extract QA fields to embed directly in report
    qa_verdict = qa_answer.get("answer", "INSUFFICIENT DATA") if isinstance(qa_answer, dict) else "INSUFFICIENT DATA"
    qa_confidence = qa_answer.get("confidence", 0) if isinstance(qa_answer, dict) else 0
    qa_why = qa_answer.get("why", "") if isinstance(qa_answer, dict) else str(qa_answer)
    qa_snippets = qa_answer.get("supporting_snippets", []) if isinstance(qa_answer, dict) else []
    qa_platforms = qa_answer.get("platforms_found", []) if isinstance(qa_answer, dict) else []
    qa_total = qa_answer.get("total_posts_analyzed", len(top_posts)) if isinstance(qa_answer, dict) else len(top_posts)

    # 6. Claude narrative sections
    claude_sections: dict = {}
    if config.ANTHROPIC_API_KEY:
        post_lines = []
        for p in top_posts[:40]:
            plat = p.get("platform", "unknown")
            author = p.get("author") or "Anonymous"
            date = str(p.get("posted_at", ""))[:10]
            content = (p.get("content_text") or "").strip()[:350]
            post_lines.append(f"[{plat} | {author} | {date}] {content}")

        platform_counts = {k: v["post_count"] for k, v in platform_breakdown.items()}

        user_message = (
            f"FOCUS QUESTION: {question}\n\n"
            f"DATA-DRIVEN VERDICT: {qa_verdict} (Confidence: {qa_confidence}%)\n"
            f"VERDICT EXPLANATION: {qa_why}\n\n"
            f"TOTAL POSTS FOUND: {len(top_posts)} across {len(platform_stats)} platform(s)\n"
            f"PLATFORM BREAKDOWN: {json.dumps(platform_counts)}\n"
            f"RELATED TERMS IN DISCOURSE: {', '.join(related_keywords[:15])}\n\n"
            f"COLLECTED POSTS SAMPLE ({min(40, len(top_posts))} most relevant):\n"
            + "\n".join(post_lines)
        )
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": config.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": "claude-sonnet-4-6",
                        "max_tokens": 4000,
                        "system": _REPORT_SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": user_message}],
                    },
                )
            raw = resp.json()["content"][0]["text"]
            raw = raw.replace("```json", "").replace("```", "").strip()
            claude_sections = json.loads(raw)
        except Exception as e:
            logger.warning("Report generation Claude call failed: %s", e)

    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    return {
        # Core identity
        "title": claude_sections.get("title", f"Public Discussion Report: {question[:70]}"),
        "main_topic": claude_sections.get("main_topic", question),
        "focus_question": question,
        "generated_at": generated_at,

        # QA verdict — embedded directly in report
        "verdict": qa_verdict,
        "verdict_confidence": qa_confidence,
        "verdict_explanation": qa_why,
        "verdict_platforms": qa_platforms,
        "qa_supporting_snippets": qa_snippets,
        "qa_total_posts": qa_total,

        # Coverage stats
        "total_posts_analyzed": len(top_posts),
        "platforms_covered": list(platform_breakdown.keys()),
        "platform_breakdown": platform_breakdown,

        # Narrative sections (Claude-generated)
        "narrative_overview": claude_sections.get(
            "narrative_overview",
            f"A total of {len(top_posts)} public posts were found discussing this topic across {len(platform_breakdown)} platform(s)."
        ),
        "executive_summary": claude_sections.get(
            "executive_summary",
            f"A total of {len(top_posts)} public posts were found discussing this topic across {len(platform_breakdown)} platform(s)."
        ),
        "key_discussion_points": claude_sections.get("key_discussion_points", []),
        "platform_observations": claude_sections.get("platform_observations", {}).get("description", ""),
        "what_to_investigate": claude_sections.get(
            "what_to_investigate",
            "Further journalistic investigation is recommended to verify claims found in these public posts."
        ),
        "interpretation": claude_sections.get(
            "interpretation",
            "Further journalistic investigation is recommended to verify claims found in these public posts."
        ),

        # Evidence
        "related_keywords": related_keywords,
        "evidence_posts": evidence_posts,

        # Disclaimer
        "disclaimer": (
            "This report is based solely on public posts collected by Discourse Analyzer from 4chan, Mastodon, and Truth Social. "
            "The claims, opinions, and discussions in these posts have not been independently verified. "
            "This report is intended as a starting point for journalistic or academic investigation, "
            "not as a statement of verified facts. All quotes are reproduced verbatim from public posts."
        ),
    }
