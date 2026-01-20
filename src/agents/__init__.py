"""
RalphOS Agent SDK Subagents

This module provides Claude Agent SDK subagents for the RalphOS pipeline:
- URLDetective: Discovers build/vehicle URLs from websites (Stage 1)
- HTMLScraper: Downloads HTML content from discovered URLs (Stage 2)
- (Future) DataExtractor: Extracts structured data from HTML (Stage 3)
"""

from .url_detective import URLDetectiveAgent, run_url_detective
from .html_scraper import HTMLScraperAgent, run_html_scraper

__all__ = [
    # Stage 1: URL Discovery
    "URLDetectiveAgent",
    "run_url_detective",
    # Stage 2: HTML Scraping
    "HTMLScraperAgent",
    "run_html_scraper",
]
