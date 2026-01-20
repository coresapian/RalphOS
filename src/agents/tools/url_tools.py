"""
Custom MCP tools for URL discovery in RalphOS.

These tools use the @tool decorator from claude-agent-sdk to create
in-process MCP tools that Claude can invoke during URL discovery tasks.

Usage:
    from src.agents.tools.url_tools import create_url_tools_server

    server = create_url_tools_server()
    options = ClaudeAgentOptions(
        mcp_servers={"url_tools": server},
        allowed_tools=[
            "mcp__url_tools__analyze_patterns",
            "mcp__url_tools__detect_pagination",
            "mcp__url_tools__extract_urls",
            "mcp__url_tools__normalize_urls",
            "mcp__url_tools__save_urls",
        ]
    )
"""

import json
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urljoin, urlunparse

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


# ============================================================================
# URL Pattern Analysis Tool
# ============================================================================

@tool(
    "analyze_patterns",
    "Analyze HTML content to discover URL patterns for build/vehicle pages. "
    "Returns pattern candidates with example URLs and frequency counts.",
    {"html": str, "base_url": str}
)
async def analyze_url_patterns(args: dict[str, Any]) -> dict[str, Any]:
    """
    Analyze HTML to discover URL patterns that likely point to build/vehicle pages.

    This tool extracts all links, groups them by pattern (replacing IDs/slugs
    with placeholders), and ranks patterns by frequency to identify the main
    content URL structure.
    """
    html = args["html"]
    base_url = args["base_url"]

    # Extract all href attributes
    href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
    hrefs = href_pattern.findall(html)

    # Normalize to absolute URLs
    parsed_base = urlparse(base_url)
    absolute_urls = []
    for href in hrefs:
        if href.startswith('javascript:') or href.startswith('#') or href.startswith('mailto:'):
            continue
        try:
            absolute_url = urljoin(base_url, href)
            # Only keep same-domain URLs
            parsed = urlparse(absolute_url)
            if parsed.netloc == parsed_base.netloc:
                absolute_urls.append(absolute_url)
        except Exception:
            continue

    # Group by pattern (replace numeric IDs, UUIDs, and slugs with placeholders)
    patterns: dict[str, list[str]] = {}
    for url in absolute_urls:
        parsed = urlparse(url)
        path = parsed.path

        # Create pattern by replacing variable parts
        pattern = path
        pattern = re.sub(r'/\d+/?', '/{id}/', pattern)  # Numeric IDs
        pattern = re.sub(r'/[a-f0-9-]{36}/?', '/{uuid}/', pattern)  # UUIDs
        pattern = re.sub(r'/[a-z0-9-]{10,}/?$', '/{slug}/', pattern, flags=re.IGNORECASE)  # Slugs

        if pattern not in patterns:
            patterns[pattern] = []
        if len(patterns[pattern]) < 5:  # Keep up to 5 examples
            patterns[pattern].append(url)

    # Sort by frequency (most common patterns first)
    sorted_patterns = sorted(
        patterns.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:15]  # Top 15 patterns

    results = [
        {
            "pattern": pattern,
            "count": len(examples),
            "examples": examples[:3]
        }
        for pattern, examples in sorted_patterns
    ]

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "total_links": len(absolute_urls),
                "unique_patterns": len(patterns),
                "top_patterns": results
            }, indent=2)
        }]
    }


# ============================================================================
# Pagination Detection Tool
# ============================================================================

