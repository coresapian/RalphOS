#!/usr/bin/env python3
"""
Build Extractor for Paramount Performance UK Tuner Showcase Pages.
Parses HTML files to extract structured build data.
"""

import json
import re
import sys
import hashlib
from pathlib import Path
from bs4 import BeautifulSoup

# Add path for build_id_generator
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "tools"))

try:
    from build_id_generator import url_to_build_id
except ImportError:
    def url_to_build_id(url: str) -> int:
        """Generate deterministic 63-bit build_id from URL."""
        hash_bytes = hashlib.md5(url.encode()).digest()
        return int.from_bytes(hash_bytes[:8], 'big') & ((1 << 63) - 1)

# Configuration
OUTPUT_DIR = Path(__file__).parent
HTML_DIR = OUTPUT_DIR / "html"
URLS_FILE = OUTPUT_DIR / "urls.json"
BUILDS_FILE = OUTPUT_DIR / "builds.json"

# Vehicle mappings from URL slug to make/model
VEHICLE_MAPPINGS = {
    "bmw-m3-upgrades": {"make": "BMW", "model": "M3", "package_name": "GRAVITY WAVE"},
    "jaguar-f-type-predator-ii": {"make": "Jaguar", "model": "F-Type", "package_name": "PREDATOR II"},
    "jaguar-f-type-predator-upgrades": {"make": "Jaguar", "model": "F-Type", "package_name": "PREDATOR"},
    "land-rover-defender-beast": {"make": "Land Rover", "model": "Defender", "package_name": "BEAST"},
    "mercedes-a45-amg-upgrades": {"make": "Mercedes-AMG", "model": "A45", "package_name": "KRAKEN"},
    "range-rover-typhon-upgrades": {"make": "Range Rover", "model": "Sport SVR", "package_name": "TYPHON"},
    "vw-golf-r-katana-fire": {"make": "Volkswagen", "model": "Golf R", "package_name": "KATANA FIRE"},
}


def extract_json_ld(soup) -> dict:
    """Extract JSON-LD structured data."""
    script = soup.select_one('script.rank-math-schema-pro')
    if script:
        try:
            return json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def extract_og_meta(soup) -> dict:
    """Extract OpenGraph metadata."""
    meta = {}
    for tag in soup.select('meta[property^="og:"]'):
        prop = tag.get("property", "").replace("og:", "")
        content = tag.get("content", "")
        if prop and content:
            meta[prop] = content
    return meta


def extract_description(soup) -> str:
    """Extract meta description."""
    desc = soup.select_one('meta[name="description"]')
    if desc:
        return desc.get("content", "")
    return ""


def extract_gallery_images(soup) -> list:
    """Extract gallery images from wp-block-gallery."""
    images = []

    # Try wp-block-gallery first
    for img in soup.select('.wp-block-gallery img'):
        src = img.get("src") or img.get("data-src")
        if src and src.startswith("http"):
            images.append(src)

    # Also try wp-block-image
    for img in soup.select('.wp-block-image img'):
        src = img.get("src") or img.get("data-src")
        if src and src.startswith("http") and src not in images:
            images.append(src)

    return images


def extract_build_from_html(html_content: str, source_url: str, slug: str) -> dict:
    """Extract build data from HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Get OG metadata
    og = extract_og_meta(soup)

    # Get vehicle mapping
    mapping = VEHICLE_MAPPINGS.get(slug, {})
    make = mapping.get("make", "")
    model = mapping.get("model", "")
    package_name = mapping.get("package_name", "")

    # Extract H1 title
    h1 = soup.select_one("h1")
    page_title = h1.get_text(strip=True) if h1 else ""

    # Use OG title as fallback
    title = og.get("title", page_title).split("|")[0].strip()

    # Build title format: "Make Model Package"
    build_title = f"{make} {model} {package_name}" if make and model else title

    # Extract description
    description = extract_description(soup)

    # Extract images
    gallery_images = extract_gallery_images(soup)
    og_image = og.get("image", "")
    if og_image and og_image not in gallery_images:
        gallery_images.insert(0, og_image)

    # Create build record
    build = {
        "build_id": url_to_build_id(source_url),
        "source_url": source_url,
        "source_type": "showcase",
        "build_source": "paramount-performance.com",
        "build_type": "Tuner Package",
        "year": "",  # Not specified on pages
        "make": make,
        "model": model,
        "trim": "",
        "build_title": build_title,
        "package_name": package_name,
        "tuner_brand": "Paramount Performance",
        "description": description,
        "gallery_images": gallery_images,
        "country_origin": "UK",
        "extraction_confidence": 0.95 if make and model else 0.7,
    }

    return build


def main():
    """Main extraction function."""
    # Load URL to slug mapping
    with open(URLS_FILE, "r", encoding="utf-8") as f:
        urls_data = json.load(f)

    url_to_slug = {}
    for url in urls_data.get("urls", []):
        match = re.search(r'/showcase/([^/]+)/?', url)
        if match:
            url_to_slug[match.group(1)] = url

    # Process all HTML files
    builds = []
    errors = []

    html_files = list(HTML_DIR.glob("*.html"))
    print(f"Processing {len(html_files)} HTML files...")

    for html_file in sorted(html_files):
        slug = html_file.stem
        source_url = url_to_slug.get(slug, f"https://paramount-performance.com/showcase/{slug}/")

        try:
            with open(html_file, "r", encoding="utf-8") as f:
                html_content = f.read()

            build = extract_build_from_html(html_content, source_url, slug)

            if not build.get("make") or not build.get("model"):
                print(f"  Warning (missing make/model): {html_file.name}")
                errors.append({
                    "file": html_file.name,
                    "error": "Missing make/model"
                })

            builds.append(build)
            print(f"  Extracted: {build['build_title']}")

        except Exception as e:
            print(f"  Error: {html_file.name} - {e}")
            errors.append({
                "file": html_file.name,
                "error": str(e)
            })

    # Save builds
    output = {
        "builds": builds,
        "metadata": {
            "total": len(builds),
            "extracted_at": __import__("datetime").datetime.now().isoformat(),
            "source": "paramount-performance.com",
            "errors": len(errors)
        }
    }

    with open(BUILDS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Summary
    print("\n" + "=" * 60)
    print("BUILD EXTRACTION COMPLETE")
    print(f"  Total builds: {len(builds)}")
    print(f"  Errors: {len(errors)}")
    print("=" * 60)

    # Make breakdown
    make_counts = {}
    for b in builds:
        make = b.get("make", "Unknown")
        make_counts[make] = make_counts.get(make, 0) + 1

    print("\nMake breakdown:")
    for make, count in sorted(make_counts.items(), key=lambda x: -x[1]):
        print(f"  {make}: {count}")


if __name__ == "__main__":
    main()
