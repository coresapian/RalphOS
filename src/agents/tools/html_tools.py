"""
Custom MCP tools for HTML scraping in RalphOS.

These tools use the @tool decorator from claude-agent-sdk to create
in-process MCP tools that Claude can invoke during HTML scraping tasks.

The HTML scraper stage (Stage 2) uses these tools to:
1. Load URLs from urls.jsonl (output of url-detective stage)
2. Fetch HTML content using httpx (simple) or Camoufox (stealth)
3. Save HTML files to the html/ directory
4. Track progress in scrape_progress.jsonl
5. Detect blocking and trigger session rotation

Usage:
    from src.agents.tools.html_tools import create_html_tools_server

    server = create_html_tools_server()
    options = ClaudeAgentOptions(
        mcp_servers={"html_tools": server},
        allowed_tools=[
            "mcp__html_tools__load_urls",
            "mcp__html_tools__fetch_html",
            "mcp__html_tools__save_html",
            "mcp__html_tools__update_progress",
            "mcp__html_tools__check_blocked",
            "mcp__html_tools__rotate_session",
            "mcp__html_tools__get_scrape_stats",
        ]
    )

Tool Summary:
    - load_urls: Load pending URLs from urls.jsonl, optionally filtering scraped ones
    - fetch_html: Fetch HTML via httpx (fast) or camoufox (stealth anti-bot)
    - save_html: Save HTML content to html/{filename}
    - update_progress: Append status record to scrape_progress.jsonl
    - check_blocked: Detect Cloudflare, CAPTCHA, 403/429 blocks
    - rotate_session: Signal need for new browser session/fingerprint
    - get_scrape_stats: Get counts of success/failed/blocked/pending
"""

import json
import hashlib
import os
import random
import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

# Import SDK tools - these will fail until SDK is installed
try:
    from claude_agent_sdk import tool, create_sdk_mcp_server
except ImportError:
    # Provide stub decorators for development without SDK installed
    def tool(name: str, description: str, params: dict):
        def decorator(func):
            func._tool_name = name
            func._tool_description = description
            func._tool_params = params
            return func
        return decorator

    def create_sdk_mcp_server(name: str, version: str = "1.0.0", tools: list = None):
        raise ImportError("claude-agent-sdk not installed. Run: pip install claude-agent-sdk")


# Optional imports for HTTP/browser functionality
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from camoufox.async_api import AsyncCamoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False

try:
    import orjson
    ORJSON_AVAILABLE = True
except ImportError:
    ORJSON_AVAILABLE = False


# ============================================================================
# Constants for Block Detection
# ============================================================================

# HTTP status codes indicating blocking
BLOCK_STATUS_CODES: Set[int] = {403, 429, 503, 520, 521, 522, 523, 524}

# Patterns in HTML that indicate blocking/challenges
BLOCK_PATTERNS: List[str] = [
    "access denied",
    "access forbidden",
    "rate limit",
    "too many requests",
    "cloudflare",
    "please complete the security check",
    "captcha",
    "recaptcha",
    "hcaptcha",
    "verify you are human",
    "blocked",
    "forbidden",
    "checking your browser",
    "please wait while we verify",
    "just a moment",
    "attention required",
    "ddos protection",
    "bot detection",
    "challenge-platform",
    "enable javascript and cookies",
    "cf-browser-verification",
]

# Headers indicating Cloudflare
CLOUDFLARE_HEADERS: List[str] = ["cf-ray", "cf-cache-status", "cf-request-id"]

# Default user agent
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# ============================================================================
# Global State for Session Management
# ============================================================================

# Browser session state (for Camoufox stealth scraping)
_browser_state: Dict[str, Any] = {
    "browser": None,
    "context": None,
    "page": None,
    "pages_scraped": 0,
    "session_id": None,
    "blocked_count": 0,
    "consecutive_blocks": 0,
    "last_rotation": None,
}

# Default throttle settings (matching stealth_scraper.py)
DEFAULT_MIN_DELAY = 2.0
DEFAULT_MAX_DELAY = 5.0
DEFAULT_ROTATE_EVERY = 50
DEFAULT_TIMEOUT_MS = 60000