@tool(
    "detect_pagination",
    "Detect pagination type and structure from HTML content. "
    "Identifies numeric pages, load-more buttons, infinite scroll, and total counts.",
    {"html": str, "current_url": str}
)
async def detect_pagination(args: dict[str, Any]) -> dict[str, Any]:
    """
    Analyze HTML to detect pagination structure and estimate total pages.

    Detects:
    - Numeric pagination (Page 1 of 45)
    - Item counts (Showing 1-20 of 1,234 results)
    - Next/prev links
    - Load more buttons
    - Infinite scroll indicators
    """
    html = args["html"]
    current_url = args["current_url"]

    result = {
        "pagination_type": "unknown",
        "total_pages": None,
        "total_items": None,
        "next_page_url": None,
        "page_links": [],
        "indicators": []
    }

    # Check for "Page X of Y" pattern
    page_of_match = re.search(r'page\s+(\d+)\s+of\s+(\d+)', html, re.IGNORECASE)
    if page_of_match:
        result["pagination_type"] = "numeric"
        result["total_pages"] = int(page_of_match.group(2))
        result["indicators"].append(f"Found 'Page {page_of_match.group(1)} of {page_of_match.group(2)}'")

    # Check for "Showing X-Y of Z results" pattern
    showing_match = re.search(
        r'showing\s+[\d,]+[-\s]+[\d,]+\s+of\s+([\d,]+)',
        html, re.IGNORECASE
    )
    if showing_match:
        total_str = showing_match.group(1).replace(',', '')
        result["total_items"] = int(total_str)
        result["indicators"].append(f"Found total count: {result['total_items']} items")

    # Check for next page link
    next_patterns = [
        r'<a[^>]*rel=["\']next["\'][^>]*href=["\']([^"\']+)["\']',
        r'<a[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']next["\']',
        r'<a[^>]*class=["\'][^"\']*next[^"\']*["\'][^>]*href=["\']([^"\']+)["\']',
    ]
    for pattern in next_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            result["next_page_url"] = urljoin(current_url, match.group(1))
            result["indicators"].append(f"Found next page link")
            break

    # Check for pagination links with numbers
    page_link_pattern = re.compile(
        r'<a[^>]*href=["\']([^"\']*[?&]page=(\d+)[^"\']*)["\']',
        re.IGNORECASE
    )
    for match in page_link_pattern.finditer(html):
        page_num = int(match.group(2))
        result["page_links"].append({
            "page": page_num,
            "url": urljoin(current_url, match.group(1))
        })

    if result["page_links"]:
        max_page = max(p["page"] for p in result["page_links"])
        if result["total_pages"] is None or max_page > result["total_pages"]:
            result["total_pages"] = max_page
        result["pagination_type"] = "numeric"

    # Check for infinite scroll indicators
    infinite_patterns = [
        r'infinite[-_]?scroll',
        r'data-infinite',
        r'loadMore',
        r'load[-_]?more',
    ]
    for pattern in infinite_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            result["pagination_type"] = "infinite_scroll"
            result["indicators"].append(f"Found infinite scroll indicator: {pattern}")
            break

    # Check for load more button
    load_more_patterns = [
        r'<button[^>]*>[^<]*load\s*more[^<]*</button>',
        r'<a[^>]*>[^<]*load\s*more[^<]*</a>',
        r'class=["\'][^"\']*load[-_]?more[^"\']*["\']',
    ]
    for pattern in load_more_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            if result["pagination_type"] == "unknown":
                result["pagination_type"] = "load_more"
            result["indicators"].append("Found load more button")
            break

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, indent=2)
        }]
    }


# ============================================================================
# URL Extraction Tool
# ============================================================================

@tool(
    "extract_urls",
    "Extract URLs matching a specific pattern from HTML content. "
    "Use after analyze_patterns to get all URLs for a discovered pattern.",
    {"html": str, "base_url": str, "pattern_regex": str}
)
async def extract_urls_from_html(args: dict[str, Any]) -> dict[str, Any]:
    """
    Extract all URLs from HTML that match a given regex pattern.

    Args:
        html: The HTML content to parse
        base_url: Base URL for resolving relative links
        pattern_regex: Regex pattern to match URL paths (e.g., r'/builds/[a-z0-9-]+/?$')
    """
    html = args["html"]
    base_url = args["base_url"]
    pattern_regex = args["pattern_regex"]

    try:
        url_pattern = re.compile(pattern_regex, re.IGNORECASE)
    except re.error as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error: Invalid regex pattern: {e}"
            }],
            "is_error": True
        }

    # Extract all href attributes
    href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
    hrefs = href_pattern.findall(html)

    # Filter and normalize URLs
    parsed_base = urlparse(base_url)
    matching_urls = set()

    for href in hrefs:
        if href.startswith('javascript:') or href.startswith('#'):
            continue
        try:
            absolute_url = urljoin(base_url, href)
            parsed = urlparse(absolute_url)

            # Only same-domain URLs
            if parsed.netloc != parsed_base.netloc:
                continue

            # Check if path matches pattern
            if url_pattern.search(parsed.path):
                # Normalize: remove fragments, ensure consistent format
                normalized = urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path.rstrip('/') + '/' if not parsed.path.endswith('/') else parsed.path,
                    '', '', ''  # No params, query, fragment
                ))
                matching_urls.add(normalized)
        except Exception:
            continue

    urls_list = sorted(matching_urls)

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "pattern": pattern_regex,
                "count": len(urls_list),
                "urls": urls_list
            }, indent=2)
        }]
    }


