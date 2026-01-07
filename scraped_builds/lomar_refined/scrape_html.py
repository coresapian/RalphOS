#!/usr/bin/env python3
"""Scrape HTML content for Lomar Refined build articles."""
import json
import os
import time
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


def url_to_filename(url):
    """Convert URL to safe filename."""
    parsed = urlparse(url)
    path = parsed.path.strip('/').replace('/', '_')
    if not path:
        path = 'index'
    return f"{path}.html"


def load_progress(progress_file):
    """Load scraping progress from file."""
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            return json.load(f)
    return {"scraped": [], "failed": [], "lastUpdated": None}


def save_progress(progress_file, scraped_urls, failed_urls):
    """Save scraping progress to file."""
    with open(progress_file, 'w') as f:
        json.dump({
            "scraped": scraped_urls,
            "failed": failed_urls,
            "lastUpdated": datetime.now().isoformat()
        }, f, indent=2)


def fetch_url_with_retry(url, max_retries=3):
    """Fetch URL with retry logic."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for attempt in range(max_retries):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=30) as response:
                return response.read().decode('utf-8')
        except (URLError, HTTPError) as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"  Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                raise


def scrape_html(output_dir="scraped_builds/lomar_refined"):
    """Main scraping function."""
    urls_file = os.path.join(output_dir, "urls.json")
    html_dir = os.path.join(output_dir, "html")
    progress_file = os.path.join(output_dir, "scrape_progress.json")

    # Create html directory if it doesn't exist
    os.makedirs(html_dir, exist_ok=True)

    # Load URLs
    print(f"Loading URLs from {urls_file}...")
    with open(urls_file, 'r') as f:
        data = json.load(f)
        urls = data.get("urls", [])

    total = len(urls)
    print(f"Found {total} URLs to scrape")

    # Load progress
    progress = load_progress(progress_file)
    scraped_urls = set(progress.get("scraped", []))
    failed_urls = set(progress.get("failed", []))

    # Filter out already scraped URLs
    remaining = [url for url in urls if url not in scraped_urls]
    print(f"Already scraped: {len(scraped_urls)}")
    print(f"Remaining to scrape: {len(remaining)}")

    if not remaining:
        print("All URLs already scraped!")
        return

    # Scrape each URL
    new_scraped = []
    new_failed = []

    for i, url in enumerate(remaining, 1):
        filename = url_to_filename(url)
        filepath = os.path.join(html_dir, filename)

        print(f"[{i}/{len(remaining)}] Scraping: {url}")

        try:
            html = fetch_url_with_retry(url)

            # Save HTML
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)

            new_scraped.append(url)
            scraped_urls.add(url)

            # Save progress every 5 URLs
            if len(new_scraped) % 5 == 0:
                save_progress(progress_file, list(scraped_urls), list(failed_urls))
                print(f"Progress saved: {len(scraped_urls)}/{total} scraped")

            # Rate limiting
            time.sleep(1.5)

        except Exception as e:
            print(f"ERROR: {e}")
            new_failed.append(url)
            failed_urls.add(url)

    # Final save
    save_progress(progress_file, list(scraped_urls), list(failed_urls))

    print(f"\n=== Scraping Complete ===")
    print(f"Total scraped: {len(scraped_urls)}/{total}")
    print(f"Failed: {len(failed_urls)}")
    print(f"HTML files saved to: {html_dir}")


if __name__ == "__main__":
    scrape_html()
