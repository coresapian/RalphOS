#!/usr/bin/env python3
"""
Auction Site URL Discovery Template

For auction/marketplace sites like Bring a Trailer, Hemmings, Cars & Bids.
Handles auction-specific features like sold listings, bid data, lot numbers.

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
from typing import List, Set, Dict, Optional
from urllib.parse import urljoin, urlparse

# 
# Configuration - EDIT THESE VALUES
# 

BASE_URL = "https://example.com" # Site base URL
LISTINGS_PATH = "/listings/" # Active listings page
SOLD_PATH = "/sold/" # Sold/completed listings (optional)
OUTPUT_FILE = "urls.json" # Output file name

# Include sold listings?
INCLUDE_SOLD = True

# Pagination
PAGINATION_STYLE = "query" # "query" or "path"
PAGE_PARAM = "page"
START_PAGE = 1
MAX_PAGES = 100

# URL patterns for auction listings
LISTING_URL_PATTERNS = [
 r'href="([^"]*(?:/listing/|/lot/|/auction/|/vehicle/)\d+[^"]*)"',
 r'href="([^"]*(?:/sold/|/completed/)\d+[^"]*)"',
]

# Pattern to extract auction metadata (optional, for enriched output)
EXTRACT_METADATA = False
METADATA_PATTERNS = {
 "lot_number": r'data-lot="(\d+)"',
 "price": r'data-price="([^"]*)"',
 "status": r'data-status="([^"]*)"',
}

# Request settings
DELAY_BETWEEN_REQUESTS = 1.5 # seconds (be respectful to auction sites)
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
 if page == START_PAGE:
 return urljoin(base_url, path)
 return urljoin(base_url, f"{path.rstrip('/')}/page/{page}/")
 else:
 full_url = urljoin(base_url, path)
 if page == START_PAGE:
 return full_url
 separator = "&" if "?" in full_url else "?"
 return f"{full_url}{separator}{PAGE_PARAM}={page}"


def has_next_page(html: str) -> bool:
 """Check if there's a next page."""
 patterns = [
 r'class="[^"]*next[^"]*"[^>]*href',
 r'rel="next"',
 r'aria-label="[Nn]ext"',
 r'>\s*Next\s*<',
 r'>\s*›\s*<',
 ]
 for pattern in patterns:
 if re.search(pattern, html, re.IGNORECASE):
 return True
 return False


def extract_listing_urls(html: str, base_url: str) -> Set[str]:
 """Extract listing URLs from HTML."""
 urls = set()
 
 for pattern in LISTING_URL_PATTERNS:
 matches = re.findall(pattern, html, re.IGNORECASE)
 for match in matches:
 full_url = urljoin(base_url, match)
 parsed = urlparse(full_url)
 
 # Filter to same domain
 if parsed.netloc == urlparse(base_url).netloc:
 # Clean URL
 clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
 urls.add(clean_url)
 
 return urls


def extract_metadata(html: str, url: str) -> Dict:
 """Extract auction metadata from listing HTML."""
 metadata = {"url": url}
 
 for key, pattern in METADATA_PATTERNS.items():
 match = re.search(pattern, html)
 if match:
 metadata[key] = match.group(1)
 
 return metadata


def discover_listings(path: str, listing_type: str = "active") -> List[str]:
 """Discover listing URLs from a paginated section."""
 urls: Set[str] = set()
 page = START_PAGE
 consecutive_empty = 0
 
 print(f"\nDiscovering {listing_type} listings from {path}")
 print("-" * 40)
 
 while page <= MAX_PAGES:
 page_url = build_page_url(BASE_URL, path, page)
 print(f"[Page {page}] {page_url}")
 
 try:
 response = requests.get(page_url, headers=HEADERS, timeout=30)
 
 if response.status_code == 404:
 print(" → 404 Not Found, stopping")
 break
 
 response.raise_for_status()
 html = response.text
 
 # Extract URLs
 page_urls = extract_listing_urls(html, BASE_URL)
 new_urls = page_urls - urls
 urls.update(page_urls)
 
 print(f" Found {len(page_urls)} ({len(new_urls)} new, {len(urls)} total)")
 
 # Check for empty pages
 if not new_urls:
 consecutive_empty += 1
 if consecutive_empty >= 2:
 print(" → No new listings, stopping")
 break
 else:
 consecutive_empty = 0
 
 # Check for more pages
 if not has_next_page(html):
 print(" → Last page reached")
 break
 
 page += 1
 time.sleep(DELAY_BETWEEN_REQUESTS)
 
 except requests.exceptions.RequestException as e:
 print(f" Error: {e}")
 page += 1
 time.sleep(DELAY_BETWEEN_REQUESTS)
 
 return sorted(list(urls))


def save_urls(urls: List[str], output_file: str, metadata: Optional[Dict] = None):
 """Save URLs to JSON file."""
 output_path = Path(output_file)
 
 data = {
 "urls": urls,
 "lastUpdated": datetime.now().isoformat(),
 "totalCount": len(urls),
 "source": BASE_URL,
 }
 
 if metadata:
 data["metadata"] = metadata
 
 with open(output_path, 'w') as f:
 json.dump(data, f, indent=2)
 
 print(f"\n Saved {len(urls)} URLs to {output_file}")


def main():
 print(f"Auction Site URL Discovery")
 print(f"Base URL: {BASE_URL}")
 print(f"Include sold: {INCLUDE_SOLD}")
 print("=" * 60)
 
 all_urls = []
 
 # Get active listings
 active_urls = discover_listings(LISTINGS_PATH, "active")
 all_urls.extend(active_urls)
 
 # Get sold listings if enabled
 if INCLUDE_SOLD and SOLD_PATH:
 sold_urls = discover_listings(SOLD_PATH, "sold")
 # Add only URLs not already in active
 new_sold = [u for u in sold_urls if u not in all_urls]
 all_urls.extend(new_sold)
 print(f"\nAdded {len(new_sold)} sold listings")
 
 # Deduplicate and sort
 all_urls = sorted(list(set(all_urls)))
 
 if all_urls:
 metadata = {
 "active_count": len(active_urls),
 "sold_count": len(all_urls) - len(active_urls) if INCLUDE_SOLD else 0,
 }
 save_urls(all_urls, OUTPUT_FILE, metadata)
 else:
 print("\nNo URLs found!")
 return 1
 
 return 0


if __name__ == "__main__":
 exit(main())

