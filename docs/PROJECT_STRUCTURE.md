# Project Structure - Discourse Analyzer

Welcome to the official developer documentation for the **Discourse Analyzer** codebase. This document outlines the structural layout of the repository, folder responsibilities, privacy considerations, and run guidelines.

## 1. Directory Structure

Below is the directory tree of the cleaned, flattened repository:

```
discourse-analyzer/
├── analysis/           # Keyword, narrative, and network analysis engines
├── api/                # FastAPI backend routers, schemas, and entry point
├── collectors/         # Social platform web scraper modules and scheduler
├── database/           # Relational schema mappings and connection pools
├── frontend/           # Plain HTML5/Vanilla JS/CSS dashboard code
├── ethics/             # System ethics declaration guidelines
├── tests/              # Pytest automated integration test suite
├── docs/               # System and architecture documentation
├── data/               # Persistent SQLite local database cache directory (gitignored)
├── exports/            # Formatted data exports directory (gitignored)
├── config.py           # Configuration management using environment variables
├── run.py              # Application main startup runner script
├── requirements.txt    # Declared Python dependencies
├── README.md           # Master project overview
├── .env.example        # Environment variable configuration template
└── .gitignore          # Repository gitignore policies
```

---

## 2. Folder Purviews

- **`analysis/`**: Responsible for calculating mathematical trends, identifying narrative co-occurrence patterns across multiple platforms, evaluating active participant networks, tracking origin sources chronologically, and running LLM-based QA reports.
- **`api/`**: Sets up the FastAPI service, configures CORS, serves static frontend assets, and exposes public JSON endpoints for the dashboard under `/api/posts`, `/api/stats`, `/api/keywords`, `/api/narratives`, and `/api/alerts`.
- **`collectors/`**: Executes recurring background cron tasks to ingest public data from alternative networks (4chan, Mastodon, and Truth Social). Includes a rate-limited scheduler to avoid overloading target networks.
- **`database/`**: Orchestrates database connections. Supports SQLite for rapid local testing and PostgreSQL for scaling with structured index vectors.
- **`frontend/`**: The web application dashboard. Serves standard HTML, CSS styles, and vanilla Javascript. Connects asynchronously with backend endpoints.
- **`ethics/`**: Houses policy descriptions regarding safe data handling and ethical public scraping methodologies.
- **`tests/`**: Contains automated integration tests validating database schema queries, collection schedulers, narrative calculations, and API routes.

---

## 3. Data & Privacy Policy

> [!IMPORTANT]
> **Discourse Analyzer** is strictly dedicated to analyzing **public discourse** on social media platforms.
> - Under no circumstances should private, hidden, paywalled, or restricted content be collected, processed, or stored.
> - No personal identifiable information (PII) other than public platform handles should be tracked.
> - The collection scheduler must adhere to rate limits (e.g., 1.1 seconds between requests for 4chan) to behave ethically.

---

## 4. Git Security Warning

> [!WARNING]
> **NEVER** commit your local `.env` configuration file, secrets, API credentials (e.g., `ANTHROPIC_API_KEY`), or database files (`discourse.db`, `test_velocity.db`, `test_origin.db`, etc.) to the Git repository.
> 
> The `.gitignore` file is fully configured to catch and ignore all database files, environment credentials, caches (`__pycache__/`, `.pytest_cache/`), and exports. Always ensure you only share the configuration template `.env.example`.

---

## 5. Basic Run Instructions

### Prerequisites
- Python 3.10+
- SQLite (or PostgreSQL)

### Setup & Launch

1. **Install Dependencies**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in the values:
   ```bash
   cp .env.example .env
   ```

3. **Run the Application**:
   ```bash
   python run.py
   ```
   The API backend will start, and the frontend dashboard will be available at `http://127.0.0.1:8000/`.
