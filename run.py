"""Entry point - starts the Discourse Analyzer (API server + data collectors)."""

from pathlib import Path
import os
import uvicorn
import config

if __name__ == "__main__":
    # Ensure working directory is the project root so relative paths (frontend/)
    # resolve correctly even when running this script from elsewhere.
    os.chdir(Path(__file__).resolve().parent)

    print("=" * 60)
    print("  Discourse Analyzer - Alternative Social Platforms")
    print("=" * 60)
    print(f"  Dashboard: http://{config.SERVER_HOST}:{config.SERVER_PORT}")
    print(f"  API Docs:  http://{config.SERVER_HOST}:{config.SERVER_PORT}/docs")
    backend_label = (
        "SQLite"
        if config.DB_BACKEND == "sqlite"
        else f"PostgreSQL on {config.DB_HOST}:{config.DB_PORT}"
    )
    print(f"  Database:  {backend_label}")
    print(f"  4chan boards: {', '.join(config.FOURCHAN_BOARDS)}")
    print(
        f"  Mastodon token: {'configured' if config.MASTODON_ACCESS_TOKEN else 'not set (public only)'}"
    )
    ts_creds = config.TRUTHSOCIAL_TOKEN or (
        config.TRUTHSOCIAL_USERNAME and config.TRUTHSOCIAL_PASSWORD
    )
    print(
        f"  Truth Social:  {'configured' if ts_creds else 'NOT SET - set TRUTHSOCIAL_USERNAME + TRUTHSOCIAL_PASSWORD'}"
    )
    print("=" * 60)

    uvicorn.run(
        "api.main:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=False,
        log_level="info",
    )
