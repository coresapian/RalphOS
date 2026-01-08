Specification for approval
  ──────────────────────────────────────────────────────────────────────────────────────────────

   RalphOS Codebase Analysis & Improvement Plan

   Executive Summary

   RalphOS is an autonomous AI agent loop system that executes multi-step web scraping tasks
   without human intervention. It wraps Claude CLI in a bash loop to process vehicle build data
   from multiple sources through a 4-stage pipeline.

   Current Status:
   •  Total Cost Involved: 295 URLs discovered, 3 HTML scraped (1% progress)
   •  5 sources pending in queue
   •  Core infrastructure functional but several improvements identified

   ──────────────────────────────────────────

   Architecture Overview

   System Design

     ┌─────────────────────────────────────────────────────────────┐
     │                   ralph.sh (Bash Loop)                  │
     │  ┌──────────────────────────────────────────────────────┐  │
     │  │  Iteration Manager                                 │  │
     │  │  - Calls Claude CLI                                │  │
     │  │  - Monitors progress (10s interval)                 │  │
     │  │  - Commits changes                                 │  │
     │  │  - Updates PRD & sources.json                       │  │
     │  └──────────────────────────────────────────────────────┘  │
     └─────────────────────────────────────────────────────────────┘
                               │
                               ▼
     ┌─────────────────────────────────────────────────────────────┐
     │              Pipeline Stages (Sub-Ralph Agents)           │
     ├──────────────┬──────────────┬──────────────┬───────────┤
     │ URL Detective│ HTML Scraper │ Build Extractor│Mod Extractor│
     │ (Stage 1)   │ (Stage 2)     │ (Stage 3)     │ (Stage 4)   │
     │ URL Discovery│ HTML Fetch     │ Data Extract  │ Mod Categorize│
     └──────────────┴──────────────┴──────────────┴───────────┘
                               │
                               ▼
     ┌─────────────────────────────────────────────────────────────┐
     │                  Data Pipeline                           │
     │  urls.jsonl → html/ → builds.json → mods.json         │
     └─────────────────────────────────────────────────────────────┘

   Key Components

   Component              │ Purpose                                    │ Status          
   -----------------------+--------------------------------------------+-----------------
   `ralph.sh`             │ Main orchestration loop                    │ ✅ Functional
   `sources.json`         │ Multi-project queue with pipeline tracking │ ✅ Working
   `prompt.md`            │ Agent behavior instructions                │ ✅ Comprehensive
   `url-detective/`       │ Stage 1: URL discovery agent               │ ✅ Implemented
   `html-scraper/`        │ Stage 2: HTML scraping agent               │ ✅ Implemented
   `build-extractor/`     │ Stage 3: Build data extraction             │ ✅ Ready
   `mod-extractor/`       │ Stage 4: Mod extraction & categorization   │ ✅ Ready
   `stealth_scraper.py`   │ Anti-bot scraping (Camoufox)               │ ✅ Available
   `category_detector.py` │ Automatic mod categorization               │ ✅ Sophisticated
   `check_completion.sh`  │ Status validation & correction             │ ✅ Robust

   ──────────────────────────────────────────

   Core Components Analysis

   1. Main Orchestration (`scripts/ralph/ralph.sh`)

   Strengths:
   •  ✅ Well-structured bash loop with proper signal handling
   •  ✅ Progress monitoring every 10 seconds
   •  ✅ Automatic archiving of completed projects
   •  ✅ Color-rich terminal output for readability
   •  ✅ Proper cleanup of child processes on SIGINT
   •  ✅ Completion status validation before proceeding

   Issues Identified:
   1. No auto-resume capability - On restart, must manually track where to resume
   2. Limited error recovery - If Claude CLI crashes, loop continues without recovery logic
   3. No checkpoint system - Progress only saved after full iteration completion
   4. Hardcoded feature flags - SCRAPE_ONLY and VERBOSE could be in config
   5. No rate limiting awareness - Doesn't respect time delays between sources

   Recommendations:
   •  Add checkpoint system (save iteration state to JSON file every 30s)
   •  Implement auto-resume from last checkpoint on restart
   •  Add exponential backoff for Claude CLI failures
   •  Move feature flags to config file (scripts/ralph/config.json)

   2. Pipeline Tracking (`scripts/ralph/sources.json`)

   Strengths:
   •  ✅ Comprehensive pipeline stage tracking (7 fields)
   •  ✅ Status validation in check_completion.sh
   •  ✅ Block event tracking (timestamp, type, count)
   •  ✅ Multi-source queue management

   Issues Identified:
   1. No progress percentage tracking - Only raw counts, no visual progress bar
   2. Manual status updates required - No auto-sync from disk during runtime
   3. No source priority system - All pending sources processed linearly
   4. Missing retry counters - Track how many times blocked sources retried
   5. No cost tracking - No API call costs or time per source

   Recommendations:
   •  Add priority field to sources (1-10, default 5)
   •  Add attempted counter for blocked sources
   •  Add lastAttempted timestamp
   •  Add totalTimeSpent per source
   •  Implement auto-source selection based on priority + status

   3. Sub-Stage Coordination

   Current Approach:
   •  Each stage is an independent agent with own prompt.md
   •  Ralph coordinates by updating sources.json pipeline fields
   •  No direct inter-stage communication

   Issues Identified:

   2. No handoff protocol - No validation between stages
   3. Duplicate code - Similar URL discovery logic in multiple sources
   4. No test suite - Each stage script is manually tested

   Recommendations:
   •  Implement stage transition validation script
   •  Add unit tests for each stage
   •  Create template scripts for new sources

   4. Data Schema & Extraction

   Schema Strengths:
   •  ✅ Comprehensive vehicle build fields (30+ properties)
   •  ✅ Strict typing with enums where appropriate
   •  ✅ Conditional fields (sale_data, wheel_specs)
   •  ✅ Validation rules (VIN pattern, year format)
   •  ✅ Modification level auto-calculation (Stock/Heavy)

   Issues Identified:
   1. Missing fields for common data - No mileage for project builds
   2. No validation script - Schema defined but not enforced
   3. Versioning missing - Schema changes could break pipeline

   Recommendations:
   •  Add schema version field ("version": "1.2.0")
   •  Create validation script (validate_builds.py)
   •  Add migration system for schema changes
   •  Add markdown documentation for required vs optional fields

   5. Category Detector (`scripts/tools/category_detector.py`)

   Strengths:
   •  ✅ Sophisticated fuzzy matching
   •  ✅ Priority-based keyword lookup
   •  ✅ Support for batch processing
   •  ✅ Comprehensive component database
   •  ✅ Confidence scoring

   Issues Identified:
   1. No learning from misclassifications - Manual corrections not saved
   2. Large component list - 500+ items, slower lookups
   3. No brand extraction - Could auto-detect brands from mod names
   4. Hard-coded categories - Cannot add new categories without code changes

   Recommendations:
   •  Add category_corrections.json for learning from errors
   •  Implement trie data structure for faster lookups
   •  Add brand detector using known manufacturer list
   •  Make categories configurable via JSON file

   ──────────────────────────────────────────

   Current State Assessment

   Pipeline Health

   Source              │ Status      │ URLs  │ HTML │ Builds │ Mods │ Progress
   --------------------+-------------+-------+------+--------+------+---------
   total_cost_involved │ in_progress │ 295   │ 3    │ null   │ null │ 1%
   custom_wheel_offset │ blocked     │ 4,497 │ 69   │ null   │ null │ 1%
   onallcylinders      │ in_progress │ ?     │ ?    │ null   │ null │ ?
   All Others          │ pending     │ 0     │ 0    │ null   │ null │ 0%

   Blocked Sources Analysis

   •  custom_wheel_offset: 4,497 URLs, 69 scraped, 4,428 blocked by 403
     •  Recommendation: Run stealth_scraper.py --source custom_wheel_offset

   •  Potential blockers: Sources with aggressive anti-bot protection may all fail without
      Camoufox

   Total Cost Involved Specifics

   URL Discovery (Stage 1): ✅ Complete
   •  295 URLs discovered
   •  All follow pattern: https://totalcostinvolved.com/testimonials/{slug}/

   HTML Scraping (Stage 2): 🔄 In Progress (1%)
   •  Only 3 of 295 HTML files scraped
   •  Issue: Scraping script exists but may have errors or be incomplete

   Root Cause Analysis:
   Looking at data/total_cost_involved/, multiple scraper scripts exist:
   •  scrape_html.py (7,568 bytes)
   •  scrape_html_mcp.py (8,314 bytes)
   •  scrape_html_with_mcp.py (3,067 bytes)
   •  batch_scraper.py (1,317 bytes)

   Multiple scraper iterations suggest:
   1. Initial approach failed → created new script
   2. MCP approach attempted → created MCP version
   3. No convergence on working solution

   Diagnosis Needed:

   bash
     python scripts/tools/diagnose_scraper.py data/total_cost_involved/

   ──────────────────────────────────────────

   Recommended Improvements

   Priority 1: Critical (Complete Blocking Issues)

   1. Fix Total Cost Involved Scraping - 1% progress suggests script bug
     •  Run diagnostic tool
     •  Check for timeout errors, blocking, or parsing issues
     •  Verify URL structure matches scraper expectations
     •  Estimated: 2-4 hours

   2. Implement Retry Logic for Blocked Sources
     •  After stealth scraper success, auto-retry remaining URLs
     •  Don't require manual intervention for every blocked source
     •  Estimated: 4-6 hours

   3. Add Real-Time Progress Dashboard
     •  Browser-based monitoring (already has dashboard_server.py)
     •  Show pipeline status, errors, ETA
     •  Estimated: 6-8 hours

   Priority 2: High (Improve Reliability)

   4. Add Checkpoint & Resume System
     •  Save iteration state every 30 seconds
     •  Auto-resume on script restart
     •  Prevents re-running completed iterations
     •  Estimated: 8-12 hours

   5. Implement Auto-Source Selection
     •  Add priority field to sources.json
     •  Pick highest priority pending source
     •  Skip blocked sources unless manually specified
     •  Estimated: 4-6 hours

   6. Add Stage Validation Tests
     •  Unit tests for each stage script
     •  Integration tests for full pipeline
     •  Prevent regressions when adding new sources
     •  Estimated: 12-16 hours

   Priority 3: Medium (Optimize Performance)

   7. Optimize Category Detector
     •  Replace linear search with trie data structure
     •  Expected speedup: 10-100x for large batches
     •  Estimated: 6-8 hours

   8. Add Parallel Scraping Support
     •  Scrape multiple URLs concurrently
     •  Rate limit per source, not globally
     •  Estimated 3-5x speedup for large sources
     •  Estimated: 16-20 hours

   9. Create Source Templates
     •  Template scripts for common site types (WordPress, custom gallery, etc.)
     •  Reduce code duplication
     •  Faster onboarding for new sources
     •  Estimated: 8-12 hours

   Priority 4: Low (Quality of Life)

   10. Add Configuration System
     •  Move hardcoded values to config file
     •  Support per-source overrides
     •  Estimated: 4-6 hours

   11. Improve Logging & Debugging
     •  Structured logging (JSON format)
     •  Log rotation (prevent massive log files)
     •  Debug mode toggle
     •  Estimated: 4-6 hours

   12. Add CLI Tool for Common Tasks
     •  ralph-cli status - Show pipeline health
     •  ralph-cli retry <source> - Retry blocked source
     •  ralph-cli add <url> - Add new source to queue
     •  Estimated: 8-10 hours

   ──────────────────────────────────────────

   Technical Debt & Code Quality Issues

   1. Bash Scripting (`ralph.sh`)

   Issues:
   •  900+ line bash script (hard to maintain)
   •  Heavy use of jq for JSON manipulation (slow)
   •  No error handling for subprocess failures
   •  Inline color codes (should use functions)

   Recommendation:
   •  Refactor critical sections to Python
   •  Use Python's json library instead of jq
   •  Add try/except blocks for subprocess calls
   •  Create color utility functions

   2. Progress Tracking

   Issues:
   •  progress.txt doesn't exist (referenced in docs but missing)
   •  No accumulated learnings documented
   •  Manual updates required
   •  No searchable knowledge base

   Recommendation:
   •  Auto-create progress.txt if missing
   •  Extract learnings from iteration logs automatically
   •  Use Markdown with tags for searching
   •  Implement knowledge base queries

   3. Data Storage

   Issues:
   •  Multiple file formats (.json, .jsonl, .json)
   •  No clear schema versioning
   •  Mixed file locations (data/ vs scripts/ralph-stages/)
   •  No backup/restore mechanism

   Recommendation:
   •  Standardize on .jsonl for lists (one record per line)
   •  Add schema version to all JSON files
   •  Consolidate data storage under data/
   •  Implement git-based backups before major operations

   4. Stealth Scraper (`stealth_scraper.py`)

   Issues:
   •  600+ line monolithic script
   •  No unit tests
   •  Hardcoded delay values
   •  No proxy rotation (mentioned in comments but not implemented)

   Recommendation:
   •  Split into classes (StealthConfig, StealthScraper, ProxyManager)
   •  Add unit tests with mocked browser
   •  Make delays configurable per source
   •  Implement proxy rotation pool

   ──────────────────────────────────────────

   Performance Optimization Opportunities

   1. Scraping Speed

   Current: ~1 URL per second (sequential)

   Optimizations:
   1. Concurrent requests: Use asyncio with semaphore (limit 10 concurrent)
   2. Connection pooling: Reuse HTTP connections
   3. Request batching: Fetch multiple pages in parallel

   Expected Speedup: 5-10x

   2. Data Processing

   Current: O(n) linear search for category detection

   Optimizations:
   1. Trie data structure: O(k) where k = keyword length
   2. Caching: Memoize frequently seen mod names
   3. Pre-computation: Build category lookup table on startup

   Expected Speedup: 50-100x for category detection

   3. I/O Bottlenecks

   Current: Synchronous file writes, no buffering

   Optimizations:
   1. Buffered writes: Flush to disk every 100 records
   2. Memory mapping: Use mmap for large JSONL files
   3. Compression: Compress old HTML files (gzip)

   Expected Speedup: 2-3x for file I/O

   ──────────────────────────────────────────

   Security & Reliability Concerns

   1. API Keys

   Issue: ZAI_API_KEY stored in .env (checked into git?)

   Recommendation:
   •  Remove .env from git (already in .gitignore)
   •  Add .env.example template
   •  Document API key setup in README
   •  Consider secret management (e.g., HashiCorp Vault)

   2. Anti-Bot Detection

   Current Approach:
   •  Simple headers in regular scrapers
   •  Camoufox for stealth scraping

   Issues:
   •  No automatic fallback to Camoufox
   •  No proxy rotation
   •  No request rate limiting

   Recommendation:
   •  Detect 403/429 errors and auto-switch to Camoufox
   •  Implement request rate limiter per source
   •  Add proxy rotation with health checks
   •  Track success rates per scraping method

   3. Data Integrity

   Issues:
   •  No checksums for downloaded files
   •  No validation of extracted data
   •  No rollback on extraction failures

   Recommendation:
   •  Add SHA256 checksums for HTML files
   •  ralph should Run validation script after each stage
   •  Implement atomic writes (write to temp, then rename)
   •  Add data restoration point before bulk operations

   ──────────────────────────────────────────

   Proposed Refactoring Roadmap

   Phase 1: Stabilization (Week 1)

   Goal: Complete blocked sources, fix critical bugs

   1. Fix Total Cost Involved scraping (Priority 1.1)
   2. Implement retry logic for stealth scrapes (Priority 1.2)
   3. Add checkpoint/resume system (Priority 2.1)

   Phase 2: Reliability (Week 2)

   Goal: Reduce manual intervention, improve uptime

   4. Implement auto-source selection (Priority 2.2)
   5. Add stage validation tests (Priority 2.3)
   6. Optimize category detector (Priority 3.1)

   7. Add parallel scraping (Priority 3.2)
   8. Create source templates (Priority 3.3)
   9. Refactor ralph.sh to Python (Priority - Debt 1)

   10. Add configuration system (Priority 4.1)
   11. Improve logging (Priority 4.2)
   12. Add CLI tool (Priority 4.3)
