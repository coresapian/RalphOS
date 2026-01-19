#!/usr/bin/env python3
"""
Source Validator - Validates potential vehicle build sources.

Usage:
    python scripts/tools/validate_source.py <url> [--verbose]
    python scripts/tools/validate_source.py --json <url>  # Output JSON
    python scripts/tools/validate_source.py --batch <file>  # Validate multiple URLs

Exit codes:
    0 = Valid source (recommended to add)
    1 = Invalid source (should skip)
    2 = Error (could not validate)
"""

import argparse
import json
import re
import sys
from datetime import datetime
from urllib.parse import urlparse, urljoin
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    parsed = urlparse(url)
    return parsed.netloc.lower().replace('www.', '')


def generate_source_id(name: str) -> str:
    """Generate source_id from name."""
    # Remove special chars, lowercase, replace spaces with underscores
    id_str = re.sub(r'[^a-zA-Z0-9\s]', '', name)
    id_str = re.sub(r'\s+', '_', id_str.strip())
    return id_str.lower()


def check_existing_sources(url: str, sources_file: str = "scripts/ralph/sources.json") -> dict:
    """Check if source already exists in sources.json."""
    result = {
        "exists": False,
        "existing_id": None,
        "domain_match": False
    }

    try:
        with open(sources_file, 'r') as f:
            data = json.load(f)

        domain = extract_domain(url)

        for source in data.get("sources", []):
            source_domain = extract_domain(source.get("url", ""))

            # Check exact URL match
            if source.get("url", "").rstrip('/') == url.rstrip('/'):
                result["exists"] = True
                result["existing_id"] = source.get("id")
                return result

            # Check domain match
            if source_domain == domain:
                result["domain_match"] = True
                result["existing_id"] = source.get("id")

    except FileNotFoundError:
        pass
    except json.JSONDecodeError:
        pass

    return result