# ============================================================================
# URL Normalization Tool
# ============================================================================

@tool(
    "normalize_urls",
    "Normalize and deduplicate a list of URLs. "
    "Removes fragments, normalizes paths, and eliminates duplicates.",
    {"urls": list}
)
async def normalize_and_dedupe_urls(args: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize and deduplicate a list of URLs.

    Normalization includes:
    - Removing URL fragments (#section)
    - Removing tracking parameters (utm_*, fbclid, etc.)
    - Consistent trailing slashes
    - Lowercase domain
    """
    urls = args["urls"]

    tracking_params = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'fbclid', 'gclid', 'ref', 'source', 'mc_cid', 'mc_eid'
    }

    normalized = set()
    for url in urls:
        try:
            parsed = urlparse(url)

            # Remove tracking params from query
            if parsed.query:
                params = parsed.query.split('&')
                clean_params = [
                    p for p in params
                    if p.split('=')[0].lower() not in tracking_params
                ]
                query = '&'.join(clean_params)
            else:
                query = ''

            # Normalize
            normalized_url = urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path,
                '',  # params
                query,
                ''  # fragment (removed)
            ))
            normalized.add(normalized_url)
        except Exception:
            continue

    urls_list = sorted(normalized)

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "original_count": len(urls),
                "deduplicated_count": len(urls_list),
                "urls": urls_list
            }, indent=2)
        }]
    }


# ============================================================================
# Save URLs Tool
# ============================================================================

@tool(
    "save_urls",
    "Save discovered URLs to a JSONL file with metadata. "
    "Each line contains {url, filename} for the html-scraper stage.",
    {"urls": list, "output_dir": str, "source_name": str}
)
async def save_urls_jsonl(args: dict[str, Any]) -> dict[str, Any]:
    """
    Save URLs to urls.jsonl in RalphOS format.

    Creates:
    - {output_dir}/urls.jsonl - One JSON object per line with url and filename
    - {output_dir}/urls_meta.json - Metadata with totalCount, lastUpdated, source
    """
    urls = args["urls"]
    output_dir = Path(args["output_dir"])
    source_name = args["source_name"]

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filenames from URLs
    url_records = []
    for url in urls:
        parsed = urlparse(url)
        path = parsed.path.strip('/')

        # Extract slug for filename
        slug = path.split('/')[-1] if path else 'index'
        slug = re.sub(r'[^a-zA-Z0-9-]', '-', slug)[:100]

        # Create unique filename using hash
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = f"{slug}-{url_hash}.html"

        url_records.append({
            "url": url,
            "filename": filename
        })

    # Write urls.jsonl
    urls_file = output_dir / "urls.jsonl"
    with open(urls_file, 'w') as f:
        for record in url_records:
            f.write(json.dumps(record) + '\n')

    # Write urls_meta.json
    meta_file = output_dir / "urls_meta.json"
    meta = {
        "totalCount": len(url_records),
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "source": source_name
    }
    with open(meta_file, 'w') as f:
        json.dump(meta, f, indent=2)

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "success": True,
                "urls_file": str(urls_file),
                "meta_file": str(meta_file),
                "total_urls": len(url_records),
                "sample_records": url_records[:3]
            }, indent=2)
        }]
    }


# ============================================================================
# Tool Registration
# ============================================================================

# List of all URL discovery tools for easy registration
url_discovery_tools = [
    analyze_url_patterns,
    detect_pagination,
    extract_urls_from_html,
    normalize_and_dedupe_urls,
    save_urls_jsonl,
]


def create_url_tools_server():
    """
    Create an SDK MCP server with all URL discovery tools.

    Usage:
        server = create_url_tools_server()
        options = ClaudeAgentOptions(
            mcp_servers={"url_tools": server},
            allowed_tools=[
                "mcp__url_tools__analyze_patterns",
                "mcp__url_tools__detect_pagination",
                "mcp__url_tools__extract_urls",
                "mcp__url_tools__normalize_urls",
                "mcp__url_tools__save_urls",
            ]
        )
    """
    return create_sdk_mcp_server(
        name="url_tools",
        version="1.0.0",
        tools=url_discovery_tools
    )
