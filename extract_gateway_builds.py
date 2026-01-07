#!/usr/bin/env python3
"""
Gateway Classic Cars Build Extraction Script

Extracts structured build data from Gateway Classic Cars HTML files.
Uses JSON-LD structured data for reliable extraction.

Usage:
    python extract_gateway_builds.py
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Add scripts/ralph to path for build_id_generator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts", "ralph"))
from build_id_generator import url_to_build_id


def infer_build_type(year: int, make: str, model: str) -> str:
    """Infer build_type based on year, make, model.

    Rules:
    - Pre-1980: Classic, Hot Rod, Rat Rod, Restomod (if modified)
    - 1980-1999: Modern Classic, Restomod
    - 2000+: Modern, USDM, JDM, Euro (based on origin)
    - Muscle cars: 1960s-1970s American V8s
    - Trucks: Work Truck, Tow Rig, Off-Road
    """
    make_lower = make.lower() if make else ""
    model_lower = model.lower() if model else ""

    # American muscle cars
    if make_lower in ["ford", "chevrolet", "pontiac", "dodge", "plymouth", "oldsmobile", "buick", "mercury"]:
        if year < 1965:
            return "Hot Rod"
        elif year < 1975:
            # Check for specific muscle models
            if any(m in model_lower for m in ["mustang", "camaro", "charger", "challenger", "gto", "firebird", "chevelle", "cuda", "charger"]):
                return "Muscle"
            return "Classic"
        elif year < 1980:
            return "Classic"
        elif year < 2000:
            return "Modern Classic"
        else:
            return "USDM"

    # European brands
    if make_lower in ["porsche", "bmw", "mercedes-benz", "audi", "volkswagen", "jaguar", "aston martin", "ferrari", "lamborghini", "alfa romeo", "fiat", "lotus"]:
        if year < 1980:
            return "Classic"
        elif year < 2000:
            return "Modern Classic"
        else:
            return "Euro"

    # Japanese brands
    if make_lower in ["toyota", "nissan", "honda", "mazda", "subaru", "mitsubishi", "lexus", "infiniti", "acura", "datsun"]:
        if year < 1980:
            return "Classic"
        elif year < 2000:
            return "JDM"
        else:
            return "JDM"

    # Trucks and SUVs
    if any(truck in model_lower for truck in ["truck", "suv", "suburban", "tahoe", "excursion", "bronco", "blazer", "pickup", "f-150", "f150", "silverado", "sierra", "ram"]):
        if year < 1980:
            return "Hot Rod"
        elif year < 2000:
            return "Classic"
        else:
            return "Work Truck"

    # Default
    if year < 1980:
        return "Classic"
    elif year < 2000:
        return "Modern Classic"
    else:
        return "USDM"


def extract_json_ld(html_content: str) -> dict:
    """Extract JSON-LD structured data from HTML.

    Args:
        html_content: Raw HTML content

    Returns:
        Parsed JSON-LD data dict, or None if not found
    """
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html_content, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def find_vehicle_data(json_ld: dict) -> dict:
    """Find Vehicle/Product object in JSON-LD @graph.

    Args:
        json_ld: Parsed JSON-LD data

    Returns:
        Vehicle data dict, or None if not found
    """
    if not json_ld:
        return None

    graph = json_ld.get('@graph', [])

    # If graph is a list, find the Vehicle/Product object
    if isinstance(graph, list):
        for item in graph:
            item_type = item.get('@type', [])
            # Handle both string and list types
            types = item_type if isinstance(item_type, list) else [item_type]
            if any(t in ['Product', 'Vehicle'] for t in types):
                return item

    # If the main object is the Vehicle
    if json_ld.get('@type') in ['Product', 'Vehicle']:
        return json_ld

    return None


def parse_year_make_model(name: str) -> tuple:
    """Parse year, make, model from vehicle name.

    Args:
        name: Vehicle name (e.g., "2021 Porsche 718")

    Returns:
        Tuple of (year, make, model) as strings
    """
    if not name:
        return None, None, None

    parts = name.strip().split()

    # First part should be year
    year = None
    if parts and parts[0].isdigit() and len(parts[0]) == 4:
        year = parts[0]
        parts = parts[1:]

    # Second part is make
    make = parts[0] if parts else None

    # Rest is model
    model = " ".join(parts[1:]) if len(parts) > 1 else None

    return year, make, model


def extract_modifications_from_description(description: str) -> list:
    """Extract modifications from vehicle description.

    Gateway Classic Cars listings don't typically have detailed mod lists.
    This function looks for common modification keywords.

    Args:
        description: Vehicle description text

    Returns:
        List of modification names
    """
    if not description:
        return []

    mods = []
    desc_lower = description.lower()

    # Common modification keywords
    mod_keywords = [
        "aftermarket", "custom", "upgraded", "performance", "racing",
        "coilover", "exhaust", "intake", "turbo", "supercharger",
        "wheels", "suspension", "brakes", "stereo", "audio"
    ]

    for keyword in mod_keywords:
        if keyword in desc_lower:
            mods.append(keyword.capitalize())

    return mods


def extract_images(html_content: str) -> list:
    """Extract image URLs from HTML.

    Args:
        html_content: Raw HTML content

    Returns:
        List of image URLs
    """
    images = []

    # From JSON-LD
    json_ld = extract_json_ld(html_content)
    if json_ld:
        vehicle = find_vehicle_data(json_ld)
        if vehicle:
            json_images = vehicle.get('image', [])
            if isinstance(json_images, list):
                images.extend(json_images)
            elif json_images:
                images.append(json_images)

    # From meta tags (og:image, twitter:image)
    og_image = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html_content)
    if og_image:
        images.append(og_image.group(1))

    twitter_image = re.search(r'<meta[^>]*name=["\']twitter:image["\'][^>]*content=["\']([^"\']+)["\']', html_content)
    if twitter_image:
        images.append(twitter_image.group(1))

    # Deduplicate
    seen = set()
    unique_images = []
    for img in images:
        if img and img not in seen:
            seen.add(img)
            unique_images.append(img)

    return unique_images


def determine_era(year: int) -> str:
    """Determine vehicle era based on year.

    Args:
        year: Model year

    Returns:
        Era classification
    """
    if year < 1946:
        return "Pre-War"
    elif year < 1975:
        return "Classic"
    elif year < 1990:
        return "Vintage"
    elif year < 2005:
        return "Modern Classic"
    else:
        return "Modern"


def infer_transmission(transmission_str: str) -> str:
    """Normalize transmission string.

    Args:
        transmission_str: Raw transmission value

    Returns:
        Normalized transmission: Manual, Automatic, DCT, CVT, Sequential, or None
    """
    if not transmission_str:
        return None

    trans_lower = transmission_str.lower()

    if "manual" in trans_lower or "standard" in trans_lower:
        return "Manual"
    elif "automatic" in trans_lower or "auto" in trans_lower:
        return "Automatic"
    elif "dual" in trans_lower or "dct" in trans_lower or "pdk" in trans_lower:
        return "DCT"
    elif "cvt" in trans_lower:
        return "CVT"
    elif "sequential" in trans_lower:
        return "Sequential"

    return None


def infer_drivetrain(description: str, model: str) -> str:
    """Infer drivetrain from description and model.

    Args:
        description: Vehicle description
        model: Vehicle model

    Returns:
        Drivetrain: RWD, FWD, AWD, 4WD, or None
    """
    text = f"{description} {model}".lower()

    if "4wd" in text or "four wheel" in text or "4x4" in text:
        return "4WD"
    elif "awd" in text or "all wheel" in text:
        return "AWD"
    elif "fwd" in text or "front wheel" in text:
        return "FWD"
    elif "rwd" in text or "rear wheel" in text:
        return "RWD"

    # Default inference based on common RWD vehicles
    rwd_vehicles = ["mustang", "camaro", "charger", "challenger", "corvette", "911", "boxster", "cayman", "silvia", "rx7", "mx5", "miata"]
    if any(v in text for v in rwd_vehicles):
        return "RWD"

    return None


def extract_location_from_url(url: str) -> str:
    """Extract location from Gateway Classic Cars URL.

    Args:
        url: Vehicle URL

    Returns:
        Location string or None
    """
    # Gateway Classic Cars has multiple locations
    # URL pattern: /vehicles/{location_code}/{id}/{slug}
    match = re.search(r'/vehicles/([a-z]+)/\d+/', url)
    if match:
        location_codes = {
            "cha": "Charlotte, NC",
            "det": "Detroit, MI",
            "lou": "Louisville, KY",
            "nsh": "Nashville, TN",
            "den": "Denver, CO",
            "phx": "Phoenix, AZ",
            "tlh": "Tallahassee, FL",
            "mil": "Milwaukee, WI",
            "kc": "Kansas City, MO"
        }
        code = match.group(1)
        return location_codes.get(code, code.upper())

    return None


def extract_html_file(html_file: Path, manifest: dict) -> dict:
    """Extract build data from a single HTML file.

    Args:
        html_file: Path to HTML file
        manifest: Manifest dict with URL mapping

    Returns:
        Build data dict
    """
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

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
        url = f"https://www.gatewayclassiccars.com/vehicles/{slug}"

    # Extract JSON-LD data
    json_ld = extract_json_ld(html_content)
    vehicle = find_vehicle_data(json_ld) if json_ld else None

    if not vehicle:
        print(f"Warning: No vehicle data found in {filename}")
        return None

    # Parse basic info
    name = vehicle.get('name', '')
    year_str, make, model = parse_year_make_model(name)

    # Get year as integer
    year = int(year_str) if year_str and year_str.isdigit() else None

    # Infer build_type
    build_type = infer_build_type(year or 2000, make or '', model or '')

    # Extract offer/sale data
    offers = vehicle.get('offers', {})
    price_numeric = offers.get('price')
    listing_price = f"${price_numeric:,.0f}" if price_numeric else None

    # Extract mileage
    mileage_obj = vehicle.get('mileageFromOdometer')
    if mileage_obj:
        mileage_numeric = mileage_obj.get('value')
        mileage = f"{mileage_numeric:,} miles" if mileage_numeric else None
    else:
        mileage_numeric = None
        mileage = None

    # Extract VIN
    vin = vehicle.get('vehicleIdentificationNumber')

    # Extract engine
    engine_obj = vehicle.get('vehicleEngine')
    engine = engine_obj.get('name') if engine_obj else None

    # Extract transmission
    trans_str = vehicle.get('vehicleTransmission')
    transmission = infer_transmission(trans_str) if trans_str else None

    # Infer drivetrain
    drivetrain = infer_drivetrain(vehicle.get('description', ''), model or '')

    # Extract description
    description = vehicle.get('description', '')

    # Extract images
    gallery_images = extract_images(html_content)
    main_image = gallery_images[0] if gallery_images else None

    # Extract modifications
    modifications_raw = extract_modifications_from_description(description)
    modification_level = "Stock"
    if len(modifications_raw) > 15:
        modification_level = "Heavily Modified"
    elif len(modifications_raw) > 5:
        modification_level = "Moderately Modified"
    elif len(modifications_raw) > 1:
        modification_level = "Lightly Modified"

    # Get location
    location = extract_location_from_url(url)

    # Determine era
    era = determine_era(year) if year else None

    # Get SKU/stock number
    sku = vehicle.get('sku')

    # Build the record
    build = {
        "build_id": url_to_build_id(url),
        "source_type": "listing",
        "build_type": build_type,
        "build_source": "gatewayclassiccars.com",
        "source_url": url,
        "build_title": name,
        "year": year_str,
        "make": make,
        "model": model,
        "trim": None,
        "generation": None,
        "engine": engine,
        "transmission": transmission,
        "drivetrain": drivetrain,
        "exterior_color": None,
        "interior_color": None,
        "build_story": description,
        "owner_username": None,
        "gallery_images": gallery_images,
        "main_image": main_image,
        "modifications_raw": modifications_raw,
        "modification_level": modification_level,
        "vehicle_summary_extracted": None,
        "extraction_confidence": 0.9,
        "sale_data": {
            "status": "active",
            "is_auction": False,
            "price": listing_price,
            "price_numeric": price_numeric,
            "listing_price": listing_price,
            "listing_price_numeric": price_numeric,
            "currency": "USD",
            "no_reserve": None,
            "bid_count": None,
            "auction_type": None,
            "end_date": None,
            "vin": vin,
            "mileage": mileage,
            "mileage_numeric": mileage_numeric,
            "title_status": "clean",
            "body_style": None,
            "location": location,
            "lot_number": sku
        },
        "wheel_and_tire_fitment_specs": None,
        "build_stats": None,
        "metadata": {
            "era": era,
            "category": "Inventory",
            "highlights": [],
            "equipment": [],
            "published_date": None,
            "scraped_at": None,
            "scraper_metadata": {
                "extractor": "gateway_classic_cars_jsonld",
                "auction_id": sku,
                "page_type": "listing"
            }
        },
        "processing": {
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "extractor_version": "1.0.0",
            "model_used": None,
            "source_scraped_at": None
        },
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "vin": vin,
        "products": [],
        "build_nickname": None
    }

    return build


def main():
    """Main extraction function."""
    html_dir = Path("scraped_builds/gateway_classic_cars/html")
    manifest_file = Path("scraped_builds/gateway_classic_cars/manifest.json")
    output_file = Path("scraped_builds/gateway_classic_cars/builds.json")

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
