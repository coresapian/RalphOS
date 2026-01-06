#!/usr/bin/env python3
"""
Gateway Classic Cars HTML Scraper
Fetches full HTML content for discovered vehicle URLs.
Saves HTML files and tracks progress for resume capability.
"""

import json
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import urlparse

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError as e:
    print(f"Error: Missing dependency. Run: pip install requests")
    print(f"Details: {e}")
    sys.exit(1)


class GatewayClassicCarsHTMLScraper:
    OUTPUT_DIR = Path("scraped_builds/gateway_classic_cars")
    URLS_FILE = OUTPUT_DIR / "urls.json"
    HTML_DIR = OUTPUT_DIR / "html"
    PROGRESS_FILE = OUTPUT_DIR / "scrape_progress.json"
    REQUEST_DELAY = 1.5  # Seconds between requests (be respectful)
    TIMEOUT = 30
    MAX_RETRIES = 3

    def __init__(self):
        self.session = self._create_session()
        self.progress = self._load_progress()

    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic."""
        session = requests.Session()

        retry_strategy = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        return session

    def _load_progress(self) -> Dict[str, Any]:
        """Load progress from file or create new."""
        if self.PROGRESS_FILE.exists():
            return json.loads(self.PROGRESS_FILE.read_text())
        return {
            "completed_urls": [],
            "failed_urls": [],
            "started_at": None,
            "last_updated": None
        }

    def _save_progress(self):
        """Save current progress to file."""
        self.progress["last_updated"] = datetime.now().isoformat()
        self.PROGRESS_FILE.write_text(json.dumps(self.progress, indent=2))

    def _load_urls(self) -> List[str]:
        """Load URLs from urls.json."""
        if not self.URLS_FILE.exists():
            raise FileNotFoundError(f"URLs file not found: {self.URLS_FILE}")

        data = json.loads(self.URLS_FILE.read_text())
        return data.get("urls", [])

    def _get_filename_from_url(self, url: str) -> str:
        """Generate filename from URL."""
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')

        # Remove /vehicles/ prefix
        if path.startswith('/vehicles/'):
            path = path[10:]  # Remove '/vehicles/'

        # Replace slashes with dashes
        filename = path.replace('/', '-')

        # Ensure .html extension
        if not filename.endswith('.html'):
            filename += '.html'

        return filename

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
        filename = self._get_filename_from_url(url)
        filepath = self.HTML_DIR / filename

        self.HTML_DIR.mkdir(parents=True, exist_ok=True)
        filepath.write_text(html, encoding='utf-8')

        return filepath

    def scrape_all_urls(self):
        """Scrape all URLs from urls.json."""
        urls = self._load_urls()

        # Filter out already completed URLs
        remaining_urls = [u for u in urls if u not in self.progress["completed_urls"]]

        print(f"\n{'='*60}")
        print("Gateway Classic Cars HTML Scraper")
        print(f"{'='*60}")
        print(f"Total URLs: {len(urls)}")
        print(f"Already completed: {len(self.progress['completed_urls'])}")
        print(f"Remaining: {len(remaining_urls)}")
        print(f"Output directory: {self.HTML_DIR.absolute()}")
        print(f"{'='*60}\n")

        if not remaining_urls:
            print("All URLs have been scraped!")
            return

        # Initialize start time if new scrape
        if self.progress["started_at"] is None:
            self.progress["started_at"] = datetime.now().isoformat()
            self._save_progress()

        total_remaining = len(remaining_urls)

        for idx, url in enumerate(remaining_urls, 1):
            print(f"[{idx}/{total_remaining}] Fetching: {url}")

            try:
                html = self.fetch_html(url)
                filepath = self.save_html(url, html)
                self.progress["completed_urls"].append(url)
                print(f"  -> Saved to: {filepath.name}")

                # Save progress every 10 URLs
                if idx % 10 == 0:
                    self._save_progress()
                    print(f"  -> Progress saved ({len(self.progress['completed_urls'])}/{len(urls)})")

                # Rate limiting
                time.sleep(self.REQUEST_DELAY)

            except Exception as e:
                print(f"  -> FAILED: {e}")
                self.progress["failed_urls"].append(url)
                self._save_progress()

        # Final progress save
        self._save_progress()

        # Summary
        print(f"\n{'='*60}")
        print("SCRAPING COMPLETE")
        print(f"{'='*60}")
        print(f"Total URLs: {len(urls)}")
        print(f"Successfully scraped: {len(self.progress['completed_urls'])}")
        print(f"Failed: {len(self.progress['failed_urls'])}")

        if self.progress["failed_urls"]:
            print(f"\nFailed URLs:")
            for url in self.progress["failed_urls"][:5]:
                print(f"  - {url}")
            if len(self.progress["failed_urls"]) > 5:
                print(f"  ... and {len(self.progress['failed_urls']) - 5} more")

        print(f"\nHTML files saved to: {self.HTML_DIR.absolute()}")
        print(f"{'='*60}")


def main():
    scraper = GatewayClassicCarsHTMLScraper()

    try:
        scraper.scrape_all_urls()
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
        print(f"Progress saved. Run again to resume.")
        scraper._save_progress()
        sys.exit(0)


if __name__ == "__main__":
    main()
