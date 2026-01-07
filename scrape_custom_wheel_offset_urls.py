#!/usr/bin/env python3
"""
Custom Wheel Offset Gallery URL Scraper
Scrapes all vehicle/build URLs from the gallery with pagination.
"""

import json
import time
import re
import sys
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)


class CustomWheelOffsetScraper:
    BASE_URL = "https://www.customwheeloffset.com/wheel-offset-gallery"
    OUTPUT_FILE = Path("scraped_builds/custom_wheel_offset/urls.json")
    REQUEST_DELAY = 1.5  # Seconds between requests
    MAX_RETRIES = 3
    TIMEOUT = 30

    def __init__(self):
        self.urls_seen = set()
        self.session = self._setup_session()

    def _setup_session(self):
        """Setup requests session with retry logic."""
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
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        return session

    def extract_urls_from_html(self, html: str) -> list:
        """Extract all gallery item URLs from HTML."""
        urls = []

        # Pattern to match gallery item URLs
        # Format: https://www.customwheeloffset.com/wheel-offset-gallery/{id}/{description}
        pattern = r'https://www\.customwheeloffset\.com/wheel-offset-gallery/\d+/[^"\'<>\s]+'

        matches = re.findall(pattern, html)
        urls.extend(matches)

        return urls

    def has_next_page(self, html: str) -> bool:
        """Check if there's a next page by looking for rel='next' link."""
        return "rel='next'" in html or 'rel="next"' in html

    def scrape_page(self, page_num: int) -> list:
        """Scrape a single page and return URLs found."""
        url = f"{self.BASE_URL}?page={page_num}"
        urls_found = []

        try:
            response = self.session.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()

            urls = self.extract_urls_from_html(response.text)
            urls_found = urls

            if urls:
                # Normalize URLs (remove fragments, sort)
                normalized = []
                for u in urls:
                    parsed = urlparse(u)
                    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if clean not in self.urls_seen:
                        normalized.append(clean)

                self.urls_seen.update(normalized)
                print(f"  Page {page_num}: Found {len(normalized)} new URLs (total: {len(self.urls_seen)})", flush=True)
            else:
                print(f"  Page {page_num}: No URLs found", flush=True)

            # Save progress every 10 pages
            if page_num % 10 == 0:
                self.save_urls()

            # Rate limiting
            time.sleep(self.REQUEST_DELAY)

        except requests.exceptions.RequestException as e:
            print(f"  Page {page_num}: Error - {e}", flush=True)

        return urls_found

    def find_total_pages(self):
        """Binary search to find the total number of pages."""
        print("Finding total number of pages...")

        low = 1
        high = 1
        # First, find an upper bound
        while True:
            try:
                response = self.session.get(f"{self.BASE_URL}?page={high}", timeout=self.TIMEOUT)
                if response.status_code == 200 and self.has_next_page(response.text):
                    high *= 2
                    if high > 100000:  # Safety limit
                        break
                else:
                    break
            except:
                break

        # Binary search for the last page
        last_page = high
        while low <= high:
            mid = (low + high) // 2
            try:
                response = self.session.get(f"{self.BASE_URL}?page={mid}", timeout=self.TIMEOUT)
                if response.status_code == 200:
                    if self.has_next_page(response.text):
                        low = mid + 1
                    else:
                        last_page = mid
                        high = mid - 1
                else:
                    high = mid - 1
            except:
                high = mid - 1

        print(f"  Total pages found: {last_page}")
        return last_page

    def scrape_all_urls(self, total_pages: int = None):
        """Scrape all pages for URLs."""
        if total_pages is None:
            total_pages = self.find_total_pages()

        print(f"\nScraping {total_pages} pages...")
        print("-" * 50)

        for page in range(1, total_pages + 1):
            self.scrape_page(page)

            # Progress update every 100 pages
            if page % 100 == 0:
                print(f"  Progress: {page}/{total_pages} pages processed ({100*page//total_pages}%)")

    def save_urls(self):
        """Save URLs to JSON file."""
        urls_list = sorted(list(self.urls_seen))  # Sort for consistency

        data = {
            "urls": urls_list,
            "lastUpdated": datetime.now().isoformat(),
            "totalCount": len(urls_list)
        }

        self.OUTPUT_FILE.write_text(json.dumps(data, indent=2))
        print("-" * 50)
        print(f"Saved {len(urls_list)} URLs to {self.OUTPUT_FILE}")


def main():
    print("=" * 50)
    print("Custom Wheel Offset Gallery URL Scraper")
    print("=" * 50)

    scraper = CustomWheelOffsetScraper()

    try:
        # We already know there are 3790 pages from manual testing
        total_pages = 3790
        print(f"Target: {total_pages} pages (estimated ~{total_pages * 30:,} URLs)")
        print("-" * 50)

        scraper.scrape_all_urls(total_pages)
        scraper.save_urls()

        print("\n" + "=" * 50)
        print("SCRAPING COMPLETE")
        print("=" * 50)
        print(f"Total URLs discovered: {len(scraper.urls_seen):,}")
        print(f"Output file: {scraper.OUTPUT_FILE}")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user. Saving partial results...")
        scraper.save_urls()
        print(f"Partial results saved: {len(scraper.urls_seen)} URLs")
    except Exception as e:
        print(f"\nError during scraping: {e}")
        scraper.save_urls()
        sys.exit(1)


if __name__ == "__main__":
    main()
