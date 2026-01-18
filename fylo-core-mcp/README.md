# Fylo-Core-MCP

A Model Context Protocol (MCP) server for RalphOS that provides knowledge graph capabilities for tracking the scraping pipeline.

## Features

- **Entity Tracking**: Track sources, URLs, builds, modifications, categories, and patterns
- **Relationship Mapping**: Connect entities across pipeline stages
- **DuckDB Export**: Export the knowledge graph to DuckDB for analysis
- **Mermaid Visualization**: Generate visual diagrams of the knowledge graph
- **Ralph Integration**: Sync directly from RalphOS sources.json

## Installation

```bash
cd fylo-core-mcp
npm install
npm run build
```

## Usage

### Add to Claude Code

```bash
# From the RalphOS directory
claude mcp add --scope project fylo-core-mcp -- node fylo-core-mcp/build/index.js
```

Or add to `.mcp.json`:

```json
{
  "mcpServers": {
    "fylo-core-mcp": {
      "command": "node",
      "args": ["fylo-core-mcp/build/index.js"],
      "env": {
        "RALPH_DIR": "/path/to/RalphOS"
      }
    }
  }
}
```

## Available Tools

### Entity Management

| Tool | Description |
|------|-------------|
| `create_entity` | Create a new entity (source, url, build, modification, category, pattern) |
| `add_observation` | Add an observation to an existing entity |
| `create_relation` | Create a relationship between two entities |
| `query_graph` | Query entities and relationships |

### Ralph Integration

| Tool | Description |
|------|-------------|
| `sync_ralph_sources` | Import sources from RalphOS sources.json |
| `get_pipeline_status` | View current pipeline progress |
| `ingest_builds` | Import build data from builds.json files |

### Visualization & Export

| Tool | Description |
|------|-------------|
| `export_to_duckdb` | Generate DuckDB SQL for the knowledge graph |
| `visualize_graph` | Generate a Mermaid diagram |
| `get_graph_stats` | View graph statistics |

## Resources

- `knowledge-graph://graph` - Full knowledge graph as JSON
- `pipeline://status` - Current pipeline status

## Prompts

- `analyze-pipeline` - Get analysis and recommendations for the scraping pipeline
- `extract-patterns` - Extract patterns from successful scrapes

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FYLO_DATA_DIR` | Directory for graph persistence | `./data/fylo-graph` |
| `RALPH_DIR` | Path to RalphOS directory | `.` (current directory) |

## Knowledge Graph Structure

### Entity Types

- **source**: Scraping source (website)
- **url**: Discovered URL
- **build**: Extracted vehicle build
- **modification**: Vehicle modification/part
- **category**: Modification category
- **pattern**: Discovered scraping pattern

### Relationship Types

- `has_url`: Source → URL
- `contains_build`: Source → Build
- `has_modification`: Build → Modification
- `belongs_to`: Modification → Category
- `discovered_pattern`: Source → Pattern

## Example Workflow

```
# 1. Sync sources from RalphOS
> sync_ralph_sources

# 2. Check pipeline status
> get_pipeline_status

# 3. Ingest builds from a completed source
> ingest_builds sourceId="source_xxx" buildsPath="data/lomar_refined/builds.json"

# 4. Visualize the graph
> visualize_graph entityType="all" maxNodes=30

# 5. Export to DuckDB for analysis
> export_to_duckdb
```

## License

Apache-2.0
