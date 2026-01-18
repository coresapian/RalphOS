# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**RalphOS** is an autonomous AI agent loop system that executes multi-step web scraping tasks without human intervention. It wraps Claude CLI in a bash loop, enabling fully autonomous execution of complex projects defined in JSON PRD (Product Requirements Document) format.

The system iterates through user stories, implements solutions, commits changes, and learns from each iteration. It's designed for web scraping with a 4-stage pipeline architecture but can handle any multi-step automation task.

## Commands

### Running Ralph

```bash
# Run with default 10 iterations (Classic mode - all 4 stages sequentially)
./scripts/ralph/ralph.sh

# Run with custom iteration count
./scripts/ralph/ralph.sh 25
./scripts/ralph/ralph.sh 50

# Scrape-only mode (stages 1-2 only)
./scripts/ralph/ralph.sh 25 --scrape-only

# Pipeline mode (parallel execution)
./scripts/ralph/ralph.sh --pipeline source_name
./scripts/ralph/ralph.sh --pipeline-all
```

### Monitoring

```bash
# View real-time output log
cat logs/ralph_output.log

# Check current project status
cat scripts/ralph/prd.json | jq '.userStories[] | {id, title, passes}'

# View accumulated learnings and patterns
cat scripts/ralph/progress.txt

# View sources queue with pipeline status
cat scripts/ralph/sources.json | jq '.sources[]'

# Monitor specific source pipeline
python scripts/dashboard/pipeline_monitor.py --source source_name
```

### Utility Tools

```bash
# Sync progress from disk to sources.json
python3 scripts/tools/sync_progress.py

# Diagnose scraper issues (exit 0=healthy, 1=issues, 2=critical)
python3 scripts/tools/diagnose_scraper.py data/source_name/

# Test URL discovery
python3 scripts/tools/test_url_discovery.py data/source_name/

# Test HTML scraper (checks >= 95% completion)
python3 scripts/tools/test_scraper.py data/source_name/scrape_html.py

# Run stealth scraper for blocked sources (Camoufox anti-detection)
python3 scripts/tools/stealth_scraper.py --source source_id --limit 100

# Generate deterministic build ID from URL
python3 scripts/tools/build_id_generator.py --json "https://example.com/build/123"

# Detect modification categories
python3 scripts/tools/category_detector.py "Akrapovic exhaust system"
```

## Architecture

### 4-Stage Pipeline

RalphOS processes sources through four sequential stages:

| Stage | Name | Description | Output |
|-------|------|-------------|--------|
| 1 | **URL Discovery** | Find all vehicle/build page URLs | `urls.json` |
| 2 | **HTML Scraping** | Download HTML for each URL | `html/*.html` |
| 3 | **Build Extraction** | Extract structured vehicle data | `builds.json` |
| 4 | **Mod Extraction** | Extract individual modifications | `mods.json` |

### Execution Modes

**Classic Mode** (Sequential)
- One Ralph instance processes all 4 stages for each source
- Stories execute one at a time in priority order
- Best for smaller sources or debugging

**Pipeline Mode** (Parallel)
- Four sub-Ralphs run concurrently, each handling one stage
- Cascading triggers: each stage starts when prior stage reaches 20 items
- Massive parallelization for large sources

### Core Loop Flow

1. Read `scripts/ralph/prd.json` for pending tasks
2. Select highest priority story where `passes: false`
3. Execute the story using Claude CLI with `prompt.md`
4. Commit changes to git
5. Update `prd.json` to mark story complete
6. Append learnings to `scripts/ralph/progress.txt`
7. Repeat until all stories complete or max iterations reached

### Key Components

**scripts/ralph/ralph.sh** - Main bash orchestration loop (~630 lines)
- Displays rich terminal UI with colored status output
- Calls Claude CLI with `--dangerously-skip-permissions`
- Detects completion signals (`RALPH_DONE`, `<promise>COMPLETE</promise>`)
- Archives completed projects with timestamps
- Auto-continues to next source when current completes
- Features: `--scrape-only`, `--verbose`, `--pipeline` modes

**scripts/ralph/pipeline.sh** - Parallel pipeline orchestrator
- Manages 4 concurrent sub-Ralphs for the same source
- Cascading triggers at threshold counts
- Coordinates stage handoffs

**scripts/ralph/check_completion.sh** - Status validator
- Calculates actual status from pipeline counts
- Exit codes: 0 (healthy), 1 (issues), 2 (critical)
- `--fix` mode corrects mismatched statuses

**scripts/ralph/prompt.md** - Agent behavior instructions (~520 lines)
- Defines 4-stage pipeline workflow
- Tool availability matrix
- REQUIRED test commands before marking complete
- Error handling workflows
- Completion criteria (100% URLs attempted)

