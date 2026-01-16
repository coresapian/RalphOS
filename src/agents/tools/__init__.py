"""
Custom MCP tools for RalphOS Agent SDK subagents.

These tools are registered as in-process MCP servers and made available
to Claude agents for URL discovery, HTML analysis, and data extraction.
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

__all__ = [
    "analyze_url_patterns",
    "detect_pagination",
    "extract_urls_from_html",
    "normalize_and_dedupe_urls",
    "save_urls_jsonl",
    "url_discovery_tools",
    "create_url_tools_server",
]
