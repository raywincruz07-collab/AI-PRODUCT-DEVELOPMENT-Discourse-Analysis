# Ethics and Compliance Statement

## Purpose and Research Intent

This prototype is developed for **academic research purposes** to support journalists and fact-checkers in understanding how conversations develop on alternative social media platforms. The system is designed to analyze publicly available discourse patterns, not to amplify, redistribute, or surveil content or users.

## Data Collection Principles

### 1. Public Data Only
- All data is collected exclusively from **publicly accessible** content
- 4chan posts are inherently public — no authentication is required or used
- Mastodon data is accessed via public API endpoints; authenticated access is only used when explicitly configured by the researcher
- Truth Social data is accessed via [truthbrush](https://github.com/stanfordio/truthbrush), an open-source academic research tool developed by the Stanford Internet Observatory. Only publicly visible posts (trending, hashtags) are collected
- No private messages, direct messages, or non-public content is collected

### 2. API Compliance
- **4chan**: Data is collected via the official read-only JSON API (`a.4cdn.org`) in compliance with their [API documentation](https://github.com/4chan/4chan-API). Rate limits (1 request/second) are strictly enforced. Attribution is provided as required ("Data sourced from 4chan.org")
- **Mastodon**: Data is accessed via Mastodon-compatible API endpoints. Standard rate limits (300 requests per 5 minutes) are respected using response header monitoring
- **Truth Social**: Data is accessed via truthbrush, which handles authentication and rate limiting internally. Only publicly visible content (trending posts, hashtag feeds) is collected. Credentials are stored locally in a `.env` file and never transmitted to third parties

### 3. No Media Download
- Media URLs (images, videos) are stored as **references only**
- No media content is downloaded, cached, or stored locally
- This minimizes storage footprint and avoids redistributing copyrighted or sensitive visual content

## Personally Identifiable Information (PII)

- **Usernames** are stored as they appear publicly on each platform
- 4chan posts are largely anonymous — the system does not attempt to deanonymize users
- No user profile scraping, follower list collection, or social graph construction is performed
- No cross-platform identity linking is attempted

## Content Warning

Data collected from these platforms **may contain**:
- Offensive, hateful, or extremist language
- Misinformation or conspiracy theories
- Graphic descriptions or references

This tool exists to **analyze** such content for research purposes, not to endorse, amplify, or redistribute it. Researchers should handle collected data with appropriate care and institutional review processes.

## Methodological Limitations

Researchers using this tool should be aware of the following limitations:

1. **Sampling Bias**: The system collects a sample, not a census. Collection gaps occur due to rate limits, API downtime, and timing
2. **4chan Ephemerality**: 4chan threads expire and are deleted. Posts not collected during their active period are permanently lost
3. **Mastodon Access**: Public API access may be restricted without authentication. Data completeness depends on platform policies at the time of collection
3a. **Truth Social Access**: Requires authenticated access via truthbrush. API availability and rate limits are subject to platform changes
4. **Temporal Coverage**: Data collection begins at system start — no historical data is backfilled unless the platform API supports it
5. **Content Parsing**: HTML stripping may lose formatting context (e.g., greentext quotes, embedded links) that carries semantic meaning
6. **Language**: Analysis is optimized for English-language content. Non-English posts may not be properly tokenized or analyzed
7. **No Sentiment/ML**: Analysis uses frequency-based methods (keyword counting, co-occurrence). No machine learning models are used, so nuance, sarcasm, and context may be missed

## Responsible Use Guidelines

- Use collected data for **research and journalism** purposes only
- Follow institutional review board (IRB) procedures when applicable
- Do not use this tool for harassment, doxxing, or targeting individuals
- Do not republish raw data in ways that could harm individuals
- Cite data sources and methodology transparently in any publications
- Consider the potential for harm when reporting on extremist content

## Data Retention

- Data is stored locally in a SQLite database file
- No data is transmitted to external services or cloud platforms
- Researchers are responsible for securely managing and eventually deleting collected data in accordance with their institutional data management policies

## Compliance Summary

| Aspect | Approach |
|--------|----------|
| Data Source | Public APIs only |
| Authentication | Optional for 4chan/Mastodon, required for Truth Social |
| Rate Limiting | Enforced per platform guidelines |
| PII Handling | Usernames only, no deanonymization |
| Media Content | URL references only, no downloads |
| Storage | Local SQLite, researcher-managed |
| Purpose | Academic research and journalism |
