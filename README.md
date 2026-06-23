# Reference DB Intelligence Agent

An OpenCode-powered agent for discovering and extracting product data from Canadian grocery websites.

Built for the **Reference DB** project — a reliable database of Canadian food products.

---

## Quick Start

```bash
# Install dependencies
uv sync

# Install Playwright browsers
uv run playwright install chromium

# Copy environment file
cp .env.example .env

# Run the agent
uv run rdai run --url https://voila.ca

# Discovery only (no extraction)
uv run rdai discover --url https://voila.ca

# Extract specific fields
uv run rdai run --url https://voila.ca --fields barcode,brand,product_name

# Limit extraction
uv run rdai run --url https://voila.ca --max-products 500
```

---

## Project Structure

```
reference-db-intelligence-agent/
├── AGENTS.md               # OpenCode agent instructions
├── PROJECT_CONTEXT.md      # Project background
├── SCRAPING_RULES.md       # Rules for all scraping code
├── opencode.json           # OpenCode configuration
├── pyproject.toml          # Python dependencies
├── .env.example            # Environment variables template
│
├── src/
│   ├── cli.py              # CLI entry point (rdai command)
│   ├── run_manager.py      # Orchestrates full pipeline
│   ├── models/
│   │   ├── product.py      # RawProduct data model
│   │   ├── run.py          # RunConfig, RunContext
│   │   └── intelligence.py # WebsiteIntelligence, ApiEndpoint, etc.
│   ├── discovery/
│   │   └── discoverer.py   # robots.txt, sitemaps, API discovery
│   ├── protection/
│   │   └── analyzer.py     # Cloudflare, CAPTCHA, bot detection
│   ├── extractors/
│   │   ├── base.py         # BaseExtractor
│   │   ├── json_ld.py      # JSON-LD extractor (priority 1)
│   │   └── playwright_extractor.py  # Playwright extractor (priority 2)
│   └── reports/
│       └── generator.py    # Markdown report generator
│
├── runs/                   # One folder per run
│   └── 2026-06-22_abc123/
│       ├── report.md
│       ├── raw_products.jsonl
│       ├── website_intelligence.json
│       ├── sitemaps.json
│       ├── protection_analysis.json
│       ├── coverage_report.json
│       ├── statistics.json
│       └── logs.json
│
└── artifacts/              # Reusable artifacts across runs
```

---

## Extraction Priority

The agent always tries free methods first:

| Priority | Method | When Used |
|----------|--------|-----------|
| 1 | JSON-LD | Always (fastest) |
| 2 | Playwright | JS-rendered pages |
| 3 | Crawl4AI | Dynamic content |
| 4 | Scrapling | Anti-bot evasion |
| 5 | BeautifulSoup | Simple HTML |
| 6 | Bright Data MCP | Last resort (requires `--bright-data`) |

---

## Run Artifacts

Every run saves:

| File | Contents |
|------|----------|
| `report.md` | Full human-readable run report |
| `raw_products.jsonl` | All extracted products (JSONL) |
| `website_intelligence.json` | All discovered APIs, sitemaps, protections |
| `protection_analysis.json` | Protection mechanisms detected |
| `sitemaps.json` | Discovered sitemaps |
| `coverage_report.json` | Field coverage statistics |
| `statistics.json` | Run statistics |
| `logs.json` | Full event log |

---

## Data Principles

- **No normalization** — data preserved exactly as found on source
- **No enrichment** — no external data added
- **Transparency** — missing values stay missing
- **Reusability** — every discovery saved for future runs

---

## Adding New Extractors

1. Create `src/extractors/your_extractor.py`
2. Inherit from `BaseExtractor`
3. Implement `extract(urls) -> tuple[list[RawProduct], ExtractionAttempt]`
4. Add to extraction priority order in `src/run_manager.py`
