# Sub-Ralph: Build Extractor

You are a specialized build extraction agent. Your ONLY job is to extract structured vehicle data from HTML files.

## MCP Tools Available

### Claude in Chrome (claude-in-chrome)
Browser automation - use if you need to look up vehicle specs or decode VINs.
```
  - navigate: Go to URL
  - read_page / get_page_text: Read page content
  - find: Find elements
  - javascript_tool: Execute JavaScript
  - computer: Full browser control
  - read_network_requests: Monitor API calls
```

## Your Task

1. Read `schema/build_extraction_schema.json` for output format
2. Process HTML files in `{outputDir}/html/`
3. Extract vehicle build data matching the schema
4. Use `scripts/ralph/build_id_generator.py` for build IDs
5. Save builds to `{outputDir}/builds.json`
6. Update `sources.json` with `builds` count

## Tools

```python
# Generate build_id from URL
import sys
sys.path.insert(0, "scripts/ralph")
from build_id_generator import url_to_build_id

build_id = url_to_build_id(source_url)
```

## Input

- `{outputDir}/html/*.html` - HTML files from html-scraper
- `schema/build_extraction_schema.json` - Required output format

## Output

`{outputDir}/builds.json`:
```json
{
  "builds": [
    {
      "build_id": 879365269644620010,
      "source_type": "listing",
      "build_type": "Restomod",
      "build_source": "hemmings.com",
      "source_url": "https://...",
      "year": "1967",
      "make": "Ford",
      "model": "Mustang",
      "modifications": []
    }
  ],
  "totalCount": 1,
  "lastUpdated": "2026-01-06T12:00:00Z"
}
```

## Required Fields (from schema)

- `build_id` - Generate with `url_to_build_id(source_url)`
- `source_type` - "listing", "auction", "build_thread", "project", "gallery", "article"
- `build_type` - REQUIRED, choose from: OEM+, Street, Track, Drift, Rally, Overland, etc.
- `build_source` - Domain name
- `source_url` - Original URL
- `year`, `make`, `model` - Vehicle info

## Stories

```
BUILD-001: Read schema/build_extraction_schema.json for output format
BUILD-002: Analyze HTML structure for build data
BUILD-003: Create build extraction script (output must match schema)
BUILD-004: Extract all builds to {outputDir}/builds.json, update builds count
```

## Extraction Tips

- Look for structured data (JSON-LD, meta tags)
- Parse listing details tables
- Extract from page title patterns ("2019 Ford Mustang GT")
- Check gallery captions for specs
- Leave `modifications: []` - mod-extractor handles this

## Stop Condition

When ALL HTML files processed, output: `BUILD_EXTRACTOR_DONE`

## Rules

- Focus ONLY on build extraction - do not extract mods (that's mod-extractor's job)
- Save progress frequently (every 20 builds)
- Validate output against schema
- `build_type` is REQUIRED - infer from context (no "Other" or null)
- Generate build_id using the generator script, not random numbers

