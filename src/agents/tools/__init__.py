"""
Custom MCP tools for RalphOS Agent SDK subagents.

These tools are registered as in-process MCP servers and made available
to Claude agents for URL discovery, HTML scraping, and data extraction.
"""

from .url_tools import (
    analyze_url_patterns,
    detect_pagination,
    extract_urls_from_html,
    normalize_and_dedupe_urls,
    save_urls_jsonl,
    url_discovery_tools,
    create_url_tools_server,
)

from .html_tools import (
    load_urls_for_scraping,
    fetch_html_content,
    save_html_file,
    update_scrape_progress,
    check_if_blocked,
    rotate_browser_session,
    get_scraping_stats,
    html_scraping_tools,
    create_html_tools_server,
)

__all__ = [
    # URL Discovery Tools
    "analyze_url_patterns",
    "detect_pagination",
    "extract_urls_from_html",
    "normalize_and_dedupe_urls",
    "save_urls_jsonl",
    "url_discovery_tools",
    "create_url_tools_server",
    # HTML Scraping Tools
    "load_urls_for_scraping",
    "fetch_html_content",
    "save_html_file",
    "update_scrape_progress",
    "check_if_blocked",
    "rotate_browser_session",
    "get_scraping_stats",
    "html_scraping_tools",
    "create_html_tools_server",
]
