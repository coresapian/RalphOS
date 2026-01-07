#!/usr/bin/env python3
"""
Charlie's Custom Creations URL Discovery Script

Discovers all custom build URLs from the /builds/ gallery page.
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
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


class CharlieURLExtractor(HTMLParser):
    """Extract build detail page URLs from Charlie's gallery."""

    def __init__(self):
        super().__init__()
        self.urls = set()
        self.base_url = "https://charliescustomcreations.com"
        self.in_gallery = False

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

            # Only include Charlie's domain
            if parsed.netloc not in ['charliescustomcreations.com', 'www.charliescustomcreations.com']:
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
                '/blog',
                '/track-order',
                '/elements/',
                '/demos/',
                '/image-sitemap',
                '/video-sitemap',
            ]

            for pattern in exclude_patterns:
                if pattern in href:
                    return

            # Include build detail pages
            # Charlie's build URLs don't have a clear pattern - they appear to be individual pages
            # We'll include URLs that look like build pages (not category pages)
            if href and href.startswith('http'):
                # Check if it looks like a page (not a file or API endpoint)
                if not any(x in href for x in ['.', 'xml', 'json', 'wp-json']):
                    # Exclude known non-build pages
                    known_non_builds = [
                        'charliescustomcreations.com/',
                        'charliescustomcreations.com/machine-shop',
                        'charliescustomcreations.com/store',
                        'charliescustomcreations.com/contact',
                    ]
                    if not any(href.rstrip('/') == x.rstrip('/') for x in known_non_builds):
                        self.urls.add(href)


def scrape_gallery():
    """Scrape the builds gallery page."""
    url = "https://charliescustomcreations.com/builds/"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        req = Request(url, headers=headers)

        with urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8')

        parser = CharlieURLExtractor()
        parser.feed(html)

        return parser.urls

    except (URLError, HTTPError) as e:
        print(f"ERROR fetching gallery: {e}")
        return set()


def main():
    """Main entry point."""
    print("=" * 60)
    print("Charlie's Custom Creations URL Discovery")
    print("=" * 60)

    # Scrape the gallery
    print("Fetching /builds/ gallery page...")
    urls = scrape_gallery()

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

    output_file = "scraped_builds/charlies_custom_creations/urls.json"
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
