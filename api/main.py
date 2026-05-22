"""FastAPI application - main entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database.connection import init_db, close_db
from collectors.scheduler import run_collector_loop
from api.routes_data import router as data_router
from api.routes_analytics import router as analytics_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Start collector in background
    collector_task = asyncio.create_task(run_collector_loop())
    logger.info("Data collectors started")

    yield

    # Shutdown
    collector_task.cancel()
    try:
        await collector_task
    except asyncio.CancelledError:
        pass
    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Discourse Analyzer",
    description="Analyze discourse on alternative social platforms",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(data_router)
app.include_router(analytics_router)

# Serve frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
async def root():
    """Serve the frontend dashboard."""
    return FileResponse("frontend/index.html")
