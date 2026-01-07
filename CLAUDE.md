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
cat ralph_output.log

# Check current project status
cat scripts/ralph/prd.json | jq '.userStories[] | {id, title, passes}'

# View accumulated learnings and patterns
cat scripts/ralph/progress.txt

# View sources queue
cat scripts/ralph/sources.json | jq '.sources[]'
```

### Scraping Scripts

```bash
# Scrape URLs (example - modify for specific source)
python3 scrape_urls.py

# Scrape HTML content
python3 scrape_html.py

# Generate manifest from scraped data
python3 create_manifest.py
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
  "outputDir": "scraped_builds/source_name",
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

### Scraping Architecture

**Output Structure:**
```
scraped_builds/
├── {source_name}/
│   ├── urls.json              # Discovered URLs
│   ├── html/                  # Saved HTML files
│   ├── manifest.json          # Scrape metadata
│   └── scrape_progress.json   # Progress tracking
```

**Python Scrapers:**
- `scrape_urls.py` - URL discovery with pagination/infinite scroll handling
- `scrape_html.py` - HTML fetching with retry logic, progress tracking, resume capability
- Both use `requests` library with retry adapters for robustness
- Rate limiting built-in (1.5s delay between requests)

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
- Monitor `ralph_output.log` for progress and errors
- Set appropriate max iterations based on task complexity
