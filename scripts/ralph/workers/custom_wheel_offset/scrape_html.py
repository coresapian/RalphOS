#!/usr/bin/env python3
"""
Custom Wheel Offset HTML Scraper
Downloads HTML pages for all discovered vehicle/build URLs with retry logic and progress tracking.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import time
import os
from datetime import datetime
from pathlib import Path

# Configuration
URLS_FILE = "/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/custom_wheel_offset/urls.json"
HTML_DIR = "/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/custom_wheel_offset/html"
PROGRESS_FILE = "/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/custom_wheel_offset/scrape_progress.json"

# Rate limiting
DELAY_BETWEEN_REQUESTS = 1.5
SAVE_EVERY_N_REQUESTS = 50

def get_filename_from_url(url):
    """Generate a safe filename from URL."""
    # URL pattern: https://www.customwheeloffset.com/wheel-offset-gallery/{id}/{description}
    # Extract the ID and description parts
    parts = url.rstrip('/').split('/')

    # The ID is second to last, description is last
    if len(parts) >= 2:
        vehicle_id = parts[-2]
        description = parts[-1]

        # Create filename: {id}_{description}.html
        # Clean description to be filesystem-safe
        safe_description = description.replace('/', '-').replace('\\', '-')
        safe_description = safe_description.replace(' ', '_').replace('?', '').replace('!', '')

        filename = f"{vehicle_id}_{safe_description}.html"

        # Ensure filename isn't too long for filesystems
        if len(filename) > 255:
            filename = f"{vehicle_id}.html"

        return filename

    # Fallback: use hash of URL
    return f"vehicle_{hash(url)}.html"

def create_session_with_retries():
    """Create a requests session with retry logic."""
    session = requests.Session()

    # Retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    })

    return session

def load_progress():
    """Load existing progress or return empty dict."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {
        "completed": [],
        "failed": [],
        "lastUpdated": None,
        "totalScraped": 0
    }

def save_progress(progress):
    """Save progress to file."""
    progress["lastUpdated"] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def load_urls():
    """Load URLs from urls.json."""
    with open(URLS_FILE, 'r') as f:
        data = json.load(f)
    return data.get("urls", [])

def main():
    print(f"[{datetime.now().isoformat()}] Starting Custom Wheel Offset HTML scraper...")

    # Ensure HTML directory exists
    Path(HTML_DIR).mkdir(parents=True, exist_ok=True)

    # Load URLs and progress
    urls = load_urls()
    progress = load_progress()

    total_urls = len(urls)
    completed = set(progress.get("completed", []))
    failed = set(progress.get("failed", []))

    print(f"[{datetime.now().isoformat()}] Total URLs to scrape: {total_urls}")
    print(f"[{datetime.now().isoformat()}] Already completed: {len(completed)}")
    print(f"[{datetime.now().isoformat()}] Previously failed: {len(failed)}")
    print(f"[{datetime.now().isoformat()}] Remaining: {total_urls - len(completed)}")

    # Create session with retry logic
    session = create_session_with_retries()

    # Scrape each URL
    newly_scraped = 0
    new_failures = []

    for i, url in enumerate(urls):
        filename = get_filename_from_url(url)
        filepath = os.path.join(HTML_DIR, filename)

        # Skip if already completed
        if url in completed or os.path.exists(filepath):
            continue

        print(f"[{datetime.now().isoformat()}] [{i+1}/{total_urls}] Scraping: {url}")

        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()

            # Save HTML
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(response.text)

            completed.add(url)
            newly_scraped += 1

            print(f"[{datetime.now().isoformat()}] [{i+1}/{total_urls}] Saved: {filename}")

            # Rate limiting
            time.sleep(DELAY_BETWEEN_REQUESTS)

            # Save progress periodically
            if newly_scraped % SAVE_EVERY_N_REQUESTS == 0:
                progress["completed"] = list(completed)
                progress["totalScraped"] = len(completed)
                save_progress(progress)
                print(f"[{datetime.now().isoformat()}] Progress checkpoint: {len(completed)}/{total_urls}")

        except Exception as e:
            print(f"[{datetime.now().isoformat()}] [{i+1}/{total_urls}] ERROR: {e}")
            new_failures.append({"url": url, "error": str(e)})
            failed.add(url)

            # Brief pause on error
            time.sleep(2)

    # Final progress save
    progress["completed"] = list(completed)
    progress["failed"] = list(failed)
    progress["totalScraped"] = len(completed)
    save_progress(progress)

    # Summary
    print(f"\n[{datetime.now().isoformat()}] Scraping complete!")
    print(f"[{datetime.now().isoformat()}] Total URLs: {total_urls}")
    print(f"[{datetime.now().isoformat()}] Successfully scraped: {len(completed)}")
    print(f"[{datetime.now().isoformat()}] Newly scraped this run: {newly_scraped}")
    print(f"[{datetime.now().isoformat()}] Failed: {len(failed)}")
    print(f"[{datetime.now().isoformat()}] HTML files saved to: {HTML_DIR}")
    print(f"[{datetime.now().isoformat()}] Progress saved to: {PROGRESS_FILE}")

if __name__ == "__main__":
    main()
