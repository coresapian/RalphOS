#!/usr/bin/env python3
"""
Mod Extractor for Paramount Performance UK Tuner

Extracts modifications from HTML files for Paramount tuning packages.
Paramount uses wp-block-list/wp-block-heading structure for package components.
"""

import json
import re
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
from bs4 import BeautifulSoup

# Configuration
OUTPUT_DIR = Path(__file__).parent
HTML_DIR = OUTPUT_DIR / "html"
BUILDS_FILE = OUTPUT_DIR / "builds.json"
MODS_FILE = OUTPUT_DIR / "mods.json"

# Category detection patterns
CATEGORY_PATTERNS = {
    "Engine": [
        r"ecu", r"remap", r"tune", r"tuning", r"stage\s*\d",
        r"pulley", r"supercharger", r"turbo",
    ],
    "Exhaust": [
        r"exhaust", r"cat\s*back", r"catback", r"downpipe",
        r"catalytic", r"sports?\s*cat", r"muffler", r"milltek",
    ],
    "Intake": [
        r"intake", r"air\s*filter", r"cold\s*air", r"induction",
    ],
    "Exterior": [
        r"carbon\s*fib", r"splitter", r"diffuser", r"wing",
        r"spoiler", r"bonnet", r"hood", r"side\s*skirt",
        r"grille", r"canard", r"fender", r"boot\s*lid",
    ],
    "Suspension": [
        r"suspension", r"coilover", r"spring", r"lowering",
        r"damper", r"shock", r"strut",
    ],
    "Wheels & Tires": [
        r"wheel", r"rim", r"tire", r"tyre", r"alloy",
    ],
    "Interior": [
        r"interior", r"seat", r"steering\s*wheel", r"dash",
        r"trim", r"pedal",
    ],
    "Cooling": [
        r"intercooler", r"radiator", r"coolant", r"cooling",
    ],
}

# Known brands
KNOWN_BRANDS = [
    "Milltek", "VIEZU", "Harrop", "KW", "H&R", "Akrapovic",
    "Paramount Performance", "Paramount", "BMC", "K&N",
]


def detect_category(mod_name):
    """Detect category from modification name."""
    mod_lower = mod_name.lower()
    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, mod_lower):
                return category
    return "Other"


def extract_brand(mod_name):
    """Extract brand from modification name."""
    mod_upper = mod_name.upper()
    for brand in KNOWN_BRANDS:
        if brand.upper() in mod_upper:
            return brand
    return "Paramount Performance"  # Default to tuner brand


def get_build_for_html(html_filename, builds):
    """Match HTML filename to a build."""
    slug = html_filename.replace(".html", "")
    for build in builds:
        if slug in build.get("source_url", ""):
            return build
    return None


