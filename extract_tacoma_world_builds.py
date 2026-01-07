#!/usr/bin/env python3
"""
Tacoma World Build Extraction Script

Extracts structured build data from Tacoma World media gallery HTML files.
 Tacoma World media pages have limited data (no JSON-LD), so we extract:
- Title (may contain vehicle info)
- Owner username
- Image URL
- Upload date
- Album name

Vehicle year/make/model are inferred from title patterns when possible.

Usage:
    python extract_tacoma_world_builds.py
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from bs4 import BeautifulSoup

# Add scripts/ralph to path for build_id_generator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts", "ralph"))
from build_id_generator import url_to_build_id


def infer_build_type_from_title(title: str) -> str:
    """Infer build_type from Tacoma World media title.

    Tacoma World is Toyota-focused, so most builds are Off-Road oriented.
    Look for keywords like: PreRunner, Overland, Off-Road, Prerunner, etc.

    Args:
        title: Media title text

    Returns:
        Inferred build_type
    """
    if not title:
        return "Daily Driver"

    title_lower = title.lower()

    # Off-road related keywords (common on Tacoma World)
    offroad_keywords = ["off-road", "offroad", "overland", "prerunner", "pre runner",
                       "4x4", "4wd", "trail", "crawl", "expedition", "adventure"]

    # Work truck keywords
    work_keywords = ["work", "utility", "service", "fleet"]

    # Stance/show keywords
    stance_keywords = ["stance", "show", "clean", "flush", "tucked"]

    # Performance keywords
    perf_keywords = ["track", "race", "drag", "drift", "performance", "speed"]

    for keyword in offroad_keywords:
        if keyword in title_lower:
            return "Off-Road"

    for keyword in work_keywords:
        if keyword in title_lower:
            return "Work Truck"

    for keyword in stance_keywords:
        if keyword in title_lower:
            return "Stance"

    for keyword in perf_keywords:
        if keyword in title_lower:
            return "Track"

    # Default for Tacoma World (Toyota trucks)
    return "Daily Driver"


def parse_year_make_model_from_title(title: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse year, make, model from Tacoma World media title.

    Tacoma World titles often contain vehicle info like:
    - "4.10 PreRunner 3rd SGTBT 1.3.25" -> year from "4.10" (April 2010), Toyota Tacoma
    - "08 RCLT King" -> 2008 Toyota Tacoma King Cab
    - "Taco Side View" -> Toyota Tacoma (generic)

    Args:
        title: Media title text

    Returns:
        Tuple of (year, make, model) as strings
    """
    if not title:
        return None, None, None

    title_clean = title.strip()
    year = None
    make = "Toyota"  # Tacoma World is Toyota-focused
    model = "Tacoma"  # Default model

    # Try to extract year from patterns like "08", "2020", "4.10" (date format)
    # Pattern 1: Two-digit year at start (e.g., "08 RCLT")
    match = re.match(r'^(\d{2})\s', title_clean)
    if match:
        two_digit = int(match.group(1))
        # Assume 00-29 is 2000-2029, 30-99 is 1930-1999
        if two_digit <= 29:
            year = f"20{two_digit:02d}"
        else:
            year = f"19{two_digit:02d}"

    # Pattern 2: Four-digit year (e.g., "2020 Tacoma")
    if not year:
        match = re.search(r'\b(19\d{2}|20\d{2})\b', title_clean)
        if match:
            year = match.group(1)

    # Pattern 3: Date format like "4.10" (April 2010)
    if not year:
        match = re.match(r'^(\d)\.(\d+)\s', title_clean)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            # This is a date, not a year - could infer year from context
            # For now, leave as None and use default
            pass

    # Look for model indicators in title
    title_lower = title_clean.lower()

    # Tacoma variants
    if "tacoma" in title_lower or "taco" in title_lower:
        model = "Tacoma"
    elif "tundra" in title_lower:
        model = "Tundra"
    elif "4runner" in title_lower or "4 runner" in title_lower:
        model = "4Runner"
    elif "seqouia" in title_lower:
        model = "Sequoia"

    # Look for trim/cab info
    trim = None
    if "dcsb" in title_lower or "double cab" in title_lower:
        trim = "Double Cab Short Bed"
    elif "dc lb" in title_lower or "long bed" in title_lower:
        trim = "Double Cab Long Bed"
    elif "access cab" in title_lower or "ac" in title_lower:
        trim = "Access Cab"
    elif "crew cab" in title_lower:
        trim = "Crew Cab"
    elif "extended cab" in title_lower:
        trim = "Extended Cab"
    elif "king cab" in title_lower:
        trim = "King Cab"
    elif "regular cab" in title_lower:
        trim = "Regular Cab"

    # Combine model with trim if found
    if trim:
        model = f"{model} {trim}"

    return year, make, model


