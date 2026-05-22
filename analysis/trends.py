"""Trend analysis - post volume and trending term detection."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from database.connection import get_backend, get_conn
from analysis.keywords import tokenize, STOPWORDS, SPIKE_NOISE_WORDS

# In-memory cache: keeps detected spikes visible for SPIKE_HOLD_HOURS after first detection
# so they don't vanish the moment posts slide out of the recent window.
_spike_cache: dict = {}
SPIKE_HOLD_HOURS = 1


async def get_trending_terms(
    platform: str = None,
    recent_hours: int = 24,
    baseline_hours: int = 168,
    n: int = 20,
) -> list[dict]:
    """Find terms trending in the recent window vs baseline.

    Computes a simple ratio: (recent_freq / baseline_freq).
    High ratio = trending up. Only includes terms with >= 3 recent mentions.
    """
    backend = get_backend()

    if backend == "sqlite":
        where = []
        params_recent = []
        params_baseline = []
        if platform:
            where.append("platform = ?")
            params_recent.append(platform)
            params_baseline.append(platform)

        where_sql = " AND ".join(where) if where else "1=1"

        async with get_conn() as conn:
            recent_rows = await (
                await conn.execute(
                    f"""SELECT content_text, thread_id, author FROM posts
                        WHERE {where_sql}
                          AND posted_at >= datetime('now', '-{recent_hours} hours')""",
                    params_recent,
                )
            ).fetchall()

            baseline_rows = await (
                await conn.execute(
                    f"""SELECT content_text, thread_id, author FROM posts
                        WHERE {where_sql}
                          AND posted_at >= datetime('now', '-{baseline_hours} hours')
                          AND posted_at < datetime('now', '-{recent_hours} hours')""",
                    params_baseline,
                )
            ).fetchall()
    else:
        where = []
        params_recent = []
        params_baseline = []
        i = 1
        if platform:
            where.append(f"platform = ${i}")
            params_recent.append(platform)
            params_baseline.append(platform)
            i += 1

        where_sql = " AND ".join(where) if where else "TRUE"

        async with get_conn() as conn:
            # Recent window
            recent_rows = await conn.fetch(
                f"""SELECT content_text, thread_id, author FROM posts
                    WHERE {where_sql}
                      AND posted_at >= NOW() - INTERVAL '{recent_hours} hours'""",
                *params_recent,
            )

            # Baseline window
            baseline_rows = await conn.fetch(
                f"""SELECT content_text, thread_id, author FROM posts
                    WHERE {where_sql}
                      AND posted_at >= NOW() - INTERVAL '{baseline_hours} hours'
                      AND posted_at < NOW() - INTERVAL '{recent_hours} hours'""",
                *params_baseline,
            )

    # Deduplicate: count each word only once per (thread_id, author) combination
    # This stops one spammy user in one thread from inflating a trend
    recent_counter = Counter()
    recent_seen = {}
    for row in recent_rows:
        text = row[0]
        thread_id = row["thread_id"] if "thread_id" in row.keys() else ""
        author = row["author"] if "author" in row.keys() else ""
        dedup_key_prefix = f"{thread_id}_{author}"
        for word in tokenize(text):
            dedup_key = f"{dedup_key_prefix}_{word}"
            if dedup_key not in recent_seen:
                recent_seen[dedup_key] = True
                recent_counter[word] += 1

    baseline_counter = Counter()
    baseline_seen = {}
    for row in baseline_rows:
        text = row[0]
        thread_id = row["thread_id"] if "thread_id" in row.keys() else ""
        author = row["author"] if "author" in row.keys() else ""
        dedup_key_prefix = f"{thread_id}_{author}"
        for word in tokenize(text):
            dedup_key = f"{dedup_key_prefix}_{word}"
            if dedup_key not in baseline_seen:
                baseline_seen[dedup_key] = True
                baseline_counter[word] += 1

    # Calculate trending score
    trending = []
    total_recent = max(sum(recent_counter.values()), 1)
    total_baseline = max(sum(baseline_counter.values()), 1)

    for term, recent_count in recent_counter.items():
        if recent_count < 3:
            continue
        recent_freq = recent_count / total_recent
        baseline_freq = (baseline_counter.get(term, 0) + 1) / total_baseline
        score = recent_freq / baseline_freq
        trending.append(
            {
                "keyword": term,
                "count": recent_count,
                "score": round(score, 2),
            }
        )

    trending.sort(key=lambda x: x["score"], reverse=True)
    return trending[:n]


async def get_velocity_alerts(
    threshold: float = 3.0,
    min_mentions: int = 5,
    window_hours: int = 1,
    baseline_hours: int = 24,
    max_age_hours: int = 2,
    platform: str = None,
) -> list[dict]:
    """Detect keywords spiking in recent window vs baseline rate."""
    backend = get_backend()
    where = ["posted_at >= datetime('now', '-%d hours')" % baseline_hours] if backend == "sqlite" else ["posted_at >= NOW() - INTERVAL '%d hours'" % baseline_hours]
    params = []
    
    if platform:
        where.append("platform = ?") if backend == "sqlite" else where.append("platform = $1")
        params.append(platform)

    where_sql = " AND ".join(where)

    try:
        if backend == "sqlite":
            async with get_conn() as conn:
                rows = await (
                    await conn.execute(
                        f"SELECT content_text, platform, posted_at, thread_id, author FROM posts WHERE {where_sql}",
                        params,
                    )
                ).fetchall()
        else:
            async with get_conn() as conn:
                rows = await conn.fetch(
                    f"SELECT content_text, platform, posted_at, thread_id, author FROM posts WHERE {where_sql}",
                    *params,
                )
    except Exception as e:
        print(f"Query error: {e}")
        return []

    # Minimum data gate: too few posts → return a flag instead of fake alerts
    if len(rows) < 20:
        return [{"not_enough_data": True, "message": "Not enough posts collected yet to detect reliable spikes. Check back after more data is collected."}]

    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(hours=window_hours)
    max_age_cutoff = now - timedelta(hours=max_age_hours)

    # (keyword, platform) -> {'recent': int, 'baseline': int, 'first_seen': datetime}
    stats = {}
    # Deduplication: track (thread_id, author, word) so one spammy user
    # in one thread cannot inflate a velocity alert
    velocity_seen = {}

    for row in rows:
        text, plat, posted_at_raw = row[0], row[1], row[2]
        thread_id = row[3] if len(row) > 3 and row[3] else ""
        author = row[4] if len(row) > 4 and row[4] else ""
        dedup_prefix = f"{thread_id}_{author}"
        # Normalize posted_at
        try:
            if isinstance(posted_at_raw, str):
                # SQLite format: 2026-05-11 21:00:00 or ISO
                dt_str = posted_at_raw.replace(" ", "T").replace("Z", "+00:00")
                if "T" not in dt_str: # handle YYYY-MM-DD
                    dt_str += "T00:00:00"
                posted_at = datetime.fromisoformat(dt_str)
                if posted_at.tzinfo is None:
                    posted_at = posted_at.replace(tzinfo=timezone.utc)
            elif posted_at_raw:
                # Postgres datetime object
                posted_at = posted_at_raw.replace(tzinfo=timezone.utc)
            else:
                continue
        except Exception:
            continue

        words = tokenize(text)
        is_recent = posted_at >= recent_cutoff
        
        for w in words:
            # Skip if this (thread, author, word) combo already counted
            dedup_key = f"{dedup_prefix}_{w}"
            if dedup_key in velocity_seen:
                continue
            velocity_seen[dedup_key] = True

            key = (w, plat)
            if key not in stats:
                stats[key] = {'recent': 0, 'baseline': 0, 'first_seen': None}

            if is_recent:
                stats[key]['recent'] += 1
                if stats[key]['first_seen'] is None or posted_at < stats[key]['first_seen']:
                    stats[key]['first_seen'] = posted_at
            else:
                stats[key]['baseline'] += 1

    alerts = []
    baseline_window = float(max(baseline_hours - window_hours, 0.1))

    for (keyword, plat), data in stats.items():
        if len(keyword) < 4 or keyword in STOPWORDS or keyword in SPIKE_NOISE_WORDS:
            continue
            
        recent_count = data['recent']
        if recent_count < min_mentions:
            continue
            
        first_seen = data['first_seen']
        if first_seen and first_seen < max_age_cutoff:
            continue

        recent_rate = recent_count / window_hours
        baseline_count = data['baseline']
        baseline_rate = baseline_count / baseline_window
        # Floor scales with recent activity — stops brand-new words faking huge spikes
        baseline_rate = max(baseline_rate, recent_count * 0.2)

        spike_ratio = recent_rate / baseline_rate

        if spike_ratio >= threshold:
            alerts.append({
                "keyword": keyword,
                "recent_count": recent_count,
                "baseline_rate": round(baseline_rate, 2),
                "spike_ratio": round(spike_ratio, 2),
                "platform": plat,
                "first_seen_spike": first_seen.isoformat() if first_seen else None,
                "approximate": True
            })

    alerts.sort(key=lambda x: (x["recent_count"], x["spike_ratio"]), reverse=True)

    # ── Spike cache: keep each spike visible for SPIKE_HOLD_HOURS after first detection ──
    now_ts = datetime.now(timezone.utc)
    hold = timedelta(hours=SPIKE_HOLD_HOURS)

    # Register / refresh new alerts in cache
    for alert in alerts:
        key = (alert["keyword"], alert["platform"])
        if key not in _spike_cache:
            _spike_cache[key] = {"data": alert, "first_detected": now_ts}
        else:
            _spike_cache[key]["data"] = alert  # update with latest counts

    # Expire entries older than hold window
    for key in list(_spike_cache.keys()):
        if now_ts - _spike_cache[key]["first_detected"] > hold:
            del _spike_cache[key]

    # Merge live alerts with still-cached (but currently below threshold) spikes
    live_keys = {(a["keyword"], a["platform"]) for a in alerts}
    cached_extras = [
        v["data"] for k, v in _spike_cache.items() if k not in live_keys
    ]

    merged = alerts + cached_extras
    merged.sort(key=lambda x: (x["recent_count"], x["spike_ratio"]), reverse=True)
    return merged[:8]
