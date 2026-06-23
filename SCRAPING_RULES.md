# Scraping Rules

Rules that apply to all scraping code in this project.

---

## Priority Order

Always try free methods first.

1. Public APIs / JSON endpoints
2. GraphQL APIs
3. Embedded application state (`__NEXT_DATA__`, `__STATE__`, etc.)
4. JSON-LD blocks
5. Crawl4AI
6. Playwright
7. Scrapling
8. BeautifulSoup + Requests
9. Bright Data MCP (only with explicit user approval)

---

## HTTP Rules

- Always set a realistic User-Agent header.
- Always set timeouts (default: 15s for discovery, 30s for extraction).
- Always follow redirects.
- Always handle errors gracefully — log and continue.
- Never crash the entire run on a single URL failure.

---

## Rate Limiting

- Add delays between requests when rate limiting is detected.
- Default delay: 1–2 seconds between requests.
- Increase to 5–10 seconds if rate limiting is detected.
- Use exponential backoff with `tenacity`.

---

## Logging

- Log every request attempt.
- Log every success and failure.
- Log every field extracted.
- Use `structlog` for all logging.

---

## Data Preservation

- Save raw source data before any processing.
- Never discard raw data even if structured parsing succeeds.
- Always store both `_raw` and `_structured` versions of complex fields.

---

## Code Style

- Use `async/await` for all I/O.
- Use `httpx.AsyncClient` (not `requests`) for HTTP.
- Use Pydantic models for all data structures.
- Use type hints everywhere.
- Keep functions small and focused.
- No monolithic scripts.

---

## Error Handling

Every extraction attempt must:

1. Catch all exceptions.
2. Log the error with context.
3. Record the failure in `ExtractionAttempt`.
4. Continue processing remaining URLs.
5. Never raise unhandled exceptions.

---

## Robots.txt

- Always fetch and store `robots.txt`.
- Do not bypass explicit `Disallow` rules for paths.
- If unsure whether a path is allowed, skip it and note it in the report.