# ============================================================================
# Load URLs Tool
# ============================================================================

@tool(
    "load_urls",
    "Load URLs from a urls.jsonl file for scraping. "
    "Returns URL list with filenames, optionally filtering already-scraped URLs.",
    {"output_dir": str, "skip_scraped": bool, "limit": int}
)
async def load_urls_for_scraping(args: dict[str, Any]) -> dict[str, Any]:
    """
    Load URLs from urls.jsonl and optionally filter out already-scraped ones.

    The urls.jsonl file contains one JSON object per line with:
    - url: The URL to scrape
    - filename: The target filename for the HTML

    Progress filtering uses scrape_progress.jsonl to skip:
    - URLs with status="success" (already scraped successfully)

    Args:
        output_dir: Directory containing urls.jsonl (e.g., "data/source_name")
        skip_scraped: If True, filter out URLs already in scrape_progress.jsonl (default: True)
        limit: Maximum number of URLs to return (default: None = all pending)

    Returns:
        Dict with:
        - success: bool
        - total_urls: Total count in urls.jsonl
        - already_scraped: Count of successfully scraped URLs
        - pending_urls: Count of URLs remaining
        - urls: List of URL records (url, filename)
        - has_more: True if more URLs exist beyond returned list
    """
    output_dir = Path(args["output_dir"])
    skip_scraped = args.get("skip_scraped", True)
    limit = args.get("limit")

    urls_file = output_dir / "urls.jsonl"
    if not urls_file.exists():
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"URLs file not found: {urls_file}",
                    "hint": "Run the url-detective stage first to generate urls.jsonl",
                    "success": False
                })
            }],
            "is_error": True
        }

    # Load all URLs
    url_records: List[Dict[str, Any]] = []
    with open(urls_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    url_records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    total_count = len(url_records)

    # Load already-scraped URLs if filtering
    scraped_urls: Set[str] = set()
    if skip_scraped:
        progress_file = output_dir / "scrape_progress.jsonl"
        if progress_file.exists():
            with open(progress_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            if record.get("status") == "success":
                                scraped_urls.add(record["url"])
                        except json.JSONDecodeError:
                            continue

    # Filter to pending only
    pending = [r for r in url_records if r.get("url") not in scraped_urls]
    pending_count = len(pending)

    # Apply limit
    return_limit = limit if limit and limit > 0 else 100
    returned_urls = pending[:return_limit]
    has_more = pending_count > return_limit

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "success": True,
                "total_urls": total_count,
                "already_scraped": len(scraped_urls),
                "pending_urls": pending_count,
                "returned_count": len(returned_urls),
                "urls": returned_urls,
                "has_more": has_more
            }, indent=2)
        }]
    }


# ============================================================================
# Fetch HTML Tool
# ============================================================================

