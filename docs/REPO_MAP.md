# RalphOS Repository Map

> Comprehensive documentation of all components, their relationships, and technical details.

## Table of Contents
1. [System Architecture](#system-architecture)
2. [UI Components](#ui-components)
3. [Backend Services](#backend-services)
4. [Core Scripts](#core-scripts)
5. [Utility Tools](#utility-tools)
6. [Data Schemas](#data-schemas)
7. [Configuration Files](#configuration-files)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        RalphOS System                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   Ralph     │───▶│   Claude    │───▶│   Data      │        │
│  │   Loop      │    │   CLI       │    │   Output    │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│        │                  │                   │                 │
│        ▼                  ▼                   ▼                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │  PRD/JSON   │    │  MCP Server │    │  Dashboard  │        │
│  │  Config     │    │ (Knowledge) │    │    UI       │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Pipeline Stages
```
URL Discovery → HTML Scraping → Build Extraction → Mod Extraction
    (US-002)       (US-003)        (US-004)          (optional)
```

---

## UI Components

### 1. Ralph Dashboard (`scripts/dashboard/dashboard.html`)

**Purpose:** Real-time monitoring interface for autonomous AI agent execution

**Technical Details:**
| Property | Value |
|----------|-------|
| File Size | ~16 KB |
| Lines of Code | 583 |
| Framework | Vanilla JavaScript |
| Refresh Interval | 5 seconds |
| API Endpoint | `http://localhost:8765/status` |

**Features:**
- Live execution status indicator (running/stopped)
- 4 stat cards: Total Sources, Completed, In Progress, HTML Files
- Current source tracking with pipeline visualization
- 4-stage pipeline progress: URLs → HTML → Builds → Mods
- Live log output with syntax highlighting
- Sources list with status indicators and progress bars

**Styling:**
```css
/* Color Palette */
--bg-primary: #0a0a0f;      /* Main background */
--accent-cyan: #22d3ee;      /* Primary accent */
--accent-green: #4ade80;     /* Success states */
--accent-yellow: #facc15;    /* In-progress states */
--accent-red: #f87171;       /* Error states */
--accent-purple: #a78bfa;    /* Secondary accent */

/* Typography */
Font Family: 'Space Grotesk' (primary), 'JetBrains Mono' (monospace)
```

**Key Functions:**
| Function | Purpose |
|----------|---------|
| `updateDashboard()` | Fetches status and updates all UI elements |
| `colorizeLog(text)` | Applies syntax highlighting to log output |
| `updateStage(id, current, total)` | Updates pipeline stage visualization |
| `updateSourcesList(sources)` | Renders sorted sources with progress bars |
| `formatNumber(num)` | Formats numbers with locale-aware commas |

---

### 2. MOTORMIA Builds Dashboard (`scripts/dashboard/Build_Scrape_Progress.html`)

**Purpose:** Static analytics dashboard displaying aggregated vehicle build data

**Technical Details:**
| Property | Value |
|----------|-------|
| File Size | ~68 KB |
| Lines of Code | 1154 |
| Data Sources | 31 automotive databases |
| Layout | 5-column grid + sidebar |

**Styling:**
```css
/* Automotive Theme Colors */
--redline: #F94868;    /* Primary accent (tachometer red) */
--torque: #62E4D3;     /* Secondary accent (torque teal) */
--carbon: #1A1A1E;     /* Background */
--asphalt: #353541;    /* Card backgrounds */
--ceramic: #FFFFFF;    /* Primary text */
```

**Data Sources Tracked:**
| Tier | Sources |
|------|---------|
| Major | Bring a Trailer, Fitment Industries, Revkit, Mecum, PCarmarket |
| Mid-tier | Barrett-Jackson, Modified1, Racing Junk, Cars and Bids, The FOAT |
| Specialty | Speedhunters, JDM Buy Sell, Hemmings, Hagerty, Holley |
| Emerging | American Trucks, Xoverland, BuildSheet QR, Ringbrothers, Kindig-it |

**Metrics Per Source:**
- Build count with delta indicators
- Modification count with delta indicators
- Average mods per build (color-coded: green ≥10, yellow ≥6, orange <6)
- Top 3 vehicle makes
- Top 3 modification brands

**Sidebar Analytics:**
- Build Volume ranking (top 8)
- Average Mods/Build ranking
- Top Models Overall
- Top Modification Brands

---

## Backend Services

### 3. Dashboard Server (`scripts/dashboard/dashboard_server.py`)

**Purpose:** HTTP API server providing real-time data to the dashboard

**Technical Details:**
| Property | Value |
|----------|-------|
| Lines of Code | 230 |
| Framework | Python `http.server` + `socketserver` |
| Port | 8765 |
| CORS | Enabled (all origins) |

**API Endpoints:**

| Endpoint | Method | Response |
|----------|--------|----------|
| `/` | GET | Serves `dashboard.html` |
| `/status` | GET | Comprehensive status JSON |
| `/log` | GET | Log tail (configurable lines) |
| `/sources` | GET | All sources with pipeline data |

**`/status` Response Schema:**
```json
{
  "timestamp": "ISO8601",
  "running": boolean,
  "sources": {
    "total": number,
    "completed": number,
    "in_progress": number,
    "pending": number,
    "blocked": number
  },
  "current_source": {
    "id": string,
    "name": string,
    "url": string,
    "pipeline": { ... },
    "status": string
  },
  "all_sources": [...],
  "html_files": number,
  "log_tail": string
}
```

**Key Methods:**
| Method | Purpose |
|--------|---------|
| `check_ralph_running()` | Checks if `ralph.sh` is running via `pgrep` |
| `get_sources_summary()` | Aggregates source counts by status |
| `get_current_source()` | Reads PRD to find active source |
| `count_html_files()` | Counts HTML files across all source directories |
| `get_log_tail(lines)` | Returns last N lines of log file |

---

### 4. Pipeline Monitor (`scripts/dashboard/pipeline_monitor.py`)

**Purpose:** CLI tool for monitoring pipeline progress and triggering cascading stages

**Technical Details:**
| Property | Value |
|----------|-------|
| Lines of Code | 290 |
| Trigger Threshold | 20 items |
| Watch Interval | 5 seconds (default) |

**Command-line Usage:**
```bash
# Check all triggers for a source
python pipeline_monitor.py --source custom_wheel_offset

# Check specific stage
python pipeline_monitor.py --source custom_wheel_offset --stage html

# JSON output for scripting
python pipeline_monitor.py --source custom_wheel_offset --json

# Watch mode (continuous monitoring)
python pipeline_monitor.py --source custom_wheel_offset --watch
```

**Pipeline Stages:**
| Stage | Data Source | Trigger Condition |
|-------|-------------|-------------------|
| URL Detective | `urls.json` | Always starts |
| HTML Scraper | `html/` directory | ≥20 URLs found |
| Build Extractor | `builds.json` | ≥20 HTML files |
| Mod Extractor | `mods.json` | ≥20 builds |

**Output Schema (JSON mode):**
```json
{
  "source_id": string,
  "timestamp": "ISO8601",
  "threshold": 20,
  "counts": { "urls": N, "html": N, "builds": N, "mods": N },
  "expected": { ... },
  "triggers": {
    "start_url_detective": boolean,
    "start_html_scraper": boolean,
    "start_build_extractor": boolean,
    "start_mod_extractor": boolean
  },
  "stages": { ... },
  "pipeline_complete": boolean
}
```

---

### 5. Fylo-Core-MCP Server (`fylo-core-mcp/src/index.ts`)

**Purpose:** Model Context Protocol server for knowledge graph tracking

**Technical Details:**
| Property | Value |
|----------|-------|
| Lines of Code | 2243 |
| Language | TypeScript |
| Framework | `@modelcontextprotocol/sdk` |
| Transport | STDIO |
| Storage | JSON file + DuckDB export |

**Available Tools:**

| Category | Tool | Description |
|----------|------|-------------|
| **Core** | `create_entity` | Create entities (source, url, build, modification, category, pattern) |
| | `create_relation` | Create relationships between entities |
| | `query_graph` | Query entities and relationships |
| | `sync_ralph_sources` | Import sources from sources.json |
| | `get_pipeline_status` | View current pipeline progress |
| | `ingest_builds` | Import build data from builds.json |
| | `visualize_graph` | Generate Mermaid diagrams |
| | `export_to_duckdb` | Export to DuckDB SQL |
| | `get_graph_stats` | View graph statistics |
| **Validation** | `validate_pipeline_stage` | Validate stage outputs |
| | `assert_condition` | Assert conditions with pass/fail |
| | `assert_batch` | Run multiple assertions |
| | `get_quality_report` | Generate quality scores (0-100) |
| | `verify_story_complete` | Verify acceptance criteria |
| | `get_completion_proof` | Generate completion evidence |
| **Diagnosis** | `diagnose_failure` | Analyze failures and suggest fixes |
| | `record_success_pattern` | Record successful patterns |
| | `get_success_patterns` | Retrieve patterns for reference |

**Entity Types:**
- `source` - Data source websites
- `url` - Individual URLs to scrape
- `build` - Extracted vehicle build data
- `modification` - Vehicle modifications
- `category` - Modification categories
- `pattern` - Successful patterns/learnings

---

## Core Scripts

### 6. Ralph Main Loop (`scripts/ralph/ralph.sh`)

**Purpose:** Main bash orchestration loop for autonomous task execution

**Flow:**
1. Read `prd.json` for pending tasks
2. Select highest priority story where `passes: false`
3. Execute story using Claude CLI
4. Commit changes to git
5. Update `prd.json` to mark story complete
6. Append learnings to `progress.txt`
7. Repeat until all stories complete or max iterations reached

**Usage:**
```bash
./scripts/ralph/ralph.sh       # Default 10 iterations
./scripts/ralph/ralph.sh 25    # Custom iteration count
```

**Completion Signals:**
- `RALPH_DONE` - All stories complete
- `<promise>COMPLETE</promise>` - Story completion marker

---

### 7. PRD Schema (`scripts/ralph/prd.json`)

**Purpose:** Project Requirements Document defining the current scraping task

**Schema:**
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

**Standard User Stories:**
| ID | Title | Purpose |
|----|-------|---------|
| US-001 | Create directory structure | Set up outputDir, urls.json, html/ |
| US-002 | Scrape all URLs | Discover content URLs from listing pages |
| US-003 | Create HTML scraping script | Fetch and save HTML content |
| US-004 | Execute full scrape | Process all discovered URLs |

---

### 8. Sources Registry (`scripts/ralph/sources.json`)

**Purpose:** Multi-project queue managing all scraping sources

**Schema:**
```json
{
  "sources": [
    {
      "id": "source_id",
      "name": "Human Readable Name",
      "url": "https://example.com",
      "outputDir": "data/source_name",
      "status": "pending|in_progress|completed|blocked",
      "pipeline": {
        "urlsFound": 0,
        "expectedUrls": 0,
        "htmlScraped": 0,
        "builds": 0,
        "mods": 0
      }
    }
  ]
}
```

**Status Values:**
| Status | Description |
|--------|-------------|
| `pending` | Not yet started |
| `in_progress` | Currently being processed |
| `completed` | All stages finished |
| `blocked` | Cannot proceed (anti-bot, etc.) |
| `skip` | Manually skipped |

---

## Utility Tools

### 9. Tools Directory (`scripts/tools/`)

| Script | Purpose | Usage |
|--------|---------|-------|
| `sync_progress.py` | Sync progress from disk to sources.json | `python3 sync_progress.py` |
| `stealth_scraper.py` | Browser automation for blocked sources | `python3 stealth_scraper.py --source ID` |
| `diagnose_scraper.py` | Analyze scraper issues | `python3 diagnose_scraper.py data/source/` |
| `test_scraper.py` | Test HTML scraper scripts | `python3 test_scraper.py data/source/scrape_html.py` |
| `test_url_discovery.py` | Test URL discovery scripts | `python3 test_url_discovery.py data/source/` |
| `build_id_generator.py` | Generate unique build IDs | Imported as module |
| `category_detector.py` | Auto-detect modification categories | Imported as module |
| `create_manifest.py` | Create data manifests | `python3 create_manifest.py` |

---

## Data Schemas

### 10. Build Extraction Schema (`schema/build_extraction_schema.json`)

**Purpose:** Defines the standard format for extracted vehicle build data

**Core Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `build_id` | string | Unique identifier |
| `build_title` | string | Display title |
| `year` | integer | Model year |
| `make` | string | Manufacturer |
| `model` | string | Model name |
| `trim` | string | Trim level |
| `generation` | string | Generation identifier |
| `engine` | string | Engine specification |
| `transmission` | string | Transmission type |
| `drivetrain` | string | Drive configuration |
| `build_type` | string | Type (restomod, track, daily, etc.) |
| `modification_level` | string | Level (stock, mild, moderate, extreme) |
| `extraction_confidence` | float | 0-1 confidence score |
| `source_url` | string | Original source URL |
| `modifications` | array | List of modifications |

### 11. Vehicle Components Taxonomy (`schema/Vehicle_Componets.json`)

**Purpose:** Hierarchical taxonomy of vehicle modification categories

**Top-level Categories:**
- Engine & Performance
- Suspension & Handling
- Wheels & Tires
- Brakes
- Exterior
- Interior
- Electrical
- Drivetrain
- Exhaust
- Fuel System

---

## Configuration Files

### 12. MCP Configuration (`.mcp.json`)

**Purpose:** Claude Code MCP server integration

```json
{
  "mcpServers": {
    "fylo-core-mcp": {
      "command": "node",
      "args": ["fylo-core-mcp/build/index.js"],
      "env": {
        "RALPH_DIR": ".",
        "FYLO_DATA_DIR": "data/fylo-graph"
      }
    }
  }
}
```

### 13. TypeScript Config (`fylo-core-mcp/tsconfig.json`)

Standard TypeScript configuration for ES modules with Node.js.

### 14. Python Requirements (`requirements.txt`)

Core dependencies:
- `requests` - HTTP client
- `beautifulsoup4` - HTML parsing
- `selenium` - Browser automation (stealth scraper)
- `lxml` - Fast XML/HTML parser

---

## Component Relationships

```
                    ┌─────────────────┐
                    │   CLAUDE.md     │
                    │  (Instructions) │
                    └────────┬────────┘
                             │
                             ▼
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ sources.json│────▶│    ralph.sh     │────▶│    prd.json     │
│  (Registry) │     │  (Main Loop)    │     │ (Current Task)  │
└─────────────┘     └────────┬────────┘     └─────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
      ┌───────────┐  ┌───────────┐  ┌───────────┐
      │ url_detec │  │html_scrap │  │ build_ext │
      │ tive.md   │  │ er.md     │  │ ractor.md │
      └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
            │              │              │
            ▼              ▼              ▼
      ┌───────────┐  ┌───────────┐  ┌───────────┐
      │ urls.json │  │  html/    │  │builds.json│
      └───────────┘  └───────────┘  └───────────┘
                                          │
                                          ▼
                                   ┌────────────┐
                                   │ Dashboard  │
                                   │ Server     │
                                   └──────┬─────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
             ┌────────────┐       ┌────────────┐       ┌────────────┐
             │ dashboard  │       │ Build_Scrape│      │  pipeline  │
             │  .html     │       │ Progress    │      │  _monitor  │
             └────────────┘       └────────────┘       └────────────┘
```

---

## UI Review Summary

### Code Quality Assessment

| Component | Lines | Quality | Notes |
|-----------|-------|---------|-------|
| dashboard.html | 583 | Good | Clean vanilla JS, proper error handling |
| Build_Scrape_Progress.html | 1154 | Good | Static HTML, hardcoded data |
| dashboard_server.py | 230 | Good | Simple HTTP server, CORS enabled |
| pipeline_monitor.py | 290 | Good | Clean CLI with multiple output modes |
| fylo-core-mcp/index.ts | 2243 | Excellent | Comprehensive MCP implementation |

### Strengths
- Consistent dark theme across all UI components
- Real-time updates with reasonable polling interval
- Comprehensive pipeline visualization
- Good separation of concerns between server and client
- Extensive validation and self-verification tools in MCP

### Considerations
- `Build_Scrape_Progress.html` uses hardcoded data (could be dynamic)
- No WebSocket for truly real-time updates (polling-based)
- Limited error UI states in dashboard
- No authentication on dashboard server (local use only)

### Recommended Improvements (Optional)
1. Convert Build_Scrape_Progress to use API data
2. Add WebSocket support for instant updates
3. Add loading states and error boundaries
4. Consider adding basic auth for non-local deployments
