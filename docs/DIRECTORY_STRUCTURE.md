# RalphOS Directory Structure

> Auto-generated documentation of the RalphOS project directory structure.

```
RalphOS/
├── .cursor/
│   └── plans/                          # IDE planning files
│       └── *.plan.md                   # Sub-ralph pipeline architecture plans
│
├── .git/                               # Git version control
│
├── FyloCore/                           # Knowledge graph platform (git submodule)
│   └── ...                             # Full FyloCore platform for advanced graph features
│
├── fylo-core-mcp/                      # MCP Server for Knowledge Graph
│   ├── src/
│   │   └── index.ts                    # Main MCP server implementation (2243 lines)
│   ├── package.json                    # Node.js dependencies
│   ├── tsconfig.json                   # TypeScript configuration
│   ├── setup.sh                        # Installation script
│   └── README.md                       # MCP server documentation
│
├── schema/                             # Data Schemas
│   ├── build_extraction_schema.json    # Schema for extracted build data
│   └── Vehicle_Componets.json          # Vehicle components taxonomy
│
├── scripts/
│   ├── dashboard/                      # Monitoring UI
│   │   ├── dashboard.html              # Ralph Dashboard (real-time monitoring)
│   │   ├── Build_Scrape_Progress.html  # MOTORMIA Builds progress dashboard
│   │   ├── dashboard_server.py         # HTTP API server (port 8765)
│   │   └── pipeline_monitor.py         # CLI pipeline progress monitor
│   │
│   ├── ralph/                          # Core Orchestration
│   │   ├── ralph.sh                    # Main bash orchestration loop
│   │   ├── ralph-parallel.sh           # Parallel execution variant
│   │   ├── pipeline.sh                 # Pipeline orchestration
│   │   ├── check_completion.sh         # Completion checker script
│   │   ├── prompt.md                   # Agent behavior instructions
│   │   ├── sources.json                # Source registry (multi-project queue)
│   │   ├── prd.json                    # Current project definition (runtime)
│   │   ├── progress.txt                # Accumulated learnings (runtime)
│   │   │
│   │   ├── prompts/                    # Specialized Agent Prompts
│   │   │   ├── url_detective.md        # URL discovery agent instructions
│   │   │   ├── html_scraper.md         # HTML scraping agent instructions
│   │   │   ├── build_extractor.md      # Build extraction agent instructions
│   │   │   └── mod_extractor.md        # Modification extraction instructions
│   │   │
│   │   └── archive/                    # Archived PRDs
│   │       └── {timestamp}_{project}_prd.json
│   │
│   └── tools/                          # Utility Scripts
│       ├── sync_progress.py            # Sync progress from disk to sources.json
│       ├── stealth_scraper.py          # Stealth scraper for blocked sources
│       ├── diagnose_scraper.py         # Scraper issue diagnostics
│       ├── test_scraper.py             # HTML scraper testing
│       ├── test_url_discovery.py       # URL discovery testing
│       ├── build_id_generator.py       # Generate unique build IDs
│       ├── category_detector.py        # Auto-detect modification categories
│       └── create_manifest.py          # Create data manifests
│
├── data/                               # Scraped Data Output (runtime)
│   └── {source_name}/
│       ├── urls.json                   # Discovered URLs
│       ├── html/                       # Saved HTML files
│       │   └── *.html
│       ├── builds.json                 # Extracted build data
│       ├── mods.json                   # Extracted modifications
│       └── scrape_progress.json        # Progress checkpoint
│
├── logs/                               # Log Files (runtime)
│   ├── ralph_output.log                # Main execution log
│   └── ralph_debug.log                 # Debug output
│
├── archive/                            # Blocked source data storage
│
├── .mcp.json                           # Claude Code MCP configuration
├── .ralph_current_prompt.md            # Current prompt state
├── .gitignore                          # Git ignore patterns
├── .gitmodules                         # Git submodules configuration
├── CLAUDE.md                           # Claude Code instructions
├── README.md                           # Project documentation
└── requirements.txt                    # Python dependencies
```

## Directory Descriptions

### Root Files
| File | Purpose |
|------|---------|
| `.mcp.json` | MCP server configuration for Claude Code integration |
| `CLAUDE.md` | Instructions and context for Claude Code when working with this repo |
| `README.md` | Main project documentation and quick start guide |
| `requirements.txt` | Python package dependencies |

### Core Directories

#### `/scripts/dashboard/` - Monitoring UI
Contains all user interface components for monitoring Ralph's execution:
- **dashboard.html** - Real-time web dashboard with live status updates
- **Build_Scrape_Progress.html** - Static analytics dashboard for build/mod statistics
- **dashboard_server.py** - Python HTTP server providing REST API on port 8765
- **pipeline_monitor.py** - Command-line tool for monitoring pipeline stages

#### `/scripts/ralph/` - Core Orchestration
The heart of RalphOS - manages the autonomous agent loop:
- **ralph.sh** - Main entry point, iterates through user stories
- **sources.json** - Registry of all scraping sources with status tracking
- **prompt.md** - Instructions defining agent behavior
- **/prompts/** - Specialized prompts for each pipeline stage

#### `/scripts/tools/` - Utility Scripts
Helper tools for debugging, testing, and data management:
- **stealth_scraper.py** - Browser automation for blocked sites
- **diagnose_scraper.py** - Analyze and fix scraper issues
- **sync_progress.py** - Synchronize progress files with registry

#### `/fylo-core-mcp/` - Knowledge Graph MCP
Model Context Protocol server for knowledge graph capabilities:
- Tracks pipeline progress across all sources
- Provides validation and self-verification tools
- Enables DuckDB export for data analysis
- Generates Mermaid visualizations

#### `/schema/` - Data Schemas
JSON schemas defining the structure of extracted data:
- **build_extraction_schema.json** - Standard format for vehicle builds
- **Vehicle_Componets.json** - Taxonomy of vehicle modification categories

### Runtime Directories

#### `/data/` - Scraped Data
Created at runtime for each source being processed:
- `urls.json` - List of discovered content URLs
- `html/` - Downloaded HTML pages
- `builds.json` - Extracted vehicle build data
- `mods.json` - Extracted modification data

#### `/logs/` - Execution Logs
Runtime logs for monitoring and debugging:
- `ralph_output.log` - Main execution output
- `ralph_debug.log` - Detailed debug information

#### `/archive/` - Historical Data
Storage for blocked sources and archived project data.
