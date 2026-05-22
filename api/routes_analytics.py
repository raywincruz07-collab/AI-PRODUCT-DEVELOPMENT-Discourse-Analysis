"""Analytics API routes - trends, keywords, narratives."""

from collections import defaultdict
import time

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional

from database.queries import get_post_volume
from analysis.keywords import get_top_keywords, get_keyword_frequency
from analysis.trends import get_trending_terms, get_velocity_alerts
from analysis.narratives import get_cooccurrence, compare_narratives, detect_narrative_differences
from analysis.origin_tracer import trace_narrative_origin
from analysis.network import get_reply_network, get_top_authors, get_thread_activity
from analysis.qa import answer_from_posts
from analysis.report_generator import generate_report
from config import ALERT_SPIKE_THRESHOLD, ALERT_MIN_MENTIONS, ALERT_WINDOW_HOURS, ALERT_BASELINE_HOURS, ALERT_MAX_AGE_HOURS

router = APIRouter(prefix="/api", tags=["analytics"])

# ── In-memory rate limiter (no Redis required) ──────────────────────────────
_request_counts: defaultdict = defaultdict(list)


def check_rate_limit(client_ip: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    """Return True if request is within limit, False if rate limit exceeded."""
    now = time.time()
    # Remove timestamps outside the window
    _request_counts[client_ip] = [
        t for t in _request_counts[client_ip]
        if now - t < window_seconds
    ]
    if len(_request_counts[client_ip]) >= max_requests:
        return False
    _request_counts[client_ip].append(now)
    return True


# ── QA Request schema ───────────────────────────────────────────────────────
class QARequest(BaseModel):
    question: str
    platform: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None


class ReportRequest(BaseModel):
    question: str
    platform: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    qa_answer: Optional[dict] = None


@router.get("/alerts/velocity")
async def velocity_alerts(
    threshold: float = Query(ALERT_SPIKE_THRESHOLD),
    platform: Optional[str] = Query(None),
    window_hours: int = Query(ALERT_WINDOW_HOURS),
):
    """Get real-time keyword velocity alerts (spikes)."""
    return await get_velocity_alerts(
        threshold=threshold,
        min_mentions=ALERT_MIN_MENTIONS,
        window_hours=window_hours,
        baseline_hours=ALERT_BASELINE_HOURS,
        max_age_hours=ALERT_MAX_AGE_HOURS,
        platform=platform
    )


@router.get("/trends/volume")
async def post_volume(
    platform: Optional[str] = Query(None),
    granularity: str = Query("hour", pattern="^(hour|day|week)$"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    """Get post volume over time."""
    return await get_post_volume(platform, granularity, start, end)


@router.get("/trends/keywords")
async def trending_keywords(
    platform: Optional[str] = Query(None),
    recent_hours: int = Query(24, ge=1),
    baseline_hours: int = Query(168, ge=1),
    n: int = Query(20, ge=1, le=100),
):
    """Get trending keywords (spiking relative to baseline)."""
    return await get_trending_terms(platform, recent_hours, baseline_hours, n)


@router.get("/keywords/top")
async def top_keywords(
    platform: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    n: int = Query(50, ge=1, le=200),
):
    """Get most frequent keywords."""
    return await get_top_keywords(platform, start, end, n)


@router.get("/keywords/frequency")
async def keyword_frequency(
    keyword: str = Query(..., description="Keyword to track"),
    platform: Optional[str] = Query(None),
    granularity: str = Query("day", pattern="^(hour|day|week)$"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    """Get frequency of a specific keyword over time."""
    return await get_keyword_frequency(keyword, platform, granularity, start, end)


@router.get("/narratives/cooccurrence")
async def narrative_cooccurrence(
    keyword: str = Query(..., description="Seed keyword"),
    platform: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    n: int = Query(20, ge=1, le=100),
):
    """Get terms that co-occur with a seed keyword."""
    return await get_cooccurrence(keyword, platform, start, end, n)


@router.get("/narratives/compare")
async def narrative_compare(
    keyword: str = Query(..., description="Keyword to compare across platforms"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    n: int = Query(15, ge=1, le=50),
):
    """Compare how a keyword's narrative differs across platforms."""
    return await compare_narratives(keyword, start, end, n)


@router.get("/narratives/differences")
async def narrative_differences(
    keyword: str = Query(..., min_length=1, description="Seed keyword"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    """Detect narrative differences across platforms based on collected data."""
    return await detect_narrative_differences(keyword, start, end)


@router.get("/narratives/origin")
async def narrative_origin(
    keyword: str = Query(..., min_length=1),
    platform: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    """Trace the origin and spread timeline of a keyword narrative."""
    if not keyword or len(keyword.strip()) < 2:
        raise HTTPException(status_code=400, detail="Keyword too short")
        
    try:
        return await trace_narrative_origin(keyword.strip(), platform, start, end)
    except Exception as e:
        # Catch all and return insufficient data to avoid 500s as requested
        return {
            "keyword": keyword,
            "error": "INSUFFICIENT DATA",
            "message": f"Trace could not be completed: {str(e)}"
        }


@router.get("/network/graph")
async def network_graph(
    platform: Optional[str] = Query(None),
    board: Optional[str] = Query(None),
    limit: int = Query(100, ge=10, le=500),
):
    """Get reply network graph (nodes=authors, edges=co-thread participation)."""
    return await get_reply_network(platform, board, limit)


@router.get("/network/authors")
async def top_authors(
    platform: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Get most active authors."""
    return await get_top_authors(platform, limit)


@router.get("/network/threads")
async def active_threads(
    platform: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Get most active threads by reply count."""
    return await get_thread_activity(platform, limit)


@router.post("/qa/answer")
async def qa_answer(body: QARequest, request: Request):
    """Answer a question based strictly on collected posts."""
    client_ip = request.client.host if request.client else "unknown"

    # Rate limit: 10 requests per minute per IP
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait before submitting another question.",
        )

    # Validate question length
    if not body.question or len(body.question.strip()) < 5:
        raise HTTPException(
            status_code=400,
            detail="Question too short. Please enter a full question.",
        )

    result = await answer_from_posts(
        question=body.question.strip(),
        platform=body.platform or None,
        start=body.start or None,
        end=body.end or None,
    )
    return result


@router.post("/qa/create-report")
async def create_report(body: ReportRequest, request: Request):
    """Generate a structured journalist-ready public discourse report."""
    client_ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(client_ip, max_requests=5, window_seconds=60):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait before generating another report.",
        )

    if not body.question or len(body.question.strip()) < 5:
        raise HTTPException(
            status_code=400,
            detail="Question too short. Please enter a full question or topic.",
        )

    # Use the QA answer already shown in the dashboard to keep verdict consistent.
    # Only recompute if the frontend didn't send one.
    if body.qa_answer:
        qa_answer = body.qa_answer
    else:
        qa_answer = await answer_from_posts(
            question=body.question.strip(),
            platform=body.platform or None,
            start=body.start or None,
            end=body.end or None,
        )

    report = await generate_report(
        question=body.question.strip(),
        qa_answer=qa_answer,
        platform=body.platform or None,
        start=body.start or None,
        end=body.end or None,
    )
    return report
