#!/usr/bin/env python3
"""
Infinite Scroll URL Discovery Template

For sites that load content via JavaScript/AJAX as user scrolls.
Uses browser automation (Playwright) to simulate scrolling.

Requirements:
    pip install playwright
    playwright install chromium

Usage:
    1. Edit the Configuration section below
    2. Run: python discover_urls.py
"""

import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Set

# ═══════════════════════════════════════════════════════════════
# Configuration - EDIT THESE VALUES
# ═══════════════════════════════════════════════════════════════

BASE_URL = "https://example.com"  # Site base URL
GALLERY_PATH = "/gallery/"  # Gallery page path
OUTPUT_FILE = "urls.json"  # Output file name

# Scroll settings
SCROLL_PAUSE = 2.0  # Seconds to wait after each scroll
MAX_SCROLLS = 100  # Maximum number of scrolls
SCROLL_DISTANCE = 1000  # Pixels to scroll each time

# CSS selectors for content items
# These should match the links you want to extract
ITEM_SELECTORS = [
    'a[href*="/gallery/"]',
    'a[href*="/project/"]',
    'a[href*="/build/"]',
    '.gallery-item a',
    '.project-card a',
]

# Optional: AJAX endpoint if you can intercept it directly
# Set to None to use browser scrolling
AJAX_ENDPOINT = None  # e.g., "/api/gallery?page={page}&limit=20"

# Browser settings
HEADLESS = True  # Set to False to see the browser

# ═══════════════════════════════════════════════════════════════
# Discovery Logic
# ═══════════════════════════════════════════════════════════════

async def discover_via_browser() -> List[str]:
    """Discover URLs by scrolling in a browser."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Error: playwright not installed")
        print("Run: pip install playwright && playwright install chromium")
        return []
    
    urls: Set[str] = set()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        full_url = f"{BASE_URL.rstrip('/')}{GALLERY_PATH}"
        print(f"Loading: {full_url}")
        
        await page.goto(full_url, wait_until="networkidle")
        await asyncio.sleep(2)  # Wait for initial content
        
        scroll_count = 0
        last_url_count = 0
        no_new_urls_count = 0
        
        while scroll_count < MAX_SCROLLS:
            scroll_count += 1
            
            # Extract URLs before scrolling
            for selector in ITEM_SELECTORS:
                try:
                    elements = await page.query_selector_all(selector)
                    for el in elements:
                        href = await el.get_attribute("href")
                        if href:
                            # Normalize URL
                            if href.startswith("/"):
                                href = f"{BASE_URL.rstrip('/')}{href}"
                            elif not href.startswith("http"):
                                continue
                            urls.add(href)
                except:
                    pass
            
            print(f"[Scroll {scroll_count}] Found {len(urls)} URLs")
            
            # Check if we're getting new URLs
            if len(urls) == last_url_count:
                no_new_urls_count += 1
                if no_new_urls_count >= 3:
                    print("No new URLs after 3 scrolls, stopping")
                    break
            else:
                no_new_urls_count = 0
                last_url_count = len(urls)
            
            # Scroll down
            await page.evaluate(f"window.scrollBy(0, {SCROLL_DISTANCE})")
            await asyncio.sleep(SCROLL_PAUSE)
            
            # Check if we've reached the bottom
            at_bottom = await page.evaluate("""
                () => {
                    return (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 100
                }
            """)
            
            if at_bottom:
                print("Reached bottom of page")
                # One more scroll in case content is still loading
                await asyncio.sleep(SCROLL_PAUSE * 2)
                if await page.evaluate("() => (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 100"):
                    break
        
        await browser.close()
    
    return sorted(list(urls))


def discover_via_ajax() -> List[str]:
    """Discover URLs by directly calling AJAX endpoint."""
    import requests
    
    urls: Set[str] = set()
    page = 1
    
    while page <= MAX_SCROLLS:
        endpoint = AJAX_ENDPOINT.format(page=page)
        api_url = f"{BASE_URL.rstrip('/')}{endpoint}"
        
        print(f"[Page {page}] Fetching: {api_url}")
        
        try:
            response = requests.get(api_url, timeout=30)
            
            if response.status_code != 200:
                print(f"  → Status {response.status_code}, stopping")
                break
            
            data = response.json()
            
            # Try common response formats
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("items", data.get("results", data.get("data", [])))
            
            if not items:
                print("  → No items found, stopping")
                break
            
            for item in items:
                url = item.get("url") or item.get("link") or item.get("href")
                if url:
                    if url.startswith("/"):
                        url = f"{BASE_URL.rstrip('/')}{url}"
                    urls.add(url)
            
            print(f"  Found {len(items)} items (total: {len(urls)})")
            
            page += 1
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            print(f"  Error: {e}")
            break
    
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
    
    print(f"\n✓ Saved {len(urls)} URLs to {output_file}")


def main():
    print(f"Infinite Scroll URL Discovery")
    print(f"Target: {BASE_URL}{GALLERY_PATH}")
    print(f"Method: {'AJAX' if AJAX_ENDPOINT else 'Browser Scrolling'}")
    print("-" * 60)
    
    if AJAX_ENDPOINT:
        urls = discover_via_ajax()
    else:
        urls = asyncio.run(discover_via_browser())
    
    if urls:
        save_urls(urls, OUTPUT_FILE)
    else:
        print("No URLs found!")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

