#!/usr/bin/env python3
"""
ECD Auto Design URL Discovery Script

Discovers all custom build URLs from ECD's showcase.
Uses numeric pagination (17 pages total, ~31 builds per page).

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


class ECDURLExtractor(HTMLParser):
    """Extract build detail page URLs from ECD showcase pages."""

    def __init__(self):
        super().__init__()
        self.urls = set()
        self.base_url = "https://ecdautodesign.com"
        self.in_showcase_item = False
        self.current_href = None

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            attrs_dict = dict(attrs)
            href = attrs_dict.get('href', '')
            text_content = attrs_dict.get('title', '')

            # Skip empty, anchors, and non-HTTPS links
            if not href or href.startswith('#') or href.startswith('mailto:'):
                return

            # Convert relative URLs to absolute
            if href.startswith('/'):
                href = urljoin(self.base_url, href)

            # Parse the URL
            parsed = urlparse(href)

            # Only include ECD domain
            if parsed.netloc not in ['ecdautodesign.com', 'www.ecdautodesign.com']:
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
                '/news',
                '/events',
                '/about',
                '/contact',
                '/locations',
                '/employment',
                '/investor',
                '/broker',
                '/faq',
                '/ecd-showcase/$',  # Main showcase page
                '/models/',
                '/create-your-build',
                '/design-process',
                '/build-process',
                '/defender-restoration',
                '/ecd-brochures',
                '/restore-your-vehicle',
                '/finance-options',
                '/trade-your-vehicle',
            ]

            for pattern in exclude_patterns:
                if pattern in href or (pattern.endswith('$') and href.rstrip('/') == pattern.rstrip('/')):
                    return

            # Include project detail pages
            # ECD project URLs typically don't have a clear pattern in the URL structure
            # so we include URLs that look like build pages (not category pages)
            if href and href.startswith('http'):
                # Exclude known non-project pages
                if not any(x in href for x in ['page/', '/ecd-showcase', '/models', '/build']):
                    self.urls.add(href)


def scrape_page(page_num):
    """Scrape a single showcase page."""
    if page_num == 1:
        url = "https://ecdautodesign.com/ecd-showcase/"
    else:
        url = f"https://ecdautodesign.com/ecd-showcase/page/{page_num}/"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        req = Request(url, headers=headers)

        with urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8')

        parser = ECDURLExtractor()
        parser.feed(html)

        return parser.urls

    except (URLError, HTTPError) as e:
        print(f"  ERROR fetching page {page_num}: {e}")
        return set()


def scrape_all_pages():
    """Scrape all showcase pages."""
    all_urls = set()

    # Try pages 1-20 (stop when we get a 404)
    print("Scanning for pages...")

    for page_num in range(1, 21):
        print(f"Fetching page {page_num}...", end=' ')

        page_urls = scrape_page(page_num)

        if not page_urls:
            # No URLs found - likely reached the end
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
    print("ECD Auto Design Showcase URL Discovery")
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

    output_file = "scraped_builds/ecd_auto_design/urls.json"
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