def extract_html_file(html_file: Path, manifest: dict) -> Optional[dict]:
    """Extract build data from a single Tacoma World HTML file.

    Args:
        html_file: Path to HTML file
        manifest: Manifest dict with URL mapping

    Returns:
        Build data dict or None if extraction fails
    """
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')

    # Get URL from manifest
    filename = html_file.name
    url = None

    # Manifest is a list of entries
    if isinstance(manifest, list):
        for entry in manifest:
            if entry.get('filename') == filename:
                url = entry.get('url')
                break
    # Manifest is a dict with 'entries' key
    elif isinstance(manifest, dict):
        for entry in manifest.get('entries', []):
            if entry.get('filename') == filename:
                url = entry.get('url')
                break

    if not url:
        # Fallback: construct URL from filename
        slug = filename.replace('.html', '')
        url = f"https://www.tacomaworld.com/media/{slug}/"

    # Extract title from <h1> tag
    title_tag = soup.find('h1')
    title = title_tag.get_text(strip=True) if title_tag else None

    # Extract owner username from breadcrumbs or sidebar
    owner = None
    username_link = soup.find('a', class_='username')
    if username_link:
        owner = username_link.get_text(strip=True)

    # Extract image URL from meta tags or img tag
    image_url = None
    # Try og:image
    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content'):
        image_url = og_image['content']
    # Try twitter:image
    if not image_url:
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            image_url = twitter_image['content']
    # Try main image tag
    if not image_url:
        img_tag = soup.find('img', class_='Image')
        if img_tag and img_tag.get('src'):
            src = img_tag['src']
            # Convert relative URL to absolute
            if src.startswith('/'):
                image_url = f"https://www.tacomaworld.com{src}"
            elif not src.startswith('http'):
                image_url = f"https://www.tacomaworld.com/media/{src}"
            else:
                image_url = src

    # Fix image URL to point to full size
    if image_url and '/full?' not in image_url:
        image_url = image_url.replace('?d=', '/full?d=')

    # Extract album name from breadcrumbs
    album = None
    album_links = soup.find_all('a', href=re.compile(r'/media/albums/'))
    for link in album_links:
        album_text = link.get_text(strip=True)
        if album_text and album_text != "Albums":
            album = album_text
            break

    # Extract upload date from datetime attribute
    upload_date = None
    date_tag = soup.find('abbr', class_='DateTime')
    if date_tag and date_tag.get('data-time'):
        try:
            timestamp = int(date_tag['data-time'])
            upload_date = datetime.fromtimestamp(timestamp).isoformat() + "Z"
        except (ValueError, TypeError):
            pass

    # Parse vehicle info from title
    year, make, model = parse_year_make_model_from_title(title)

    # Infer build_type
    build_type = infer_build_type_from_title(title)

    # Generate build_id
    build_id = url_to_build_id(url)

    # Build gallery images array
    gallery_images = [image_url] if image_url else []

    # Build the record
    build = {
        "build_id": build_id,
        "source_type": "gallery",
        "build_type": build_type,
        "build_source": "tacomaworld.com",
        "source_url": url,
        "build_title": title,
        "year": year,
        "make": make,
        "model": model,
        "trim": None,
        "generation": None,
        "engine": None,
        "transmission": None,
        "drivetrain": None,
        "exterior_color": None,
        "interior_color": None,
        "build_story": f"Media from {album} album on Tacoma World." if album else "Media from Tacoma World gallery.",
        "owner_username": owner,
        "gallery_images": gallery_images,
        "main_image": image_url,
        "modifications": [],
        "modification_level": "Stock",
        "vehicle_summary_extracted": None,
        "extraction_confidence": 0.6,  # Lower confidence due to limited data
        "sale_data": None,  # Not a listing
        "wheel_and_tire_fitment_specs": None,
        "build_stats": None,
        "metadata": {
            "era": None,
            "category": "Gallery",
            "highlights": [],
            "equipment": [],
            "published_date": upload_date,
            "scraped_at": None,
            "scraper_metadata": {
                "extractor": "tacoma_world_gallery_parser",
                "album": album,
                "page_type": "gallery_media"
            }
        },
        "processing": {
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "extractor_version": "1.0.0",
            "model_used": None,
            "source_scraped_at": upload_date
        },
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "vin": None,
        "products": [],
        "build_nickname": None
    }

    return build


def main():
    """Main extraction function."""
    html_dir = Path("scraped_builds/tacoma_world/html")
    manifest_file = Path("scraped_builds/tacoma_world/manifest.json")
    output_file = Path("scraped_builds/tacoma_world/builds.json")

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Load manifest for URL mapping
    manifest = {}
    if manifest_file.exists():
        with open(manifest_file, 'r') as f:
            manifest = json.load(f)

    # Get all HTML files
    html_files = list(html_dir.glob("*.html"))
    total_files = len(html_files)

    print(f"Found {total_files} HTML files to process")

    # Extract builds
    builds = []
    failed = []

    for i, html_file in enumerate(html_files, 1):
        try:
            build = extract_html_file(html_file, manifest)
            if build:
                builds.append(build)
                if i % 100 == 0:
                    print(f"Progress: {i}/{total_files} builds extracted")
            else:
                failed.append(html_file.name)
        except Exception as e:
            print(f"Error processing {html_file.name}: {e}")
            failed.append(html_file.name)

    # Sort by build_id
    builds.sort(key=lambda b: b['build_id'])

    # Write output
    with open(output_file, 'w') as f:
        json.dump(builds, f, indent=2)

    # Summary
    print(f"\nExtraction complete!")
    print(f"Total builds extracted: {len(builds)}")
    print(f"Failed: {len(failed)}")
    print(f"Output: {output_file}")

    if failed:
        print(f"\nFailed files:")
        for f in failed[:10]:
            print(f"  - {f}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")


if __name__ == "__main__":
    main()
