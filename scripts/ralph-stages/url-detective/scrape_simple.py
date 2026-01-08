#!/usr/bin/env python3
"""
Simple URL scraper using only standard library.
"""

import urllib.request
import urllib.error
import re
import json
from html.parser import HTMLParser

class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href':
                    self.links.append(value)

def main():
    base_url = "https://totalcostinvolved.com/customer-showcase/"
    output_file = "../../../data/total_cost_involved/urls.jsonl"

    print(f"Fetching {base_url}...")

    try:
        # Fetch the page
        req = urllib.request.Request(
            base_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8')

        print(f"Fetched {len(html)} bytes")

        # Extract links
        parser = LinkExtractor()
        parser.feed(html)

        # Filter URLs
        vehicle_urls = set()
        skip_patterns = [
            r'/shop/', r'/product/', r'/cart/', r'/checkout/', r'/my-account/',
            r'/customer-showcase/?$', r'/news/', r'/blog/', r'/contact/', r'/about/',
            r'facebook\.com', r'twitter\.com', r'instagram\.com', r'youtube\.com',
            r'^#', r'mailto:', r'tel:',
        ]

        for link in parser.links:
            # Skip patterns
            skip = False
            for pattern in skip_patterns:
                if re.search(pattern, link, re.IGNORECASE):
                    skip = True
                    break
            if skip:
                continue

            # Convert relative URLs to absolute
            if link.startswith('/'):
                link = 'https://totalcostinvolved.com' + link
            elif not link.startswith('http'):
                continue

            # Only keep totalcostinvolved.com URLs
            if 'totalcostinvolved.com' not in link:
                continue

            # Skip the main showcase page
            if link.rstrip('/') == base_url.rstrip('/'):
                continue

            vehicle_urls.add(link)

        # Convert to sorted list
        urls = sorted(list(vehicle_urls))

        print(f"\nFound {len(urls)} unique vehicle URLs")

        if urls:
            # Save to JSONL file
            with open(output_file, 'w') as f:
                for url in urls:
                    # Extract slug from URL for filename
                    slug = url.replace('https://totalcostinvolved.com/', '').rstrip('/')
                    slug = re.sub(r'[^a-zA-Z0-9\-]', '-', slug).strip('-')
                    slug = re.sub(r'-+', '-', slug)
                    if not slug:
                        slug = 'vehicle'
                    filename = f"{slug}.html"

                    f.write(json.dumps({"url": url, "filename": filename}) + '\n')

            print(f"Saved to {output_file}")

            # Print first 10 URLs for verification
            print("\nFirst 10 URLs:")
            for i, url in enumerate(urls[:10], 1):
                print(f"  {i}. {url}")

            if len(urls) > 10:
                print(f"\n... and {len(urls) - 10} more")
        else:
            print("\nNo vehicle URLs found.")
            print("\nAll internal links found (sample):")
            all_links = [link for link in parser.links if 'totalcostinvolved.com' in link]
            unique = sorted(set(all_links))[:20]
            for link in unique:
                print(f"  {link}")

    except urllib.error.URLError as e:
        print(f"Error fetching URL: {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
