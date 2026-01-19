#!/usr/bin/env python3
"""
Source Discovery Script - Finds new vehicle build sources.

This script is designed to work with MCP tools (webSearchPrime, webReader) when run
through Ralph, or can be used standalone to generate search queries and process results.

Usage:
    # Generate search queries
    python scripts/tools/discover_sources.py --queries

    # Process search results (pipe from MCP or provide file)
    python scripts/tools/discover_sources.py --process <results.json>

    # Add validated source to sources.json
    python scripts/tools/discover_sources.py --add <source_entry.json>

    # List existing sources
    python scripts/tools/discover_sources.py --list

    # Show discovery stats
    python scripts/tools/discover_sources.py --stats
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Paths
SOURCES_FILE = "scripts/ralph/sources.json"
DISCOVERY_LOG = "logs/source_discovery.json"
CANDIDATES_FILE = "logs/source_candidates.json"

# Search query templates for different discovery strategies
SEARCH_QUERIES = {
    # === GENERAL CATEGORIES ===
    "build_showcase": [
        "car build showcase gallery modifications",
        "vehicle project builds parts list",
        "custom car portfolio builds specs",
        "modified vehicle showcase mods",
        "automotive build feature modifications",
    ],
    "forum_threads": [
        "build thread forum automotive modifications",
        "project car build log forum",
        "car build showcase forum parts list",
        "vehicle modification build thread",
    ],
    "tuner_shops": [
        "tuning shop customer builds portfolio",
        "performance shop builds gallery",
        "custom exhaust shop vehicle builds",
        "aftermarket parts shop build showcase",
    ],
    "wheel_fitment": [
        "wheel fitment gallery builds",
        "custom wheel offset showcase",
        "aftermarket wheels vehicle gallery",
        "fitment showcase modifications",
    ],
    "auctions": [
        "modified car auction site",
        "custom vehicle auction listings",
        "enthusiast car auction builds",
        "collector car auction modified",
    ],
    "publications": [
        "car build feature article magazine",
        "automotive project feature builds",
        "modified vehicle showcase publication",
        "project car article series mods",
    ],

    # === US VEHICLE-SPECIFIC ===
    "jdm": [
        "civic build showcase modifications",
        "s2000 build thread mods list",
        "miata mx5 build gallery parts",
        "wrx sti build showcase modifications",
        "240sx silvia build thread parts",
    ],
    "trucks": [
        "tacoma build showcase modifications",
        "f150 build thread mods list",
        "silverado build gallery parts",
        "4runner build showcase overland",
        "jeep wrangler build thread mods",
    ],
    "muscle": [
        "mustang build showcase modifications",
        "camaro build thread mods list",
        "corvette build gallery parts",
        "challenger charger build showcase",
    ],
    "european": [
        "golf gti build showcase modifications",
        "bmw m3 build thread mods list",
        "audi rs build gallery parts",
        "mercedes amg build showcase",
    ],
    "exotic": [
        "ferrari build showcase tuning",
        "lamborghini modifications gallery",
        "porsche 911 build thread mods",
        "mclaren build showcase parts",
    ],

    # === INTERNATIONAL MARKETS ===

    # Japan - Drift, VIP, Time Attack, Bosozoku
    "japan": [
        "日本 チューニング カスタム builds",  # Japanese tuning custom
        "japan tuning car builds modifications",
        "japanese drift builds showcase",
        "VIP style car builds japan",
        "time attack builds japan modifications",
        "japanese car meeting showcase builds",
        "option magazine style builds",
        "wangan midnight style builds mods",
        "HKS tuned car builds gallery",
        "RE Amemiya RX7 builds showcase",
        "Top Secret GTR builds modifications",
    ],

    # Germany - Autobahn, VAG, BMW tuning
    "germany": [
        "german tuning car builds modifications",
        "autobahn tuner builds showcase",
        "ABT tuning builds gallery",
        "Brabus mercedes builds modifications",
        "AC Schnitzer BMW builds showcase",
        "german VAG tuning builds forum",
        "MTM audi tuning builds",
        "Techart porsche builds modifications",
        "german car tuning magazine builds",
        "Essen motorshow car builds",
    ],

    # UK - Modified car scene, stance
    "uk": [
        "UK modified car builds showcase",
        "british car tuning builds forum",
        "UK stance builds gallery",
        "modified nationals car builds",
        "players classic car builds UK",
        "fast car magazine builds UK",
        "UK ford tuning builds RS",
        "vauxhall modified builds UK",
        "UK time attack builds showcase",
        "UK car meet builds gallery",
    ],

    # Australia - HSV, FPV, ute culture
    "australia": [
        "australian car builds modifications",
        "HSV holden builds showcase",
        "FPV ford australia builds",
        "australian ute builds modifications",
        "street machine builds australia",
        "summernats car builds showcase",
        "australian V8 builds forum",
        "aussie burnout car builds",
        "australian muscle car builds",
        "powercruise builds australia",
    ],

    # Scandinavia - Rally, Volvo, winter builds
    "scandinavia": [
        "scandinavian car builds modifications",
        "swedish volvo builds showcase",
        "finnish rally builds modifications",
        "norway stance builds gallery",
        "gatebil car builds showcase",
        "swedish drift builds forum",
        "saab tuning builds modifications",
        "nordic car meet builds",
        "volvo turbo builds showcase",
        "koenigsegg inspired builds",
    ],

    # Middle East - UAE, Saudi supercar tuning
    "middle_east": [
        "UAE supercar tuning builds",
        "dubai modified car builds showcase",
        "saudi arabia car builds gallery",
        "middle east luxury car tuning",
        "gulf car festival builds",
        "qatar car builds modifications",
        "arab drifting builds showcase",
        "dubai custom car builds forum",
        "middle east stance builds",
        "arabian car culture builds",
    ],

    # Brazil - VW scene, hot hatches
    "brazil": [
        "brazilian car builds modifications",
        "brasil tuning builds showcase",
        "VW fusca beetle builds brazil",
        "brazilian hot hatch builds",
        "gol GTI builds brazil modifications",
        "brazil car meet builds gallery",
        "fiat uno turbo builds brazil",
        "chevette builds brazil tuning",
        "opala builds brazil showcase",
        "salao do automovel builds",
    ],

    # Southeast Asia - Thailand, Indonesia, Malaysia
    "southeast_asia": [
        "thailand car builds modifications",
        "indonesian car builds showcase",
        "malaysian car builds forum",
        "bangkok auto salon builds",
        "indonesia modified car gallery",
        "proton builds malaysia tuning",
        "thai drift builds showcase",
        "singapore car builds modifications",
        "philippines car builds forum",
        "ASEAN car culture builds",
    ],

    # Russia - Lada, drift scene
    "russia": [
        "russian car builds modifications",
        "lada tuning builds showcase",
        "russian drift builds gallery",
        "VAZ builds russia modifications",
        "russian car tuning forum builds",
        "moscow tuning show builds",
        "russian stance builds showcase",
        "priora builds russia tuning",
        "russian JDM builds gallery",
        "russian car meet builds",
    ],

    # New Zealand - JDM imports, V8 culture
    "new_zealand": [
        "new zealand car builds modifications",
        "NZ JDM import builds showcase",
        "kiwi car builds forum",
        "new zealand V8 builds gallery",
        "NZ drift builds modifications",
        "new zealand stance builds",
        "NZ holden builds showcase",
        "wellington car meet builds",
        "auckland modified car builds",
        "new zealand ford builds",
    ],

    # Netherlands - VAG scene, lowered cars
    "netherlands": [
        "dutch car builds modifications",
        "netherlands VAG tuning builds",
        "dutch stance builds showcase",
        "holland car meet builds gallery",
        "dutch golf GTI builds forum",
        "netherlands modified car builds",
        "dutch lowrider builds showcase",
        "amsterdam car culture builds",
        "wörthersee dutch builds",
        "netherlands BMW builds tuning",
    ],

    # France - Peugeot, Renault, hot hatches
    "france": [
        "french car builds modifications",
        "peugeot GTI builds showcase france",
        "renault sport builds modifications",
        "french hot hatch builds forum",
        "clio RS builds france gallery",
        "megane RS builds modifications",
        "french tuning builds showcase",
        "alpine A110 builds france",
        "citroen DS builds modifications",
        "french car meet builds gallery",
    ],

    # South Korea - Hyundai, Kia, Genesis tuning
    "south_korea": [
        "korean car builds modifications",
        "hyundai tuning builds showcase",
        "kia stinger builds modifications",
        "genesis builds korea gallery",
        "korean car meet builds forum",
        "seoul motor show custom builds",
        "korean drift builds showcase",
        "korean stance builds gallery",
        "veloster N builds korea",
        "korean tuning shop builds",
    ],

    # Mexico - VW scene, lowriders
    "mexico": [
        "mexican car builds modifications",
        "mexico VW beetle vocho builds",
        "mexican lowrider builds showcase",
        "tsuru builds mexico tuning",
        "mexican car meet builds gallery",
        "mexico tuning builds forum",
        "mexican muscle car builds",
        "autoshow mexico custom builds",
        "mexican drift builds showcase",
        "mexico car culture builds",
    ],

    # Canada - Winter builds, truck culture
    "canada": [
        "canadian car builds modifications",
        "canada truck builds showcase",
        "canadian winter builds gallery",
        "canadian muscle car builds forum",
        "importfest canada builds",
        "CSCS time attack builds canada",
        "canadian drift builds showcase",
        "quebec car builds modifications",
        "alberta truck builds lifted",
        "canadian euro builds gallery",
    ],

    # Poland - Stance, drift scene
    "poland": [
        "polish car builds modifications",
        "poland stance builds showcase",
        "polish drift builds gallery",
        "polish car meet builds forum",
        "poland BMW builds modifications",
        "polish tuning builds showcase",
        "poznan motor show builds",
        "polish VAG builds gallery",
        "poland car culture builds",
        "polish project car builds",
    ],

    # South Africa - Spin culture, modified scene
    "south_africa": [
        "south african car builds modifications",
        "SA spin car builds showcase",
        "south africa modified builds gallery",
        "johannesburg car meet builds",
        "cape town car builds forum",
        "south african BMW builds modifications",
        "SA car culture builds showcase",
        "south african golf builds",
        "SA stance builds gallery",
        "south african tuning builds",
    ],
}

# Known good source patterns (for scoring)
GOOD_PATTERNS = [
    r'forum.*build',
    r'build.*thread',
    r'project.*car',
    r'showcase.*build',
    r'gallery.*mod',
    r'fitment.*wheel',
    r'auction.*enthusiast',
]

# Known bad patterns (to filter out)
BAD_PATTERNS = [
    r'facebook\.com',
    r'instagram\.com',
    r'tiktok\.com',
    r'youtube\.com',
    r'pinterest\.com',
    r'reddit\.com',  # Requires special handling
    r'ebay\.com',
    r'craigslist',
    r'autotrader\.com',
    r'cars\.com',
    r'cargurus\.com',
    r'carmax\.com',
    r'amazon\.com',
    r'wikipedia\.org',
]


def load_sources():
    """Load existing sources."""
    try:
        with open(SOURCES_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"sources": []}


def save_sources(data):
    """Save sources to file."""
    with open(SOURCES_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def load_discovery_log():
    """Load discovery log."""
    try:
        with open(DISCOVERY_LOG, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "sessions": [],
            "total_searches": 0,
            "total_candidates": 0,
            "total_added": 0,
            "skip_reasons": {}
        }


def save_discovery_log(log):
    """Save discovery log."""
    os.makedirs(os.path.dirname(DISCOVERY_LOG), exist_ok=True)
    with open(DISCOVERY_LOG, 'w') as f:
        json.dump(log, f, indent=2)


def get_existing_domains():
    """Get set of existing source domains."""
    sources = load_sources()
    domains = set()
    for source in sources.get("sources", []):
        url = source.get("url", "")
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace('www.', '')
        domains.add(domain)
    return domains


def extract_domain(url):
    """Extract domain from URL."""
    parsed = urlparse(url)
    return parsed.netloc.lower().replace('www.', '')


def is_bad_pattern(url):
    """Check if URL matches a bad pattern."""
    url_lower = url.lower()
    for pattern in BAD_PATTERNS:
        if re.search(pattern, url_lower):
            return True
    return False


def score_url(url, title="", snippet=""):
    """Score a URL based on relevance."""
    score = 0.5  # Base score
    combined = f"{url} {title} {snippet}".lower()

    # Good patterns
    for pattern in GOOD_PATTERNS:
        if re.search(pattern, combined):
            score += 0.1

    # Vehicle mentions
    vehicle_keywords = ["build", "mod", "custom", "project", "tuned", "modified"]
    for keyword in vehicle_keywords:
        if keyword in combined:
            score += 0.05

    # Penalty for bad indicators
    bad_indicators = ["price", "buy now", "for sale", "dealer", "inventory"]
    for indicator in bad_indicators:
        if indicator in combined:
            score -= 0.1

    return max(0.0, min(1.0, score))


def generate_queries(categories=None, limit=None):
    """Generate search queries."""
    queries = []

    if categories:
        for cat in categories:
            if cat in SEARCH_QUERIES:
                queries.extend(SEARCH_QUERIES[cat])
    else:
        for cat_queries in SEARCH_QUERIES.values():
            queries.extend(cat_queries)

    # Dedupe while preserving order
    seen = set()
    unique = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    if limit:
        unique = unique[:limit]

    return unique


def process_search_results(results):
    """
    Process search results and return candidate sources.

    Expected input format (from MCP webSearchPrime):
    {
        "results": [
            {"url": "...", "title": "...", "snippet": "..."},
            ...
        ]
    }
    """
    existing = get_existing_domains()
    candidates = []
    skipped = {"duplicate": 0, "bad_pattern": 0, "low_score": 0}

    for result in results.get("results", []):
        url = result.get("url", "")
        title = result.get("title", "")
        snippet = result.get("snippet", "")

        if not url:
            continue

        domain = extract_domain(url)

        # Check if already exists
        if domain in existing:
            skipped["duplicate"] += 1
            continue

        # Check bad patterns
        if is_bad_pattern(url):
            skipped["bad_pattern"] += 1
            continue

        # Score the URL
        score = score_url(url, title, snippet)

        if score < 0.4:
            skipped["low_score"] += 1
            continue

        candidates.append({
            "url": url,
            "domain": domain,
            "title": title,
            "snippet": snippet,
            "score": score,
            "discovered_at": datetime.now().isoformat()
        })

    # Sort by score
    candidates.sort(key=lambda x: x["score"], reverse=True)

    return {
        "candidates": candidates,
        "skipped": skipped,
        "total_processed": len(results.get("results", []))
    }


def add_source(entry, sources_file=SOURCES_FILE):
    """Add a validated source to sources.json."""
    data = load_sources()

    # Check for duplicate
    existing_ids = {s.get("id") for s in data.get("sources", [])}
    if entry.get("id") in existing_ids:
        return {"success": False, "error": f"Source ID '{entry['id']}' already exists"}

    existing_domains = get_existing_domains()
    domain = extract_domain(entry.get("url", ""))
    if domain in existing_domains:
        return {"success": False, "error": f"Domain '{domain}' already has a source"}

    # Add discovery metadata if not present
    if "discovery" not in entry:
        entry["discovery"] = {
            "discovered_at": datetime.now().isoformat(),
            "discovered_by": "discover_sources.py"
        }

    # Add required fields if missing
    if "pipeline" not in entry:
        entry["pipeline"] = {
            "expectedUrls": None,
            "urlsFound": None,
            "htmlScraped": None,
            "htmlFailed": None,
            "htmlBlocked": None,
            "builds": None,
            "mods": None
        }

    if "status" not in entry:
        entry["status"] = "pending"

    if "notes" not in entry:
        entry["notes"] = ""

    # Add to sources
    data["sources"].append(entry)
    save_sources(data)

    # Update discovery log
    log = load_discovery_log()
    log["total_added"] = log.get("total_added", 0) + 1
    save_discovery_log(log)

    return {"success": True, "source_id": entry["id"]}


def list_sources(status=None):
    """List sources, optionally filtered by status."""
    data = load_sources()
    sources = data.get("sources", [])

    if status:
        sources = [s for s in sources if s.get("status") == status]

    return sources


def get_stats():
    """Get discovery statistics."""
    sources = load_sources()
    log = load_discovery_log()

    stats = {
        "total_sources": len(sources.get("sources", [])),
        "by_status": {},
        "discovery_log": {
            "total_searches": log.get("total_searches", 0),
            "total_candidates": log.get("total_candidates", 0),
            "total_added": log.get("total_added", 0),
            "sessions": len(log.get("sessions", []))
        }
    }

    for source in sources.get("sources", []):
        status = source.get("status", "unknown")
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

    return stats


def generate_source_id(name):
    """Generate a valid source ID from name."""
    id_str = re.sub(r'[^a-zA-Z0-9\s]', '', name)
    id_str = re.sub(r'\s+', '_', id_str.strip())
    return id_str.lower()


def create_source_entry(url, name=None, validation_notes=""):
    """Create a source entry from URL."""
    domain = extract_domain(url)

    if not name:
        # Generate name from domain
        name = domain.replace('.com', '').replace('.net', '').replace('.org', '')
        name = ' '.join(word.capitalize() for word in name.split('.'))

    source_id = generate_source_id(name)

    return {
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
            "discovered_by": "discover_sources.py",
            "validation_notes": validation_notes
        },
        "notes": ""
    }


def main():
    parser = argparse.ArgumentParser(description="Source Discovery Script")
    parser.add_argument("--queries", "-q", action="store_true",
                       help="Generate search queries")
    parser.add_argument("--categories", "-c", nargs="+",
                       choices=list(SEARCH_QUERIES.keys()),
                       help="Query categories to use")
    parser.add_argument("--limit", "-l", type=int, default=10,
                       help="Limit number of queries (default: 10)")
    parser.add_argument("--process", "-p", help="Process search results file")
    parser.add_argument("--add", "-a", help="Add source from JSON file")
    parser.add_argument("--add-url", "-u", help="Add source from URL directly")
    parser.add_argument("--name", "-n", help="Name for URL (with --add-url)")
    parser.add_argument("--list", action="store_true", help="List sources")
    parser.add_argument("--status", "-s", help="Filter by status (with --list)")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")

    args = parser.parse_args()

    if args.queries:
        queries = generate_queries(args.categories, args.limit)
        if args.json:
            print(json.dumps({"queries": queries}, indent=2))
        else:
            print(f"Generated {len(queries)} search queries:\n")
            for i, q in enumerate(queries, 1):
                print(f"{i}. {q}")

    elif args.process:
        try:
            with open(args.process, 'r') as f:
                results = json.load(f)
        except FileNotFoundError:
            print(f"Error: File not found: {args.process}", file=sys.stderr)
            sys.exit(2)

        processed = process_search_results(results)

        if args.json:
            print(json.dumps(processed, indent=2))
        else:
            print(f"Processed {processed['total_processed']} results")
            print(f"Found {len(processed['candidates'])} candidates")
            print(f"Skipped: {processed['skipped']}")
            print("\nTop candidates:")
            for c in processed['candidates'][:10]:
                print(f"  [{c['score']:.2f}] {c['domain']}: {c['title'][:50]}...")

    elif args.add:
        try:
            with open(args.add, 'r') as f:
                entry = json.load(f)
        except FileNotFoundError:
            print(f"Error: File not found: {args.add}", file=sys.stderr)
            sys.exit(2)

        result = add_source(entry)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result["success"]:
                print(f"Added source: {result['source_id']}")
            else:
                print(f"Error: {result['error']}")
                sys.exit(1)

    elif args.add_url:
        entry = create_source_entry(args.add_url, args.name)
        result = add_source(entry)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result["success"]:
                print(f"Added source: {result['source_id']}")
                print(json.dumps(entry, indent=2))
            else:
                print(f"Error: {result['error']}")
                sys.exit(1)

    elif args.list:
        sources = list_sources(args.status)
        if args.json:
            print(json.dumps(sources, indent=2))
        else:
            print(f"Sources ({len(sources)}):\n")
            for s in sources:
                print(f"  [{s.get('status', 'unknown')}] {s.get('id')}: {s.get('name')}")
                print(f"           URL: {s.get('url')}")

    elif args.stats:
        stats = get_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("Source Discovery Statistics")
            print("=" * 40)
            print(f"Total sources: {stats['total_sources']}")
            print("\nBy status:")
            for status, count in stats['by_status'].items():
                print(f"  {status}: {count}")
            print("\nDiscovery log:")
            for key, val in stats['discovery_log'].items():
                print(f"  {key}: {val}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
