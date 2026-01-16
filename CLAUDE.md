# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**RalphOS** is an autonomous AI agent loop system that executes multi-step web scraping tasks without human intervention. It wraps Claude CLI in a bash loop, enabling fully autonomous execution of complex projects defined in JSON PRD (Product Requirements Document) format.

## Pipeline Architecture

RalphOS processes sources through a 3-stage pipeline:

```
Stage 1: URL Discovery    →  Stage 2: HTML Scraping    →  Stage 3: Data Extraction
(url-detective)              (html-scraper)               (data-extractor)
    ↓                            ↓                            ↓
urls.jsonl                  html/*.html                  builds.jsonl + mods.jsonl
```

Each stage has an independent runner in `scripts/ralph-stages/` with its own prompt.md and queue.json.

## Commands

### Running Ralph

```bash
# Standard Ralph loop (default 10 iterations)
./scripts/ralph/ralph.sh

# Custom iteration count
./scripts/ralph/ralph.sh 25

# Factory Ralph (production-grade with Git snapshots, JSONL logging, circuit breakers)
./scripts/ralph/run_factory_ralph.sh 25
./scripts/ralph/run_factory_ralph.sh 50 high   # auto_level: low/medium/high
```

### Testing & Validation

```bash
# Test URL discovery
python3 scripts/tools/test_url_discovery.py data/source_name/

# Test HTML scraper
python3 scripts/tools/test_scraper.py data/source_name/scrape_html.py

# Diagnose scraper issues
python3 scripts/tools/diagnose_scraper.py data/source_name/

# Validate outputs
python3 scripts/tools/validate_output.py data/source_name/
python3 scripts/tools/validate_builds.py data/source_name/
python3 scripts/tools/validate_stage.py data/source_name/
```

### Monitoring

```bash
# View real-time output
tail -f logs/ralph_output.log

# Check project status
cat scripts/ralph/prd.json | jq '.userStories[] | {id, title, passes}'

# View sources queue
cat scripts/ralph/sources.json | jq '.sources[] | {id, name, status}'

# Sync progress from disk
python3 scripts/tools/sync_progress.py
```

### Stealth Scraping

```bash
# Run Camoufox stealth scraper for anti-bot protected sites
python3 scripts/tools/stealth_scraper.py --source source_id
python3 scripts/tools/stealth_scraper.py --source source_id --limit 100

# Aggressive mode (more fingerprint rotation)
python3 scripts/tools/aggressive_stealth_scraper.py --source source_id
```

## Architecture

### Core Loop Flow

1. Read `scripts/ralph/prd.json` for pending tasks
2. Select highest priority story where `passes: false`
3. Execute using Claude CLI with instructions from `prompt.md`
4. Commit changes to git
5. Update `prd.json` to mark story complete
6. Append learnings to `progress.txt`
7. Repeat until all stories complete or max iterations reached

### Key Files

| File | Purpose |
|------|---------|
| `scripts/ralph/ralph.sh` | Main bash orchestration loop |
| `scripts/ralph/run_factory_ralph.sh` | Production-grade loop with circuit breakers |
| `scripts/ralph/prompt.md` | Agent behavior instructions |
| `scripts/ralph/prd.json` | Current project definition |
| `scripts/ralph/sources.json` | Multi-project queue |
| `scripts/ralph/progress.txt` | Accumulated learnings |
| `scripts/ralph/TOOLS.md` | Complete toolkit documentation |

### Stage Runners

| Stage | Directory | Output |
|-------|-----------|--------|
| URL Detective | `scripts/ralph-stages/url-detective/` | `urls.jsonl`, `urls_meta.json` |
| HTML Scraper | `scripts/ralph-stages/html-scraper/` | `html/*.html`, `scrape_progress.jsonl` |
| Data Extractor | `scripts/ralph-stages/data-extractor/` | `builds.jsonl`, `mods.jsonl` |

Each stage directory contains: `prompt.md`, `queue.json`, `progress.txt`

### Project Structure

```
RalphOS/
├── scripts/
│   ├── ralph/              # Core orchestration
│   │   ├── ralph.sh        # Main loop
│   │   ├── run_factory_ralph.sh  # Production loop
│   │   ├── prompt.md       # Agent instructions
│   │   ├── TOOLS.md        # Toolkit documentation
│   │   ├── ralph_utils.py  # Core utilities
│   │   ├── ralph_duckdb.py # Database ops
│   │   ├── ralph_vlm.py    # Vision analysis
│   │   ├── ralph_validator.py  # Visual validation
│   │   └── ralph_mcp.py    # MCP integration
│   │
│   ├── ralph-stages/       # Independent stage runners
│   │   ├── url-detective/
│   │   ├── html-scraper/
│   │   └── data-extractor/
│   │
│   ├── tools/              # Utility scripts
│   │   ├── build_id_generator.py
│   │   ├── category_detector.py
│   │   ├── stealth_scraper.py
│   │   ├── diagnose_scraper.py
│   │   └── browser/        # Chrome automation
│   │
│   └── dashboard/          # Monitoring UI
│
├── data/                   # Scraped data output
│   └── {source_name}/
│       ├── urls.jsonl
│       ├── html/
│       ├── builds.jsonl
│       └── mods.jsonl
│
├── input/                  # Source CSV files
├── schema/                 # Data schemas
├── logs/                   # Log files
└── archive/                # Blocked source data
```

