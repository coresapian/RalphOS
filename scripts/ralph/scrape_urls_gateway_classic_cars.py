#!/usr/bin/env python3
"""
Gateway Classic Cars URL Scraper
Scrapes all vehicle URLs from the inventory pages.
"""

import json
import time
import re
from pathlib import Path
from datetime import datetime
from typing import List, Set

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError as e:
    print(f"Error: Missing dependency. Run: pip install requests")
    print(f"Details: {e}")
    exit(1)


class GatewayClassicCarsURLScraper:
    BASE_URL = "https://www.gatewayclassiccars.com"
    INVENTORY_URL = f"{BASE_URL}/vehicles"
    OUTPUT_DIR = Path("scraped_builds/gateway_classic_cars")
    URLS_FILE = OUTPUT_DIR / "urls.json"
    REQUEST_DELAY = 1.5  # Seconds between requests
    TIMEOUT = 30
    MAX_RETRIES = 3

    def __init__(self):
        self.session = self._create_session()
        self.urls: Set[str] = set()

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

    def extract_urls_from_page(self, page_num: int) -> List[str]:
        """Extract vehicle URLs from a single page."""
        url = f"{self.INVENTORY_URL}?page={page_num}"
        print(f"Fetching page {page_num}...")

        try:
            response = self.session.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()
            html = response.text

            # Extract URLs from JSON-LD structured data
            urls = []

            # Method 1: Parse JSON-LD structured data
            json_ld_pattern = r'"url":"(https://www\.gatewayclassiccars\.com/vehicles/[^"]+)"'
            matches = re.findall(json_ld_pattern, html)

            for match in matches:
                # Unescape URL
                unescaped = match.replace(r'\u0026', '&')
                if unescaped.startswith(self.BASE_URL):
                    urls.append(unescaped)

            # Method 2: Also look for vehicle links in HTML
            link_pattern = r'href="(https://www\.gatewayclassiccars\.com/vehicles/[^/]+/\d+/[^"]+)"'
            link_matches = re.findall(link_pattern, html)
            urls.extend(link_matches)

            # Deduplicate
            unique_urls = list(set(urls))
            print(f"  Found {len(unique_urls)} vehicle URLs")
            return unique_urls

        except requests.exceptions.RequestException as e:
            print(f"  Error fetching page {page_num}: {e}")
            return []

    def get_total_pages(self) -> int:
        """Determine total number of pages from the first page."""
        print("Determining total pages...")

        response = self.session.get(self.INVENTORY_URL, timeout=self.TIMEOUT)
        response.raise_for_status()
        html = response.text

        # Look for pagination in the HTML
        # The page shows links like "1, 2, 3, ... 109, 110"
        max_page_pattern = r'page=(\d+)">(\d+)<'
        matches = re.findall(max_page_pattern, html)

        if matches:
            max_page = max(int(m[1]) for m in matches)
            print(f"  Found {max_page} pages")
            return max_page

        # Alternative: check for "Page X of Y" text
        page_count_pattern = r'Page (\d+) of (\d+)'
        match = re.search(page_count_pattern, html)
        if match:
            total = int(match.group(2))
            print(f"  Found {total} pages")
            return total

        # Default to checking pages until we hit a 404
        print("  Could not determine page count, will check until 404")
        return 0  # Will use continuous checking

    def scrape_all_urls(self):
        """Scrape all vehicle URLs from all pages."""
        print("\n" + "=" * 60)
        print("Gateway Classic Cars URL Scraper")
        print("=" * 60)

        # Create output directory
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Get total pages
        total_pages = self.get_total_pages()

        if total_pages == 0:
            # Determine pages by checking until 404
            print("\nDetecting pages by checking for 404...")
            page = 1
            while True:
                urls = self.extract_urls_from_page(page)
                if not urls:
                    # Check if this is a real 404 or just empty page
                    response = self.session.get(f"{self.INVENTORY_URL}?page={page}", timeout=self.TIMEOUT)
                    if response.status_code == 404:
                        print(f"\n  Page {page} returned 404, stopping.")
                        break
                    print(f"  Page {page} has no vehicles, stopping.")
                    break
                self.urls.update(urls)
                page += 1
                time.sleep(self.REQUEST_DELAY)
        else:
            # Scrape all known pages
            for page in range(1, total_pages + 1):
                urls = self.extract_urls_from_page(page)
                self.urls.update(urls)

                if page < total_pages:
                    time.sleep(self.REQUEST_DELAY)

        # Convert to sorted list
        sorted_urls = sorted(self.urls)

        # Save to file
        data = {
            "urls": sorted_urls,
            "lastUpdated": datetime.now().isoformat(),
            "totalCount": len(sorted_urls)
        }

        self.URLS_FILE.write_text(json.dumps(data, indent=2))

        # Summary
        print("\n" + "=" * 60)
        print("URL SCRAPING COMPLETE")
        print("=" * 60)
        print(f"Total URLs found: {len(sorted_urls)}")
        print(f"Saved to: {self.URLS_FILE.absolute()}")
        print("=" * 60)


def main():
    scraper = GatewayClassicCarsURLScraper()

    try:
        scraper.scrape_all_urls()
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
        print("Partial results may be saved.")
        exit(0)


if __name__ == "__main__":
    main()
