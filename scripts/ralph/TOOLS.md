# Ralph's Enhanced Toolkit

This document describes all available tools for Factory Ralph loops.
**IMPORTANT:** Use these tools instead of raw commands for robustness and consistency.

---

## 📚 Quick Reference

| Tool | Purpose | Usage |
|------|---------|-------|
| `ralph_utils.py` | Core Python utilities | `from ralph_utils import *` |
| `ralph_duckdb.py` | Database operations | `from ralph_duckdb import RalphDuckDB` |
| `ralph_vlm.py` | Vision analysis (Moondream) | `from ralph_vlm import MoondreamClient` |
| `ralph_validator.py` | Visual validation gate | `from ralph_validator import RalphValidator` |
| `ralph_mcp.py` | MCP server integration | `from ralph_mcp import get_mcp_client` |
| `browser_helper.js` | Browser DOM utilities | `browser_evaluate(script=...)` |
| `cloudflare_bypass_scraper.py` | FREE CF Turnstile bypass | `python scripts/tools/cloudflare_bypass_scraper.py` |

---

## 1. Core Utilities (`ralph_utils.py`)

### File Operations

```python
from ralph_utils import safe_write, safe_write_json, safe_read_json, ensure_directory

# ALWAYS use safe_write for file output (atomic, crash-safe)
safe_write("output.txt", content)
safe_write_json("data.json", {"key": "value"})

# Read JSON with default fallback
data = safe_read_json("config.json", default={})

# Ensure directory exists
ensure_directory("data/source_name/html")
```

### URL Utilities

```python
from ralph_utils import normalize_url, extract_domain, deduplicate_urls, is_valid_url

# Normalize for consistent comparison
url = normalize_url("HTTPS://WWW.Example.COM/page?utm_source=test#section")
# Returns: "https://example.com/page"

# Extract domain
domain = extract_domain("https://www.example.com/path")
# Returns: "example.com"

# Remove duplicates
unique_urls = deduplicate_urls(url_list)

# Validate URL
if is_valid_url(url):
    process(url)
```

### HTTP Client

```python
from ralph_utils import get_robust_session, is_blocked_response

# Get session with automatic retries and backoff
session = get_robust_session(retries=3)
response = session.get("https://api.example.com/data")

# Check for blocking
if is_blocked_response(response.status_code, response.headers, response.text):
    handle_blocked()
```

### Logging

```python
from ralph_utils import logger

# Structured logging (outputs to JSONL)
logger.info("Task started", {"source": "luxury4play"})
logger.success("Scrape complete", {"urls": 50})
logger.warning("Rate limited", {"delay": 5})
logger.error("Request failed", {"status": 403})
```

### Batch Processing

```python
from ralph_utils import batch_process, retry_with_backoff, RateLimiter

# Process items with rate limiting
limiter = RateLimiter(requests_per_second=2)
for url in urls:
    limiter.wait()
    response = session.get(url)

# Retry with exponential backoff
result = retry_with_backoff(
    lambda: session.get(url),
    max_retries=3
)
```

---

## 2. DuckDB Database (`ralph_duckdb.py`)

### Basic Operations

```python
from ralph_duckdb import RalphDuckDB, get_db

# Create/connect to database
db = RalphDuckDB("ralph_data.duckdb")  # File-based
db = RalphDuckDB(":memory:")           # In-memory

# Execute SQL
db.execute("CREATE TABLE test AS SELECT * FROM range(10)")

# Query as dict list
results = db.query("SELECT * FROM test WHERE id > 5")

# Query as pandas DataFrame
df = db.query_to_df("SELECT * FROM builds WHERE year > 2020")

# Single value
count = db.query_scalar("SELECT COUNT(*) FROM builds")
```

### Data Import

```python
# Import from any supported format (auto-detected)
db.import_file("data/builds.json", "builds")
db.import_file("data/urls.csv", "urls")
db.import_file("data/mods.parquet", "mods")

# RalphOS-specific imports
db.import_builds("data/luxury4play")    # Imports builds.json
db.import_mods("data/luxury4play")      # Imports mods.json
db.import_urls("data/luxury4play")      # Imports urls.json
```

### Data Export

```python
# Export table to file
db.export_table("builds", "output/builds.parquet")  # Best performance
db.export_table("builds", "output/builds.csv")
db.export_table("builds", "output/builds.json")

# Export query results
db.export_query("SELECT * FROM builds WHERE year > 2023", "recent_builds.parquet")
```

### Analytics

