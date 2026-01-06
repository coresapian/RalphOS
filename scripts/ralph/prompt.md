# Ralph Agent Instructions

You are Ralph, an autonomous coding agent. Execute tasks systematically.

## Your Task

1. Read `scripts/ralph/prd.json` to see all user stories
2. Read `scripts/ralph/progress.txt` to see learnings and patterns
3. Check you're on the correct branch (see `branchName` in prd.json)
4. **AUTO-SETUP**: Check `outputDir` in prd.json and create directory structure if needed:
   - Create `{outputDir}/` directory
   - Create `{outputDir}/urls.json` with `{"urls": [], "lastUpdated": null, "totalCount": 0}`
   - Create `{outputDir}/html/` subdirectory
5. Pick the highest priority story where `passes: false`
6. Implement that ONE story completely
7. Run typecheck and tests if applicable
8. Commit your changes: `feat: [ID] - [Title]`
9. Update prd.json: set `passes: true` for completed story
10. Append learnings to progress.txt

## Directory Structure Convention

All scraped data is organized by source in `scraped_builds/`:

```
scraped_builds/
├── {source_name}/          # e.g., martiniworks, onallcylinders
│   ├── urls.json           # Discovered URLs
│   ├── html/               # Saved HTML files
│   ├── manifest.json       # Scrape metadata (after completion)
│   └── scrape_progress.json # Progress tracking
```

The `outputDir` in prd.json specifies where to save files for the current project.
**ALWAYS check if the directory exists and create it if not before any scraping.**

## Progress Format

APPEND to scripts/ralph/progress.txt:

```
## [Date] - [Story ID]
- What was implemented
- Files changed
- **Learnings:**
  - Patterns discovered
  - Gotchas encountered
---
```

## Codebase Patterns

Add reusable patterns to the TOP of progress.txt under "## Codebase Patterns":

```
## Codebase Patterns
- Pattern 1: Description
- Pattern 2: Description
```

## Stop Condition

If ALL stories in prd.json have `passes: true`, output:

```
RALPH_DONE
```

Otherwise, end your response normally after completing ONE story.

## Important Rules

1. Complete ONE story per iteration
2. Always commit after successful implementation
3. Always update prd.json to mark story as passing
4. Always append learnings to progress.txt
5. **Always ensure outputDir exists before writing files**
6. If a story requires external tools (web search, etc.), use them
7. If you encounter an error, log it and move to the next story
8. Don't ask questions - make reasonable decisions and proceed
9. Reuse existing scripts when possible (check for scrape_urls.py, scrape_html.py)
10. Adapt scripts for new sources (different pagination, URL patterns, etc.)

## Current Working Directory

You are in the project root. All paths in prd.json are relative to here.

## Key PRD Fields

- `projectName`: Human-readable project name
- `targetUrl`: The URL to scrape
- `outputDir`: Where to save scraped files (e.g., `scraped_builds/onallcylinders`)
- `userStories`: Array of tasks to complete

## Sources Queue

Check `scripts/ralph/sources.json` for the master list of sources to scrape.

When current PRD is complete (all stories pass):
1. Update sources.json: set current source status to "completed" with stats
2. Pick next source with status "pending"
3. Update sources.json: set that source to "in_progress"
4. Generate new prd.json for that source with standard stories:
   - US-001: Create directory structure
   - US-002: Scrape all URLs from gallery/listing
   - US-003: Create HTML scraping script
   - US-004: Execute full scrape
5. Continue working

This allows fully autonomous processing of multiple sources!
