#!/usr/bin/env python3
"""Analyze RaceMarket site structure to find URLs and pagination."""

import json
import re
from pathlib import Path

# Load the fetched HTML content from webReader output
html_file = Path("scripts/ralph/workers/racemarket/fetched_page.html")
if not html_file.exists():
    print("ERROR: fetched_page.html not found. Run webReader first.")
    exit(1)

html = html_file.read_text()

# Find all item URLs
item_pattern = r'href="(/index\.php\?page=item&id=\d+)"'
item_urls = re.findall(item_pattern, html)

print(f"Found {len(item_urls)} item URLs on page")

# Get unique URLs
unique_urls = sorted(set(item_urls))
print(f"Unique URLs: {len(unique_urls)}")

# Full URLs
full_urls = [f"https://racemarket.net{url}" for url in unique_urls]

print("\nSample item URLs:")
for url in full_urls[:10]:
    print(f"  {url}")

# Find pagination
pag_pattern = r'href="(/index\.php\?page=search[^"]*iPage=\d+[^"]*)"'
pag_urls = re.findall(pag_pattern, html)

print(f"\nFound {len(pag_urls)} pagination links")
print("Sample pagination URLs:")
for url in pag_urls[:10]:
    print(f"  {url}")

# Extract max page number from pagination
max_page = 0
for url in pag_urls:
    match = re.search(r'iPage=(\d+)', url)
    if match:
        page_num = int(match.group(1))
        max_page = max(max_page, page_num)

print(f"\nMax page number found: {max_page}")

# Look for item count pattern
count_pattern = r'(\d+[,\d]*)\s+ads?'
counts = re.findall(count_pattern, html)
if counts:
    print(f"\nPossible item counts: {counts}")

# Save results
output = {
    "items_per_page": len(unique_urls),
    "sample_item_urls": full_urls[:20],
    "pagination_urls": [f"https://racemarket.net{url}" for url in pag_urls],
    "max_page_found": max_page
}

output_file = Path("scripts/ralph/workers/racemarket/site_analysis.json")
output_file.parent.mkdir(parents=True, exist_ok=True)
output_file.write_text(json.dumps(output, indent=2))

print(f"\nAnalysis saved to {output_file}")
