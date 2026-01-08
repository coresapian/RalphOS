#!/usr/bin/env python3
"""
Scrape all vehicle URLs from Total Cost Involved customer showcase.
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin, urlparse

def extract_slug(url):
    """Extract slug from URL for filename."""
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    # Get last segment of path
    slug = path.split('/')[-1] if path.split('/')[-1] else 'vehicle'
    # Clean slug
    slug = re.sub(r'[^\w\-]', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    if not slug:
        slug = 'vehicle'
    return f"{slug}.html"

def main():
    base_url = "https://totalcostinvolved.com/customer-showcase/"
    output_file = "../data/total_cost_involved/urls.jsonl"

    # Headers to avoid blocking
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    print(f"Fetching {base_url}...")
    response = requests.get(base_url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')

    # Find all links that go to individual vehicle pages
    # Look for <a> tags within the gallery/grid
    vehicle_urls = set()

    # Try different selectors to find vehicle page links
    # Method 1: Look for links in the main content area
    main_content = soup.find('div', class_='et_pb_module')
    if main_content:
        # Find all links within the gallery
        for link in main_content.find_all('a', href=True):
            href = link['href']
            # Filter for internal links that look like vehicle pages
            if (href.startswith('/') or href.startswith('https://totalcostinvolved.com/')) and \
               not href.startswith('/customer-showcase/') and \
               not href.startswith('#') and \
               '/shop/' not in href and \
               '/product/' not in href and \
               'facebook.com' not in href and \
               'twitter.com' not in href and \
               'instagram.com' not in href:

                # Convert relative URLs to absolute
                full_url = urljoin(base_url, href)

                # Only add if it's a totalcostinvolved.com URL
                if 'totalcostinvolved.com' in full_url:
                    vehicle_urls.add(full_url)

    # Also try looking for specific gallery item patterns
    # Many WordPress galleries use specific classes
    for link in soup.find_all('a', href=True):
        href = link['href']
        full_url = urljoin(base_url, href)

        # Check if it looks like a vehicle page (not category, shop, etc)
        if 'totalcostinvolved.com' in full_url:
            parsed = urlparse(full_url)
            path = parsed.path

            # Skip certain paths
            skip_paths = ['/shop/', '/product/', '/cart/', '/checkout/', '/my-account/',
                         '/customer-showcase/', '/news/', '/blog/', '/contact/', '/about/']

            if not any(skip in path for skip in skip_paths):
                # Check if the link contains vehicle-like keywords or is in a gallery context
                parent = link.find_parent(class_=re.compile(r'gallery|grid|item|testimonial|showcase', re.I))
                if parent:
                    vehicle_urls.add(full_url)

    # Remove the showcase page itself if present
    vehicle_urls.discard(base_url.rstrip('/'))
    vehicle_urls.discard('https://totalcostinvolved.com/customer-showcase')

    # Convert to sorted list
    urls = sorted(list(vehicle_urls))

    print(f"Found {len(urls)} unique vehicle URLs")

    if urls:
        # Save to JSONL file
        with open(output_file, 'w') as f:
            for url in urls:
                filename = extract_slug(url)
                f.write(json.dumps({"url": url, "filename": filename}) + '\n')

        print(f"Saved to {output_file}")

        # Print first 10 URLs for verification
        print("\nFirst 10 URLs:")
        for i, url in enumerate(urls[:10], 1):
            print(f"  {i}. {url}")

        if len(urls) > 10:
            print(f"\n... and {len(urls) - 10} more")
    else:
        print("No vehicle URLs found. The page may use JavaScript to load content.")
        print("\nAttempting to find links in all anchor tags...")
        all_links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href and 'totalcostinvolved.com' in href:
                all_links.append(href)

        # Show unique internal links for analysis
        unique_internal = sorted(set(all_links))
        print(f"\nFound {len(unique_internal)} internal links. Sample:")
        for link in unique_internal[:20]:
            print(f"  {link}")

if __name__ == '__main__':
    main()
