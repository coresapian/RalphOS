#!/usr/bin/env python3
"""
Total Cost Involved URL Discovery Script

Discovers all customer build URLs from TCI Engineering's showcase.
Single-page gallery with all builds visible inline - no pagination.

Usage:
    python scrape_urls.py
"""

import json
import re
import time
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


class TCIURLExtractor(HTMLParser):
    """Extract build detail page URLs from TCI showcase."""

    def __init__(self):
        super().__init__()
        self.urls = set()
        self.base_url = "https://totalcostinvolved.com"

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            attrs_dict = dict(attrs)
            href = attrs_dict.get('href', '')

            # Skip empty, anchors, and non-TCI links
            if not href or href.startswith('#') or href.startswith('mailto:'):
                return

            # Convert relative URLs to absolute
            if href.startswith('/'):
                href = urljoin(self.base_url, href)

            # Parse the URL
            parsed = urlparse(href)

            # Only include TCI domain links
            if parsed.netloc not in ['totalcostinvolved.com', 'www.totalcostinvolved.com']:
                return

            # Exclude navigation, admin, and non-build pages
            exclude_patterns = [
                '/wp-',
                '/feed/',
                '/xmlrpc',
                '/cart',
                '/checkout',
                '/my-account',
                '/shop',
                '/product',
                '/news',
                '/events',
                '/about',
                '/contact',
                '/installation',
                '/catalog',
                '/warranty',
                '/testimonial',
                '/customer-showcase/$',  # Main page itself
            ]

            for pattern in exclude_patterns:
                if pattern in href or (pattern.endswith('$') and href.rstrip('/') == pattern.rstrip('/')):
                    return

            # Include detail pages that are NOT the main showcase page
            if 'customer-showcase' in href and href != 'https://totalcostinvolved.com/customer-showcase/' and href != 'https://totalcostinvolved.com/customer-showcase':
                self.urls.add(href)


def scrape_all_pages():
    """Scrape all showcase pages and extract build URLs."""
    base_url = "https://totalcostinvolved.com/customer-showcase/"
    all_urls = set()

    # Single page - no pagination
    print(f"Fetching: {base_url}")

    try:
        from urllib.request import urlopen, Request
        from urllib.error import URLError, HTTPError

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        req = Request(base_url, headers=headers)

        with urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8')

        parser = TCIURLExtractor()
        parser.feed(html)

        page_urls = parser.urls
        all_urls.update(page_urls)

        print(f"  Found {len(page_urls)} build URLs")

        time.sleep(1.5)

    except (URLError, HTTPError) as e:
        print(f"ERROR fetching {base_url}: {e}")
        return []

    # Return sorted URLs
    return sorted(list(all_urls))


def main():
    """Main entry point."""
    print("=" * 60)
    print("TCI Engineering Showcase URL Discovery")
    print("=" * 60)

    # Scrape all URLs
    urls = scrape_all_pages()

    if not urls:
        print("\nNo URLs found. Exiting.")
        return

    # Save to urls.json
    output = {
        "urls": urls,
        "lastUpdated": datetime.now().isoformat(),
        "totalCount": len(urls)
    }

    output_file = "scraped_builds/total_cost_involved/urls.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Discovery Complete!")
    print(f"{'=' * 60}")
    print(f"Total URLs found: {len(urls)}")
    print(f"Saved to: {output_file}")
    print(f"\nFirst 5 URLs:")
    for url in urls[:5]:
        print(f"  - {url}")


if __name__ == "__main__":
    main()
