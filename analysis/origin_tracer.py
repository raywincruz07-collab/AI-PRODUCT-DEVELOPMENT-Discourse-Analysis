"""Narrative Origin Tracer - trace where a narrative began and how it spread."""

import json
from datetime import datetime, timezone, timedelta
from database.connection import get_backend, get_conn

async def trace_narrative_origin(keyword: str, platform: str = None, start: str = None, end: str = None) -> dict:
    """Find the origin and spread pattern of a keyword narrative."""
    backend = get_backend()
    
    # Base query for all posts containing the keyword
    where = ["content_text LIKE ?"] if backend == "sqlite" else ["content_text ILIKE $1"]
    params = [f"%{keyword}%"]
    
    if platform:
        where.append("platform = ?" if backend == "sqlite" else "platform = $2")
        params.append(platform)
        
    if start:
        where.append("posted_at >= ?" if backend == "sqlite" else f"posted_at >= ${len(params)+1}")
        params.append(start)
        
    if end:
        where.append("posted_at <= ?" if backend == "sqlite" else f"posted_at <= ${len(params)+1}")
        params.append(end)
        
    where_sql = " AND ".join(where)
    
    try:
        if backend == "sqlite":
            async with get_conn() as conn:
                rows = await (
                    await conn.execute(
                        f"SELECT id, platform, author, board_or_feed, posted_at, content_text, metadata_json, replies FROM posts WHERE {where_sql} ORDER BY posted_at ASC",
                        params,
                    )
                ).fetchall()
        else:
            async with get_conn() as conn:
                rows = await conn.fetch(
                    f"SELECT id, platform, author, board_or_feed, posted_at, content_text, metadata_json, replies FROM posts WHERE {where_sql} ORDER BY posted_at ASC",
                    *params,
                )
    except Exception as e:
        return {"keyword": keyword, "error": "INSUFFICIENT DATA", "message": f"Database error: {str(e)}"}

    if not rows or len(rows) < 3:
        return {
            "keyword": keyword,
            "error": "INSUFFICIENT DATA",
            "message": "Not enough collected posts to trace this narrative reliably."
        }

    # Step 1: Origin Post (first row)
    origin_row = rows[0]
    origin_id, origin_plat, origin_auth, origin_board, origin_at_raw, origin_text, origin_meta_raw, origin_replies = origin_row
    
    def parse_dt(raw):
        if isinstance(raw, str):
            dt_str = raw.replace(" ", "T").replace("Z", "+00:00")
            if "T" not in dt_str: dt_str += "T00:00:00"
            dt = datetime.fromisoformat(dt_str)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        return raw.replace(tzinfo=timezone.utc) if raw and raw.tzinfo is None else raw

    origin_at = parse_dt(origin_at_raw)

    origin_data = {
        "platform": origin_plat,
        "author": origin_auth,
        "board_or_feed": origin_board,
        "posted_at": origin_at.isoformat(),
        "content_snippet": origin_text[:140],
    }

    # Step 2 & 3: Spread Timeline and Amplifiers
    platforms_seen = {} # plat -> {'first': dt, 'count': int}
    amplifiers = []
    seen_authors = set()
    
    total_reach = 0
    has_follower_data = False

    for row in rows:
        _, plat, auth, _, at_raw, text, meta_raw, _ = row
        at = parse_dt(at_raw)
        
        # Timeline logic
        day_diff = (at - origin_at).days + 1
        if plat not in platforms_seen:
            platforms_seen[plat] = {"first_seen_day": day_diff, "first_seen_at": at.isoformat(), "total_posts": 0}
        platforms_seen[plat]["total_posts"] += 1
        
        # Amplifier logic
        # Exclude Anonymous from 4chan
        is_anon = (plat == "4chan" and (not auth or auth.lower() == "anonymous"))
        if not is_anon and auth not in seen_authors and len(amplifiers) < 5:
            seen_authors.add(auth)
            
            followers = None
            if meta_raw:
                try:
                    meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
                    followers = meta.get("followers_count")
                    if followers is not None:
                        total_reach += followers
                        has_follower_data = True
                except: pass
                
            amplifiers.append({
                "author": auth,
                "platform": plat,
                "posted_at": at.isoformat(),
                "day_number": day_diff,
                "followers": followers,
                "content_snippet": text[:120],
            })

    timeline = [
        {"platform": p, **data} for p, data in platforms_seen.items()
    ]
    timeline.sort(key=lambda x: x["first_seen_day"])

    # Step 4: Coordination Detection
    coordination_signal = "ORGANIC SPREAD"
    coordination_window = None
    
    # Take top amplifiers who are NOT from 4chan for timing check
    non_4chan_amps = [a for a in amplifiers if a["platform"] != "4chan"]
    if len(non_4chan_amps) >= 3:
        # Check if 3+ posted within 2 hour window on same day
        # Simplest: check min/max of first 3
        amps_dt = [parse_dt(a["posted_at"]) for a in non_4chan_amps]
        # Sort just in case (though amplifiers is already sorted)
        amps_dt.sort()
        
        # Check sliding window of 3
        for i in range(len(amps_dt) - 2):
            win_start = amps_dt[i]
            win_end = amps_dt[i+2]
            diff = (win_end - win_start).total_seconds() / 60
            if diff <= 120:
                coordination_signal = "POSSIBLE COORDINATED AMPLIFICATION"
                coordination_window = int(diff)
                break

    # Step 6: Data Quality Assessment
    data_quality = "Limited"
    plat_count = len(platforms_seen)
    post_count = len(rows)
    
    if plat_count >= 3 and post_count >= 50:
        data_quality = "Strong"
    elif plat_count >= 2 or post_count >= 20:
        data_quality = "Moderate"

    return {
        "keyword": keyword,
        "origin": origin_data,
        "spread_timeline": timeline,
        "top_amplifiers": amplifiers,
        "coordination_signal": coordination_signal,
        "coordination_window_minutes": coordination_window,
        "direct_reach": total_reach if has_follower_data else None,
        "data_quality": data_quality,
        "total_posts_found": len(rows),
        "limitation_note": "Analysis is based solely on posts collected by Discourse Analyzer. Collection gaps may affect accuracy of origin detection."
    }
