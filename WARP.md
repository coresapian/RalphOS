# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**RalphOS** is an autonomous AI agent loop system that executes multi-step web scraping tasks without human intervention. It wraps Claude CLI in a bash loop, processing tasks defined in JSON PRD format through a 4-stage pipeline for vehicle build data extraction.

## Commands

### Running Ralph

```bash
# Run with default 10 iterations
./scripts/ralph/ralph.sh

# Run with custom iteration count
./scripts/ralph/ralph.sh 25

# Scrape-only mode (skip extraction stages)
./scripts/ralph/ralph.sh 25 --scrape-only
```

### Testing

```bash
# Run full test suite
./tests/run_tests.sh

# Run individual tests
python3 tests/test_checkpoint_manager.py -v
python3 tests/test_source_discovery.py -v
python3 tests/test_parallel_processor.py -v
python3 tests/test_integration.py -v

# Stage-specific validation
python scripts/tools/test_url_discovery.py data/{source}/     # Stage 1
python scripts/tools/test_scraper.py data/{source}/scrape_html.py  # Stage 2
```

### Monitoring & Diagnostics

```bash
# View logs
cat logs/ralph_output.log

# Check project status
cat scripts/ralph/prd.json | jq '.userStories[] | {id, title, passes}'

# Diagnose scraper issues
python scripts/tools/diagnose_scraper.py data/{source}/

# Sync progress from disk
python scripts/tools/sync_progress.py
```

### Browser Automation

```bash
# Start Chrome with user profile (cookies, logins)
./scripts/tools/browser/start.js --profile

# Navigate / execute JS / screenshot
./scripts/tools/browser/nav.js https://example.com
./scripts/tools/browser/eval.js 'document.querySelectorAll("a").length'
./scripts/tools/browser/screenshot.js
```

## Architecture

### 4-Stage Pipeline

Each source goes through these stages sequentially:

1. **URL Discovery** (`scripts/ralph-stages/url-detective/`) - Find all content URLs from gallery/listing pages
2. **HTML Scraping** (`scripts/ralph-stages/html-scraper/`) - Download HTML for each discovered URL
3. **Build Extraction** (`scripts/ralph-stages/build-extractor/`) - Extract structured vehicle build data
4. **Mod Extraction** (`scripts/ralph-stages/mod-extractor/`) - Extract modification details

### Core Loop Flow

1. Read `scripts/ralph/prd.json` for pending tasks
2. Select highest priority story where `passes: false`
3. Execute via Claude CLI with `scripts/ralph/prompt.md` instructions
4. Commit changes, update PRD, append learnings to `progress.txt`
5. Repeat until all stories complete or max iterations reached
6. Archive completed project, pick next source from `sources.json`

### Key Files

| File | Purpose |
|------|---------|
| `scripts/ralph/ralph.sh` | Main bash orchestration loop |
| `scripts/ralph/prompt.md` | Agent behavior instructions |
| `scripts/ralph/prd.json` | Current project tasks (user stories) |
| `scripts/ralph/progress.txt` | Accumulated learnings across iterations |
| `scripts/ralph/sources.json` | Multi-project queue with pipeline status |
| `schema/build_extraction_schema.json` | Output format for extracted builds |

### Factory Ralph Tools (`scripts/ralph/`)

| Module | Purpose |
|--------|---------|
| `ralph_utils.py` | Safe file I/O, logging, HTTP sessions, URL normalization |
| `ralph_duckdb.py` | DuckDB database operations |
| `ralph_vlm.py` | Vision/image analysis via Moondream |
| `ralph_validator.py` | Visual validation gate |

### Output Structure

```
data/{source_name}/
├── urls.json           # Discovered URLs (Stage 1)
├── html/               # Saved HTML files (Stage 2)
├── builds.json         # Extracted build data (Stage 3)
├── mods.json           # Extracted modifications (Stage 4)
└── scrape_progress.json
```

## Important Conventions

### Tool Usage Rules

- **File I/O**: Always use `ralph_utils.safe_write()` / `safe_read_json()` - never raw `open()`
- **Logging**: Use `logger.info()` / `logger.error()` - never `print()`
- **HTTP**: Use `ralph_utils.get_robust_session()` for auto-retry
- **DuckDB**: Use `GROUP BY ALL` for aggregations
- **Build IDs**: Generate via `python scripts/tools/build_id_generator.py {url}`
- **Mod Categories**: Use `from category_detector import detect_category`

### Git Commits

Format: `feat: [Story ID] - [Title]`

### Stop Condition

When all stories have `passes: true`, output `RALPH_DONE` to signal completion.

### Validation Before Completion

**Never mark stories as `passes: true` unless validation tests pass:**

```bash
# Stage 1: URL discovery must pass
python scripts/tools/test_url_discovery.py data/{source}/

# Stage 2: Scraper must pass (script exists AND progress >= 95%)
python scripts/tools/test_scraper.py data/{source}/scrape_html.py
```

## Dependencies

- **Claude CLI**: `npm install -g @anthropic-ai/claude-code`
- **jq**: JSON parsing in bash
- **Python 3**: With packages in `requirements.txt` (requests, beautifulsoup4, camoufox, playwright)
- **Node.js**: Browser automation scripts
- **Bash 4+**: Loop script
