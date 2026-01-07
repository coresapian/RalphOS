#!/usr/bin/env python3
"""
Process Tacoma World forum pages to extract thread URLs.
Handles MCP webReader output and extracts thread URLs.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Set, List, Dict

# File paths
PAGES_FILE = Path("/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/tacoma_world_builds/pages_to_fetch.json")
OUTPUT_FILE = Path("/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/tacoma_world_builds/urls.json")
PROCESSED_FILE = Path("/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/tacoma_world_builds/processed_pages.json")

# Thread URL pattern
THREAD_PATTERN = re.compile(r'/threads/([^.]+)\.(\d+)/')


def extract_urls_from_html(html_content: str) -> Set[str]:
    """Extract thread URLs from HTML content."""
    urls = set()

    # Find all matches of the thread pattern
    matches = THREAD_PATTERN.findall(html_content)

    for slug, thread_id in matches:
        url = f"https://www.tacomaworld.com/threads/{slug}.{thread_id}/"
        urls.add(url)

    return urls


def load_pages() -> List[Dict]:
    """Load the list of pages to fetch."""
    with open(PAGES_FILE, 'r') as f:
        data = json.load(f)
    return data['pages']


def save_urls(urls: List[str]):
    """Save the collected URLs to the output file."""
    data = {
        'urls': sorted(urls),
        'totalCount': len(urls),
        'lastUpdated': datetime.utcnow().isoformat() + 'Z'
    }
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def load_processed() -> Dict:
    """Load processed page data."""
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE, 'r') as f:
            return json.load(f)
    return {
        'processed_pages': [],
        'failed_pages': [],
        'total_threads_found': 0
    }


def save_processed(processed: List[Dict], failed: List[Dict], total: int):
    """Save processed page data."""
    data = {
        'processed_pages': processed,
        'failed_pages': failed,
        'total_threads_found': total,
        'lastUpdated': datetime.utcnow().isoformat() + 'Z'
    }
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def main():
    """Main execution function."""
    print("=" * 80)
    print("Tacoma World URL Extraction from MCP Fetched Content")
    print("=" * 80)

    # Load existing processed data
    processed_data = load_processed()
    processed_pages = processed_data['processed_pages']
    failed_pages = processed_data['failed_pages']

    print(f"\nPreviously processed: {len(processed_pages)} pages")
    print(f"Previously failed: {len(failed_pages)} pages")

    # All collected thread URLs
    all_thread_urls = set()

    # Process successful fetches
    for page_data in processed_pages:
        if 'html_content' in page_data:
            urls = extract_urls_from_html(page_data['html_content'])
            all_thread_urls.update(urls)
            print(f"Extracted {len(urls)} URLs from {page_data['forum']} page {page_data['page']}")

    print(f"\nTotal unique thread URLs discovered: {len(all_thread_urls)}")

    # Save the URLs
    save_urls(list(all_thread_urls))

    print(f"\nURLs saved to: {OUTPUT_FILE}")
    print("=" * 80)

    # Summary
    print("\nSUMMARY:")
    print(f"  Processed pages: {len(processed_pages)}")
    print(f"  Failed pages: {len(failed_pages)}")
    print(f"  Total unique threads: {len(all_thread_urls)}")
    print("\nNOTE: Tacoma World blocks paginated URLs (page-2, page-3, etc.).")
    print("Only the first page of each forum section is accessible.")
    print("Expected total if all pages were accessible: ~7,854 threads")
    print(f"Actual threads discovered (first pages only): {len(all_thread_urls)}")
    print("=" * 80)


if __name__ == '__main__':
    main()
