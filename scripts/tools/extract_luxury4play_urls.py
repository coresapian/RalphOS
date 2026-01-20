#!/usr/bin/env python3
"""
Luxury4Play URL Extractor
Discovers and extracts vehicle/build URLs from luxury4play.com
Uses only standard library + requests (no BeautifulSoup needed)
"""
import re
import json
import time
import html
from urllib.parse import urljoin, urlparse
import sys

try:
    import requests
except ImportError:
    print("Missing dependency: requests")
    print("Install with: pip install requests")
    sys.exit(1)

BASE_URL = "https://luxury4play.com"
OUTPUT_DIR = "data/luxury4play"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_page(url):
    """Fetch a page with proper headers and error handling"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 403:
            print(f"  [ACCESS DENIED] {url}")
            return None
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response
    except Exception as e:
        return None

def extract_urls_from_html(html_content, base_url, pattern):
    """Extract URLs matching a pattern from HTML using regex"""
    urls = []
    # Match href attributes with our pattern
    for match in re.finditer(r'href=["\']([^"\']*' + pattern + r'[^"\']*)["\']', html_content):
        url = match.group(1)
        # Skip fragments and javascript
        if url.startswith('#') or url.startswith('javascript:'):
            continue
        full_url = urljoin(base_url, url)
        urls.append(full_url)
    return urls

def extract_showcase_urls(showcase_url):
    """Extract showcase item URLs"""
    print(f"[*] Checking: {showcase_url}")
    response = fetch_page(showcase_url)
    if not response:
        return []

    html_content = response.text
    items = []

    # Find all showcase links: /showcase/{slug}.{id}/
    showcase_urls = extract_urls_from_html(
        html_content,
        BASE_URL,
        r'/showcase/[^/]+\.\d+/?'
    )

    for url in showcase_urls:
        match = re.search(r'/showcase/[^.]+\.(\d+)/', url)
        if match:
            item_id = match.group(1)
            # Extract slug and create filename
            slug_part = url.split('/showcase/')[-1].replace(f'.{item_id}', '').replace('/', '')
            slug = slug_part.replace('-', '_') if slug_part else f"showcase-{item_id}"
            filename = f"{slug}.html"

            items.append({
                "url": url.split('?')[0],  # Remove query params
                "filename": filename,
                "item_id": item_id
            })

    print(f"  Found {len(items)} showcase items")
    return items

def extract_garage_urls(garage_url):
    """Extract garage vehicle URLs"""
    print(f"[*] Checking: {garage_url}")
    response = fetch_page(garage_url)
    if not response:
        return []

    html_content = response.text
    items = []

    # Look for garage vehicle profile links
    # These might be /garage/{slug}.{id}/ format
    garage_urls = extract_urls_from_html(
        html_content,
        BASE_URL,
        r'/garage/[^/]+\.\d+/?'
    )

    for url in garage_urls:
        # Skip pagination links
        if '/page-' in url:
            continue
        match = re.search(r'/garage/[^.]+\.(\d+)/', url)
        if match:
            vehicle_id = match.group(1)
            slug_part = url.split('/garage/')[-1].replace(f'.{vehicle_id}', '').replace('/', '')
            slug = slug_part.replace('-', '_') if slug_part else f"garage-{vehicle_id}"
            filename = f"{slug}.html"

            items.append({
                "url": url.split('?')[0],
                "filename": filename,
                "vehicle_id": vehicle_id
            })

    print(f"  Found {len(items)} garage vehicles")
    return items

def main():
    print("="*60)
    print("Luxury4Play URL Discovery")
    print("="*60)

    all_urls = []
    seen = set()

    # Step 1: Extract from Showcase (with pagination)
    print("\n" + "="*60)
    print("STEP 1: Checking Showcase section")
    print("="*60)

    for page in range(1, 51):  # Check up to 50 pages
        if page == 1:
            page_url = f"{BASE_URL}/showcase/"
        else:
            page_url = f"{BASE_URL}/showcase/?page={page}"

        items = extract_showcase_urls(page_url)
        if not items:
            if page > 1:  # Only break if not first page
                print(f"  No more items found after page {page-1}")
                break
            continue

        # Deduplicate and add
        for item in items:
            if item['url'] not in seen:
                seen.add(item['url'])
                all_urls.append(item)

        time.sleep(0.5)  # Be respectful

    print(f"\n  Total unique showcase items: {len([u for u in all_urls if 'item_id' in u])}")

    # Step 2: Extract from Garage (with pagination)
    print("\n" + "="*60)
    print("STEP 2: Checking Garage section")
    print("="*60)

    initial_count = len(all_urls)
    for page in range(1, 51):
        page_url = f"{BASE_URL}/garage/page-{page}/"
        items = extract_garage_urls(page_url)
        if not items:
            if page > 1:
                print(f"  No more vehicles found after page {page-1}")
                break
            continue

        for item in items:
            if item['url'] not in seen:
                seen.add(item['url'])
                all_urls.append(item)

        time.sleep(0.5)

    garage_count = len(all_urls) - initial_count
    print(f"\n  Total unique garage vehicles: {garage_count}")

    # Step 3: Save results
    print("\n" + "="*60)
    print("STEP 3: Saving discovered URLs")
    print("="*60)

    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_file = os.path.join(OUTPUT_DIR, "urls.jsonl")
    with open(output_file, 'w') as f:
        for item in all_urls:
            f.write(json.dumps(item) + '\n')

    # Save metadata
    metadata = {
        "totalCount": len(all_urls),
        "lastUpdated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "luxury4play",
        "breakdown": {
            "showcase": len([u for u in all_urls if 'item_id' in u]),
            "garage": len([u for u in all_urls if 'vehicle_id' in u])
        }
    }

    meta_file = os.path.join(OUTPUT_DIR, "urls_meta.json")
    with open(meta_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  Total URLs discovered: {metadata['totalCount']}")
    print(f"  - Showcase items: {metadata['breakdown']['showcase']}")
    print(f"  - Garage vehicles: {metadata['breakdown']['garage']}")
    print(f"  Output file: {output_file}")
    print(f"  Metadata: {meta_file}")
    print(f"{'='*60}\n")

    # Log to progress file
    progress_file = "scripts/ralph/progress.txt"
    with open(progress_file, 'a') as f:
        f.write(f"\n## {time.strftime('%Y-%m-%d %H:%M:%S')} - luxury4play URL Discovery\n")
        f.write(f"- Total URLs discovered: {metadata['totalCount']}\n")
        f.write(f"  - Showcase: {metadata['breakdown']['showcase']}\n")
        f.write(f"  - Garage: {metadata['breakdown']['garage']}\n")
        if metadata['totalCount'] == 0:
            f.write("**STATUS**: Site appears to block access or requires authentication\n")
        f.write("---\n")

    if metadata['totalCount'] == 0:
        print("\n[WARNING] No URLs discovered!")
        print("This site likely requires authentication or has changed structure.")
        print("Consider marking this source as blocked.\n")

if __name__ == "__main__":
    main()
