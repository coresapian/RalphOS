#!/usr/bin/env python3
"""
Creative Bespoke URL Discovery Script

Discovers all vehicle inventory URLs from Creative Bespoke dealership.
AutoRevo platform with pagination - vehicle inventory for sale.

Usage:
    python scrape_urls.py
"""

import json
import re
import time
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


class CreativeBespokeExtractor(HTMLParser):
    """Extract vehicle detail page URLs from Creative Bespoke inventory."""

    def __init__(self):
        super().__init__()
        self.urls = set()
        self.base_url = "https://creativebespoke.com"

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            attrs_dict = dict(attrs)
            href = attrs_dict.get('href', '')

            # Skip empty, anchors, and non-HTTPS links
            if not href or href.startswith('#') or href.startswith('mailto:'):
                return

            # Convert relative URLs to absolute
            if href.startswith('/'):
                href = urljoin(self.base_url, href)

            # Parse the URL
            parsed = urlparse(href)

            # Only include Creative Bespoke domain
            if parsed.netloc not in ['creativebespoke.com', 'www.creativebespoke.com']:
                return

            # Exclude navigation, admin, and non-vehicle pages
            exclude_patterns = [
                '/assets/',
                '/login',
                '/finance',
                '/contact',
                '/about',
                '/staff',
                '/map',
                '/privacy',
                '/sitemap',
                '/vehicle-finder',
            ]

            for pattern in exclude_patterns:
                if pattern in href:
                    return

            # Include vehicle detail pages
            # Creative Bespoke vehicle URLs follow patterns like /vehicles/2021-bentley-etc
            if href and href.startswith('http'):
                # Check if it's a vehicle page (contains /vehicles/ but not the main listing)
                if '/vehicles/' in href and href != 'https://creativebespoke.com/vehicles' and href != 'https://creativebespoke.com/vehicles/':
                    # Exclude pagination URLs
                    if 'page=' not in href and 'sort=' not in href:
                        self.urls.add(href)


def scrape_page(page_num=None):
    """Scrape a single inventory page."""
    if page_num is None or page_num == 1:
        url = "https://creativebespoke.com/vehicles"
    else:
        url = f"https://creativebespoke.com/vehicles?page={page_num}"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        req = Request(url, headers=headers)

        with urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8')

        parser = CreativeBespokeExtractor()
        parser.feed(html)

        return parser.urls

    except (URLError, HTTPError) as e:
        print(f"  ERROR fetching page: {e}")
        return set()


def scrape_all_pages():
    """Scrape all inventory pages."""
    all_urls = set()

    # Try pages 1-10 (stop when we get no new URLs)
    print("Scanning for pages...")

    for page_num in [None, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
        page_label = "1" if page_num is None else str(page_num)
        print(f"Fetching page {page_label}...", end=' ')

        page_urls = scrape_page(page_num)

        if not page_urls:
            print(f"No URLs found - stopping")
            break

        new_urls = page_urls - all_urls
        all_urls.update(page_urls)

        print(f"Found {len(new_urls)} new URLs (total: {len(all_urls)})")

        # If no new URLs on this page, we've reached the end
        if len(new_urls) == 0:
            print(f"No new URLs - stopping")
            break

        # Rate limiting
        time.sleep(1.5)

    return sorted(list(all_urls))


def main():
    """Main entry point."""
    print("=" * 60)
    print("Creative Bespoke Vehicle URL Discovery")
    print("=" * 60)

    # Scrape all URLs
    urls = scrape_all_pages()

    if not urls:
        print("\nNo URLs found. Exiting.")
        return

    # Remove duplicates and sort
    unique_urls = sorted(list(set(urls)))

    # Save to urls.json
    output = {
        "urls": unique_urls,
        "lastUpdated": datetime.now().isoformat(),
        "totalCount": len(unique_urls)
    }

    output_file = "scraped_builds/creative_bespoke/urls.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Discovery Complete!")
    print(f"{'=' * 60}")
    print(f"Total URLs found: {len(unique_urls)}")
    print(f"Saved to: {output_file}")
    print(f"\nFirst 5 URLs:")
    for url in unique_urls[:5]:
        print(f"  - {url}")


if __name__ == "__main__":
    main()
