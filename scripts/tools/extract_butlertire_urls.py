#!/usr/bin/env python3
"""
Extract vehicle detail page URLs from Butler Tire gallery.
"""
import requests
import re
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

BASE_URL = "https://www.butlertire.com"
GALLERY_URL = f"{BASE_URL}/gallery/"

def get_gallery_page(page_num):
    """Fetch a gallery page and return BeautifulSoup object."""
    url = f"{GALLERY_URL}?page={page_num}" if page_num > 1 else GALLERY_URL
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Error fetching page {page_num}: {e}")
        return None

def extract_vehicle_urls(soup):
    """Extract vehicle detail page URLs from gallery page."""
    urls = []

    # Look for all links that might be vehicle detail pages
    for a in soup.find_all('a', href=True):
        href = a['href']

        # Skip navigation and filter links
        if any(skip in href for skip in ['?page=', '/gallery#', 'javascript:', 'mailto:', 'tel:']):
            continue

        # Look for links that contain gallery path patterns
        # Based on image URLs: /images/gallery/{Make}/{Model}/{Vehicle_Name}/
        # The detail pages might follow similar pattern
        if '/gallery/' in href and href not in ['/gallery/', '/gallery', 'https://www.butlertire.com/gallery/']:
            # Convert to absolute URL
            full_url = urljoin(BASE_URL, href)

            # Only add if it looks like a vehicle detail page (not a category/filter)
            # Vehicle detail pages typically have longer paths
            path = urlparse(full_url).path
            if path.count('/') >= 3:  # e.g., /gallery/make/model/vehicle-name
                urls.append(full_url)

    return list(set(urls))  # Deduplicate

def get_total_pages(soup):
    """Get total number of pages from pagination."""
    # Look for pagination links
    pagination = soup.find('div', class_='pagination')
    if pagination:
        # Find all page numbers
        page_links = pagination.find_all('a')
        pages = []
        for link in page_links:
            text = link.get_text(strip=True)
            if text.isdigit():
                pages.append(int(text))
        return max(pages) if pages else 1

    # Alternative: look for » or "last" link
    for a in soup.find_all('a', href=True):
        if '?page=' in a['href']:
            match = re.search(r'page=(\d+)', a['href'])
            if match:
                return int(match.group(1))

    return 160  # Fallback based on observation

def main():
    """Main extraction function."""
    print("Fetching first page to analyze structure...")
    soup = get_gallery_page(1)

    if not soup:
        print("Failed to fetch first page")
        return

    total_pages = get_total_pages(soup)
    print(f"Detected {total_pages} pages in gallery")

    # Test extraction on first page
    print("\nTesting URL extraction on page 1...")
    test_urls = extract_vehicle_urls(soup)
    print(f"Found {len(test_urls)} vehicle URLs on page 1")
    if test_urls:
        print("Sample URLs:")
        for url in test_urls[:5]:
            print(f"  {url}")

    # Now extract all URLs
    all_urls = []
    output_file = "data/butlertire/urls.jsonl"

    print(f"\nExtracting URLs from all {total_pages} pages...")
    for page in range(1, total_pages + 1):
        if page > 1:
            soup = get_gallery_page(page)
            if not soup:
                continue

        urls = extract_vehicle_urls(soup)
        all_urls.extend(urls)

        print(f"Page {page}/{total_pages}: {len(urls)} URLs (total: {len(all_urls)})")

        # Be respectful with delays
        if page < total_pages:
            time.sleep(0.5)

    # Deduplicate
    all_urls = list(set(all_urls))
    print(f"\nTotal unique URLs found: {len(all_urls)}")

    # Save to JSONL file
    with open(output_file, 'w') as f:
        for url in sorted(all_urls):
            # Generate filename from URL
            path = urlparse(url).path
            # Remove /gallery/ prefix and trailing slash, replace slashes with hyphens
            filename = path.replace('/gallery/', '').rstrip('/') + '.html'
            filename = filename.replace('/', '-')

            f.write(json.dumps({"url": url, "filename": filename}) + '\n')

    print(f"\nSaved {len(all_urls)} URLs to {output_file}")

    # Create metadata
    metadata = {
        "totalCount": len(all_urls),
        "lastUpdated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "butlertire",
        "totalPages": total_pages
    }

    with open("data/butlertire/urls_meta.json", 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"Metadata saved to data/butlertire/urls_meta.json")

if __name__ == "__main__":
    main()