@tool(
    "fetch_html",
    "Fetch HTML content from a URL using httpx (simple sites) or Camoufox (anti-bot sites). "
    "Returns HTML content, status code, and block detection. Use camoufox for protected sites.",
    {"url": str, "method": str, "timeout": int, "min_delay": float, "max_delay": float}
)
async def fetch_html_content(args: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch HTML from a URL using the specified method.

    Two fetch methods:
    - httpx: Fast, direct HTTP request. Best for simple sites without anti-bot protection.
    - camoufox: Stealth browser with anti-detection features. Use for Cloudflare/captcha sites.

    Camoufox features:
    - Anti-detection fingerprinting via BrowserForge
    - Human-like cursor movement (humanize=True)
    - WebRTC blocking to prevent IP leaks
    - Random OS fingerprint (Windows/macOS)

    Args:
        url: The URL to fetch
        method: 'httpx' for simple sites, 'camoufox' for anti-bot protected sites
        timeout: Request timeout in milliseconds (default: 60000)
        min_delay: Minimum delay before request in seconds (default: 0 for httpx, 2 for camoufox)
        max_delay: Maximum delay before request in seconds (default: 0 for httpx, 5 for camoufox)

    Returns:
        Dict with:
        - success: bool
        - url: The requested URL
        - status_code: HTTP status code
        - html: HTML content (None if failed/blocked)
        - html_length: Length of HTML content
        - is_blocked: True if blocking detected
        - method: Fetch method used
        - scraped_at: ISO timestamp
    """
    url = args["url"]
    method = args.get("method", "httpx").lower()
    timeout = args.get("timeout", DEFAULT_TIMEOUT_MS)

    # Set defaults based on method
    if method == "camoufox":
        min_delay = args.get("min_delay", DEFAULT_MIN_DELAY)
        max_delay = args.get("max_delay", DEFAULT_MAX_DELAY)
    else:
        min_delay = args.get("min_delay", 0)
        max_delay = args.get("max_delay", 0)

    # Apply randomized delay if configured
    if min_delay > 0 or max_delay > 0:
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    scraped_at = datetime.now(timezone.utc).isoformat()

    if method == "httpx":
        if not HTTPX_AVAILABLE:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": "httpx not installed. Run: pip install httpx",
                        "success": False
                    })
                }],
                "is_error": True
            }

        try:
            headers = {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }

            async with httpx.AsyncClient(
                timeout=timeout / 1000,
                follow_redirects=True,
                headers=headers
            ) as client:
                response = await client.get(url)

                is_blocked = response.status_code in BLOCK_STATUS_CODES
                html_content = response.text if response.status_code < 400 else None

                # Check content for block indicators
                if html_content and not is_blocked:
                    html_lower = html_content.lower()
                    for pattern in BLOCK_PATTERNS[:10]:  # Check first 10 patterns
                        if pattern in html_lower:
                            is_blocked = True
                            break

                # Update session state
                _browser_state["pages_scraped"] += 1
                if is_blocked:
                    _browser_state["consecutive_blocks"] += 1
                else:
                    _browser_state["consecutive_blocks"] = 0

                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "success": not is_blocked and response.status_code < 400,
                            "url": url,
                            "status_code": response.status_code,
                            "html": html_content,
                            "html_length": len(response.text) if response.text else 0,
                            "is_blocked": is_blocked,
                            "method": "httpx",
                            "scraped_at": scraped_at
                        })
                    }]
                }
        except Exception as e:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": False,
                        "url": url,
                        "error": str(e),
                        "method": "httpx",
                        "scraped_at": scraped_at
                    })
                }],
                "is_error": True
            }

    elif method == "camoufox":
        if not CAMOUFOX_AVAILABLE:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": "camoufox not installed. Run: pip install camoufox[geoip]",
                        "hint": "For batch scraping, prefer scripts/tools/stealth_scraper.py",
                        "success": False
                    })
                }],
                "is_error": True
            }

        # Note: For batch Camoufox scraping, prefer using stealth_scraper.py
        # This tool provides single-URL support for testing/debugging
        try:
            # Get proxy from environment if available
            proxy_user = os.environ.get("BRIGHTDATA_PROXY_USER", "")
            proxy_pass = os.environ.get("BRIGHTDATA_PROXY_PASS", "")
            proxy_host = os.environ.get("BRIGHTDATA_PROXY_HOST", "brd.superproxy.io")
            proxy_port = os.environ.get("BRIGHTDATA_PROXY_PORT", "33335")

            launch_kwargs: Dict[str, Any] = {
                "headless": True,
                "humanize": True,
                "block_webrtc": True,
                "os": ["windows", "macos"],
                "config": {
                    "canvas:aaOffset": 1,
                    "canvas:aaCapOffset": True,
                }
            }

            # Add proxy if configured
            if proxy_user and proxy_pass:
                launch_kwargs["proxy"] = {
                    "server": f"http://{proxy_host}:{proxy_port}",
                    "username": proxy_user,
                    "password": proxy_pass,
                }
                launch_kwargs["geoip"] = True
            else:
                launch_kwargs["locale"] = "en-US"

            async with AsyncCamoufox(**launch_kwargs) as browser:
                context = await browser.new_context(ignore_https_errors=True)
                page = await context.new_page()

                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=timeout
                )

                if not response:
                    await page.close()
                    await context.close()
                    return {
                        "content": [{
                            "type": "text",
                            "text": json.dumps({
                                "success": False,
                                "url": url,
                                "error": "No response received",
                                "method": "camoufox",
                                "scraped_at": scraped_at
                            })
                        }]
                    }

                status = response.status
                is_blocked = status in BLOCK_STATUS_CODES

                # Wait for JS to settle
                await asyncio.sleep(0.5)
                html = await page.content()

                await page.close()
                await context.close()

                # Check for Cloudflare/captcha challenges
                if html and not is_blocked:
                    html_lower = html.lower()
                    for pattern in BLOCK_PATTERNS:
                        if pattern in html_lower:
                            is_blocked = True
                            break

                # Update session state
                _browser_state["pages_scraped"] += 1
                if is_blocked:
                    _browser_state["consecutive_blocks"] += 1
                    _browser_state["blocked_count"] += 1
                else:
                    _browser_state["consecutive_blocks"] = 0

                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "success": not is_blocked and status < 400,
                            "url": url,
                            "status_code": status,
                            "html": html if not is_blocked and status < 400 else None,
                            "html_length": len(html) if html else 0,
                            "is_blocked": is_blocked,
                            "method": "camoufox",
                            "scraped_at": scraped_at,
                            "proxy_used": bool(proxy_user and proxy_pass)
                        })
                    }]
                }
        except Exception as e:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": False,
                        "url": url,
                        "error": str(e),
                        "method": "camoufox",
                        "scraped_at": scraped_at
                    })
                }],
                "is_error": True
            }

    else:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Unknown method: {method}. Use 'httpx' or 'camoufox'",
                    "success": False
                })
            }],
            "is_error": True
        }


# ============================================================================
# Save HTML Tool
# ============================================================================

@tool(
    "save_html",
    "Save HTML content to a file in the html/ directory. "
    "Uses atomic write to prevent corruption. Creates directory if needed.",
    {"output_dir": str, "filename": str, "html": str, "url": str}
)
async def save_html_file(args: dict[str, Any]) -> dict[str, Any]:
    """
    Save HTML content to a file with atomic write for crash safety.

    The file is saved to {output_dir}/html/{filename}.
    Uses temp file + rename pattern to prevent partial writes.

    Args:
        output_dir: Base output directory (e.g., "data/source_name")
        filename: Filename for the HTML file (from urls.jsonl)
        html: HTML content to save
        url: Source URL (for metadata/logging)

    Returns:
        Dict with:
        - success: bool
        - file_path: Absolute path to saved file
        - url: Source URL
        - size_bytes: Size of saved content
    """
    output_dir = Path(args["output_dir"])
    filename = args["filename"]
    html = args["html"]
    url = args["url"]

    # Ensure .html extension
    if not filename.endswith(".html"):
        filename += ".html"

    html_dir = output_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)

    html_file = html_dir / filename

    try:
        # Atomic write using temp file
        temp_file = html_file.with_suffix(".tmp")
        temp_file.write_text(html, encoding="utf-8")
        temp_file.replace(html_file)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "file_path": str(html_file.absolute()),
                    "url": url,
                    "filename": filename,
                    "size_bytes": len(html.encode("utf-8"))
                }, indent=2)
            }]
        }
    except Exception as e:
        # Clean up temp file if it exists
        temp_file = html_file.with_suffix(".tmp")
        if temp_file.exists():
            try:
                temp_file.unlink()
            except:
                pass

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": str(e),
                    "url": url,
                    "filename": filename
                }, indent=2)
            }],
            "is_error": True
        }


# ============================================================================
# Update Progress Tool
# ============================================================================

@tool(
    "update_progress",
    "Update scrape_progress.jsonl with the result of a scraping attempt. "
    "Tracks success, failure, or blocked status for checkpoint/resume.",
    {"output_dir": str, "url": str, "filename": str, "status": str, "error": str}
)
async def update_scrape_progress(args: dict[str, Any]) -> dict[str, Any]:
    """
    Append a progress record to scrape_progress.jsonl.

    Progress file format (JSONL - one record per line):
    {"url": "...", "filename": "...", "status": "success", "timestamp": "..."}
    {"url": "...", "filename": "...", "status": "failed", "error": "404", "timestamp": "..."}
    {"url": "...", "filename": "...", "status": "blocked", "error": "403", "timestamp": "..."}

    Status values:
    - "success": HTML saved successfully
    - "failed": Non-blocking error (404, timeout, parse error)
    - "blocked": Blocking detected (403, 429, Cloudflare, CAPTCHA)

    Args:
        output_dir: Base output directory (e.g., "data/source_name")
        url: The URL that was scraped
        filename: Filename used for the HTML
        status: 'success', 'failed', or 'blocked'
        error: Error message/code if status is not success (optional)

    Returns:
        Dict with:
        - success: bool
        - record: The progress record that was written
        - blocked_count: Total blocked URLs in this session
    """
    output_dir = Path(args["output_dir"])
    url = args["url"]
    filename = args["filename"]
    status = args["status"]
    error = args.get("error")

    progress_file = output_dir / "scrape_progress.jsonl"

    # Ensure directory exists
    progress_file.parent.mkdir(parents=True, exist_ok=True)

    record: Dict[str, Any] = {
        "url": url,
        "filename": filename,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if error:
        record["error"] = error

    try:
        with open(progress_file, "a") as f:
            if ORJSON_AVAILABLE:
                f.write(orjson.dumps(record).decode() + "\n")
            else:
                f.write(json.dumps(record) + "\n")

        # Update global state
        if status == "blocked":
            _browser_state["blocked_count"] += 1
            _browser_state["consecutive_blocks"] += 1
        elif status == "success":
            _browser_state["consecutive_blocks"] = 0

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "record": record,
                    "blocked_count": _browser_state["blocked_count"],
                    "consecutive_blocks": _browser_state["consecutive_blocks"]
                }, indent=2)
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": str(e),
                    "url": url
                }, indent=2)
            }],
            "is_error": True
        }


# ============================================================================
# Check Blocked Tool
# ============================================================================

@tool(
    "check_blocked",
    "Detect if HTTP response indicates blocking (403, 429, Cloudflare, CAPTCHA, etc.). "
    "Analyzes status code, headers, and HTML content. Returns detection and recommendations.",
    {"html": str, "status_code": int, "headers": dict}
)
async def check_if_blocked(args: dict[str, Any]) -> dict[str, Any]:
    """
    Analyze response to detect if we're blocked by anti-bot measures.

    Checks multiple indicators:
    1. HTTP status codes (403, 429, 503, 520-524)
    2. Cloudflare headers (cf-ray, cf-cache-status)
    3. HTML content patterns (challenge, captcha, blocked, etc.)
    4. Short response content (often indicates block pages)

    Block types detected:
    - http_403: Forbidden response
    - rate_limit: 429 Too Many Requests
    - cloudflare: Cloudflare challenge/protection
    - captcha: CAPTCHA/reCAPTCHA/hCaptcha
    - access_denied: Generic access denied
    - ddos_protection: DDoS protection page

    Args:
        html: The HTML content to analyze
        status_code: HTTP status code from the response
        headers: Response headers (optional, for Cloudflare detection)

    Returns:
        Dict with:
        - is_blocked: True if blocking detected
        - block_type: Type of block (cloudflare, captcha, etc.)
        - indicators: List of detected indicators
        - recommendation: Suggested action
        - should_stop: True if scraping should stop immediately
        - should_rotate: True if session rotation recommended
    """
    html = args.get("html", "")
    status_code = args.get("status_code", 200)
    headers = args.get("headers", {})

    is_blocked = False
    block_type: Optional[str] = None
    indicators: List[str] = []

    # Check HTTP status codes
    if status_code in BLOCK_STATUS_CODES:
        is_blocked = True
        if status_code == 403:
            block_type = "http_403"
            indicators.append("HTTP 403 Forbidden")
        elif status_code == 429:
            block_type = "rate_limit"
            indicators.append("HTTP 429 Too Many Requests")
        elif status_code == 503:
            block_type = "service_unavailable"
            indicators.append("HTTP 503 Service Unavailable")
        elif status_code >= 520:
            block_type = "cloudflare_error"
            indicators.append(f"Cloudflare error {status_code}")

    # Check Cloudflare headers
    if headers:
        headers_lower = {k.lower(): v for k, v in headers.items()}
        for cf_header in CLOUDFLARE_HEADERS:
            if cf_header in headers_lower:
                indicators.append(f"Cloudflare header: {cf_header}")
                if status_code >= 400:
                    is_blocked = True
                    if not block_type:
                        block_type = "cloudflare"

    # Check HTML content for block indicators
    html_lower = html.lower() if html else ""

    # Cloudflare-specific checks
    cloudflare_checks = [
        ("cloudflare" in html_lower and "challenge" in html_lower, "Cloudflare challenge page"),
        ("ray id" in html_lower and "cloudflare" in html_lower, "Cloudflare Ray ID"),
        ("cf-browser-verification" in html_lower, "Cloudflare browser verification"),
        ("challenge-platform" in html_lower, "Cloudflare challenge platform"),
        ("just a moment" in html_lower and "cloudflare" in html_lower, "Cloudflare 'Just a moment' page"),
    ]

    # CAPTCHA checks
    captcha_checks = [
        ("captcha" in html_lower, "CAPTCHA detected"),
        ("recaptcha" in html_lower, "reCAPTCHA detected"),
        ("hcaptcha" in html_lower, "hCaptcha detected"),
        ("verify you are human" in html_lower, "Human verification required"),
    ]

    # Access denied checks
    access_checks = [
        ("access denied" in html_lower, "Access denied message"),
        ("access forbidden" in html_lower, "Access forbidden message"),
        ("blocked" in html_lower and "ip" in html_lower, "IP blocked message"),
        ("please enable javascript" in html_lower, "JavaScript verification required"),
        ("checking your browser" in html_lower, "Browser check in progress"),
    ]

    # DDoS protection checks
    ddos_checks = [
        ("ddos protection" in html_lower, "DDoS protection active"),
        ("bot detection" in html_lower, "Bot detection triggered"),
    ]

    # Evaluate all checks
    for check, message in cloudflare_checks:
        if check:
            is_blocked = True
            if not block_type:
                block_type = "cloudflare"
            indicators.append(message)

    for check, message in captcha_checks:
        if check:
            is_blocked = True
            if not block_type:
                block_type = "captcha"
            indicators.append(message)

    for check, message in access_checks:
        if check:
            is_blocked = True
            if not block_type:
                block_type = "access_denied"
            indicators.append(message)

    for check, message in ddos_checks:
        if check:
            is_blocked = True
            if not block_type:
                block_type = "ddos_protection"
            indicators.append(message)

    # Check for very short HTML (often indicates block pages)
    if html and len(html) < 500 and status_code >= 400:
        indicators.append("Very short response content")
        if not is_blocked:
            is_blocked = True
            block_type = "short_response"

    # Generate recommendation
    recommendation: Optional[str] = None
    should_stop = False
    should_rotate = False

    if is_blocked:
        if block_type == "cloudflare":
            recommendation = "Use Camoufox stealth browser. If already using, rotate session and increase delays."
            should_rotate = True
            should_stop = _browser_state["consecutive_blocks"] >= 3
        elif block_type == "captcha":
            recommendation = "CAPTCHA requires manual intervention or residential proxy with CAPTCHA solving service."
            should_stop = True
        elif block_type == "rate_limit":
            recommendation = "Rate limited. Increase delays to 5-10 seconds and rotate session."
            should_rotate = True
        elif block_type == "ddos_protection":
            recommendation = "DDoS protection triggered. Wait 5+ minutes before retrying with stealth browser."
            should_stop = True
        else:
            recommendation = "Consider rotating IP/session and increasing delays between requests."
            should_rotate = True

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "is_blocked": is_blocked,
                "block_type": block_type,
                "indicators": indicators,
                "recommendation": recommendation,
                "should_stop": should_stop,
                "should_rotate": should_rotate,
                "consecutive_blocks": _browser_state["consecutive_blocks"],
                "total_blocked": _browser_state["blocked_count"]
            }, indent=2)
        }]
    }


# ============================================================================
# Rotate Session Tool
# ============================================================================

@tool(
    "rotate_session",
    "Signal that browser session should be rotated for new fingerprint/IP. "
    "Call after blocks or every 50 pages for stealth. Resets consecutive block counter.",
    {"reason": str, "force": bool}
)
async def rotate_browser_session(args: dict[str, Any]) -> dict[str, Any]:
    """
    Request a session rotation for new browser fingerprint/proxy IP.

    Session rotation should be triggered:
    1. After detecting blocks (403, 429, Cloudflare)
    2. Every 50 pages for proactive stealth
    3. After 3+ consecutive blocks
    4. Manually when performance degrades

    What happens during rotation:
    - Browser context is closed
    - New context created with fresh fingerprint (via BrowserForge)
    - If using proxy, may get new IP
    - Counters reset (pages_scraped, consecutive_blocks)

    Args:
        reason: Why rotation is needed ('blocked', 'periodic', 'consecutive_blocks', 'manual')
        force: If True, force rotation even if not strictly needed (default: False)

    Returns:
        Dict with:
        - success: bool
        - reason: Rotation reason
        - new_session_id: New session identifier
        - previous_state: State before rotation
        - recommended_delay_seconds: Wait time before resuming
        - message: Human-readable status
    """
    reason = args.get("reason", "manual")
    force = args.get("force", False)

    # Capture previous state
    previous_state = {
        "pages_scraped": _browser_state["pages_scraped"],
        "consecutive_blocks": _browser_state["consecutive_blocks"],
        "blocked_count": _browser_state["blocked_count"],
        "last_rotation": _browser_state["last_rotation"],
    }

    # Check if rotation is needed (unless forced)
    needs_rotation = (
        force or
        _browser_state["consecutive_blocks"] > 0 or
        _browser_state["pages_scraped"] >= DEFAULT_ROTATE_EVERY
    )

    if not needs_rotation:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "reason": reason,
                    "message": "Rotation not needed at this time. Use force=True to override.",
                    "current_state": previous_state
                }, indent=2)
            }]
        }

    # Reset session state
    _browser_state["pages_scraped"] = 0
    _browser_state["consecutive_blocks"] = 0
    _browser_state["last_rotation"] = datetime.now(timezone.utc).isoformat()
    _browser_state["session_id"] = hashlib.md5(
        datetime.now().isoformat().encode()
    ).hexdigest()[:8]

    # Recommended delay after rotation (longer if blocked)
    if "block" in reason.lower():
        delay = random.uniform(5.0, 10.0)
    else:
        delay = random.uniform(2.0, 5.0)

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "success": True,
                "reason": reason,
                "new_session_id": _browser_state["session_id"],
                "previous_state": previous_state,
                "recommended_delay_seconds": round(delay, 1),
                "message": f"Session rotation completed ({reason}). Wait {delay:.1f}s before continuing.",
                "instructions": [
                    "Close current browser context",
                    "Create new context with fresh fingerprint",
                    "If using proxy, request new IP",
                    f"Wait {delay:.1f} seconds before resuming",
                    "Resume with fresh session"
                ]
            }, indent=2)
        }]
    }


# ============================================================================
# Get Scrape Stats Tool
# ============================================================================

@tool(
    "get_scrape_stats",
    "Get scraping statistics from scrape_progress.jsonl. "
    "Returns counts, completion percentage, and overall status.",
    {"output_dir": str}
)
async def get_scraping_stats(args: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate comprehensive scraping statistics from progress file.

    Reads both urls.jsonl (total) and scrape_progress.jsonl (completed)
    to provide full progress metrics.

    Overall status values:
    - "not_started": No progress file exists
    - "in_progress": Scraping underway, no blocks
    - "blocked": Hit blocking, scraping paused
    - "complete": All URLs processed

    Args:
        output_dir: Directory containing urls.jsonl and scrape_progress.jsonl

    Returns:
        Dict with:
        - total_urls: Total URLs from urls.jsonl
        - success: Successfully scraped count
        - failed: Failed (non-blocking) count
        - blocked: Blocked count
        - pending: Remaining to process
        - completion_percentage: Progress percentage
        - overall_status: Current state
        - session_state: Current browser session state
        - output_files: Paths to relevant files
    """
    output_dir = Path(args["output_dir"])
    progress_file = output_dir / "scrape_progress.jsonl"
    urls_file = output_dir / "urls.jsonl"
    html_dir = output_dir / "html"

    stats: Dict[str, Any] = {
        "total_urls": 0,
        "success": 0,
        "failed": 0,
        "blocked": 0,
        "pending": 0,
        "completion_percentage": 0.0,
        "overall_status": "not_started"
    }

    # Count total URLs
    if urls_file.exists():
        with open(urls_file) as f:
            stats["total_urls"] = sum(1 for line in f if line.strip())
    else:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    **stats,
                    "error": "urls.jsonl not found - run url-detective stage first",
                    "urls_file": str(urls_file)
                }, indent=2)
            }]
        }

    # Count progress
    if progress_file.exists():
        with open(progress_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        status = record.get("status", "unknown")
                        if status == "success":
                            stats["success"] += 1
                        elif status == "failed":
                            stats["failed"] += 1
                        elif status == "blocked":
                            stats["blocked"] += 1
                    except json.JSONDecodeError:
                        continue

    # Count actual HTML files (for verification)
    html_file_count = 0
    if html_dir.exists():
        html_file_count = len(list(html_dir.glob("*.html")))

    # Calculate pending and completion
    stats["pending"] = max(0, stats["total_urls"] - stats["success"] - stats["failed"] - stats["blocked"])

    if stats["total_urls"] > 0:
        stats["completion_percentage"] = round(
            (stats["success"] + stats["failed"] + stats["blocked"]) / stats["total_urls"] * 100, 1
        )

    # Determine overall status
    if stats["blocked"] > 0:
        stats["overall_status"] = "blocked"
    elif stats["pending"] == 0 and stats["total_urls"] > 0:
        stats["overall_status"] = "complete"
    elif stats["success"] + stats["failed"] > 0:
        stats["overall_status"] = "in_progress"
    else:
        stats["overall_status"] = "not_started"

    # Add session state info
    stats["session_state"] = {
        "pages_scraped_this_session": _browser_state["pages_scraped"],
        "consecutive_blocks": _browser_state["consecutive_blocks"],
        "session_blocked_count": _browser_state["blocked_count"],
        "last_rotation": _browser_state["last_rotation"],
        "session_id": _browser_state["session_id"]
    }

    # Add file paths for reference
    stats["output_files"] = {
        "urls_file": str(urls_file),
        "progress_file": str(progress_file),
        "html_dir": str(html_dir),
        "html_file_count": html_file_count
    }

    # Validation check
    if html_file_count != stats["success"]:
        stats["warning"] = f"HTML file count ({html_file_count}) doesn't match success count ({stats['success']})"

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(stats, indent=2)
        }]
    }


# ============================================================================
# Tool Registration
# ============================================================================

# List of all HTML scraping tools for easy registration
html_scraping_tools = [
    load_urls_for_scraping,
    fetch_html_content,
    save_html_file,
    update_scrape_progress,
    check_if_blocked,
    rotate_browser_session,
    get_scraping_stats,
]


def create_html_tools_server():
    """
    Create an SDK MCP server with all HTML scraping tools.

    Usage:
        server = create_html_tools_server()
        options = ClaudeAgentOptions(
            mcp_servers={"html_tools": server},
            allowed_tools=[
                "mcp__html_tools__load_urls",
                "mcp__html_tools__fetch_html",
                "mcp__html_tools__save_html",
                "mcp__html_tools__update_progress",
                "mcp__html_tools__check_blocked",
                "mcp__html_tools__rotate_session",
                "mcp__html_tools__get_scrape_stats",
            ]
        )
    """
    return create_sdk_mcp_server(
        name="html_tools",
        version="1.0.0",
        tools=html_scraping_tools
    )