## Enhanced Toolkit

Use these Python utilities instead of raw commands for robustness:

### ralph_utils.py - Core Utilities

```python
from ralph_utils import safe_write, safe_write_json, safe_read_json, logger
from ralph_utils import normalize_url, deduplicate_urls, get_robust_session

# Atomic, crash-safe file writes
safe_write_json("output.json", data)

# Structured logging (outputs to JSONL)
logger.info("Scraping started", {"source": "luxury4play"})

# URL operations
urls = deduplicate_urls(url_list)
clean_url = normalize_url(messy_url)

# HTTP with auto-retry
session = get_robust_session(retries=3)
```

### ralph_duckdb.py - Database Operations

```python
from ralph_duckdb import RalphDuckDB

db = RalphDuckDB("ralph_data.duckdb")
db.import_file("builds.json", "builds")
df = db.query_to_df("SELECT * FROM builds WHERE year > 2020")
db.export_table("builds", "output.parquet")
```

### ralph_validator.py - Visual Validation Gate

```python
from ralph_validator import RalphValidator

validator = RalphValidator()
result = validator.validate("screenshot.png", "Submit button is visible")
if result['passed']:
    create_success_file()
```

### Key Tool Scripts

| Script | Purpose |
|--------|---------|
| `build_id_generator.py` | Generate deterministic build_id from URL |
| `category_detector.py` | Auto-categorize modifications using Vehicle_Components.json |
| `stealth_scraper.py` | Camoufox anti-bot scraping with session rotation |

## Data Schema

Schema defined in `schema/build_extraction_schema.json`:

**Required fields:** `build_id`, `source_type`, `build_type`, `build_source`, `source_url`, `year`, `make`, `model`

**Modification Levels:**
- Stock: 0-1 mods
- Lightly Modified: 2-5 mods
- Moderately Modified: 6-15 mods
- Heavily Modified: 16+ mods

**Build Types:** OEM+, Street, Track, Drift, Rally, Time Attack, Drag, Show, Restomod, Pro Touring, Overland, Off-Road, etc.

## Browser Automation

Three methods available:

### 1. Chrome DevTools MCP (Recommended)
```
chrome_navigate - Navigate to URL
chrome_screenshot - Capture viewport
chrome_evaluate - Execute JavaScript
chrome_click - Click elements
```

### 2. Browser CLI Scripts
```bash
scripts/tools/browser/start.js --profile  # Start Chrome with logins
scripts/tools/browser/nav.js https://...  # Navigate
scripts/tools/browser/eval.js 'document.title'  # Execute JS
scripts/tools/browser/cookies.js           # Extract cookies
scripts/tools/browser/pick.js "Click button"  # Visual picker
```

### 3. Camoufox Stealth Browser
For anti-bot protected sites. Features:
- Anti-detection fingerprinting via BrowserForge
- Human-like cursor movement (`humanize=True`)
- WebRTC blocking to prevent IP leaks
- Session rotation every 50 pages
- Randomized delays: 2-5 seconds

## PRD Format

```json
{
  "projectName": "Project Name",
  "branchName": "main",
  "targetUrl": "https://example.com",
  "outputDir": "data/source_name",
  "userStories": [
    {
      "id": "US-001",
      "title": "Story title",
      "acceptanceCriteria": ["criteria 1", "criteria 2"],
      "priority": 1,
      "passes": false
    }
  ]
}
```

## Conventions

### Git Commits
Format: `feat: [ID] - [Title]`

### Progress Logging
```markdown
## [Date] - [Story ID]
- What was implemented
- Files changed
- **Learnings:** key discoveries
---
```

### Stop Conditions
- `RALPH_DONE` - All stories complete
- `URL_DETECTIVE_DONE` - Stage 1 complete
- `HTML_SCRAPER_DONE` - Stage 2 complete
- `DATA_EXTRACTOR_DONE` - Stage 3 complete
- `HTML_SCRAPER_BLOCKED` - Hit anti-bot protection

## Requirements

- **Claude CLI**: `npm install -g @anthropic-ai/claude-code`
- **jq**: For JSON parsing in bash
- **Python 3** with packages: `pip install -r requirements.txt`
- **Camoufox**: `pip install camoufox[geoip] && python3 -m camoufox fetch`
- **Node.js**: For browser automation scripts

## Safety Notes

- Ralph runs with `--dangerously-skip-permissions` - only use in trusted environments
- Rate limit: minimum 2-5 seconds between requests
- Monitor `logs/ralph_output.log` for progress and errors
- If blocked (403/429), stop immediately and mark source in sources.json
