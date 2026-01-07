#!/usr/bin/env python3
"""
Extract build data from OnAllCylinders article HTML files.

OnAllCylinders is a WordPress blog by Summit Racing featuring vehicle build articles.
This script extracts available data from HTML - no JSON-LD structured data available.

Usage:
    python extract_onallcylinders_builds.py
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Add scripts/ralph to path for build_id_generator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts', 'ralph'))
from build_id_generator import url_to_build_id

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing BeautifulSoup4...")
    os.system("pip install beautifulsoup4")
    from bs4 import BeautifulSoup


# Build type keyword mappings for content analysis
BUILD_TYPE_KEYWORDS = {
    "Hot Rod": ["hot rod", "hotrod", "classic", "rat rod", "street rod"],
    "Restomod": ["restomod", "resto-mod", "modernized", "restored"],
    "Pro Touring": ["pro touring", "autocross", "track ready", "handling"],
    "Muscle": ["muscle car", "pony car", "gto", "chevelle", "mustang", "camaro", "challenger", "charger"],
    "Off-Road": ["offroad", "off-road", "4x4", "lifted", "jeep", "bronco", "crawler"],
    "Overland": ["overland", "overlanding", "expedition", "adventure"],
    "Street": ["street car", "daily driver", "cruiser"],
    "Show": ["show car", "concours", "trailer queen", "show quality"],
    "Drag": ["drag race", "drag strip", "quarter mile", "drag car"],
    "Drift": ["drift", "drifting", "slide", "angle"],
    "Track": ["track car", "race car", "time attack", "lapping"],
    "Restoration": ["restoration", "barn find", "original", "survivor"],
    "USDM": ["american", "domestic", "usdm"],
    "JDM": ["jdm", "japanese", "import"],
    "Euro": ["european", "euro", "german", "british", "italian"],
}

# Make/model patterns from titles (regex-based)
MAKE_MODEL_PATTERNS = [
    # Pattern: (regex, make_extract, model_extract)
    (r'(Factory Five)\s+(\w+)', 'Factory Five', lambda m: m.group(2) + ' Roadster'),
    (r'(Jeep)\s+(\w+)', 'Jeep', lambda m: m.group(2)),
    (r'(Ford|Chevy|Chevrolet|Dodge|Plymouth|Pontiac|Buick|Oldsmobile|AMC)\s+([A-Z][a-z]+)', None, None),  # Generic
    (r'(Mustang|Camaro|Challenger|Charger|Corvette|GTO|Chevelle|Impala)', None, None),  # Model-only
]


def infer_build_type(title: str, content: str) -> str:
    """Infer build type from title and content keywords."""
    text = (title + " " + content).lower()

    scores = {}
    for build_type, keywords in BUILD_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[build_type] = score

    if scores:
        return max(scores.items(), key=lambda x: x[1])[0]
    return "Street"  # Default


def infer_make_model(title: str) -> tuple:
    """Infer make and model from article title."""
    title_lower = title.lower()

    # Special cases
    if "factory five" in title_lower:
        if "mk4" in title_lower or "mk 4" in title_lower:
            return "Factory Five", "Mk4 Roadster"
        if "mk3" in title_lower or "mk 3" in title_lower:
            return "Factory Five", "Mk3 Roadster"
        if "type 65" in title_lower or "cobra" in title_lower:
            return "Factory Five", "Type 65 Coupe"
        if "gtm" in title_lower:
            return "Factory Five", "GTM"
        return "Factory Five", "Roadster"

    if "jeep" in title_lower:
        if "wrangler" in title_lower or "jl" in title_lower or "jk" in title_lower:
            return "Jeep", "Wrangler"
        if "cherokee" in title_lower:
            return "Jeep", "Cherokee"
        if "grand cherokee" in title_lower:
            return "Jeep", "Grand Cherokee"
        return "Jeep", None

    # Look for common makes
    makes = ["ford", "chevy", "chevrolet", "dodge", "plymouth", "pontiac", "buick", "oldsmobile",
             "gmc", "cadillac", "lincoln", "mercury", "amc", "toyota", "nissan", "honda", "mazda",
             "subaru", "mitsubishi", "hyundai", "kia", "volkswagen", "bmw", "mercedes", "audi",
             "porsche", "ferrari", "lamborghini", "aston martin", "jaguar", "lotus"]

    found_make = None
    for make in makes:
        if make in title_lower:
            found_make = make.title()
            break

    return found_make, None


def infer_year(title: str, content: str) -> str:
    """Infer vehicle year from title and content."""
    # Look for 4-digit years in typical vehicle range (1900-2026)
    years = re.findall(r'\b(19[3-9]\d|20[0-2]\d)\b', title + " " + content)

    if years:
        # Return the most frequently mentioned year, or first if equal
        from collections import Counter
        return max(Counter(years).items(), key=lambda x: x[1])[0]

    return None


def extract_images(soup, article) -> list:
    """Extract image URLs from article."""
    images = []

    # First try OG image as main image
    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content'):
        images.append(og_image['content'])

    # Get all images from article
    if article:
        for img in article.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src and not src.startswith('data:') and src not in images:
                # Skip small/tracking images
                if any(x in src.lower() for x in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    images.append(src)

    return images[:20]  # Limit to 20 images per build


def extract_article_text(article) -> str:
    """Extract clean article text for build_story."""
    if not article:
        return ""

    # Get all paragraphs
    paragraphs = article.find_all('p')
    text_parts = []

    for p in paragraphs:
        text = p.get_text(strip=True)
        if text and len(text) > 20:  # Skip short/empty paragraphs
            text_parts.append(text)

    return "\n\n".join(text_parts)


def extract_build_from_html(filepath: str, manifest_entry: dict) -> dict:
    """Extract build data from a single HTML file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')

    # Extract title
    h1 = soup.find('h1')
    title = h1.get_text(strip=True) if h1 else manifest_entry.get('title', 'Unknown')

    # Get article content
    article = soup.find('article')

    # Extract published date
    meta_date = soup.find('meta', property='article:published_time')
    published_date = meta_date.get('content') if meta_date else None

    # Extract source URL from canonical link
    canonical = soup.find('link', rel='canonical')
    source_url = canonical.get('href', manifest_entry.get('url', ''))

    # Extract images
    gallery_images = extract_images(soup, article)
    main_image = gallery_images[0] if gallery_images else None

    # Extract article text for build_story
    build_story = extract_article_text(article)

    # Infer vehicle details
    make, model = infer_make_model(title)
    year = infer_year(title, build_story)
    build_type = infer_build_type(title, build_story)

    # Generate build_id
    build_id = url_to_build_id(source_url)

    return {
        "build_id": build_id,
        "source_type": "article",
        "build_type": build_type,
        "build_source": "onallcylinders.com",
        "source_url": source_url,
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
        "build_story": build_story[:50000] if build_story else None,  # Limit size
        "owner_username": None,
        "gallery_images": gallery_images,
        "main_image": main_image,
        "modifications": [],  # Will be extracted in Stage 4
        "modification_level": None,
        "vehicle_summary_extracted": None,
        "extraction_confidence": 0.5,  # Lower confidence due to inference
        "sale_data": None,  # Blog articles, not sales
        "wheel_and_tire_fitment_specs": None,
        "build_stats": None,
        "metadata": {
            "era": None,
            "category": "Blog Article",
            "highlights": [],
            "equipment": [],
            "published_date": published_date,
            "scraped_at": manifest_entry.get('scraped_at'),
            "scraper_metadata": {
                "extractor": "extract_onallcylinders_builds.py",
                "page_type": "article"
            }
        },
        "processing": {
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "extractor_version": "1.0.0",
            "model_used": None,
            "source_scraped_at": manifest_entry.get('scraped_at')
        },
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "vin": None,
        "products": [],
        "build_nickname": None
    }


