"""Narrative analysis - co-occurrence and topic clustering."""

import re
from collections import Counter
from database.connection import get_backend, get_conn
from database.queries import search_posts
from analysis.keywords import tokenize, SPIKE_NOISE_WORDS, STOPWORDS


def _extract_cooccurrence_terms(rows, seed_keyword: str, min_bigram_count: int = 3) -> Counter:
    """Two-pass extraction: merge frequent adjacent word pairs into phrases.

    Pass 1 counts all bigrams. Pass 2 greedily uses bigrams that crossed the
    frequency threshold, so 'donald trump' and 'strait hormuz' appear as
    single entries instead of two separate words.
    """
    kw_lower = seed_keyword.lower()

    # Pass 1 — tokenize every post and tally bigram frequencies
    all_tokens: list[list[str]] = []
    bigram_counts: Counter = Counter()

    for row in rows:
        words = re.findall(r"[a-zA-Z]+", row[0].lower())
        tokens = [
            w for w in words
            if len(w) > 3 and w not in STOPWORDS and w not in SPIKE_NOISE_WORDS
        ]
        all_tokens.append(tokens)
        for i in range(len(tokens) - 1):
            bigram_counts[f"{tokens[i]} {tokens[i + 1]}"] += 1

    frequent_bigrams = {bg for bg, cnt in bigram_counts.items() if cnt >= min_bigram_count}

    # Pass 2 — build per-post term sets, preferring the highest-count bigram at each position
    counter: Counter = Counter()
    for tokens in all_tokens:
        consumed: set[int] = set()
        terms: set[str] = set()

        # Collect candidate bigrams with their corpus counts, sorted best-first
        candidates = []
        for i in range(len(tokens) - 1):
            bg = f"{tokens[i]} {tokens[i + 1]}"
            if bg in frequent_bigrams:
                candidates.append((bigram_counts[bg], i, bg, tokens[i], tokens[i + 1]))
        candidates.sort(reverse=True)  # highest-count bigrams win overlapping positions

        for _, i, bg, w0, w1 in candidates:
            if i in consumed or (i + 1) in consumed:
                continue
            consumed.add(i)
            consumed.add(i + 1)
            if w0 != kw_lower and w1 != kw_lower:
                terms.add(bg)

        for i, tok in enumerate(tokens):
            if i not in consumed and tok != kw_lower and len(tok) > 3:
                terms.add(tok)

        counter.update(terms)

    # Suppress lone words that are mostly captured in a bigram.
    # Allow up to 30% more occurrences as standalone before keeping the word
    # (handles cases like "white" in "white house" where a few extra lone uses
    # aren't worth a separate chart entry).
    bigram_words: set[str] = set()
    for bg, bg_count in counter.items():
        if " " in bg:
            for word in bg.split():
                if counter.get(word, 0) <= bg_count * 1.3:
                    bigram_words.add(word)
    for word in bigram_words:
        counter.pop(word, None)

    return counter


async def get_cooccurrence(
    keyword: str,
    platform: str = None,
    start: str = None,
    end: str = None,
    n: int = 20,
) -> dict:
    """Find terms that co-occur with a seed keyword.

    Returns the top N terms that appear in the same posts as the keyword,
    revealing how discourse around a topic is framed.
    """
    backend = get_backend()

    if backend == "sqlite":
        where = ["content_text LIKE ?"]
        params = [f"%{keyword}%"]
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
                f"SELECT content_text FROM posts WHERE {where_sql}", params
            )
            rows = await cur.fetchall()
    else:
        where = []
        params = []
        i = 1

        where.append(f"content_text ILIKE ${i}")
        params.append(f"%{keyword}%")
        i += 1
        if platform:
            where.append(f"platform = ${i}")
            params.append(platform)
            i += 1
        if start:
            where.append(f"posted_at >= ${i}")
            params.append(start)
            i += 1
        if end:
            where.append(f"posted_at <= ${i}")
            params.append(end)
            i += 1

        where_sql = " AND ".join(where) if where else "TRUE"
        async with get_conn() as conn:
            rows = await conn.fetch(
                f"SELECT content_text FROM posts WHERE {where_sql}", *params
            )

    counter = _extract_cooccurrence_terms(rows, keyword)
    co_occurring = [{"keyword": k, "count": c} for k, c in counter.most_common(n)]

    return {
        "seed_keyword": keyword,
        "total_posts": len(rows),
        "co_occurring": co_occurring,
    }


