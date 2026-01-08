#!/usr/bin/env python3
"""
Extract testimonial/vehicle URLs from Total Cost Involved customer showcase.
"""

import urllib.request
import re
import json
from html.parser import HTMLParser

class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current_link = None

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href':
                    self.current_link = value
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

        # Extract all testimonial URLs using regex
        # Pattern: https://totalcostinvolved.com/testimonials/some-vehicle-name/
        pattern = r'https://totalcostinvolved\.com/testimonials/[^"\s]+/'

        testimonial_urls = set(re.findall(pattern, html))

        # Also try to find in href="..." format
        href_pattern = r'href="(https://totalcostinvolved\.com/testimonials/[^"]+)"'
        testimonial_urls.update(re.findall(href_pattern, html))

        # Also try for URLs that end without trailing slash
        pattern_no_slash = r'https://totalcostinvolved\.com/testimonials/[^"\s<]+'
        for match in re.finditer(pattern_no_slash, html):
            url = match.group(0)
            # Filter out URLs with quotes or other trailing chars
            if '"' not in url and '<' not in url:
                testimonial_urls.add(url)

        # Clean URLs (remove trailing quotes, spaces, etc.)
        cleaned_urls = set()
        for url in testimonial_urls:
            url = url.rstrip('"').rstrip("'").rstrip('>').strip()
            if url.startswith('https://totalcostinvolved.com/testimonials/'):
                # Ensure consistent format
                if not url.endswith('/'):
                    url += '/'
                cleaned_urls.add(url)

        # Convert to sorted list
        urls = sorted(list(cleaned_urls))

        print(f"\nFound {len(urls)} unique testimonial/vehicle URLs")

        if urls:
            # Save to JSONL file
            with open(output_file, 'w') as f:
                for url in urls:
                    # Extract slug from URL for filename
                    slug = url.replace('https://totalcostinvolved.com/testimonials/', '').rstrip('/')
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

            print(f"\nTotal: {len(urls)} vehicle pages to scrape")
        else:
            print("\nNo testimonial URLs found!")

    except urllib.error.URLError as e:
        print(f"Error fetching URL: {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
