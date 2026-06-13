# Discourse Analyzer

**Discourse Analyzer** is a research-oriented web application designed to collect, process, and analyze public text discourse from decentralized and alternative social platforms, including **4chan**, **Mastodon**, and **Truth Social**. 

Developed to support journalists, political scientists, and information integrity researchers, the platform identifies high-velocity narrative spikes, charts cross-platform propagation, maps author networks, and generates automated, context-aware analysis reports.

---

## Architecture Flow

The system operates across a modular, multi-tier asynchronous architecture:

```mermaid
flowchart LR
    A[Collectors<br>4chan, Mastodon] --> B[(Database<br>SQLite/PostgreSQL)]
    B --> C[Analysis Engines<br>Trends, QA]
    C --> D[FastAPI Backend<br>JSON REST]
    D --> E[Frontend Web UI<br>Vanilla JS]
```

1. **Collectors**: Background worker threads running on a rate-limited scheduler ingest public feeds.
2. **Database**: Thread-safe relational data engines with support for SQL engines (SQLite locally, PostgreSQL for enterprise deployments).
3. **Analysis Modules**: Algorithms that compute token distributions, phrase co-occurrences, time-series velocities, and origin trace records.
4. **FastAPI Backend**: A performant async framework that serves analytics JSON payloads and handles background tasks.
5. **Frontend Dashboard**: A responsive, rich HTML/JS client displaying plots, graphs, and export panels.

---

## Implementation Status

| Component | Status |
|---|---|
| Database layer | Locally validated |
| Analysis modules | Locally validated |
| FastAPI backend | Locally validated |
| Collectors | Present in codebase; external integration validation pending |
| Frontend dashboard | Present in codebase; manual UI validation pending |
| AI-powered Q&A | Present in codebase; requires API credentials; end-to-end validation pending |
| Tests | 31 tests passed locally |
| Live deployment | Not deployed |

## Core System Modules

- **Post Explorer**: Allows researchers to search and filter aggregated public posts by platform, keyword, author, and time window.
- **Trends Dashboard**: Identifies trending keywords and alerts researchers to high-velocity narrative spikes using time-series baseline analytics.
- **Narrative Explorer**: Details keyword association networks using co-occurrence matrices, showcasing how distinct concepts cluster together on different platforms.
- **Origin Tracer**: Traces the path of a narrative across alternative media platforms. Analyzes publication timestamps to outline which platform hosted the early mentions of a narrative and how it spread.
- **Ask the Data (AI-Powered Q&A)**: Leverages LLM retrieval-augmented generation to write detailed, citation-backed analytical summaries about trends in the dataset.
- **Data Export Suite**: Supports exporting filtered subsets of data directly in structured JSON or CSV format for further analysis in external statistical suites (R, Pandas).

---

## Getting Started & Local Setup

### Prerequisites
- **Python**: version 3.10 or higher
- **Database**: SQLite (built-in) or PostgreSQL

### 1. Installation

Clone and install dependencies inside a Python virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuration (`.env`)

Discourse Analyzer is managed entirely through environment variables. Copy the provided configuration template:
```bash
cp .env.example .env
```

Open `.env` and fill in the parameters. Key configuration gates include:
- `DB_BACKEND`: Set to `sqlite` for zero-configuration setup, or `postgresql` for production.
- `FOURCHAN_BOARDS`: Comma-separated list of boards to scan (e.g., `pol,news,biz`).
- `ANTHROPIC_API_KEY`: Required to enable the **Ask the Data** semantic Q&A report generation.
- `SERVER_PORT`: Target local port (defaults to `8000`).

---

## Running Locally

To start the collectors scheduler and FastAPI server:
```bash
python run.py
```

The system will:
1. Initialize connection pools to the designated SQL database.
2. Spawn background scrapers for the selected platforms.
3. Serve the web application at `http://127.0.0.1:8000/`.

To run the automated integration tests:
```bash
pytest
```

---

## Ethics & Privacy Policy

Information integrity research demands the highest ethical standards:
- **Strictly Public Data Only**: The scrapers only read public, non-authenticated boards and public hashtags. Private profiles, restricted channels, or paywalled networks are never scanned.
- **Rate Limit Compliance**: Collectors adhere to API guidelines and rate limiters (e.g., 1.1s request throttling for 4chan) to respect target platform infrastructure.
- **No PII Collection**: The system tracks public user handles and post contents; no real names, private messages, or geo-location records are collected.

---

## System Limitations & Future Roadmaps

### Current Limitations
- **API Dependencies**: Scraping libraries for dynamic social platforms depend on external website layouts and are subject to upstream breakage when platform structures change.
- **LLM Rate Limits**: Massive batch reports using the Claude API can trigger rate limits under high-concurrency requests.

### Future Enhancements
- **Dynamic Network Graphs**: Transitioning static networks to real-time interactive D3.js topologies.
- **Vector Space Embeddings**: Introducing transformer-based semantic embeddings to cluster conceptually identical posts regardless of specific keyword variations.