def main():
    """Main extraction function."""
    html_dir = Path("scraped_builds/onallcylinders/html")
    manifest_file = Path("scraped_builds/onallcylinders/manifest.json")
    output_file = Path("scraped_builds/onallcylinders/builds.json")

    print(f"Reading manifest from {manifest_file}...")
    with open(manifest_file) as f:
        manifest = json.load(f)

    # Handle both list and dict manifest formats
    articles = manifest.get('articles', []) if isinstance(manifest, dict) else manifest

    print(f"Found {len(articles)} articles in manifest")

    builds = []
    errors = []

    for entry in articles:
        filename = entry.get('filename')
        if not filename:
            continue

        filepath = html_dir / filename
        if not filepath.exists():
            errors.append(f"File not found: {filename}")
            continue

        try:
            build = extract_build_from_html(str(filepath), entry)
            builds.append(build)
            print(f"Extracted: {build['build_title'][:60]}... (ID: {build['build_id']})")
        except Exception as e:
            errors.append(f"{filename}: {str(e)}")
            print(f"ERROR: {filename} - {str(e)}")

    # Sort by build_id
    builds.sort(key=lambda b: b['build_id'])

    # Write output
    print(f"\nWriting {len(builds)} builds to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(builds, f, indent=2)

    # Summary
    print(f"\n=== EXTRACTION COMPLETE ===")
    print(f"Total builds: {len(builds)}")
    print(f"Errors: {len(errors)}")

    if errors:
        print(f"\nErrors:")
        for error in errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    # Stats
    with_year = sum(1 for b in builds if b.get('year'))
    with_make = sum(1 for b in builds if b.get('make'))
    with_model = sum(1 for b in builds if b.get('model'))
    with_images = sum(1 for b in builds if b.get('gallery_images'))
    with_story = sum(1 for b in builds if b.get('build_story'))

    print(f"\n=== FIELD COVERAGE ===")
    print(f"Year: {with_year}/{len(builds)} ({100*with_year/len(builds):.1f}%)")
    print(f"Make: {with_make}/{len(builds)} ({100*with_make/len(builds):.1f}%)")
    print(f"Model: {with_model}/{len(builds)} ({100*with_model/len(builds):.1f}%)")
    print(f"Images: {with_images}/{len(builds)} ({100*with_images/len(builds):.1f}%)")
    print(f"Build Story: {with_story}/{len(builds)} ({100*with_story/len(builds):.1f}%)")


if __name__ == "__main__":
    main()
