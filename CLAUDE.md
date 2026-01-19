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

### Source Discovery Ralph

```bash
# Run standard discovery (find ~5 new sources)
./scripts/ralph/ralph-discovery.sh

# Quick discovery (3 sources, fewer searches)
./scripts/ralph/ralph-discovery.sh --quick

# Deep discovery (all vehicle categories, ~15 sources)
./scripts/ralph/ralph-discovery.sh --deep

# Continuous discovery (runs until stopped)
./scripts/ralph/ralph-discovery.sh --continuous

# Target specific vehicle types
./scripts/ralph/ralph-discovery.sh --categories jdm trucks muscle
```

### Source Discovery Tools

```bash
# Generate search queries
python3 scripts/tools/discover_sources.py --queries --limit 10

# List existing sources
python3 scripts/tools/discover_sources.py --list

# Show discovery statistics
python3 scripts/tools/discover_sources.py --stats

# Validate a potential source
python3 scripts/tools/validate_source.py "https://example.com/builds" --verbose

# Generate discovery PRD
python3 scripts/tools/generate_discovery_prd.py --quick
python3 scripts/tools/generate_discovery_prd.py --deep
python3 scripts/tools/generate_discovery_prd.py --categories jdm trucks

# Add a source directly
python3 scripts/tools/discover_sources.py --add-url "https://site.com/builds" --name "Site Name"
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
│   │   ├── ralph-discovery.sh  # Source discovery loop
│   │   ├── ralph-parallel.sh
│   │   ├── pipeline.sh
│   │   ├── check_completion.sh
│   │   ├── prompt.md       # Agent instructions
│   │   ├── prompts/        # Specialized prompts
│   │   │   ├── source_discovery.md  # Discovery agent prompt
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
│   │   ├── test_url_discovery.py
│   │   ├── discover_sources.py      # Source discovery queries/management
│   │   ├── validate_source.py       # Source validation
│   │   └── generate_discovery_prd.py # Discovery PRD generator
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
├── FyloCore/               # Knowledge graph platform (submodule)
├── fylo-core-mcp/          # MCP server for knowledge graph
│   ├── src/index.ts        # Main MCP server implementation
│   ├── package.json
│   └── README.md
├── .mcp.json               # Claude Code MCP configuration
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

### Source Discovery System

The Source Discovery Ralph autonomously finds new vehicle build websites and adds them to the sources queue.

#### Discovery Architecture

```
Source Discovery Flow:
1. Generate search queries (vehicle types, build forums, tuner shops)
2. Execute web searches via MCP (webSearchPrime)
3. Filter results (exclude social media, dealerships, bad patterns)
4. Validate candidates via MCP (webReader)
   - Check for individual build pages
   - Verify modifications are listed
   - Test pagination accessibility
5. Add valid sources to sources.json with discovery metadata
6. Continue until target sources found or iterations exhausted
```

#### Valid Source Criteria

Sources must have:
- **Individual build pages** (not just a thumbnail gallery)
- **Vehicle specifications** (year, make, model)
- **Modifications listed** (aftermarket parts, upgrades)
- **Scrapable content** (static HTML, no auth required)
- **Working pagination** (if paginated)

#### Source Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `build_showcase` | Car build portfolio sites | Speedhunters, StanceNation |
| `forum_threads` | Forum build thread sections | TacomaWorld, E46Fanatics |
| `tuner_shops` | Tuner shop customer builds | Performance shop portfolios |
| `wheel_fitment` | Wheel/fitment galleries | Custom Wheel Offset |
| `auctions` | Modified car auctions | Bring a Trailer, Cars & Bids |
| `publications` | Car magazine features | Super Street, Hot Rod |
| `jdm` | JDM vehicle builds | Civic, Miata, Supra forums |
| `trucks` | Truck/off-road builds | Tacoma, F-150, Jeep forums |
| `muscle` | American muscle builds | Mustang, Camaro, Corvette |
| `european` | European car builds | BMW, VW, Porsche forums |
| `exotic` | Supercar tuning | Ferrari, Lamborghini shops |

#### Discovery Metadata

New sources include discovery tracking:
```json
{
  "id": "source_id",
  "name": "Source Name",
  "url": "https://example.com/builds",
  "discovery": {
    "discovered_at": "2026-01-19T07:00:00Z",
    "discovered_by": "source_discovery_ralph",
    "confidence_score": 0.85,
    "vehicle_types": ["jdm", "trucks"],
    "validation_notes": "Forum with 500+ build threads"
  }
}
```

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

## Fylo-Core-MCP (Knowledge Graph)

RalphOS includes a knowledge graph MCP server for tracking pipeline progress and visualizing data.

### Setup

```bash
# Install and build the MCP server
cd fylo-core-mcp
./setup.sh

# Or manually
npm install && npm run build
```

### Available Tools

#### Core Tools
| Tool | Description |
|------|-------------|
| `sync_ralph_sources` | Import sources from sources.json into the knowledge graph |
| `get_pipeline_status` | View current pipeline progress across all sources |
| `ingest_builds` | Import build data from builds.json files |
| `create_entity` | Create entities (source, url, build, modification, category, pattern) |
| `create_relation` | Create relationships between entities |
| `query_graph` | Query entities and relationships |
| `visualize_graph` | Generate Mermaid diagrams of the knowledge graph |
| `export_to_duckdb` | Export graph to DuckDB SQL for analysis |
| `get_graph_stats` | View graph statistics |

#### Validation & Self-Verification Tools
| Tool | Description |
|------|-------------|
| `validate_pipeline_stage` | Validate pipeline stage outputs (url_discovery, html_scrape, build_extraction, mod_extraction) |
| `assert_condition` | Assert conditions (file_exists, count_gte, json_valid) with pass/fail |
| `assert_batch` | Run multiple assertions at once |
| `get_quality_report` | Generate quality report with numeric scores (0-100) |
| `verify_story_complete` | Verify user story acceptance criteria with evidence |
| `get_completion_proof` | Generate completion proof showing outputs |
| `diagnose_failure` | Analyze failures and suggest fixes |
| `record_success_pattern` | Record successful patterns for future reference |
| `get_success_patterns` | Retrieve recorded success patterns |

### Usage in Claude Code

The MCP is configured in `.mcp.json`. After building, restart Claude Code to use the tools:

```
> sync_ralph_sources
> get_pipeline_status
> visualize_graph entityType="source"
```

### DuckDB Integration

Export the knowledge graph to DuckDB for analysis:

```bash
# Export to SQL
> export_to_duckdb

# Load in DuckDB
duckdb
.read data/fylo-graph/knowledge-graph.sql
SELECT * FROM source_summary;
SELECT * FROM entity_relationships;
```

## FyloCore (Full Knowledge Graph Platform)

The complete FyloCore platform is available in the `FyloCore/` directory for advanced knowledge graph features:

- Real-time collaborative editing
- AI-powered document ingestion
- PostgreSQL + pgvector for vector embeddings
- Schema-aware graph structure

See `FyloCore/README.md` for setup instructions.

## Safety Notes

- Ralph runs with `--dangerously-skip-permissions` - only use in trusted environments
- Always implement respectful rate limiting for web scraping
- Monitor `logs/ralph_output.log` for progress and errors
- Set appropriate max iterations based on task complexity