def extract_mods_from_html(html_path, build):
    """Extract modifications from a single HTML file."""
    mods = []
    build_id = build.get("build_id")
    source_url = build.get("source_url")
    package_name = build.get("package_name", "")

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    # Method 1: Extract from wp-block-list items (linked mods)
    for ul in soup.find_all("ul", class_="wp-block-list"):
        for li in ul.find_all("li"):
            # Get anchor text if it's a link
            link = li.find("a")
            if link:
                mod_name = link.get_text(strip=True)
            else:
                mod_name = li.get_text(strip=True)

            if mod_name and len(mod_name) > 3:
                # Clean up nbsp and extra whitespace
                mod_name = mod_name.replace("\xa0", " ").strip()
                
                # Skip non-mod items
                if any(skip in mod_name.lower() for skip in ["click here", "visit", "order", "contact"]):
                    continue

                mod = {
                    "build_id": build_id,
                    "source_url": source_url,
                    "mod_name": mod_name,
                    "brand": extract_brand(mod_name),
                    "category": detect_category(mod_name),
                    "is_tuner_package": True,
                    "package_name": package_name,
                    "confidence": 0.9
                }
                mods.append(mod)

    # Method 2: Extract from wc-block-grid product titles (related products)
    for product_title in soup.find_all("div", class_="wc-block-grid__product-title"):
        mod_name = product_title.get_text(strip=True)
        if mod_name and len(mod_name) > 5:
            # Skip if it's just the car model name
            make = build.get("make", "").lower()
            model = build.get("model", "").lower()
            mod_lower = mod_name.lower()

            # Check if this is a relevant mod (contains performance keywords)
            if any(kw in mod_lower for kw in ["exhaust", "remap", "tuning", "intake", "suspension", "intercooler", "carbon"]):
                # Skip if it's for a completely different car
                if make and make not in mod_lower and model not in mod_lower:
                    continue

                mod = {
                    "build_id": build_id,
                    "source_url": source_url,
                    "mod_name": mod_name,
                    "brand": extract_brand(mod_name),
                    "category": detect_category(mod_name),
                    "is_tuner_package": True,
                    "package_name": package_name,
                    "confidence": 0.8
                }
                mods.append(mod)

    # Method 3: Extract from wp-block-heading sections (for context)
    for heading in soup.find_all(["h2", "h3"], class_="wp-block-heading"):
        heading_text = heading.get_text(strip=True).lower()
        
        # Skip generic headings
        if any(skip in heading_text for skip in [
            "presenting", "about", "choice is yours", "contact",
            "installation", "order", "dyno", "halo"
        ]):
            continue

        # Look for mods mentioned in heading itself
        if any(term in heading_text for term in ["carbon", "exhaust", "intake", "upgrades"]):
            # Get the next paragraph for more details
            next_p = heading.find_next("p")
            if next_p:
                text = next_p.get_text(strip=True)
                # Extract specific items mentioned
                if "includes" in text.lower() or "package" in text.lower():
                    # Parse list of items from paragraph
                    items = re.findall(r'(?:^|,\s*)([A-Z][^,]+?)(?=,|$|\.)', text)
                    for item in items:
                        item = item.strip()
                        if len(item) > 3 and len(item) < 100:
                            mod = {
                                "build_id": build_id,
                                "source_url": source_url,
                                "mod_name": item,
                                "brand": extract_brand(item),
                                "category": detect_category(item),
                                "is_tuner_package": True,
                                "package_name": package_name,
                                "confidence": 0.7
                            }
                            mods.append(mod)

    return mods


def dedupe_mods(mods):
    """Remove duplicate mods."""
    seen = set()
    unique = []
    for mod in mods:
        key = (mod["build_id"], mod["mod_name"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(mod)
    return unique


def main():
    # Load builds
    with open(BUILDS_FILE, "r", encoding="utf-8") as f:
        builds_data = json.load(f)

    builds = builds_data.get("builds", [])
    print(f"Loaded {len(builds)} builds")

    # Process each HTML file
    html_files = list(HTML_DIR.glob("*.html"))
    print(f"Found {len(html_files)} HTML files")

    all_mods = []
    builds_with_mods = 0

    for html_path in html_files:
        build = get_build_for_html(html_path.name, builds)
        if not build:
            print(f"  Warning: No build found for {html_path.name}")
            continue

        mods = extract_mods_from_html(html_path, build)
        if mods:
            builds_with_mods += 1
            all_mods.extend(mods)
            print(f"  {build.get('build_title')}: {len(mods)} mods")

    # Dedupe
    all_mods = dedupe_mods(all_mods)

    # Category breakdown
    categories = Counter(m["category"] for m in all_mods)

    # Save
    output = {
        "mods": all_mods,
        "metadata": {
            "total_mods": len(all_mods),
            "builds_with_mods": builds_with_mods,
            "total_builds": len(builds),
            "mod_rate": round(builds_with_mods / len(builds) * 100, 1) if builds else 0,
            "extracted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "paramount-performance.com",
            "categories": dict(categories)
        }
    }

    with open(MODS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Summary
    print("\n" + "=" * 60)
    print("MOD EXTRACTION COMPLETE")
    print(f"  Total builds: {len(builds)}")
    print(f"  Builds with mods: {builds_with_mods}")
    print(f"  Total mods: {len(all_mods)}")
    print(f"  Mod rate: {output['metadata']['mod_rate']}%")
    print("=" * 60)

    print("\nCategory breakdown:")
    for cat, count in categories.most_common():
        print(f"  {cat}: {count}")

    print("\nTop modifications:")
    mod_counts = Counter(m["mod_name"] for m in all_mods)
    for name, count in mod_counts.most_common(15):
        print(f"  {name}: {count}")


if __name__ == "__main__":
    main()
