#!/usr/bin/env python3
"""
Tacoma World URL Discovery Script
Scrapes media URLs from the publicly accessible media gallery index pages.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from urllib.parse import urljoin
from datetime import datetime

# Configuration
BASE_URL = "https://www.tacomaworld.com"
MEDIA_INDEX_URL = "https://www.tacomaworld.com/media/"
OUTPUT_FILE = "/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/tacoma_world/urls.json"

# Rate limiting
DELAY_BETWEEN_REQUESTS = 1.5

def get_page_count(soup):
    """Get total number of pages from pagination."""
    # Look for pagination text like "Page 1 of 52"
    page_text = soup.get_text()
    match = re.search(r'Page \d+ of (\d+)', page_text)
    if match:
        return int(match.group(1))

    # Alternative: look for last page link
    pagination = soup.find('div', class_='PageNav')
    if pagination:
        last_page = pagination.get('data-last', '')
        if last_page.isdigit():
            return int(last_page)

    return None

def extract_media_urls_from_page(soup):
    """Extract media URLs from a gallery index page."""
    urls = []

    # Look for media containers with class "mediaContainer media-ID"
    for container in soup.find_all('div', class_='mediaContainer'):
        # Extract media ID from class name
        classes = container.get('class', [])
        media_id = None
        for cls in classes:
            if cls.startswith('media-') and cls != 'mediaContainer':
                media_id = cls.replace('media-', '')
                break

        if not media_id:
            continue

        # Find the link within the container
        link = container.find('a', href=True)
        if not link:
            continue

        href = link['href']

        # Build full URL
        full_url = urljoin(BASE_URL, href)

        # Extract title from link text or nearby element
        title_elem = container.find(class_='mediaTitle')
        title = title_elem.get_text(strip=True) if title_elem else ''

        # Extract username if available
        username_elem = container.find(class_='username')
        if not username_elem:
            # Try finding in parent containers
            username_elem = container.find('a', class_='username')
        username = username_elem.get_text(strip=True) if username_elem else ''

        # Extract image URL if available
        img_elem = container.find('img')
        img_url = img_elem.get('src', '') if img_elem else ''

        urls.append({
            'url': full_url,
            'media_id': media_id,
            'title': title,
            'username': username,
            'image_url': img_url,
            'type': 'media'
        })

    return urls

def main():
    print(f"[{datetime.now().isoformat()}] Starting Tacoma World URL discovery...")

    # Session with headers
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    })

    all_urls = []
    seen_ids = set()

    try:
        # Fetch first page to determine total pages
        print(f"[{datetime.now().isoformat()}] Fetching page 1...")
        response = session.get(MEDIA_INDEX_URL)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        urls = extract_media_urls_from_page(soup)

        for url_data in urls:
            media_id = url_data['media_id']
            if media_id not in seen_ids:
                seen_ids.add(media_id)
                all_urls.append(url_data)

        print(f"[{datetime.now().isoformat()}] Page 1: Found {len(urls)} media items")

        # Get total page count
        total_pages = get_page_count(soup)
        if total_pages:
            print(f"[{datetime.now().isoformat()}] Total pages to scrape: {total_pages}")
        else:
            print(f"[{datetime.now().isoformat()}] Could not determine page count, scraping limited pages")
            total_pages = 10  # Fallback: scrape 10 pages

        # Scrape remaining pages
        for page in range(2, min(total_pages + 1, 100)):  # Cap at 100 pages for safety
            print(f"[{datetime.now().isoformat()}] Fetching page {page}/{total_pages}...")

            time.sleep(DELAY_BETWEEN_REQUESTS)

            page_url = f"{MEDIA_INDEX_URL}?page={page}"
            response = session.get(page_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            urls = extract_media_urls_from_page(soup)

            page_new = 0
            for url_data in urls:
                media_id = url_data['media_id']
                if media_id not in seen_ids:
                    seen_ids.add(media_id)
                    all_urls.append(url_data)
                    page_new += 1

            print(f"[{datetime.now().isoformat()}] Page {page}: Found {len(urls)} items ({page_new} new)")

            # Stop if we're not finding new items
            if page_new == 0 and page > 5:
                print(f"[{datetime.now().isoformat()}] No new items found, stopping early")
                break

    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Error during scraping: {e}")

    # Save results
    output_data = {
        "urls": [u['url'] for u in all_urls],
        "totalCount": len(all_urls),
        "lastUpdated": datetime.now().isoformat(),
        "mediaDetails": all_urls  # Keep metadata for later use
    }

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"[{datetime.now().isoformat()}] Complete!")
    print(f"[{datetime.now().isoformat()}] Total unique media URLs found: {len(all_urls)}")
    print(f"[{datetime.now().isoformat()}] Saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
