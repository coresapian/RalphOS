#!/usr/bin/env python3
"""
WordPress Gallery URL Discovery Template

For WordPress sites using standard gallery/portfolio plugins.
Handles REST API, pagination, and custom post types.

Usage:
 1. Edit the Configuration section below
 2. Run: python discover_urls.py
"""

import json
import re
import requests
import time
from datetime import datetime
from pathlib import Path
from typing import List, Set
from urllib.parse import urljoin, urlparse

# 
# Configuration - EDIT THESE VALUES
# 

BASE_URL = "https://example.com" # Site base URL
GALLERY_PATH = "/gallery/" # Gallery page path
POST_TYPE = "post" # WordPress post type: post, page, portfolio, project, etc.
OUTPUT_FILE = "urls.json" # Output file name

# Optional: If site uses REST API
USE_REST_API = False
REST_ENDPOINT = "/wp-json/wp/v2/posts" # Change post type as needed
PER_PAGE = 100

# Request settings
DELAY_BETWEEN_REQUESTS = 1.0 # seconds
MAX_PAGES = 100 # Safety limit

HEADERS = {
 "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
 "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# 
# Discovery Logic
# 

def discover_via_rest_api(base_url: str, endpoint: str, per_page: int = 100) -> List[str]:
 """Discover URLs via WordPress REST API."""
 urls = []
 page = 1
 
 while page <= MAX_PAGES:
 api_url = f"{base_url}{endpoint}?per_page={per_page}&page={page}"
 print(f"Fetching API page {page}: {api_url}")
 
 try:
 response = requests.get(api_url, headers=HEADERS, timeout=30)
 
 if response.status_code == 400:
 # No more pages
 break
 
 response.raise_for_status()
 posts = response.json()
 
 if not posts:
 break
 
 for post in posts:
 url = post.get("link") or post.get("url")
 if url:
 urls.append(url)
 
 print(f" Found {len(posts)} posts (total: {len(urls)})")
 
 # Check for more pages
 total_pages = int(response.headers.get("X-WP-TotalPages", 1))
 if page >= total_pages:
 break
 
 page += 1
 time.sleep(DELAY_BETWEEN_REQUESTS)
 
 except requests.exceptions.RequestException as e:
 print(f"Error fetching API: {e}")
 break
 
 return urls


def discover_via_html(base_url: str, gallery_path: str) -> List[str]:
 """Discover URLs by scraping HTML pages."""
 urls: Set[str] = set()
 visited: Set[str] = set()
 
 gallery_url = urljoin(base_url, gallery_path)
 to_visit = [gallery_url]
 
 # Common patterns for gallery item links
 link_patterns = [
 r'href="([^"]*(?:/gallery/|/portfolio/|/project/|/build/|/vehicle/)[^"]*)"',
 r'href="([^"]*(?:\.com/[a-z0-9-]+/[a-z0-9-]+/?)[^"]*)"',
 ]
 
 # Pagination patterns
 page_patterns = [
 r'href="([^"]*[?&]page=\d+[^"]*)"',
 r'href="([^"]*/page/\d+/?[^"]*)"',
 r'class="[^"]*next[^"]*"[^>]*href="([^"]*)"',
 ]
 
 page_count = 0
 
 while to_visit and page_count < MAX_PAGES:
 current_url = to_visit.pop(0)
 
 if current_url in visited:
 continue
 
 visited.add(current_url)
 page_count += 1
 
 print(f"[{page_count}] Fetching: {current_url}")
 
 try:
 response = requests.get(current_url, headers=HEADERS, timeout=30)
 response.raise_for_status()
 html = response.text
 
 # Extract item URLs
 for pattern in link_patterns:
 matches = re.findall(pattern, html, re.IGNORECASE)
 for match in matches:
 full_url = urljoin(base_url, match)
 parsed = urlparse(full_url)
 
 # Filter to same domain
 if parsed.netloc == urlparse(base_url).netloc:
 # Skip common non-content paths
 skip_paths = ['/wp-', '/tag/', '/category/', '/author/', '/feed/', 
 '/comments/', '/trackback/', '.jpg', '.png', '.gif']
 if not any(skip in full_url.lower() for skip in skip_paths):
 urls.add(full_url)
 
 # Find pagination links
 for pattern in page_patterns:
 matches = re.findall(pattern, html, re.IGNORECASE)
 for match in matches:
 page_url = urljoin(base_url, match)
 if page_url not in visited and page_url not in to_visit:
 # Only follow pagination on same path
 if gallery_path in page_url or '/page/' in page_url:
 to_visit.append(page_url)
 
 print(f" Found {len(urls)} unique URLs so far")
 time.sleep(DELAY_BETWEEN_REQUESTS)
 
 except requests.exceptions.RequestException as e:
 print(f"Error fetching {current_url}: {e}")
 continue
 
 return sorted(list(urls))


def save_urls(urls: List[str], output_file: str):
 """Save URLs to JSON file."""
 output_path = Path(output_file)
 
 data = {
 "urls": urls,
 "lastUpdated": datetime.now().isoformat(),
 "totalCount": len(urls)
 }
 
 with open(output_path, 'w') as f:
 json.dump(data, f, indent=2)
 
 print(f"\n Saved {len(urls)} URLs to {output_file}")


def main():
 print(f"WordPress Gallery URL Discovery")
 print(f"Base URL: {BASE_URL}")
 print(f"Method: {'REST API' if USE_REST_API else 'HTML Scraping'}")
 print("-" * 60)
 
 if USE_REST_API:
 urls = discover_via_rest_api(BASE_URL, REST_ENDPOINT, PER_PAGE)
 else:
 urls = discover_via_html(BASE_URL, GALLERY_PATH)
 
 if urls:
 save_urls(urls, OUTPUT_FILE)
 else:
 print("No URLs found!")
 return 1
 
 return 0


if __name__ == "__main__":
 exit(main())

