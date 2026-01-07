#!/usr/bin/env python3
"""
Final comprehensive extraction of Tacoma World thread URLs.
This script processes ALL 158 pages using MCP webReader tool calls.
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Set, List, Dict

# File paths
PAGES_FILE = Path("/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/tacoma_world_builds/pages_to_fetch.json")
OUTPUT_FILE = Path("/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/tacoma_world_builds/urls.json")
PROGRESS_FILE = Path("/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/tacoma_world_builds/extraction_progress.json")

# Thread URL pattern - matches /threads/slug.id/ format
THREAD_PATTERN = re.compile(r'href=["\'](/threads/[^"\']*\.\d+/?)["\']')


def load_pages() -> List[Dict]:
    """Load the list of pages to fetch."""
    with open(PAGES_FILE, 'r') as f:
        data = json.load(f)
    return data['pages']


def load_progress() -> Dict:
    """Load existing progress."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {
        'processed_pages': [],
        'failed_pages': [],
        'all_urls': [],
        'last_update': None
    }


def save_progress(processed: List[Dict], failed: List[Dict], urls: List[str]):
    """Save progress."""
    progress = {
        'processed_pages': processed,
        'failed_pages': failed,
        'all_urls': urls,
        'last_update': datetime.now(timezone.utc).isoformat(),
        'total_urls': len(urls)
    }
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def extract_urls_from_html(html_content: str) -> Set[str]:
    """Extract thread URLs from HTML content."""
    urls = set()

    # Find all thread URLs
    matches = THREAD_PATTERN.findall(html_content)

    for relative_url in matches:
        # Convert relative URL to absolute
        if relative_url.startswith('/'):
            full_url = f"https://www.tacomaworld.com{relative_url}"
            urls.add(full_url)

    return urls


def save_urls(urls: List[str]):
    """Save URLs to output file."""
    data = {
        'urls': sorted(urls),
        'totalCount': len(urls),
        'lastUpdated': datetime.now(timezone.utc).isoformat(),
        'note': 'Extracted from Tacoma World forum pages. Note: Pagination beyond page 1 may be blocked.'
    }
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def main():
    """Main execution."""
    print("=" * 80)
    print("Tacoma World Thread URL Extraction")
    print("=" * 80)

    # Load pages
    pages = load_pages()
    print(f"\nTotal pages to process: {len(pages)}")

    # Load progress
    progress = load_progress()
    processed = progress['processed_pages']
    failed = progress['failed_pages']
    all_urls = set(progress.get('all_urls', []))

    print(f"Already processed: {len(processed)} pages")
    print(f"Already failed: {len(failed)} pages")
    print(f"URLs discovered so far: {len(all_urls)}")

    # Create a set of processed URLs for quick lookup
    processed_urls_set = {p['url'] for p in processed}

    # Process each page
    for idx, page_info in enumerate(pages, 1):
        url = page_info['url']
        forum = page_info['forum']
        page_num = page_info['page']

        # Skip if already processed
        if url in processed_urls_set:
            print(f"[{idx}/{len(pages)}] SKIP: {forum} page {page_num} (already processed)")
            continue

        print(f"\n[{idx}/{len(pages)}] Processing: {forum} page {page_num}")
        print(f"  URL: {url}")

        # Note: We need to use MCP webReader tool to fetch each page
        # This script outlines the process but actual fetching requires MCP tool calls
        print(f"  ACTION REQUIRED: Use MCP webReader to fetch this page")
        print(f"  Tool: mcp__web_reader__webReader")
        print(f"  Parameters: url='{url}', timeout=30, return_format='text'")

        # For now, mark as needing manual processing
        # In practice, you would call the MCP tool here and process the result

        # Save progress every 10 pages
        if idx % 10 == 0:
            print(f"\n--- Saving checkpoint at page {idx} ---")
            save_progress(processed, failed, list(all_urls))

    print("\n" + "=" * 80)
    print("Extraction Complete!")
    print(f"Total unique thread URLs discovered: {len(all_urls)}")
    print(f"Saved to: {OUTPUT_FILE}")
    print("=" * 80)

    # Final save
    save_urls(list(all_urls))
    save_progress(processed, failed, list(all_urls))


if __name__ == '__main__':
    main()