**scripts/ralph/prompts/** - Specialized stage prompts
- `url_detective.md` - Stage 1: URL discovery specialist
- `html_scraper.md` - Stage 2: HTML fetching with retry logic
- `build_extractor.md` - Stage 3: Structured data extraction
- `mod_extractor.md` - Stage 4: Modification extraction

### Configuration Files

**scripts/ralph/prd.json** - Project definition
```json
{
  "projectName": "Project Name",
  "branchName": "main",
  "targetUrl": "https://example.com",
  "outputDir": "data/source_name",
  "pipelineStage": 1,
  "userStories": [
    {
      "id": "US-001",
      "title": "Story title",
      "acceptanceCriteria": ["criteria 1", "criteria 2"],
      "priority": 1,
      "passes": false,
      "notes": "optional notes"
    }
  ]
}
```

**scripts/ralph/sources.json** - Multi-project registry with pipeline tracking
```json
{
  "sources": [
    {
      "id": "source_name",
      "name": "Display Name",
      "url": "https://example.com",
      "outputDir": "data/source_name",
      "status": "pending|in_progress|blocked|completed",
      "pipeline": {
        "expectedUrls": 100,
        "urlsFound": 50,
        "htmlScraped": 45,
        "htmlFailed": 5,
        "htmlBlocked": 0,
        "builds": 40,
        "mods": 120
      },
      "blockEvents": []
    }
  ]
}
```

**scripts/ralph/progress.txt** - Accumulated learnings
- Top section: "Codebase Patterns" for reusable rules
- Chronological entries with implementation details
- Critical for knowledge transfer between iterations

### Project Structure

```
RalphOS/
├── scripts/
│   ├── ralph/                  # Core orchestration
│   │   ├── ralph.sh            # Main loop script
│   │   ├── ralph-parallel.sh   # Parallel execution
│   │   ├── pipeline.sh         # Pipeline orchestrator
│   │   ├── check_completion.sh # Status validator
│   │   ├── prompt.md           # Agent instructions
│   │   ├── prompts/            # Specialized stage prompts
│   │   │   ├── url_detective.md
│   │   │   ├── html_scraper.md
│   │   │   ├── build_extractor.md
│   │   │   └── mod_extractor.md
│   │   ├── prd.json            # Current project
│   │   ├── sources.json        # Source registry
│   │   ├── progress.txt        # Learnings
│   │   └── archive/            # Archived PRDs
│   │
│   ├── tools/                  # Utility scripts
│   │   ├── sync_progress.py    # Sync disk counts to sources.json
│   │   ├── stealth_scraper.py  # Camoufox anti-detection browser
│   │   ├── diagnose_scraper.py # Error analysis and categorization
│   │   ├── build_id_generator.py # Deterministic ID from URL
│   │   ├── category_detector.py  # Fuzzy mod category matching
│   │   ├── create_manifest.py  # Final metadata creation
│   │   ├── test_scraper.py     # Scraper validation
│   │   └── test_url_discovery.py # URL discovery validation
│   │
│   └── dashboard/              # Monitoring UI
│       ├── dashboard.html      # Web dashboard
│       ├── dashboard_server.py # Python server
│       ├── pipeline_monitor.py # CLI monitor
│       └── Build_Scrape_Progress.html
│
├── schema/                     # Data schemas
│   ├── build_extraction_schema.json  # JSON Schema for builds
│   └── Vehicle_Components.json        # Mod category taxonomy
│
├── data/                       # Scraped data output (gitignored)
│   └── {source_name}/
│       ├── urls.json           # Discovered URLs
│       ├── html/               # Saved HTML files
│       ├── builds.json         # Extracted build data
│       ├── mods.json           # Extracted modifications
│       └── scrape_progress.json # Progress tracking
│
├── logs/                       # Log files (gitignored)
│   ├── ralph_output.log
│   └── ralph_debug.log
│
├── archive/                    # Blocked source data (gitignored)
├── CLAUDE.md
├── README.md
└── requirements.txt
```

### Standard User Stories

New scraping projects typically follow this 4-stage pattern:
- **US-001**: URL Discovery - Find all vehicle/build URLs from gallery/listing
- **US-002**: HTML Scraping - Download HTML content for discovered URLs
- **US-003**: Build Extraction - Extract structured data using schema
- **US-004**: Mod Extraction - Extract and categorize modifications

## MCP Integration

Ralph uses Claude's Model Context Protocol (MCP) for web interaction:

| Tool | Purpose |
|------|---------|
| `webReader` | Fetch URLs with markdown conversion, timeout:120 |
| `webSearchPrime` | Web search with domain filtering |
| `claude-in-chrome` | Full browser automation (navigate, click, scroll, JS) |
| `read_network_requests` | Monitor APIs for pagination discovery |

These tools bypass Python DNS restrictions in sandboxed environments.

## Completion Signals

Ralph monitors Claude output for these signals:

| Signal | Meaning |
|--------|---------|
| `<promise>COMPLETE</promise>` | Current story complete |
| `RALPH_DONE` | All sources complete |
| `URL_DETECTIVE_DONE` | Stage 1 complete |
| `HTML_SCRAPER_DONE` | Stage 2 complete |
| `HTML_SCRAPER_BLOCKED` | Anti-bot block detected |

## Anti-Bot Handling

When blocked (403/429/Cloudflare):

1. Mark source as `"blocked"` (not `"completed"`)
2. Record block event with timestamp in `blockEvents` array
3. Add note: `"Run: python scripts/tools/stealth_scraper.py --source {id}"`
4. Move to next source (don't auto-retry)
5. Human runs stealth scraper manually with Camoufox

**Stealth Scraper Features:**
- Firefox-based anti-detection browser (Camoufox)
- Automatic fingerprint generation via BrowserForge
- GeoIP auto-detection from proxy IP
- Human-like cursor movement
- WebGL/Canvas anti-fingerprinting

## Schema Details

### Build Extraction Schema

Required fields: `build_id`, `source_type`, `build_type`, `build_source`, `source_url`, `year`, `make`, `model`

Build types (29 options): OEM+, Street, Track, Drift, Rally, Time Attack, Drag, Show, Restomod, Restoration, Pro Touring, Overland, Off-Road, Rock Crawler, Prerunner, Trophy Truck, Lowrider, Stance, VIP, Bosozoku, Rat Rod, Hot Rod, Muscle, JDM, Euro, USDM, Daily Driver, Weekend Warrior, Work Truck, Tow Rig

### Vehicle Components Taxonomy

50+ modification categories including: Belt Drive, Body & Lamp Assembly, Brake & Wheel Hub, Cooling System, Drivetrain, Engine & Block, Electrical, Exhaust System, Forced Induction, Fuel System, Interior Trim, Lighting, Suspension, Transmission, Wheel, etc.

## Important Conventions

### Auto-Setup
Each iteration should verify `outputDir` exists and create structure if needed:
- Create `{outputDir}/` directory
- Create `{outputDir}/urls.json` with `{"urls": [], "lastUpdated": null, "totalCount": 0}`
- Create `{outputDir}/html/` subdirectory

### Progress Format
Append to `scripts/ralph/progress.txt`:
```markdown
## [Date] - [Story ID]
- What was implemented
- Files changed
- **Learnings:**
  - Patterns discovered
  - Gotchas encountered
---
```

### Git Commit Convention
Use format: `feat: [ID] - [Title]`

### Stop Condition
When ALL stories have `passes: true`, output `RALPH_DONE` to signal completion.

### Archiving
Completed projects are automatically archived with timestamp:
- `scripts/ralph/archive/{timestamp}_{project}_prd.json`
- `scripts/ralph/archive/{timestamp}_{project}_progress.txt`

### Testing Requirements
Before marking any stage complete, run the appropriate test:
```bash
# Stage 1: URL Discovery
python3 scripts/tools/test_url_discovery.py data/source_name/

# Stage 2: HTML Scraping
python3 scripts/tools/test_scraper.py data/source_name/

# All stages: Diagnose issues
python3 scripts/tools/diagnose_scraper.py data/source_name/
```

## Requirements

- **Claude CLI**: `npm install -g @anthropic-ai/claude-code`
- **jq**: For JSON parsing in bash
- **Python 3** with dependencies from `requirements.txt`:
  - `requests`, `beautifulsoup4`, `lxml` - Core scraping
  - `camoufox[geoip]`, `playwright` - Stealth scraping
  - `orjson`, `tqdm` - Data handling
  - `python-dotenv` - Environment
  - `selenium` - Legacy scrapers
- **Git**: For version control
- **Bash 4+**: For the loop script

## Key Patterns from Codebase

- Always check if directory exists before writing files
- Use ISO8601 timestamps for JSON metadata
- Implement retry logic for network requests (3 attempts with backoff)
- Save progress checkpoints every 20 items
- Use sorted lists for consistent JSON output
- Handle pagination (both numeric and infinite scroll)
- Normalize URLs (remove fragments, deduplicate)
- Include user-agent headers in requests
- Rate limiting: 1.5s between requests minimum
- Use MCP tools when Python DNS is blocked

## Error Handling Workflow

1. **Diagnose**: Run `diagnose_scraper.py` to categorize errors
2. **Error Types**:
   - DNS errors → Use MCP webReader instead
   - Timeout → Increase timeout, add retries
   - 403/429 → Use stealth_scraper.py
   - Cloudflare → Use stealth_scraper.py with Camoufox
   - 5xx → Retry with backoff
   - 404 → Skip and log
   - SSL → Check certificate validity
3. **Fix**: Apply appropriate solution
4. **Retest**: Verify fix with test scripts

## Safety Notes

- Ralph runs with `--dangerously-skip-permissions` - only use in trusted environments
- Always implement respectful rate limiting for web scraping
- Monitor `logs/ralph_output.log` for progress and errors
- Set appropriate max iterations based on task complexity
- Never commit `.env` files or credentials
- The `data/`, `logs/`, and `archive/` directories are gitignored
