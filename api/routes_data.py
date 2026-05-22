import csv
import io
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query, Response
from fastapi.responses import StreamingResponse
from database.queries import search_posts, get_post_by_id, get_stats, get_posts_for_export

router = APIRouter(prefix="/api", tags=["data"])


@router.get("/posts")
async def list_posts(
    keyword: Optional[str] = Query(None, description="Full-text search keyword"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    author: Optional[str] = Query(None, description="Filter by author"),
    board: Optional[str] = Query(None, description="Filter by board/feed"),
    start: Optional[str] = Query(None, description="Start date (ISO format)"),
    end: Optional[str] = Query(None, description="End date (ISO format)"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """List and search posts with filters."""
    posts, total = await search_posts(
        query=keyword,
        platform=platform,
        author=author,
        board=board,
        start=start,
        end=end,
        page=page,
        limit=limit,
    )
    return {"posts": posts, "total": total, "page": page, "limit": limit}


@router.get("/posts/{post_id}")
async def get_post(post_id: int):
    """Get a single post by ID."""
    post = await get_post_by_id(post_id)
    if not post:
        return {"error": "Post not found"}
    return post


@router.get("/stats")
async def stats():
    """Get collection statistics."""
    return await get_stats()


@router.get("/export")
async def export_data(
    platform: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    format: str = Query("csv", regex="^(csv|json)$"),
):
    """Export posts as CSV or JSON."""
    posts = await get_posts_for_export(platform=platform, start=start_date, end=end_date)

    if not posts:
        return Response(content="No data found for the selected filters.", status_code=404)

    # Format filename: discourse_export_<platform>_<start>_to_<end>.<ext>
    p_name = platform or "all"
    s_date = start_date or "earliest"
    e_date = end_date or "latest"
    filename = f"discourse_export_{p_name}_{s_date}_to_{e_date}.{format}"

    if format == "json":

        def json_serial(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError("Type %s not serializable" % type(obj))

        content = json.dumps(posts, default=json_serial)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    # CSV Export
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=posts[0].keys())
    writer.writeheader()
    writer.writerows(posts)

    return StreamingResponse(
        io.StringIO(output.getvalue()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
