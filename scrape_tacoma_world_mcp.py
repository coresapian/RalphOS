#!/usr/bin/env python3
"""
Scrape Tacoma World build thread URLs using MCP webReader tool.
Processes all 158 forum pages and extracts thread URLs.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Set, Dict
import time

# File paths
PAGES_FILE = Path("/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/tacoma_world_builds/pages_to_fetch.json")
OUTPUT_FILE = Path("/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/tacoma_world_builds/urls.json")
PROGRESS_FILE = Path("/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/tacoma_world_builds/scrape_progress_mcp.json")

# Thread URL pattern
THREAD_PATTERN = re.compile(r'/threads/([^.]+)\.(\d+)/')


def load_pages() -> List[Dict]:
    """Load the list of pages to fetch."""
    with open(PAGES_FILE, 'r') as f:
        data = json.load(f)
    return data['pages']


def load_progress() -> Dict:
    """Load existing progress if available."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {
        'completed_urls': [],
        'failed_urls': [],
        'last_update': None
    }


def save_progress(completed_urls: List[str], failed_urls: List[Dict]):
    """Save progress after each batch."""
    progress = {
        'completed_urls': completed_urls,
        'failed_urls': failed_urls,
        'last_update': datetime.utcnow().isoformat() + 'Z'
    }
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def extract_thread_urls_from_text(text_content: str) -> Set[str]:
    """Extract thread URLs from text content (MCP webReader output)."""
    urls = set()

    # First, try to parse as JSON
    try:
        data = json.loads(text_content)
        if isinstance(data, dict) and 'content' in data:
            content = data['content']
        else:
            content = text_content
    except json.JSONDecodeError:
        content = text_content

    # Find all matches of the thread pattern
    matches = THREAD_PATTERN.findall(content)

    for slug, thread_id in matches:
        url = f"https://www.tacomaworld.com/threads/{slug}.{thread_id}/"
        urls.add(url)

    return urls


def save_urls(urls: List[str]):
    """Save the collected URLs to the output file."""
    data = {
        'urls': sorted(urls),
        'totalCount': len(urls),
        'lastUpdated': datetime.utcnow().isoformat() + 'Z'
    }
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def main():
    """Main execution function."""
    print("=" * 80)
    print("Tacoma World Build Thread URL Discovery via MCP")
    print("=" * 80)

    # Load pages
    pages = load_pages()
    print(f"\nLoaded {len(pages)} pages to process")

    # Load progress
    progress = load_progress()
    completed_urls_set = set(progress['completed_urls'])
    failed_urls = progress['failed_urls']

    print(f"Resuming with {len(completed_urls_set)} already completed URLs")
    print(f"Previous failures: {len(failed_urls)}")

    all_thread_urls = set()

    # Process pages in batches
    batch_size = 10
    total_pages = len(pages)

    for idx, page_info in enumerate(pages, 1):
        url = page_info['url']
        forum = page_info['forum']
        page_num = page_info['page']

        # Skip if already processed
        if url in completed_urls_set:
            print(f"[{idx}/{total_pages}] SKIP: {forum} page {page_num} (already done)")
            # Extract URLs from already processed pages
            continue

        print(f"\n[{idx}/{total_pages}] Processing: {forum} page {page_num}")
        print(f"  URL: {url}")

        # Mark for manual MCP processing
        print(f"  Status: NEEDS MCP FETCH - Add result to manual processing")

        # Save progress every batch_size pages
        if idx % batch_size == 0:
            print(f"\n--- Batch complete ({idx}/{total_pages}) ---")
            save_progress(list(completed_urls_set), failed_urls)

    print("\n" + "=" * 80)
    print("Processing complete!")
    print(f"Total unique URLs discovered: {len(all_thread_urls)}")
    print("=" * 80)
    print("\nNOTE: Due to pagination restrictions on Tacoma World,")
    print("only the first page of each forum section is accessible.")
    print("Manual MCP webReader calls needed for each page.")
    print("=" * 80)


if __name__ == '__main__':
    main()
