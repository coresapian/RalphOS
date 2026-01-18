# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**RalphOS** is an autonomous AI agent loop system that executes multi-step web scraping tasks without human intervention. It wraps Claude CLI in a bash loop, enabling fully autonomous execution of complex projects defined in JSON PRD (Product Requirements Document) format.

The system iterates through user stories, implements solutions, commits changes, and learns from each iteration. It's designed for web scraping but can handle any multi-step automation task.

## Commands

### Running Ralph

```bash
# Run with default 10 iterations
./scripts/ralph/ralph.sh

# Run with custom iteration count
./scripts/ralph/ralph.sh 25
./scripts/ralph/ralph.sh 50
```

### Monitoring

```bash
# View real-time output log
cat logs/ralph_output.log

# Check current project status
cat scripts/ralph/prd.json | jq '.userStories[] | {id, title, passes}'

# View accumulated learnings and patterns
cat scripts/ralph/progress.txt

# View sources queue
cat scripts/ralph/sources.json | jq '.sources[]'
```

### Utility Tools

```bash
# Sync progress from disk to sources.json
python3 scripts/tools/sync_progress.py

# Diagnose scraper issues
python3 scripts/tools/diagnose_scraper.py data/source_name/

# Test URL discovery
python3 scripts/tools/test_url_discovery.py data/source_name/

# Test HTML scraper
python3 scripts/tools/test_scraper.py data/source_name/scrape_html.py

# Run stealth scraper for blocked sources
python3 scripts/tools/stealth_scraper.py --source source_id
```

## Architecture

### Core Loop Flow

1. Read `scripts/ralph/prd.json` for pending tasks
2. Select highest priority story where `passes: false`
3. Execute the story using Claude CLI
4. Commit changes to git
5. Update `prd.json` to mark story complete
6. Append learnings to `scripts/ralph/progress.txt`
7. Repeat until all stories complete or max iterations reached

### Key Components

**scripts/ralph/ralph.sh** - Main bash orchestration loop
- Displays project status with colored terminal output
- Calls Claude CLI with instructions from `prompt.md`
- Detects completion signals (`RALPH_DONE`, `<promise>COMPLETE</promise>`)
- Archives completed projects
- Tracks elapsed time per iteration

**scripts/ralph/prompt.md** - Agent behavior instructions
- Defines task execution workflow
- Specifies directory structure conventions
- Contains stop conditions and rules

**scripts/ralph/prd.json** - Project definition
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
      "passes": false,
      "notes": "optional notes"
    }
  ]
}
```

**scripts/ralph/progress.txt** - Accumulated learnings
- Top section contains reusable "Codebase Patterns"
- Each story gets a dated entry with implementation details and learnings
- Critical for knowledge transfer between iterations

**scripts/ralph/sources.json** - Multi-project queue
- Manages multiple scraping projects sequentially
- Tracks status: pending/in_progress/completed
- Auto-generates new PRDs when current project completes

### Stage Prompts (Pipeline Mode)

The `scripts/ralph/prompts/` directory contains specialized prompts for parallel sub-Ralph execution in Pipeline Mode. Each prompt defines a focused agent for one stage of the scraping pipeline:

**url_detective.md** - URL Discovery Agent
- Discovers all vehicle/build URLs on a website
- Analyzes pagination, sitemaps, and infinite scroll
- Outputs: `{outputDir}/urls.json`
- Stop signal: `URL_DETECTIVE_DONE`

**html_scraper.md** - HTML Downloading Agent
- Downloads HTML content for discovered URLs
- Handles rate limiting and anti-bot detection
- Outputs: `{outputDir}/html/*.html`, `scrape_progress.json`
- Stop signals: `HTML_SCRAPER_DONE` or `HTML_SCRAPER_BLOCKED`

**build_extractor.md** - Build Data Extraction Agent
- Extracts structured vehicle data from HTML files
- Uses `schema/build_extraction_schema.json` for output format
- Outputs: `{outputDir}/builds.json`
- Stop signal: `BUILD_EXTRACTOR_DONE`

**mod_extractor.md** - Modification Extraction Agent
- Extracts vehicle modifications from build records
- Uses `category_detector.py` for categorization
- Outputs: Updates `builds.json`, creates `{outputDir}/mods.json`
- Stop signal: `MOD_EXTRACTOR_DONE`

### Project Structure

```
RalphOS/
├── scripts/
│   ├── ralph/              # Core orchestration
│   │   ├── ralph.sh        # Main loop script
│   │   ├── ralph-parallel.sh
│   │   ├── pipeline.sh
│   │   ├── check_completion.sh
│   │   ├── prompt.md       # Agent instructions
│   │   ├── prompts/        # Stage prompts for Pipeline Mode
│   │   │   ├── url_detective.md
│   │   │   ├── html_scraper.md
│   │   │   ├── build_extractor.md
│   │   │   └── mod_extractor.md
│   │   ├── sources.json    # Source registry
│   │   ├── progress.txt    # Learnings
│   │   └── archive/        # Archived PRDs
│   │
│   ├── tools/              # Utility scripts
│   │   ├── sync_progress.py
│   │   ├── stealth_scraper.py
│   │   ├── diagnose_scraper.py
│   │   ├── build_id_generator.py
│   │   ├── category_detector.py
│   │   ├── create_manifest.py
│   │   ├── test_scraper.py
│   │   └── test_url_discovery.py
│   │
│   └── dashboard/          # Monitoring UI
│       ├── dashboard.html
│       ├── dashboard_server.py
│       ├── pipeline_monitor.py
│       └── Build_Scrape_Progress.html
│
├── data/                   # Scraped data output
│   ├── {source_name}/
│   │   ├── urls.json       # Discovered URLs
│   │   ├── html/           # Saved HTML files
│   │   ├── builds.json     # Extracted build data
│   │   ├── mods.json       # Extracted modifications
│   │   └── scrape_progress.json
│   └── ...
│
├── schema/                 # Data schemas
│   ├── build_extraction_schema.json
│   └── Vehicle_Componets.json
│
├── logs/                   # Log files
│   ├── ralph_output.log
│   └── ralph_debug.log
│
├── archive/                # Blocked source data
├── CLAUDE.md
├── README.md
└── requirements.txt
```

### Standard User Stories

New scraping projects typically follow this pattern:
- **US-001**: Create directory structure (outputDir, urls.json, html/)
- **US-002**: Scrape all URLs from gallery/listing (discover content)
- **US-003**: Create HTML scraping script (fetch content)
- **US-004**: Execute full scrape (process all discovered URLs)

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

## Requirements

- **Claude CLI**: `npm install -g @anthropic-ai/claude-code`
- **jq**: For JSON parsing in bash
- **Python 3** with `requests` library
- **Git**: For version control
- **Bash 4+**: For the loop script

## Key Patterns from Codebase

- Always check if directory exists before writing files
- Use ISO8601 timestamps for JSON metadata
- Implement retry logic for network requests
- Save progress checkpoints every N items
- Use sorted lists for consistent JSON output
- Handle pagination (both numeric and infinite scroll)
- Normalize URLs (remove fragments, duplicates)
- Include user-agent headers in requests

## Safety Notes

- Ralph runs with `--dangerously-skip-permissions` - only use in trusted environments
- Always implement respectful rate limiting for web scraping
- Monitor `logs/ralph_output.log` for progress and errors
- Set appropriate max iterations based on task complexity
