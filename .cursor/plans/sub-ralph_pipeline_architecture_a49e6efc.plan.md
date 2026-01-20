---
name: Sub-Ralph Pipeline Architecture
overview: Create a cascading sub-agent architecture where main Ralph orchestrates 4 specialized sub-ralphs that work in parallel with threshold-based triggers (20 items). Each sub-ralph focuses on one pipeline stage.
todos:
  - id: prompts
    content: Create 4 sub-ralph prompt files in scripts/ralph/prompts/
    status: completed
  - id: monitor
    content: Create pipeline_monitor.py for threshold-based triggers
    status: completed
  - id: orchestrator
    content: Create pipeline.sh orchestrator script
    status: completed
  - id: update-main
    content: Update ralph.sh to use pipeline mode
    status: completed
  - id: update-prompt
    content: Update prompt.md for orchestrator/QC role
    status: completed
---

# Sub-Ralph Pipeline Architecture

## Architecture Overview

```mermaid
flowchart LR
    subgraph orchestrator [Main Ralph - Orchestrator]
        O[ralph.sh]
    end
    
    subgraph pipeline [Cascading Pipeline - Same Source]
        URL[url-detective]
        HTML[html-scraper]
        BUILD[build-extractor]
        MOD[mod-extractor]
    end
    
    O -->|spawn| URL
    URL -->|20 URLs| HTML
    HTML -->|20 HTMLs| BUILD
    BUILD -->|20 builds| MOD
    
    URL -.->|writes| urls_json[urls.json]
    HTML -.->|writes| html_dir[html/]
    BUILD -.->|writes| builds_json[builds.json]
    MOD -.->|writes| mods_json[mods.json]
```



## Execution Flow

```mermaid
sequenceDiagram
    participant Main as Main Ralph
    participant URL as url-detective
    participant HTML as html-scraper
    participant BUILD as build-extractor
    participant MOD as mod-extractor
    
    Main->>URL: Start Stage 1
    loop Until all URLs found
        URL->>URL: Discover URLs
        URL-->>Main: 20 URLs ready
        Main->>HTML: Start Stage 2
    end
    
    loop Until all HTML scraped
        HTML->>HTML: Scrape HTML
        HTML-->>Main: 20 HTMLs ready
        Main->>BUILD: Start Stage 3
    end
    
    loop Until all builds extracted
        BUILD->>BUILD: Extract builds
        BUILD-->>Main: 20 builds ready
        Main->>MOD: Start Stage 4
    end
    
    MOD->>MOD: Extract mods
    MOD-->>Main: Complete
    Main->>Main: Next source
```



## Files to Create

### 1. Sub-Ralph Prompt Files

| File | Purpose ||------|---------|| [`scripts/ralph/prompts/url_detective.md`](scripts/ralph/prompts/url_detective.md) | URL discovery specialist || [`scripts/ralph/prompts/html_scraper.md`](scripts/ralph/prompts/html_scraper.md) | HTML scraping specialist || [`scripts/ralph/prompts/build_extractor.md`](scripts/ralph/prompts/build_extractor.md) | Build extraction specialist || [`scripts/ralph/prompts/mod_extractor.md`](scripts/ralph/prompts/mod_extractor.md) | Mod extraction specialist |

### 2. Pipeline Orchestrator

[`scripts/ralph/pipeline.sh`](scripts/ralph/pipeline.sh) - Main orchestration script:

```bash
# Monitors output files and triggers sub-ralphs
# - Watches urls.json count, triggers html-scraper at 20
# - Watches html/ count, triggers build-extractor at 20
# - Watches builds.json count, triggers mod-extractor at 20
# - Waits for all 4 to complete before next source
```



### 3. Progress Monitor

[`scripts/ralph/pipeline_monitor.py`](scripts/ralph/pipeline_monitor.py) - Tracks pipeline state:

```python
# Watches output files and returns trigger signals
def check_triggers(source_id):
    urls_count = count_urls(f"scraped_builds/{source_id}/urls.json")
    html_count = count_files(f"scraped_builds/{source_id}/html/")
    builds_count = count_builds(f"scraped_builds/{source_id}/builds.json")
    
    return {
        "start_html_scraper": urls_count >= 20,
        "start_build_extractor": html_count >= 20,
        "start_mod_extractor": builds_count >= 20
    }
```



## Sub-Ralph Responsibilities

### url-detective

- Focus: URL discovery ONLY
- Input: source URL from sources.json
- Output: `{outputDir}/urls.json`
- Tools: MCP webReader, webSearchPrime
- Stories: URL-001 through URL-004
- Stops when: All URLs discovered, expectedUrls updated

### html-scraper

- Focus: HTML scraping ONLY
- Input: `{outputDir}/urls.json`
- Output: `{outputDir}/html/*.html`
- Stories: HTML-001 through HTML-003
- Stops when: All URLs scraped OR blocked (sets status)

### build-extractor

- Focus: Build extraction ONLY
- Input: `{outputDir}/html/`, `schema/build_extraction_schema.json`
- Output: `{outputDir}/builds.json`
- Tools: `build_id_generator.py`
- Stories: BUILD-001 through BUILD-004
- Stops when: All HTMLs processed

### mod-extractor

- Focus: Mod extraction ONLY
- Input: `{outputDir}/builds.json`, `schema/build_extraction_schema.json`
- Output: `{outputDir}/mods.json`
- Tools: `category_detector.py`
- Stories: MOD-001 through MOD-004
- Stops when: All builds processed

## Trigger Thresholds

| Trigger | Condition | Action ||---------|-----------|--------|| Start html-scraper | `len(urls.json) >= 20` | Spawn html-scraper subprocess || Start build-extractor | `count(html/*.html) >= 20` | Spawn build-extractor subprocess || Start mod-extractor | `len(builds.json) >= 20` | Spawn mod-extractor subprocess || Source complete | All 4 sub-ralphs exit 0 | Move to next source |

## Quality Control (Main Ralph)

After all sub-ralphs complete:

1. Verify counts: `urlsFound == len(urls.json)`
2. Verify counts: `htmlScraped == count(html/)`
3. Validate `builds.json` against schema
4. Validate `mods.json` has categories from `category_detector.py`
5. Update `sources.json` with final pipeline counts
6. Set status: `completed`, `blocked`, or `in_progress`

## Implementation Order

1. Create prompt files for each sub-ralph (focused, minimal)
2. Create `pipeline_monitor.py` for threshold checking