#!/usr/bin/env python3
"""
HTML Scraper for Paramount Performance UK Tuner Showcase Pages.
Downloads HTML from discovered URLs with proper rate limiting.
"""

import json
import time
import random
import re
from pathlib import Path

import httpx

# Configuration
OUTPUT_DIR = Path(__file__).parent
HTML_DIR = OUTPUT_DIR / "html"
URLS_FILE = OUTPUT_DIR / "urls.json"

# Request settings
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

MIN_DELAY = 2.0
MAX_DELAY = 4.0


def url_to_filename(url: str) -> str:
    """Convert URL to safe filename."""
    # Extract showcase slug: /showcase/bmw-m3-upgrades/ -> bmw-m3-upgrades
    match = re.search(r'/showcase/([^/]+)/?', url)
    if match:
        slug = match.group(1)
        return f"{slug}.html"
    # Fallback
    return url.replace("https://", "").replace("/", "_").rstrip("_") + ".html"


def scrape_url(client: httpx.Client, url: str) -> tuple[str, int]:
    """Scrape a single URL, return (html, status_code)."""
    try:
        response = client.get(url, follow_redirects=True, timeout=30.0)
        return response.text, response.status_code
    except httpx.TimeoutException:
        return "", 0
    except Exception as e:
        print(f"  Error: {e}")
        return "", -1


def main():
    # Ensure output directory exists
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    # Load URLs
    with open(URLS_FILE, "r", encoding="utf-8") as f:
        urls_data = json.load(f)

    urls = urls_data.get("urls", [])
    print(f"Scraping {len(urls)} URLs from Paramount Performance...")

    # Track results
    success = 0
    failed = 0
    skipped = 0

    with httpx.Client(headers=HEADERS, proxy=None) as client:
        for i, url in enumerate(urls, 1):
            filename = url_to_filename(url)
            filepath = HTML_DIR / filename

            # Skip if already scraped
            if filepath.exists():
                print(f"[{i}/{len(urls)}] SKIP (exists): {filename}")
                skipped += 1
                continue

            print(f"[{i}/{len(urls)}] Scraping: {url}")

            html, status = scrape_url(client, url)

            if status == 200 and html:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"  SUCCESS: {len(html):,} bytes -> {filename}")
                success += 1
            elif status == 403:
                print(f"  BLOCKED (403)")
                failed += 1
            elif status == 429:
                print(f"  RATE LIMITED (429)")
                failed += 1
            elif status == 404:
                print(f"  NOT FOUND (404)")
                failed += 1
            else:
                print(f"  FAILED: status={status}")
                failed += 1

            # Rate limiting
            if i < len(urls):
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                time.sleep(delay)

    # Summary
    print("\n" + "=" * 60)
    print("HTML SCRAPING COMPLETE")
    print(f"  Success: {success}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped}")
    print("=" * 60)


if __name__ == "__main__":
    main()
