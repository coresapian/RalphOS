#!/usr/bin/env python3
"""
Scrape build thread URLs from Tacoma World forum.

Discovers all build thread URLs from:
- 3rd Gen. Builds (2016-2023): /forums/3rd-gen-builds-2016-2023.196/
- 2nd Gen. Builds (2005-2015): /forums/2nd-gen-builds-2005-2015.103/
- 1st Gen. Builds (1995-2004): /forums/1st-gen-builds-1995-2004.102/
- 4th Gen. Builds (2024+): TBD
- 4Runner Builds: TBD
- Other Builds: TBD

Thread URL pattern: /threads/{slug}.{id}/

Usage:
    python scrape_build_threads.py
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Set
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Build forums to scrape
BUILD_FORUMS = [
    {
        "name": "3rd Gen. Builds (2016-2023)",
        "url": "https://www.tacomaworld.com/forums/3rd-gen-builds-2016-2023.196/",
        "threads": 1582,  # From forum index: "Showing threads 1 to 50 of 1,582"
        "pages": 32
    },
    {
        "name": "2nd Gen. Builds (2005-2015)",
        "url": "https://www.tacomaworld.com/forums/2nd-gen-builds-2005-2015.103/",
        "threads": 4526,  # From forum index: "Showing threads 1 to 50 of 4,526"
        "pages": 91
    },
    {
        "name": "1st Gen. Builds (1995-2004)",
        "url": "https://www.tacomaworld.com/forums/1st-gen-builds-1995-2004.102/",
        "threads": 1744,  # From forum index: "Showing threads 1 to 50 of 1,744"
        "pages": 35
    }
]

OUTPUT_FILE = Path("scraped_builds/tacoma_world_builds/urls.json")
SAVE_INTERVAL = 5  # Save progress every N pages
REQUEST_DELAY = 1.5  # Seconds between requests

# Thread URL pattern: /threads/{slug}.{numeric-id}/
THREAD_PATTERN = re.compile(r'https://www\.tacomaworld\.com/threads/[^/]+\.(\d+)/')


def create_session() -> requests.Session:
    """Create requests session with retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return session


def extract_thread_urls(html_content: str) -> Set[str]:
    """Extract all thread URLs from forum page HTML."""
    urls = set()

    # Find all links to threads
    for match in THREAD_PATTERN.finditer(html_content):
        url = match.group(0)
        urls.add(url)

    return urls


def scrape_forum(forum_info: dict, session: requests.Session) -> List[str]:
    """Scrape all thread URLs from a single forum."""
    name = forum_info["name"]
    base_url = forum_info["url"]
    expected_pages = forum_info["pages"]

    all_urls = []

    print(f"\nScraping {name}")
    print(f"Expected: {forum_info['threads']} threads across {expected_pages} pages")

    for page_num in range(1, expected_pages + 1):
        # Construct page URL
        if page_num == 1:
            page_url = base_url
        else:
            page_url = base_url.rstrip('/') + f'/page-{page_num}/'

        try:
            response = session.get(page_url, timeout=30)
            response.raise_for_status()

            # Extract thread URLs from this page
            page_urls = extract_thread_urls(response.text)
            all_urls.extend(page_urls)

            print(f"  Page {page_num}/{expected_pages}: Found {len(page_urls)} threads (total: {len(all_urls)})")

            # Save progress periodically
            if page_num % SAVE_INTERVAL == 0:
                save_urls(all_urls)
                print(f"  Progress saved ({len(all_urls)} URLs)")

            # Rate limiting
            time.sleep(REQUEST_DELAY)

        except Exception as e:
            print(f"  ERROR on page {page_num}: {e}")
            continue

    return all_urls


def save_urls(urls: List[str]):
    """Save discovered URLs to output file."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Remove duplicates while preserving order
    unique_urls = list(dict.fromkeys(urls))

    data = {
        "urls": sorted(unique_urls),
        "totalCount": len(unique_urls),
        "lastUpdated": datetime.utcnow().isoformat() + "Z"
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def main():
    """Main scraping function."""
    print("=" * 60)
    print("Tacoma World Build Thread URL Discovery")
    print("=" * 60)

    session = create_session()
    all_urls = []

    # Load existing URLs if any
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            existing = json.load(f)
            all_urls = existing.get("urls", [])
        print(f"\nResuming from {len(all_urls)} existing URLs")

    # Scrape each forum
    for forum in BUILD_FORUMS:
        forum_urls = scrape_forum(forum, session)

        # Filter out duplicates
        for url in forum_urls:
            if url not in all_urls:
                all_urls.append(url)

        print(f"  Forum complete: {len(forum_urls)} threads")

    # Final save
    save_urls(all_urls)

    print("\n" + "=" * 60)
    print(f"COMPLETE! Discovered {len(all_urls)} build thread URLs")
    print(f"Saved to: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