async def compare_narratives(
    keyword: str,
    start: str = None,
    end: str = None,
    n: int = 15,
) -> dict:
    """Compare how a keyword's narrative differs across platforms."""
    fourchan_result = await get_cooccurrence(
        keyword, platform="4chan", start=start, end=end, n=n
    )
    mastodon_result = await get_cooccurrence(
        keyword, platform="mastodon", start=start, end=end, n=n
    )
    truthsocial_result = await get_cooccurrence(
        keyword, platform="truthsocial", start=start, end=end, n=n
    )

    return {
        "keyword": keyword,
        "4chan": fourchan_result,
        "mastodon": mastodon_result,
        "truthsocial": truthsocial_result,
    }


def _platform_label(p: str) -> str:
    labels = {"4chan": "4chan", "mastodon": "Mastodon", "truthsocial": "Truth Social"}
    return labels.get(p, p)


def _build_interpretation(keyword: str, valid_platforms: list, status: str, overlap_ratio: float) -> dict:
    """Build a human-readable interpretation from keyword data. No invention — only describes what the data shows."""
    kw = keyword.capitalize()
    platform_names = [_platform_label(p["platform"]) for p in valid_platforms]

    # Per-platform interpretation: describe framing via top keywords as context
    platform_interpretations = []
    for vp in valid_platforms:
        pname = _platform_label(vp["platform"])
        kws = vp["top_keywords"][:5]  # use top 5 as context
        if kws:
            kw_phrase = ", ".join(f'"{k}"' for k in kws[:3])
            rest = f" and related terms like {', '.join(repr(k) for k in kws[3:])}" if len(kws) > 3 else ""
            interp = (
                f"{pname} discussions mentioning \"{keyword}\" are most often associated "
                f"with {kw_phrase}{rest}."
            )
        else:
            interp = f"{pname} had posts mentioning \"{keyword}\" but no strongly co-occurring terms were identified."
        platform_interpretations.append({
            "platform": vp["platform"],
            "label": pname,
            "interpretation": interp,
        })

    # Final observation: compare framing across platforms
    if len(valid_platforms) >= 2:
        p1 = valid_platforms[0]
        p2 = valid_platforms[1]
        p1_kws = ", ".join(p1["top_keywords"][:3]) if p1["top_keywords"] else "general topics"
        p2_kws = ", ".join(p2["top_keywords"][:3]) if p2["top_keywords"] else "general topics"
        p1_label = _platform_label(p1["platform"])
        p2_label = _platform_label(p2["platform"])

        if status == "Similar Narrative":
            final_observation = (
                f"Both {p1_label} and {p2_label} discuss \"{keyword}\" through a very similar "
                f"set of related terms ({p1_kws}), suggesting the topic is framed consistently across these platforms."
            )
        elif status == "Mildly Different Framing":
            final_observation = (
                f"{p1_label} discusses \"{keyword}\" mainly through terms like {p1_kws}, while "
                f"{p2_label} leans more toward {p2_kws}. There is some shared vocabulary, "
                f"but each platform emphasizes different aspects of the topic."
            )
        else:  # Distinct Framing
            final_observation = (
                f"{p1_label} discusses \"{keyword}\" mainly through terms like {p1_kws}, while "
                f"{p2_label} frames it differently — around {p2_kws}. This indicates distinct "
                f"framing across platforms, though it does not necessarily imply contradiction."
            )
    else:
        final_observation = f"Only one platform had enough posts about \"{keyword}\" for reliable comparison."

    # Plain-English meaning of the status
    if status == "Similar Narrative":
        plain_explanation = (
            f"The platforms appear to discuss \"{keyword}\" in broadly similar ways. "
            "This could mean the topic is being reported factually and consistently, "
            "or that the same news cycle is driving conversation across communities."
        )
    elif status == "Mildly Different Framing":
        plain_explanation = (
            f"The platforms share some common framing of \"{keyword}\" but diverge in emphasis. "
            "This is normal for topics that have multiple dimensions — different communities "
            "may focus on different aspects without necessarily contradicting each other."
        )
    else:
        plain_explanation = (
            f"The platforms frame \"{keyword}\" using largely different associated terms. "
            "This indicates that each community is contextualizing the topic in its own way. "
            "This is a framing difference, not a confirmed factual contradiction — the same "
            "underlying events may simply be interpreted through different lenses."
        )

    # Why this conclusion was reached
    total_posts = sum(vp["post_count"] for vp in valid_platforms)
    pct = round(overlap_ratio * 100)
    why = [
        f"At least 2 platforms had enough posts about \"{keyword}\" (minimum 5 each) to support comparison.",
        f"A total of {total_posts} posts were analyzed across {len(valid_platforms)} platform(s).",
        f"Only {pct}% of the top associated terms were shared between platforms — "
        + ("a high level of overlap, indicating similar framing." if pct >= 50
           else "some overlap, indicating mild divergence." if pct >= 30
           else "a low level of overlap, indicating distinct framing."),
        "No factual contradiction was inferred — the conclusion is based strictly on keyword framing patterns.",
    ]

    return {
        "final_observation": final_observation,
        "plain_explanation": plain_explanation,
        "platform_interpretations": platform_interpretations,
        "why_this_conclusion": why,
    }


