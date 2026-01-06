#!/usr/bin/env python3
"""
OnAllCylinders Article URL Scraper
Scrapes all article URLs from the Rods, Rides & Rigs category.
Handles pagination to discover all articles.
"""

import json
import re
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Set

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"Error: Missing dependency. Run: pip install requests beautifulsoup4")
    print(f"Details: {e}")
    sys.exit(1)


class OnAllCylindersURLScraper:
    BASE_URL = "https://www.onallcylinders.com/category/rods-rides-rigs/"
    OUTPUT_DIR = Path("scraped_builds/onallcylinders")
    URLS_FILE = OUTPUT_DIR / "urls.json"
    REQUEST_DELAY = 1.5  # Seconds between requests (be respectful)
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

    def get_page_url(self, page_num: int) -> str:
        """Get URL for a specific pagination page."""
        if page_num == 1:
            return self.BASE_URL
        return f"{self.BASE_URL}page/{page_num}/"

    def fetch_page(self, url: str) -> str:
        """Fetch HTML content from URL."""
        try:
            response = self.session.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"  Error fetching {url}: {e}")
            raise

    def extract_article_urls(self, html: str) -> List[str]:
        """Extract article URLs from page HTML."""
        urls = []
        soup = BeautifulSoup(html, 'html.parser')

        # Look for article links - OnAllCylinders uses various patterns
        # Common patterns:
        # - <a> tags with href starting with /YYYY/MM/
        # - Article titles in <h2> or <h3> with class containing "entry-title"
        # - Links within article containers

        # Pattern 1: Links with date-based URLs (most common for articles)
        for link in soup.find_all('a', href=re.compile(r'/\d{4}/\d{2}/')):
            href = link.get('href')
            if href and self._is_valid_article_url(href):
                # Ensure we have the full URL
                if href.startswith('/'):
                    href = 'https://www.onallcylinders.com' + href
                urls.append(href)

        # Pattern 2: Entry title links
        for link in soup.find_all('a', class_=re.compile(r'entry-title', re.I)):
            href = link.get('href')
            if href and self._is_valid_article_url(href):
                if href.startswith('/'):
                    href = 'https://www.onallcylinders.com' + href
                urls.append(href)

        # Pattern 3: Article/post type links
        for article in soup.find_all('article'):
            for link in article.find_all('a', href=True):
                href = link.get('href')
                if href and self._is_valid_article_url(href):
                    if href.startswith('/'):
                        href = 'https://www.onallcylinders.com' + href
                    urls.append(href)

        return list(set(urls))  # Remove duplicates

    def _is_valid_article_url(self, url: str) -> bool:
        """Check if URL is a valid article URL (not category, pagination, etc)."""
        # Skip pagination links
        if '/page/' in url:
            return False

        # Skip category/section links
        skip_patterns = [
            '/category/',
            '/author/',
            '/tag/',
            '/comments',
            '/feed/',
            'wp-login',
            'wp-content',
            '.pdf',
            'mailto:',
            'tel:',
            'javascript:',
        ]

        for pattern in skip_patterns:
            if pattern in url.lower():
                return False

        # Include date-based article URLs
        if re.search(r'/\d{4}/\d{2}/', url):
            return True

        return False

    def scrape_all_pages(self, max_pages: int = 45):
        """Scrape all paginated pages to discover article URLs."""
        print(f"\n{'='*60}")
        print("OnAllCylinders URL Scraper")
        print(f"{'='*60}")
        print(f"Base URL: {self.BASE_URL}")
        print(f"Max pages to scan: {max_pages}")
        print(f"Output file: {self.URLS_FILE.absolute()}")
        print(f"{'='*60}\n")

        # Ensure output directory exists
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        page_num = 1
        consecutive_empty_pages = 0
        max_consecutive_empty = 3  # Stop after 3 consecutive pages with no new URLs

        while page_num <= max_pages:
            url = self.get_page_url(page_num)
            print(f"[Page {page_num}/{max_pages}] Scraping: {url}")

            try:
                html = self.fetch_page(url)
                page_urls = self.extract_article_urls(html)

                # Track new URLs found on this page
                new_urls = [u for u in page_urls if u not in self.urls]
                for u in new_urls:
                    self.urls.add(u)

                print(f"  -> Found {len(page_urls)} URLs ({len(new_urls)} new)")
                print(f"  -> Total unique URLs so far: {len(self.urls)}")

                # Check for empty pages (end of pagination)
                if len(new_urls) == 0:
                    consecutive_empty_pages += 1
                    print(f"  -> No new URLs (empty page #{consecutive_empty_pages})")
                    if consecutive_empty_pages >= max_consecutive_empty:
                        print(f"\n  Reached end of pagination ({consecutive_empty_pages} consecutive empty pages)")
                        break
                else:
                    consecutive_empty_pages = 0

                # Rate limiting
                time.sleep(self.REQUEST_DELAY)

            except Exception as e:
                print(f"  -> FAILED: {e}")
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= max_consecutive_empty:
                    print(f"\n  Too many errors, stopping")
                    break

            page_num += 1

        # Save results
        self._save_urls()

    def _save_urls(self):
        """Save discovered URLs to JSON file."""
        sorted_urls = sorted(list(self.urls))

        data = {
            "urls": sorted_urls,
            "lastUpdated": datetime.now().isoformat(),
            "totalCount": len(sorted_urls)
        }

        self.URLS_FILE.write_text(json.dumps(data, indent=2))

        print(f"\n{'='*60}")
        print("SCRAPING COMPLETE")
        print(f"{'='*60}")
        print(f"Total URLs discovered: {len(sorted_urls)}")
        print(f"Saved to: {self.URLS_FILE.absolute()}")
        print(f"{'='*60}")

        # Show sample URLs
        if sorted_urls:
            print(f"\nSample URLs:")
            for url in sorted_urls[:5]:
                print(f"  - {url}")
            if len(sorted_urls) > 5:
                print(f"  ... and {len(sorted_urls) - 5} more")


def main():
    scraper = OnAllCylindersURLScraper()

    try:
        scraper.scrape_all_pages(max_pages=45)
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
        if scraper.urls:
            print(f"Saving {len(scraper.urls)} URLs discovered so far...")
            scraper._save_urls()
        sys.exit(0)


if __name__ == "__main__":
    main()
