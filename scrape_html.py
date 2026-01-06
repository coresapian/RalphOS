#!/usr/bin/env python3
"""
MartiniWorks Build Thread HTML Scraper
Fetches and saves HTML content for all discovered build thread URLs.
Supports progress tracking and resume capability.
"""

import json
import time
import sys
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, List, Set

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)


class HTMLScraper:
    URLS_FILE = Path("scraped_builds/urls.json")
    OUTPUT_DIR = Path("scraped_builds/html")
    PROGRESS_FILE = Path("scraped_builds/scrape_progress.json")
    REQUEST_DELAY = 1.5  # Seconds between requests (be respectful)
    TIMEOUT = 30  # Request timeout in seconds
    MAX_RETRIES = 3

    def __init__(self):
        self.session = self._create_session()
        self.progress = self._load_progress()

    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic."""
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set user agent
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        return session

    def _load_progress(self) -> Dict:
        """Load existing progress or initialize new tracking."""
        if self.PROGRESS_FILE.exists():
            try:
                data = json.loads(self.PROGRESS_FILE.read_text())
                print(f"Found existing progress: {len(data.get('completed', []))} URLs completed")
                return data
            except Exception as e:
                print(f"Warning: Could not load progress file: {e}")

        return {
            "startedAt": datetime.now().isoformat(),
            "lastUpdated": None,
            "completed": [],
            "failed": [],
            "totalCount": 0
        }

    def _save_progress(self):
        """Save current progress state."""
        self.progress["lastUpdated"] = datetime.now().isoformat()
        self.progress["totalCount"] = len(self.progress["completed"])
        self.PROGRESS_FILE.write_text(json.dumps(self.progress, indent=2))

    def _get_slug_from_url(self, url: str) -> str:
        """Extract slug from URL for filename."""
        parsed = urlparse(url)
        # Remove leading/trailing slashes and get the last segment
        path = parsed.path.strip("/")
        # Handle URLs like /build-threads/acura/integra/1993-...
        # We want the full meaningful path
        if path.startswith("build-threads/"):
            path = path.replace("build-threads/", "")
        return path.replace("/", "-") + ".html"

    def load_urls(self) -> List[str]:
        """Load URLs from urls.json."""
        if not self.URLS_FILE.exists():
            print(f"Error: {self.URLS_FILE} not found. Run scrape_urls.py first.")
            sys.exit(1)

        data = json.loads(self.URLS_FILE.read_text())
        urls = data.get("urls", [])
        print(f"Loaded {len(urls)} URLs from {self.URLS_FILE}")
        return urls

    def fetch_html(self, url: str) -> str:
        """Fetch HTML content from URL."""
        try:
            response = self.session.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"  Error fetching {url}: {e}")
            raise

    def save_html(self, url: str, html: str) -> Path:
        """Save HTML content to file."""
        slug = self._get_slug_from_url(url)
        output_path = self.OUTPUT_DIR / slug

        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        return output_path

    def scrape_all(self):
        """Main scraping method with progress tracking."""
        urls = self.load_urls()
        completed: Set[str] = set(self.progress.get("completed", []))
        failed: Set[str] = set(self.progress.get("failed", []))

        remaining = [url for url in urls if url not in completed]
        total = len(urls)

        print(f"\n{'='*60}")
        print(f"HTML Scraper Started")
        print(f"{'='*60}")
        print(f"Total URLs: {total}")
        print(f"Already completed: {len(completed)}")
        print(f"Failed (will retry): {len(failed)}")
        print(f"Remaining to scrape: {len(remaining)}")
        print(f"Output directory: {self.OUTPUT_DIR.absolute()}")
        print(f"{'='*60}\n")

        if not remaining:
            print("All URLs have been scraped!")
            return

        # Also retry failed URLs
        for url in list(failed):
            if url not in remaining:
                remaining.append(url)

        for idx, url in enumerate(remaining, 1):
            print(f"[{idx}/{len(remaining)}] Scraping: {url}")

            try:
                # Fetch HTML
                html = self.fetch_html(url)

                # Save to file
                output_path = self.save_html(url, html)
                print(f"  -> Saved: {output_path.name}")

                # Update progress
                completed.add(url)
                failed.discard(url)

                # Save progress every 10 URLs
                if len(completed) % 10 == 0:
                    self.progress["completed"] = list(completed)
                    self.progress["failed"] = list(failed)
                    self._save_progress()
                    print(f"  -> Progress checkpoint: {len(completed)}/{total} completed")

                # Rate limiting delay
                time.sleep(self.REQUEST_DELAY)

            except Exception as e:
                print(f"  -> FAILED: {e}")
                failed.add(url)
                # Save progress after failure too
                self.progress["completed"] = list(completed)
                self.progress["failed"] = list(failed)
                self._save_progress()

        # Final progress save
        self.progress["completed"] = list(completed)
        self.progress["failed"] = list(failed)
        self.progress["finishedAt"] = datetime.now().isoformat()
        self._save_progress()

        # Summary
        print(f"\n{'='*60}")
        print("SCRAPING COMPLETE")
        print(f"{'='*60}")
        print(f"Total processed: {total}")
        print(f"Successfully scraped: {len(completed)}")
        print(f"Failed: {len(failed)}")

        if failed:
            print(f"\nFailed URLs:")
            for url in failed:
                print(f"  - {url}")

        print(f"{'='*60}")


def main():
    scraper = HTMLScraper()

    try:
        scraper.scrape_all()
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user. Progress has been saved.")
        scraper._save_progress()
        sys.exit(0)


if __name__ == "__main__":
    main()