```python
# Get table info
info = db.get_table_info("builds")
# Returns: {"table_name": "builds", "row_count": 150, "columns": [...]}

# Get build statistics
stats = db.get_build_stats()
# Returns: {"total_builds": 150, "by_make": [...], "by_year": [...]}

# Deduplicate
removed = db.deduplicate_builds("builds", key_columns=["build_id"])
```

### Advanced SQL (DuckDB-Specific)

```sql
-- GROUP BY ALL: Auto-group non-aggregated columns
SELECT make, model, COUNT(*) as count
FROM builds
GROUP BY ALL;

-- SELECT * EXCLUDE: Get all columns except specified
SELECT * EXCLUDE (internal_id, created_at)
FROM builds;

-- Window functions
SELECT
    build_id,
    year,
    ROW_NUMBER() OVER (PARTITION BY make ORDER BY year DESC) as rank
FROM builds;
```

---

## 3. Vision Language Model (`ralph_vlm.py`)

### Setup

```python
from ralph_vlm import MoondreamClient, get_vlm

# Using Ollama (faster startup)
vlm = MoondreamClient(provider="ollama")

# Using Hugging Face (newest features)
vlm = MoondreamClient(provider="huggingface")
```

### Basic Analysis

```python
# Ask any question about an image
result = vlm.analyze_image("screenshot.png", "What is the main color?")

# Extract text (OCR)
text = vlm.extract_text("code_screenshot.png", region="center")

# Describe UI
description = vlm.describe_ui("dashboard.png")
```

### UI Verification

```python
# Find element
result = vlm.find_element("page.png", "submit button")
if result['found']:
    print(f"Found: {result['description']}")

# Check text presence
result = vlm.check_text_presence("page.png", "Welcome, User")
if result['found']:
    print("Login successful")

# Get color info
color = vlm.get_color_info("button.png", "submit button")
```

### Chart Analysis

```python
# Analyze data visualization
analysis = vlm.analyze_chart("sales_chart.png", "What is the trend?")
```

### Best Practices

**✅ Good Prompts (Specific):**
- "Is the 'Login' button red?"
- "Is the text centered in the box?"
- "Are there exactly 3 navigation links?"

**❌ Bad Prompts (Vague):**
- "Does it look good?"
- "Is the design nice?"
- "Is it done?"

---

## 4. Visual Validator (`ralph_validator.py`)

The **Final Gatekeeper** for Factory Ralph loops.

### Setup

```python
from ralph_validator import RalphValidator

validator = RalphValidator(provider="ollama")
```

### Core Validation

```python
# Main validation - returns Pass/Fail
result = validator.validate("screenshot.png", "The submit button is blue and visible")

if result['passed']:
    # Task complete!
    create_success_file()
else:
    # Fix needed
    print(f"Fix: {result['reasoning']}")
```

### Specialized Validators

```python
# OCR validation (check text presence)
result = validator.check_ocr("page.png", "Welcome, User", exact_match=False)

# Layout validation
result = validator.check_ui_layout("dashboard.png", "Three column layout with sidebar")

# Element visibility
result = validator.check_element_visible("page.png", "navigation menu")

# Color check
result = validator.check_color("button.png", "submit button", "blue")

# State check
result = validator.check_state("form.png", "submit button", "enabled")
```

### Multi-Criteria Validation

```python
# All criteria must pass
result = validator.validate_all("page.png", [
    "Header is visible at top",
    "Navigation has 5 links",
    "Footer contains copyright"
])

if result['passed']:
    print(f"All {result['passed_count']}/{result['total_criteria']} passed")
```

### Mandatory Validation Protocol

**Before creating `.ralph_success`:**

1. Take screenshot: `browser_screenshot(path="validate.png")`
2. Run validation: `validator.validate("validate.png", criteria)`
3. Only proceed if `result['passed'] == True`

---

## 5. MCP Integration (`ralph_mcp.py`)

### Setup

```python
from ralph_mcp import get_mcp_client

mcp = get_mcp_client()
```

### Vision MCP Tools

```python
# Convert UI to code
result = mcp.ui_to_artifact("design.png", output_type="code")

# Extract text from screenshot
result = mcp.extract_text_from_screenshot("code.png", language_hint="python")

# Diagnose error
result = mcp.diagnose_error_screenshot("error.png", context="during npm install")

# Analyze diagram
result = mcp.understand_technical_diagram("architecture.png")

# Analyze chart
result = mcp.analyze_data_visualization("chart.png", analysis_focus="trends")

# Compare UIs
result = mcp.ui_diff_check("expected.png", "actual.png")
```