async def detect_narrative_differences(
    keyword: str, start: str = None, end: str = None
) -> dict:
    """Detect framing differences across platforms with human-readable interpretation."""
    # 1. Get platform-wise keyword data
    comparison = await compare_narratives(keyword, start, end, n=10)
    platforms = ["4chan", "mastodon", "truthsocial"]

    # 2. Filter platforms with enough posts (evidence threshold: 5 posts minimum)
    valid_platforms = []
    total_posts = 0
    for p in platforms:
        res = comparison[p]
        if res["total_posts"] >= 5:
            posts, _ = await search_posts(
                query=keyword, platform=p, start=start, end=end, limit=3
            )
            snippets = [post["content_text"] for post in posts]
            valid_platforms.append({
                "platform": p,
                "post_count": res["total_posts"],
                "top_keywords": [k["keyword"] for k in res["co_occurring"]],
                "snippets": snippets,
            })
            total_posts += res["total_posts"]

    if len(valid_platforms) < 2:
        return {
            "keyword": keyword,
            "status": "Insufficient Data",
            "message": "Insufficient data to compare narratives reliably.",
            "detail": (
                f"Fewer than 2 platforms had 5 or more posts mentioning \"{keyword}\". "
                "Try a more common keyword or wait for more data to be collected."
            ),
            "platforms": valid_platforms,
        }

    # 3. Calculate keyword overlap between platforms
    all_keywords = set()
    for vp in valid_platforms:
        all_keywords.update(vp["top_keywords"])

    if not all_keywords:
        overlap_ratio = 1.0
    else:
        shared_count = sum(
            1 for kw in all_keywords
            if sum(1 for vp in valid_platforms if kw in vp["top_keywords"]) >= 2
        )
        overlap_ratio = round(shared_count / len(all_keywords), 2)

    # 4. Classify based on overlap
    if overlap_ratio >= 0.50:
        status = "Similar Narrative"
    elif overlap_ratio >= 0.30:
        status = "Mildly Different Framing"
    else:
        status = "Distinct Framing"

    # 5. Confidence score
    post_score = min(25, total_posts // 10)
    snippet_score = 10 if any(vp["snippets"] for vp in valid_platforms) else 0
    confidence_score = min(95, 40 + len(valid_platforms) * 10 + post_score + snippet_score)

    # 6. Build interpretation layer (human-readable prose)
    interpretation = _build_interpretation(keyword, valid_platforms, status, overlap_ratio)

    return {
        "keyword": keyword,
        "status": status,
        "confidence_score": confidence_score,
        "overlap_ratio": overlap_ratio,
        # Interpretation layer — shown first in the UI
        "final_observation": interpretation["final_observation"],
        "plain_explanation": interpretation["plain_explanation"],
        "platform_interpretations": interpretation["platform_interpretations"],
        "why_this_conclusion": interpretation["why_this_conclusion"],
        # Supporting evidence — shown after interpretation
        "platforms": valid_platforms,
    }
