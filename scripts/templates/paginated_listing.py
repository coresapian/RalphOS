#!/usr/bin/env python3
"""
Paginated Listing URL Discovery Template

For sites with classic numbered pagination (page 1, 2, 3...).
Handles both query string (?page=N) and path-based (/page/N/) pagination.

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
from typing import List, Set, Optional
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

# 
# Configuration - EDIT THESE VALUES
# 

BASE_URL = "https://example.com" # Site base URL
LISTING_PATH = "/inventory/" # Listing page path
OUTPUT_FILE = "urls.json" # Output file name

# Pagination style: "query" (?page=N) or "path" (/page/N/)
PAGINATION_STYLE = "query"
PAGE_PARAM = "page" # Query parameter name (for query style)
START_PAGE = 1 # First page number

# CSS/regex selectors for item links
# Add patterns that match your site's item URLs
ITEM_URL_PATTERNS = [
 r'href="([^"]*(?:/vehicle/|/listing/|/item/|/detail/)[^"]*)"',
 r'href="([^"]*(?:/inventory/\d+[^"]*)"',
]

# Pattern to detect if there are more pages
NEXT_PAGE_PATTERNS = [
 r'class="[^"]*next[^"]*"[^>]*href',
 r'rel="next"',
 r'aria-label="Next"',
]

# Request settings
DELAY_BETWEEN_REQUESTS = 1.0 # seconds
MAX_PAGES = 500 # Safety limit

HEADERS = {
 "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
 "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# 
# Discovery Logic
# 

def build_page_url(base_url: str, path: str, page: int) -> str:
 """Build URL for a specific page number."""
 if PAGINATION_STYLE == "path":
 # Path-based: /inventory/page/2/
 if page == START_PAGE:
 return urljoin(base_url, path)
 return urljoin(base_url, f"{path.rstrip('/')}/page/{page}/")
 else:
 # Query-based: /inventory/?page=2
 full_url = urljoin(base_url, path)
 if page == START_PAGE:
 return full_url
 separator = "&" if "?" in full_url else "?"
 return f"{full_url}{separator}{PAGE_PARAM}={page}"


def has_next_page(html: str) -> bool:
 """Check if there's a next page link."""
 for pattern in NEXT_PAGE_PATTERNS:
 if re.search(pattern, html, re.IGNORECASE):
 return True
 return False


def extract_item_urls(html: str, base_url: str) -> Set[str]:
 """Extract item URLs from HTML."""
 urls = set()
 
 for pattern in ITEM_URL_PATTERNS:
 matches = re.findall(pattern, html, re.IGNORECASE)
 for match in matches:
 full_url = urljoin(base_url, match)
 parsed = urlparse(full_url)
 
 # Filter to same domain
 if parsed.netloc == urlparse(base_url).netloc:
 # Clean URL (remove fragments, normalize)
 clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
 if parsed.query:
 # Keep only essential query params
 clean_url += f"?{parsed.query}"
 urls.add(clean_url)
 
 return urls


def discover_urls() -> List[str]:
 """Discover all item URLs from paginated listing."""
 all_urls: Set[str] = set()
 page = START_PAGE
 consecutive_empty = 0
 
 while page <= MAX_PAGES:
 page_url = build_page_url(BASE_URL, LISTING_PATH, page)
 print(f"[Page {page}] Fetching: {page_url}")
 
 try:
 response = requests.get(page_url, headers=HEADERS, timeout=30)
 
 if response.status_code == 404:
 print(" → 404 Not Found, stopping")
 break
 
 response.raise_for_status()
 html = response.text
 
 # Extract URLs from this page
 page_urls = extract_item_urls(html, BASE_URL)
 new_urls = page_urls - all_urls
 all_urls.update(page_urls)
 
 print(f" Found {len(page_urls)} URLs ({len(new_urls)} new, {len(all_urls)} total)")
 
 # Check for more pages
 if not page_urls:
 consecutive_empty += 1
 if consecutive_empty >= 2:
 print(" → No URLs found on consecutive pages, stopping")
 break
 else:
 consecutive_empty = 0
 
 if not has_next_page(html):
 print(" → No next page link found, stopping")
 break
 
 page += 1
 time.sleep(DELAY_BETWEEN_REQUESTS)
 
 except requests.exceptions.RequestException as e:
 print(f" Error: {e}")
 # Continue to next page on error
 page += 1
 time.sleep(DELAY_BETWEEN_REQUESTS)
 continue
 
 return sorted(list(all_urls))


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
 print(f"Paginated Listing URL Discovery")
 print(f"Base URL: {BASE_URL}{LISTING_PATH}")
 print(f"Pagination: {PAGINATION_STYLE} (param: {PAGE_PARAM})")
 print("-" * 60)
 
 urls = discover_urls()
 
 if urls:
 save_urls(urls, OUTPUT_FILE)
 else:
 print("No URLs found!")
 return 1
 
 return 0


if __name__ == "__main__":
 exit(main())