### Web Tools

```python
# Search web
results = mcp.search_web("DuckDB Python tutorial", num_results=10)

# Read webpage
content = mcp.read_webpage("https://duckdb.org/docs")
```

### GitHub Tools (Zread)

```python
# Search repository docs
results = mcp.search_repo_docs("https://github.com/duckdb/duckdb", "Python API")

# Get repo structure
structure = mcp.get_repo_structure("https://github.com/duckdb/duckdb", path="src")

# Read specific file
content = mcp.read_repo_file("https://github.com/duckdb/duckdb", "README.md")
```

---

## 6. Browser Helper (`browser_helper.js`)

### Injection

First, inject the helper into the browser context:

```javascript
browser_evaluate(script=<contents of scripts/tools/browser_helper.js>)
```

### Text Extraction

```javascript
// Get text from multiple elements
RALPH.getTextList('.product-title')
// Returns: ['iPhone 15', 'MacBook Pro', 'iPad Air']

// Get all visible page text
RALPH.getAllText(5000)
```

### Element Finding

```javascript
// Find by visible text (most robust!)
RALPH.findByText('Submit').click()
RALPH.findByText('Add to Cart', 'button').click()

// Find by aria-label
RALPH.findByLabel('Search')

// Find nearest clickable element
RALPH.findClickable('.icon-wrapper')
```

### Waiting

```javascript
// Wait for element (MutationObserver-based, efficient)
await RALPH.waitFor('.modal-content')
await RALPH.waitFor('#results', 10000)

// Wait for text
await RALPH.waitForText('Success!')

// Wait for network idle
await RALPH.waitForNetworkIdle(500, 10000)
```

### Interaction

```javascript
// Click and wait for effects
await RALPH.clickAndWait('#submit-btn', 100)

// Fill form field (dispatches React/Vue events)
RALPH.fillField('#email', 'test@example.com')

// Fill multiple fields
RALPH.fillForm({
    '#email': 'test@example.com',
    '#password': 'secret123'
})

// Select dropdown option
RALPH.selectOption('#country', 'US')
```

### Data Extraction

```javascript
// Extract table data
const data = RALPH.extractTable('table.results')
// Returns: { headers: ['Name', 'Price'], rows: [['iPhone', '$999'], ...] }

// Get all links
const links = RALPH.getLinks({ internal: true, external: false })
// Returns: [{ href: '...', text: '...', internal: true }, ...]
```

### React/Vue Inspection

```javascript
// Get React component props
const props = RALPH.getReactProps('.product-card')

// Get React state
const state = RALPH.getReactState('.shopping-cart')

// Get Vue data
const data = RALPH.getVueData('.app-container')
```

### Scrolling

```javascript
// Scroll to bottom (for infinite scroll)
await RALPH.scrollToBottom(500, 50)

// Scroll element into view
RALPH.scrollIntoView('.target-element')
```

### Utilities

```javascript
// Highlight element for debugging
RALPH.highlight('.button', 'red')
RALPH.clearHighlights()

// Get page metadata
const info = RALPH.getPageInfo()
// Returns: { url, title, description, canonical, ogTitle, ogImage }

// Check if text exists
if (RALPH.hasText('Welcome')) { ... }

// Count elements
const count = RALPH.count('.product-item')
```

---

## 🔧 Tool Selection Guide

| Task | Tool |
|------|------|
| File I/O | `ralph_utils.safe_write`, `safe_read_json` |
| HTTP requests | `ralph_utils.get_robust_session` |
| Data storage | `ralph_duckdb.RalphDuckDB` |
| Image analysis | `ralph_vlm.MoondreamClient` |
| Visual validation | `ralph_validator.RalphValidator` |
| Cloudflare bypass | `cloudflare_bypass_scraper.py` |
| Web search | `ralph_mcp.search_web` |
| GitHub exploration | `ralph_mcp.get_repo_structure` |
| DOM traversal | `browser_helper.js` (RALPH.*) |

---

## 7. Cloudflare Bypass Scraper (`cloudflare_bypass_scraper.py`)

A FREE Cloudflare Turnstile bypass solution using Camoufox's anti-detection capabilities combined with `camoufox-captcha` for automatic solving. **No proxies or paid services required.**

### Why It Works Without Proxies