def analyze_page_content(content: str) -> dict:
    """Analyze page content for vehicle build indicators."""
    analysis = {
        "has_vehicle_mentions": False,
        "has_modification_mentions": False,
        "has_individual_links": False,
        "has_pagination": False,
        "is_static_gallery": False,
        "requires_auth": False,
        "is_javascript_heavy": False,
        "is_dealership": False,
        "vehicle_types_found": [],
        "mod_keywords_found": [],
        "link_count": 0,
        "confidence_score": 0.0
    }

    content_lower = content.lower()

    # Vehicle type keywords
    vehicle_keywords = {
        "jdm": ["civic", "integra", "s2000", "240sx", "silvia", "rx-7", "rx7", "miata", "mx-5", "wrx", "sti", "evo", "lancer", "supra", "skyline", "gtr", "gt-r"],
        "american_muscle": ["mustang", "camaro", "corvette", "challenger", "charger", "firebird", "trans am", "chevelle", "gto", "nova"],
        "truck": ["f-150", "f150", "silverado", "tacoma", "tundra", "ram", "colorado", "ranger", "frontier"],
        "offroad": ["jeep", "wrangler", "4runner", "land cruiser", "bronco", "defender", "land rover"],
        "european": ["golf", "gti", "m3", "m4", "m5", "rs3", "rs6", "c63", "amg", "911", "porsche", "cayman", "boxster"],
        "exotic": ["ferrari", "lamborghini", "mclaren", "aston martin", "bentley", "rolls-royce"]
    }

    for category, keywords in vehicle_keywords.items():
        for keyword in keywords:
            if keyword in content_lower:
                analysis["has_vehicle_mentions"] = True
                if category not in analysis["vehicle_types_found"]:
                    analysis["vehicle_types_found"].append(category)

    # Modification keywords
    mod_keywords = [
        # Suspension
        "coilovers", "lowering springs", "air suspension", "lift kit", "suspension",
        # Engine
        "turbo", "supercharger", "intake", "exhaust", "headers", "downpipe", "tune", "tuned", "ecu",
        # Wheels
        "wheels", "rims", "offset", "spacers", "fitment",
        # Exterior
        "body kit", "widebody", "spoiler", "wing", "wrap", "paint",
        # Interior
        "seats", "steering wheel", "roll cage", "harness",
        # Brakes
        "big brake kit", "bbk", "rotors", "calipers", "brake",
        # Drivetrain
        "clutch", "flywheel", "differential", "lsd", "transmission swap"
    ]

    for keyword in mod_keywords:
        if keyword in content_lower:
            analysis["has_modification_mentions"] = True
            if keyword not in analysis["mod_keywords_found"]:
                analysis["mod_keywords_found"].append(keyword)

    # Check for individual page links (build pages, threads, projects)
    link_patterns = [
        r'href=["\'][^"\']*/(build|project|thread|vehicle|car|listing|auction)[s]?/[^"\']+["\']',
        r'href=["\'][^"\']*\.(html?|php)["\']',
        r'href=["\'][^"\']+/\d+/?["\']',  # Numeric IDs
    ]

    for pattern in link_patterns:
        matches = re.findall(pattern, content_lower)
        if matches:
            analysis["has_individual_links"] = True
            analysis["link_count"] = max(analysis["link_count"], len(matches))

    # Check for pagination
    pagination_patterns = [
        r'page[=/-]?\d+',
        r'(next|prev|previous)\s*(page)?',
        r'class=["\'][^"\']*pagination[^"\']*["\']',
        r'aria-label=["\'][^"\']*page[^"\']*["\']'
    ]

    for pattern in pagination_patterns:
        if re.search(pattern, content_lower):
            analysis["has_pagination"] = True
            break

    # Check for static gallery indicators
    static_gallery_patterns = [
        r'<img[^>]*>((?!</a>).)*$',  # Images not wrapped in links
        r'class=["\'][^"\']*gallery[^"\']*masonry[^"\']*["\']',
        r'class=["\'][^"\']*lightbox[^"\']*["\']'
    ]

    # Check for auth requirements
    auth_patterns = [
        r'(login|sign.?in|log.?in|register|create.?account)',
        r'(members?.?only|subscribers?.?only)',
        r'<form[^>]*action=["\'][^"\']*login'
    ]

    for pattern in auth_patterns:
        if re.search(pattern, content_lower):
            analysis["requires_auth"] = True
            break

    # Check for JavaScript-heavy indicators
    js_heavy_patterns = [
        r'<script[^>]*src=["\'][^"\']*react',
        r'<script[^>]*src=["\'][^"\']*angular',
        r'<script[^>]*src=["\'][^"\']*vue',
        r'__NEXT_DATA__',
        r'window\.__INITIAL_STATE__',
        r'data-react-',
        r'ng-app'
    ]

    for pattern in js_heavy_patterns:
        if re.search(pattern, content_lower):
            analysis["is_javascript_heavy"] = True
            break

    # Check for dealership indicators
    dealer_patterns = [
        r'(buy.?now|add.?to.?cart|price|msrp|\$[\d,]+)',
        r'(dealer|dealership|inventory|for.?sale)',
        r'(financing|trade.?in|test.?drive)',
        r'(carfax|autocheck|vehicle.?history)'
    ]

    dealer_count = 0
    for pattern in dealer_patterns:
        if re.search(pattern, content_lower):
            dealer_count += 1

    if dealer_count >= 3:
        analysis["is_dealership"] = True

    # Calculate confidence score
    score = 0.0

    if analysis["has_vehicle_mentions"]:
        score += 0.2
    if analysis["has_modification_mentions"]:
        score += 0.3
    if analysis["has_individual_links"]:
        score += 0.2
    if analysis["has_pagination"]:
        score += 0.1

    # Penalties
    if analysis["is_static_gallery"]:
        score -= 0.3
    if analysis["requires_auth"]:
        score -= 0.2
    if analysis["is_javascript_heavy"]:
        score -= 0.1
    if analysis["is_dealership"]:
        score -= 0.4

    # Bonus for variety
    if len(analysis["vehicle_types_found"]) >= 2:
        score += 0.1
    if len(analysis["mod_keywords_found"]) >= 3:
        score += 0.1

    analysis["confidence_score"] = max(0.0, min(1.0, score))

    return analysis


