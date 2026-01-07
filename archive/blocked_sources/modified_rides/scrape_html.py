#!/usr/bin/env python3
"""
HTML Scraper for Modified Rides
Downloads HTML content for all discovered URLs with retry logic and progress tracking
"""

import json
import os
import time
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def create_session_with_retries():
    """Create a requests session with retry logic"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_filename_from_url(url):
    """Generate a safe filename from URL"""
    parsed = urlparse(url)
    path = parsed.path.rstrip('.html')

    # Extract slug from path: /news/modified-cars/article-slug.html -> article-slug
    parts = path.split('/')
    slug = parts[-1] if parts else 'unknown'

    # Create hash for uniqueness
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

    return f"{slug}_{url_hash}.html"


def load_progress(progress_file):
    """Load existing progress or return empty dict"""
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            return json.load(f)
    return {
        "startedAt": None,
        "lastUpdated": None,
        "totalUrls": 0,
        "completedUrls": 0,
        "failedUrls": [],
        "lastUrlIndex": 0
    }


def save_progress(progress_file, progress_data):
    """Save progress to file"""
    progress_data["lastUpdated"] = datetime.now().isoformat()
    with open(progress_file, 'w') as f:
        json.dump(progress_data, f, indent=2)


def main():
    # Configuration
    base_dir = Path(__file__).parent
    urls_file = base_dir / "urls.json"
    html_dir = base_dir / "html"
    progress_file = base_dir / "scrape_progress.json"

    # Ensure html directory exists
    html_dir.mkdir(exist_ok=True)

    # Load URLs
    print(f"Loading URLs from {urls_file}...")
    with open(urls_file, 'r') as f:
        data = json.load(f)
        urls = data.get("urls", [])

    total_urls = len(urls)
    print(f"Found {total_urls} URLs to scrape")

    # Load or initialize progress
    progress = load_progress(progress_file)

    if progress.get("startedAt") is None:
        progress["startedAt"] = datetime.now().isoformat()
        progress["totalUrls"] = total_urls
        progress["completedUrls"] = 0
        progress["failedUrls"] = []
        progress["lastUrlIndex"] = 0
        print("Starting fresh scrape")
    else:
        print(f"Resuming from URL index {progress['lastUrlIndex']}")
        print(f"Previously completed: {progress['completedUrls']}/{total_urls}")

    # Create session with retries
    session = create_session_with_retries()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # Start scraping from where we left off
    start_index = progress.get("lastUrlIndex", 0)
    completed_count = progress.get("completedUrls", 0)

    for i in range(start_index, total_urls):
        url = urls[i]

        # Generate filename
        filename = get_filename_from_url(url)
        filepath = html_dir / filename

        # Skip if already downloaded
        if filepath.exists():
            print(f"[{i+1}/{total_urls}] Already exists: {filename}")
            completed_count += 1
            progress["lastUrlIndex"] = i + 1
            progress["completedUrls"] = completed_count
            continue

        # Download HTML
        try:
            print(f"[{i+1}/{total_urls}] Downloading: {url}")
            response = session.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # Save HTML
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(response.text)

            completed_count += 1
            progress["completedUrls"] = completed_count
            progress["lastUrlIndex"] = i + 1

            # Save progress every 10 URLs
            if (i + 1) % 10 == 0:
                save_progress(progress_file, progress)
                print(f"  Progress saved: {completed_count}/{total_urls} completed")

            # Rate limiting - respectful delay
            time.sleep(1.5)

        except Exception as e:
            print(f"  ERROR: {e}")
            progress["failedUrls"].append({
                "url": url,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            # Save progress immediately on error
            save_progress(progress_file, progress)
            time.sleep(2)  # Extra delay on error
            continue

    # Final progress save
    save_progress(progress_file, progress)

    print("\n" + "="*60)
    print("SCRAPE COMPLETE")
    print("="*60)
    print(f"Total URLs: {total_urls}")
    print(f"Successfully downloaded: {completed_count}")
    print(f"Failed: {len(progress['failedUrls'])}")
    print(f"HTML directory: {html_dir}")
    print(f"Progress file: {progress_file}")
    print("="*60)


if __name__ == "__main__":
    main()
