#!/usr/bin/env python3
"""
Example: Run the HTML Scraper agent standalone.

This example shows how to use the HTML Scraper to download HTML content
for discovered URLs using httpx (simple sites) or Camoufox (anti-bot sites).

Prerequisites:
    pip install claude-agent-sdk>=0.1.19
    pip install camoufox[geoip]
    python3 -m camoufox fetch
    export ANTHROPIC_API_KEY=your_api_key

Usage:
    python src/agents/examples/run_html_scraper.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.agents.html_scraper import run_html_scraper


async def main():
    """Example: Scrape HTML from a source directory containing urls.jsonl."""

    # Example: Scrape HTML for a source that already has urls.jsonl
    # Replace with your actual source directory
    result = await run_html_scraper(
        output_dir="data/example_source",
        source_name="example_source",
        use_stealth=True,  # Use Camoufox for anti-bot protected sites
        limit=10,  # Limit to 10 URLs for testing
        verbose=True
    )

    if result["success"]:
        print("\n" + "=" * 50)
        print("HTML Scraping Complete!")
        print("=" * 50)
        print(f"Status: {result['status']}")
        print(f"Scraped: {result['scraped_count']}")
        print(f"Failed: {result['failed_count']}")
        print(f"Blocked: {result['blocked_count']}")
        print(f"HTML directory: {result['html_dir']}")
        print(f"Total cost: ${result['cost_usd']:.4f}")

        if result["blocked_count"] > 0:
            print("\nWARNING: Some URLs were blocked (403/429).")
            print("Consider increasing delays or using different proxy.")
    else:
        print(f"\nError: {result.get('error', 'Unknown error')}")
        if result["status"] == "blocked":
            print("Site has anti-bot protection. Try with use_stealth=True.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
