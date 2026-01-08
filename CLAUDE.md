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

### Project Structure

```
RalphOS/
├── scripts/
│   ├── ralph/              # Core orchestration
│   │   ├── ralph.sh        # Main loop script
│   │   ├── check_completion.sh
│   │   ├── prompt.md       # Agent instructions
│   │   ├── sources.json    # Source registry
│   │   ├── progress.txt    # Learnings
│   │   └── archive/        # Archived PRDs
│   │
│   ├── ralph-stages/       # Independent stage runners
│   │   ├── url-detective/  # Stage 1: URL discovery
│   │   ├── html-scraper/   # Stage 2: HTML scraping
│   │   └── data-extractor/ # Stage 3: Builds + Mods (combined)
│   │
│   ├── tools/              # Utility scripts
│   │   ├── sync_progress.py
│   │   ├── stealth_scraper.py
│   │   ├── diagnose_scraper.py
│   │   ├── build_id_generator.py
│   │   ├── category_detector.py
│   │   ├── create_manifest.py
│   │   ├── test_scraper.py
│   │   ├── test_url_discovery.py
│   │   └── browser/        # Chrome automation
│   │       ├── start.js    # Launch Chrome :9222
│   │       ├── nav.js      # Navigate tabs
│   │       ├── eval.js     # Execute JS
│   │       ├── screenshot.js
│   │       ├── cookies.js  # Extract cookies
│   │       └── pick.js     # Visual element picker
│   │
│   └── dashboard/          # Monitoring UI
│       ├── dashboard.html
│       ├── dashboard_server.py
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
- **Python 3** with `camoufox` library
- **Git**: For version control
- **Bash 4+**: For the loop script
- **Node.js**: For browser automation scripts

## Browser Tools

All Ralphs have access to browser automation for web interaction:

### Chrome DevTools MCP (Native tools)

Configured in `~/.claude.json` for RalphOS project:
```
chrome_navigate - Navigate to URL
chrome_screenshot - Capture viewport  
chrome_evaluate - Execute JavaScript in page
chrome_click - Click elements
chrome_type - Type text
```

### Browser CLI Scripts

Located in `scripts/tools/browser/`:
```bash
# Start Chrome with your profile (cookies, logins)
./scripts/tools/browser/start.js --profile

# Navigate
./scripts/tools/browser/nav.js https://example.com

# Execute JavaScript
./scripts/tools/browser/eval.js 'document.querySelectorAll("a").length'

# Screenshot
./scripts/tools/browser/screenshot.js

# Extract cookies (including HTTP-only)
./scripts/tools/browser/cookies.js

# Visual element picker
./scripts/tools/browser/pick.js "Click the submit button"
```

### Workflow

1. Start Chrome: `./scripts/tools/browser/start.js --profile`
2. Use MCP tools OR CLI scripts (both connect to Chrome :9222)
3. For stealth scraping, prefer `scripts/tools/stealth_scraper.py` (Camoufox)

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