| Factor | Impact |
|--------|--------|
| **Home IP = Residential** | ISP-assigned IPs have high trust scores (no datacenter reputation) |
| **Camoufox Fingerprinting** | C++ level injection is undetectable via JavaScript |
| **camoufox-captcha** | Traverses Shadow DOM to click CF checkbox automatically |
| **Persistent Profile** | Saves `cf_clearance` cookies between runs |

### Installation

```bash
# Install dependencies
pip install "camoufox[geoip]>=0.4.11" camoufox-captcha orjson tqdm

# Fetch Camoufox browser binary
python -m camoufox fetch
```

### Basic Usage

```bash
# Standard scraping (headless mode)
python scripts/tools/cloudflare_bypass_scraper.py --source audiocityusa --limit 50

# Debug mode (visible browser)
python scripts/tools/cloudflare_bypass_scraper.py --source nicheroadwheels --no-headless --limit 10

# Custom output directory
python scripts/tools/cloudflare_bypass_scraper.py --source mysite --output data/mysite/html
```

### Critical Configuration

```python
from camoufox.async_api import AsyncCamoufox
from camoufox_captcha import solve_captcha

# These settings are REQUIRED for CF bypass
launch_kwargs = {
    "os": "windows",  # Vary: windows, macos, linux
    "humanize": True,  # Natural cursor movement at C++ level
    "block_webrtc": True,  # Prevent IP leaks
    "config": {
        "forceScopeAccess": True  # CRITICAL: Pierces closed Shadow DOM
    },
    "disable_coop": True,  # CRITICAL: CF iframe cross-origin bypass
    "headless": True,
    "persistent_context": True,
    "user_data_dir": "/path/to/profile",  # Saves cookies
}

async with AsyncCamoufox(**launch_kwargs) as browser:
    page = await browser.new_page()
    await page.goto(url)

    # Detect and solve Cloudflare
    if await is_cloudflare_challenge(page):
        success = await solve_captcha(
            page,
            captcha_type="cloudflare",
            challenge_type="turnstile",  # or "interstitial"
            solve_attempts=3,
            solve_click_delay=(0.5, 1.5),
        )
```

### How camoufox-captcha Works

1. **Shadow DOM Traversal**: CF hides its checkbox in a closed Shadow DOM. `forceScopeAccess: True` opens access.
2. **COOP Bypass**: `disable_coop: True` allows interaction with CF's cross-origin iframe.
3. **Human-like Clicking**: Random delays (0.5-1.5s) + Camoufox's C++ cursor movement.
4. **Cookie Persistence**: After solving, `cf_clearance` cookie is saved for future requests.

### Challenge Types

| Type | Detection Pattern | Description |
|------|-------------------|-------------|
| `interstitial` | Full-page challenge | "Checking your browser..." wait page |
| `turnstile` | Embedded checkbox | Smaller widget on page requiring click |

### Python Integration Example

```python
from pathlib import Path
from cloudflare_bypass_scraper import CloudflareBypassScraper, CloudflareScraperConfig

config = CloudflareScraperConfig(
    source_name="mysite",
    headless=True,
    user_data_dir=Path("./browser_profiles/mysite"),
    solve_attempts=3,
    page_load_timeout=60000,
)

scraper = CloudflareBypassScraper(config)

# Scrape URLs
results = await scraper.scrape_urls(
    urls=["https://example.com/page1", "https://example.com/page2"],
    output_dir=Path("data/mysite/html"),
)

print(f"Success: {results['success']}, Failed: {results['failed']}")
```

### Troubleshooting

| Problem | Solution |
|---------|----------|
| Still getting blocked | Enable `--no-headless` to verify challenge appears |
| Challenge not detected | Check page content for "Checking your browser" or `cf-turnstile` |
| Cookie not persisting | Verify `persistent_context=True` and `user_data_dir` is writable |
| Slow solving | Increase `solve_click_delay` range for more natural timing |

### When to Use This Tool

- **audiocityusa**, **nicheroadwheels** - Known CF-protected sources
- Any site showing "Checking your browser..." interstitial
- Sites with Turnstile checkbox captchas
- When `aggressive_stealth_scraper.py` hits 403/429 errors

---

## ⚠️ Mandatory Rules

1. **NEVER use `open()` directly** - Always use `safe_write()` / `safe_read_json()`
2. **NEVER use `print()` for logging** - Use `logger.info()` / `logger.error()`
3. **NEVER guess selectors** - Use `RALPH.findByText()` for robustness
4. **ALWAYS validate visually** - Use `RalphValidator` before declaring success
5. **ALWAYS use GROUP BY ALL** - Avoid listing columns in DuckDB aggregations