def validate_source(url: str, content: str = None, verbose: bool = False) -> dict:
    """
    Validate a potential source.

    Returns dict with:
        - valid: bool
        - reason: str
        - recommendation: str
        - analysis: dict
        - suggested_entry: dict (if valid)
    """
    result = {
        "url": url,
        "valid": False,
        "reason": "",
        "recommendation": "skip",
        "analysis": None,
        "suggested_entry": None,
        "validated_at": datetime.now().isoformat()
    }

    # Check if already exists
    existing = check_existing_sources(url)
    if existing["exists"]:
        result["reason"] = f"Already exists in sources.json as '{existing['existing_id']}'"
        result["recommendation"] = "skip_duplicate"
        return result

    if existing["domain_match"]:
        result["reason"] = f"Domain already has source '{existing['existing_id']}' - may be duplicate"
        result["recommendation"] = "review_duplicate"

    # Analyze content if provided
    if content:
        analysis = analyze_page_content(content)
        result["analysis"] = analysis

        # Validation checks
        if analysis["is_dealership"]:
            result["reason"] = "Appears to be a dealership inventory site"
            result["recommendation"] = "skip_dealership"
            return result

        if analysis["requires_auth"]:
            result["reason"] = "Requires authentication/login"
            result["recommendation"] = "skip_auth_required"
            return result

        if not analysis["has_vehicle_mentions"]:
            result["reason"] = "No vehicle-related content found"
            result["recommendation"] = "skip_no_vehicles"
            return result

        if not analysis["has_modification_mentions"]:
            result["reason"] = "No modification/parts content found"
            result["recommendation"] = "skip_no_mods"
            return result

        if not analysis["has_individual_links"] and analysis["is_static_gallery"]:
            result["reason"] = "Static gallery without individual build pages"
            result["recommendation"] = "skip_static_gallery"
            return result

        if analysis["is_javascript_heavy"] and not analysis["has_individual_links"]:
            result["reason"] = "JavaScript-heavy site, may require browser automation"
            result["recommendation"] = "review_js_heavy"
            return result

        # Check confidence score
        if analysis["confidence_score"] < 0.3:
            result["reason"] = f"Low confidence score ({analysis['confidence_score']:.2f})"
            result["recommendation"] = "review_low_confidence"
            return result

        # Valid source!
        result["valid"] = True
        result["reason"] = f"Valid source (confidence: {analysis['confidence_score']:.2f})"
        result["recommendation"] = "add_to_queue"

        # Generate suggested entry
        domain = extract_domain(url)
        name = domain.replace('.com', '').replace('.net', '').replace('.org', '')
        name = ' '.join(word.capitalize() for word in name.split('.'))
        source_id = generate_source_id(name)

        result["suggested_entry"] = {
            "id": source_id,
            "name": name,
            "url": url,
            "outputDir": f"data/{source_id}",
            "status": "pending",
            "pipeline": {
                "expectedUrls": None,
                "urlsFound": None,
                "htmlScraped": None,
                "htmlFailed": None,
                "htmlBlocked": None,
                "builds": None,
                "mods": None
            },
            "discovery": {
                "discovered_at": datetime.now().isoformat(),
                "discovered_by": "source_discovery_ralph",
                "confidence_score": analysis["confidence_score"],
                "vehicle_types": analysis["vehicle_types_found"],
                "mod_keywords": analysis["mod_keywords_found"][:5]  # Top 5
            },
            "notes": ""
        }
    else:
        result["reason"] = "No content provided for analysis"
        result["recommendation"] = "needs_fetch"

    return result


def main():
    parser = argparse.ArgumentParser(description="Validate potential vehicle build sources")
    parser.add_argument("url", nargs="?", help="URL to validate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")
    parser.add_argument("--batch", "-b", help="Batch validate URLs from file")
    parser.add_argument("--content", "-c", help="HTML content to analyze (optional)")
    parser.add_argument("--content-file", "-f", help="File containing HTML content")

    args = parser.parse_args()

    if args.batch:
        # Batch mode
        try:
            with open(args.batch, 'r') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        except FileNotFoundError:
            print(f"Error: Batch file not found: {args.batch}", file=sys.stderr)
            sys.exit(2)

        results = []
        for url in urls:
            result = validate_source(url, verbose=args.verbose)
            results.append(result)
            if not args.json:
                status = "VALID" if result["valid"] else "SKIP"
                print(f"[{status}] {url}: {result['reason']}")

        if args.json:
            print(json.dumps(results, indent=2))

        valid_count = sum(1 for r in results if r["valid"])
        print(f"\nSummary: {valid_count}/{len(results)} valid sources")
        sys.exit(0 if valid_count > 0 else 1)

    elif args.url:
        # Single URL mode
        content = None

        if args.content:
            content = args.content
        elif args.content_file:
            try:
                with open(args.content_file, 'r') as f:
                    content = f.read()
            except FileNotFoundError:
                print(f"Error: Content file not found: {args.content_file}", file=sys.stderr)
                sys.exit(2)

        result = validate_source(args.url, content=content, verbose=args.verbose)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"URL: {result['url']}")
            print(f"Valid: {result['valid']}")
            print(f"Reason: {result['reason']}")
            print(f"Recommendation: {result['recommendation']}")

            if args.verbose and result["analysis"]:
                print(f"\nAnalysis:")
                print(f"  Vehicle mentions: {result['analysis']['has_vehicle_mentions']}")
                print(f"  Modification mentions: {result['analysis']['has_modification_mentions']}")
                print(f"  Individual links: {result['analysis']['has_individual_links']}")
                print(f"  Pagination: {result['analysis']['has_pagination']}")
                print(f"  Confidence: {result['analysis']['confidence_score']:.2f}")
                print(f"  Vehicle types: {', '.join(result['analysis']['vehicle_types_found'])}")
                print(f"  Mod keywords: {', '.join(result['analysis']['mod_keywords_found'][:5])}")

            if result["suggested_entry"]:
                print(f"\nSuggested source entry:")
                print(json.dumps(result["suggested_entry"], indent=2))

        sys.exit(0 if result["valid"] else 1)

    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
