# Japan Job Crawler

An automated job crawler that aggregates listings from major Japanese hiring platforms — Indeed Japan, Wantedly, Rikunabi NEXT, doda, and Mynavi. It uses Playwright for real browser rendering, SQLite for local storage with URL deduplication, and supports CSV/JSON export along with a Web UI for visual task management.

> **Disclaimer**: This tool is intended for personal job search and research only. Please respect each site's Terms of Service and `robots.txt`. Do not use for commercial scraping or high-frequency requests.

---

## Features

- **Multi-site support** — Indeed, Wantedly, Rikunabi, doda, Mynavi (pluggable architecture)
- **Real browser rendering** — Playwright handles JavaScript-heavy pages and Cloudflare challenges
- **Human behavior simulation** — Random delays, mouse scrolling, and click patterns to reduce detection
- **Unified data model** — All sites produce a standard `JobInfo` structure
- **Deduplication & persistence** — SQLite storage with automatic URL-based deduplication
- **Export** — CSV (Excel-compatible) and JSON
- **Web UI** — Local dashboard at `http://localhost:8080` to configure and monitor crawls
- **REST API** — FastAPI endpoints for queries, stats, and export (`http://localhost:8000`)
- **Scheduled crawling** — Built-in interval-based scheduling

---

## Architecture

```
┌──────────────────────────────────────────────┐
│         main.py / webui.py / api.py          │
│           (CLI · Web UI · REST API)           │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│                 Scheduler                     │
│     Rate limiting · Task queue · Retries      │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│           Spider Layer (per-site)             │
│  IndeedSpider · WantedlySpider · Rikunabi …  │
└──────┬─────────────────────┬─────────────────┘
       │                     │
┌──────▼──────┐    ┌─────────▼────────┐
│   Fetcher   │    │     Parser       │
│ (Playwright)│    │ (lxml + BS4)     │
└──────┬──────┘    └─────────┬────────┘
       │                     │
       └──────────┬──────────┘
                  │
         ┌────────▼────────┐
         │     Storage      │
         │    (SQLite)      │
         └─────────────────┘
```

---

## Supported Sites

| Site | Anti-bot Difficulty | Data Quality | Notes |
|------|--------------------:|:------------:|-------|
| Indeed Japan | ★★★☆☆ | ★★☆☆☆ | Largest volume |
| Wantedly | ★★☆☆☆ | ★★★★☆ | IT / Startup focused |
| Rikunabi NEXT | ★★★★☆ | ★★★★☆ | High-quality direct listings |
| doda | ★★★☆☆ | ★★★★☆ | Rich job details |
| Mynavi | ★★★☆☆ | ★★★☆☆ | Traditional enterprise sector |

---

## Installation

**Requirements:** Python 3.11+ · Windows / macOS / Linux

```bash
git clone https://github.com/moiraroman/japan-job-crawler.git
cd japan-job-crawler

# (Recommended) Create a virtual environment
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

pip install -r requirements.txt
playwright install chromium
```

---

## Quick Start

### CLI

```bash
# Crawl all sites with default keywords
python main.py

# Target specific sites
python main.py --sites indeed_jp wantedly

# Custom keywords and locations
python main.py --keywords "Python engineer" "Web developer" --locations "Tokyo" "Osaka"

# Limit pages per site
python main.py --max-pages 3

# Show browser window (for debugging)
python main.py --headed

# Dry run — no data saved
python main.py --dry-run
```

### Web UI

```bash
python webui.py
# Open http://localhost:8080 in your browser
```

### REST API

```bash
python api.py
# Swagger docs at http://localhost:8000/docs
```

### Scheduled Crawling

```bash
# Run every 6 hours
python main.py --schedule --interval 6
```

### Export

```bash
python main.py --export-csv output/jobs.csv
python main.py --export-json output/jobs.json
python main.py --export-csv output/wantedly.csv --sites wantedly
```

---

## Project Structure

```
japan-job-crawler/
├── main.py                    # CLI entry point
├── webui.py                   # Web UI server  (port 8080)
├── api.py                     # FastAPI server (port 8000)
├── scheduler.py               # Task scheduler
├── test_crawler.py            # Integration tests
├── verify.py                  # Config validation
├── requirements.txt
├── README.md
├── DESIGN.md                  # Product design document
├── config/
│   ├── settings.py            # Site configs & global settings
│   └── __init__.py
├── fetcher/
│   ├── browser_fetcher.py     # Playwright wrapper
│   └── __init__.py
├── parser/
│   ├── html_parser.py         # Per-site HTML parsers
│   └── __init__.py
├── spiders/
│   ├── base_spider.py         # Base spider class
│   ├── mynavi_spider.py       # Mynavi spider
│   └── __init__.py
├── storage/
│   ├── db.py                  # SQLite operations
│   └── __init__.py
├── webui_templates/           # Jinja2 templates
├── webui_static/              # CSS / JS assets
└── data/                      # Database & export directory
```

---

## Data Model

```python
@dataclass
class JobInfo:
    title: str           # Job title
    company: str         # Company name
    location: str        # Work location
    salary: str          # Salary range
    employment_type: str # Employment type (full-time, contract, etc.)
    description: str     # Job description
    requirements: str    # Requirements
    url: str             # Detail page URL (unique key for dedup)
    source: str          # Source site name
    posted_date: str     # Posting date
```

---

## Adding a New Site

1. Add site configuration in `config/settings.py`
2. Implement a parser in `parser/html_parser.py`
3. Create a spider class in `spiders/base_spider.py`

See `DESIGN.md` for detailed instructions.

---

## License

MIT License — For learning and personal use only. Commercial use is prohibited.
