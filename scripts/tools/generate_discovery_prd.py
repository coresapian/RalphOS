#!/usr/bin/env python3
"""
Generate Discovery PRD - Creates PRD files for source discovery sessions.

Usage:
    # Quick discovery session (5 queries)
    python scripts/tools/generate_discovery_prd.py --quick

    # Standard discovery session (10 queries)
    python scripts/tools/generate_discovery_prd.py

    # Deep discovery session (all categories)
    python scripts/tools/generate_discovery_prd.py --deep

    # Target specific vehicle types
    python scripts/tools/generate_discovery_prd.py --categories jdm trucks muscle

    # Target minimum new sources
    python scripts/tools/generate_discovery_prd.py --target 10
"""

import argparse
import json
import os
from datetime import datetime

PRD_FILE = "scripts/ralph/prd.json"

# Discovery categories and their search priorities
DISCOVERY_CATEGORIES = {
    # === GENERAL CATEGORIES ===
    "build_showcase": {
        "name": "Build Showcases",
        "description": "General car build showcase and portfolio sites",
        "priority": 1,
        "region": "general"
    },
    "forum_threads": {
        "name": "Forum Build Threads",
        "description": "Automotive forums with build thread sections",
        "priority": 2,
        "region": "general"
    },
    "tuner_shops": {
        "name": "Tuner Shop Portfolios",
        "description": "Performance shops showcasing customer builds",
        "priority": 3,
        "region": "general"
    },
    "wheel_fitment": {
        "name": "Wheel Fitment Galleries",
        "description": "Wheel and fitment showcase sites",
        "priority": 4,
        "region": "general"
    },
    "auctions": {
        "name": "Auction Sites",
        "description": "Modified vehicle auction platforms",
        "priority": 5,
        "region": "general"
    },
    "publications": {
        "name": "Automotive Publications",
        "description": "Car magazines and build feature sites",
        "priority": 6,
        "region": "general"
    },

    # === US VEHICLE-SPECIFIC ===
    "jdm": {
        "name": "JDM Builds (US)",
        "description": "Japanese domestic market vehicle builds in US",
        "priority": 7,
        "region": "us"
    },
    "trucks": {
        "name": "Truck/Off-Road Builds",
        "description": "Trucks, overlanders, and off-road vehicles",
        "priority": 8,
        "region": "us"
    },
    "muscle": {
        "name": "American Muscle",
        "description": "Classic and modern muscle car builds",
        "priority": 9,
        "region": "us"
    },
    "european": {
        "name": "European Builds (US)",
        "description": "BMW, Audi, Mercedes, VW, Porsche builds in US",
        "priority": 10,
        "region": "us"
    },
    "exotic": {
        "name": "Exotic/Supercar Builds",
        "description": "Ferrari, Lamborghini, McLaren tuning",
        "priority": 11,
        "region": "us"
    },

    # === INTERNATIONAL MARKETS ===
    "japan": {
        "name": "Japan",
        "description": "Japanese tuning - drift, VIP, time attack, bosozoku",
        "priority": 12,
        "region": "international"
    },
    "germany": {
        "name": "Germany",
        "description": "German tuning - ABT, Brabus, AC Schnitzer, autobahn builds",
        "priority": 13,
        "region": "international"
    },
    "uk": {
        "name": "United Kingdom",
        "description": "UK modified scene - stance, Ford RS, track day builds",
        "priority": 14,
        "region": "international"
    },
    "australia": {
        "name": "Australia",
        "description": "Australian builds - HSV, FPV, ute culture, burnout cars",
        "priority": 15,
        "region": "international"
    },
    "scandinavia": {
        "name": "Scandinavia",
        "description": "Nordic builds - Gatebil, Volvo, rally, winter builds",
        "priority": 16,
        "region": "international"
    },
    "middle_east": {
        "name": "Middle East",
        "description": "Gulf region - Dubai supercars, luxury tuning",
        "priority": 17,
        "region": "international"
    },
    "brazil": {
        "name": "Brazil",
        "description": "Brazilian builds - VW Fusca, hot hatches, Opala",
        "priority": 18,
        "region": "international"
    },
    "southeast_asia": {
        "name": "Southeast Asia",
        "description": "Thai, Indonesian, Malaysian car culture builds",
        "priority": 19,
        "region": "international"
    },
    "russia": {
        "name": "Russia",
        "description": "Russian builds - Lada/VAZ tuning, drift scene",
        "priority": 20,
        "region": "international"
    },
    "new_zealand": {
        "name": "New Zealand",
        "description": "NZ builds - JDM imports, V8 culture",
        "priority": 21,
        "region": "international"
    },
    "netherlands": {
        "name": "Netherlands",
        "description": "Dutch builds - VAG scene, stance, Wörthersee style",
        "priority": 22,
        "region": "international"
    },
    "france": {
        "name": "France",
        "description": "French builds - Peugeot GTI, Renault Sport, hot hatches",
        "priority": 23,
        "region": "international"
    },
    "south_korea": {
        "name": "South Korea",
        "description": "Korean builds - Hyundai, Kia, Genesis tuning",
        "priority": 24,
        "region": "international"
    },
    "mexico": {
        "name": "Mexico",
        "description": "Mexican builds - VW Vocho, lowriders, Tsuru",
        "priority": 25,
        "region": "international"
    },
    "canada": {
        "name": "Canada",
        "description": "Canadian builds - winter builds, truck culture",
        "priority": 26,
        "region": "international"
    },
    "poland": {
        "name": "Poland",
        "description": "Polish builds - stance, BMW, drift scene",
        "priority": 27,
        "region": "international"
    },
    "south_africa": {
        "name": "South Africa",
        "description": "SA builds - spin culture, Golf scene",
        "priority": 28,
        "region": "international"
    },
}

# Helper functions to get categories by region
def get_categories_by_region(region):
    """Get categories filtered by region."""
    return [k for k, v in DISCOVERY_CATEGORIES.items() if v.get("region") == region]

def get_international_categories():
    """Get all international market categories."""
    return get_categories_by_region("international")

def get_us_categories():
    """Get US-specific categories."""
    return get_categories_by_region("us")

def get_general_categories():
    """Get general categories."""
    return get_categories_by_region("general")


def generate_quick_prd():
    """Generate a quick discovery PRD (5 searches)."""
    return {
        "projectName": "Source Discovery - Quick Session",
        "branchName": "main",
        "mode": "discovery",
        "targetNewSources": 3,
        "maxIterations": 10,
        "userStories": [
            {
                "id": "DISC-001",
                "title": "Search for build showcase sites",
                "acceptanceCriteria": [
                    "Execute 2 web searches for build showcase sites",
                    "Validate each result URL with webReader",
                    "Document results in discovery log"
                ],
                "searchCategory": "build_showcase",
                "priority": 1,
                "passes": False
            },
            {
                "id": "DISC-002",
                "title": "Search for forum build threads",
                "acceptanceCriteria": [
                    "Execute 2 web searches for forum build thread sections",
                    "Validate each result URL with webReader",
                    "Document results in discovery log"
                ],
                "searchCategory": "forum_threads",
                "priority": 2,
                "passes": False
            },
            {
                "id": "DISC-003",
                "title": "Validate and add new sources",
                "acceptanceCriteria": [
                    "Run validate_source.py on each candidate",
                    "Add valid sources to sources.json",
                    "Update sources.json with discovery metadata"
                ],
                "priority": 3,
                "passes": False
            }
        ],
        "createdAt": datetime.now().isoformat(),
        "discoveryConfig": {
            "categories": ["build_showcase", "forum_threads"],
            "queriesPerCategory": 2,
            "minConfidenceScore": 0.4
        }
    }


def generate_standard_prd():
    """Generate a standard discovery PRD (10 searches)."""
    return {
        "projectName": "Source Discovery - Standard Session",
        "branchName": "main",
        "mode": "discovery",
        "targetNewSources": 5,
        "maxIterations": 20,
        "userStories": [
            {
                "id": "DISC-001",
                "title": "Search for build showcase and tuner sites",
                "acceptanceCriteria": [
                    "Execute 3 web searches for build showcase sites",
                    "Execute 2 web searches for tuner shop portfolios",
                    "Validate promising results with webReader"
                ],
                "searchCategories": ["build_showcase", "tuner_shops"],
                "priority": 1,
                "passes": False
            },
            {
                "id": "DISC-002",
                "title": "Search for forum and community sites",
                "acceptanceCriteria": [
                    "Execute 3 web searches for forum build threads",
                    "Execute 2 web searches for wheel fitment galleries",
                    "Validate promising results with webReader"
                ],
                "searchCategories": ["forum_threads", "wheel_fitment"],
                "priority": 2,
                "passes": False
            },
            {
                "id": "DISC-003",
                "title": "Validate candidate sources",
                "acceptanceCriteria": [
                    "Fetch main page of each candidate with webReader",
                    "Check for individual build page links",
                    "Verify modifications are listed",
                    "Score each candidate (0-1)"
                ],
                "priority": 3,
                "passes": False
            },
            {
                "id": "DISC-004",
                "title": "Add validated sources to queue",
                "acceptanceCriteria": [
                    "Add sources with score >= 0.4 to sources.json",
                    "Set status to 'pending'",
                    "Include discovery metadata",
                    "Update discovery log"
                ],
                "priority": 4,
                "passes": False
            }
        ],
        "createdAt": datetime.now().isoformat(),
        "discoveryConfig": {
            "categories": ["build_showcase", "tuner_shops", "forum_threads", "wheel_fitment"],
            "queriesPerCategory": 2,
            "minConfidenceScore": 0.4
        }
    }


def generate_deep_prd():
    """Generate a deep discovery PRD (all categories including international)."""
    stories = []
    story_num = 1

    # Group categories into batches - US and general first
    us_batches = [
        ["build_showcase", "forum_threads"],
        ["tuner_shops", "wheel_fitment"],
        ["auctions", "publications"],
        ["jdm", "trucks"],
        ["muscle", "european"],
        ["exotic"]
    ]

    # International batches
    intl_batches = [
        ["japan", "germany", "uk"],
        ["australia", "scandinavia", "new_zealand"],
        ["middle_east", "brazil", "mexico"],
        ["southeast_asia", "russia", "south_korea"],
        ["netherlands", "france", "poland", "south_africa"],
        ["canada"]
    ]

    all_batches = us_batches + intl_batches

    for batch in all_batches:
        batch_names = [DISCOVERY_CATEGORIES[c]["name"] for c in batch if c in DISCOVERY_CATEGORIES]
        if not batch_names:
            continue
        stories.append({
            "id": f"DISC-{story_num:03d}",
            "title": f"Search: {', '.join(batch_names)}",
            "acceptanceCriteria": [
                f"Execute 2 web searches per category ({', '.join(batch)})",
                "Validate promising results with webReader",
                "Document candidates with scores"
            ],
            "searchCategories": batch,
            "priority": story_num,
            "passes": False
        })
        story_num += 1

    # Add validation and addition stories
    stories.append({
        "id": f"DISC-{story_num:03d}",
        "title": "Deep validation of all candidates",
        "acceptanceCriteria": [
            "Fetch sample build page from each candidate",
            "Verify vehicle info is present (year, make, model)",
            "Verify modifications are listed",
            "Check pagination accessibility",
            "Score each candidate"
        ],
        "priority": story_num,
        "passes": False
    })
    story_num += 1

    stories.append({
        "id": f"DISC-{story_num:03d}",
        "title": "Add validated sources to queue",
        "acceptanceCriteria": [
            "Add all sources with score >= 0.4",
            "Include full discovery metadata",
            "Generate discovery report"
        ],
        "priority": story_num,
        "passes": False
    })

    return {
        "projectName": "Source Discovery - Deep Session (Global)",
        "branchName": "main",
        "mode": "discovery",
        "targetNewSources": 30,
        "maxIterations": 100,
        "userStories": stories,
        "createdAt": datetime.now().isoformat(),
        "discoveryConfig": {
            "categories": list(DISCOVERY_CATEGORIES.keys()),
            "queriesPerCategory": 2,
            "minConfidenceScore": 0.4
        }
    }


def generate_international_prd():
    """Generate a PRD focused on international markets only."""
    stories = []
    story_num = 1

    # International batches by region
    intl_batches = [
        (["japan", "south_korea"], "East Asia"),
        (["germany", "netherlands", "france", "poland"], "Europe"),
        (["uk", "scandinavia"], "UK & Nordic"),
        (["australia", "new_zealand"], "Oceania"),
        (["middle_east", "south_africa"], "Middle East & Africa"),
        (["brazil", "mexico"], "Latin America"),
        (["southeast_asia", "russia"], "Asia"),
        (["canada"], "North America"),
    ]

    for batch, region_name in intl_batches:
        batch_names = [DISCOVERY_CATEGORIES[c]["name"] for c in batch if c in DISCOVERY_CATEGORIES]
        if not batch_names:
            continue
        stories.append({
            "id": f"DISC-{story_num:03d}",
            "title": f"Search {region_name}: {', '.join(batch_names)}",
            "acceptanceCriteria": [
                f"Execute 3 web searches per country ({', '.join(batch)})",
                "Look for local tuning shops, forums, and car culture sites",
                "Validate promising results with webReader",
                "Document candidates with scores"
            ],
            "searchCategories": batch,
            "priority": story_num,
            "passes": False
        })
        story_num += 1

    # Validation story
    stories.append({
        "id": f"DISC-{story_num:03d}",
        "title": "Validate international candidates",
        "acceptanceCriteria": [
            "Fetch sample build page from each candidate",
            "Verify content is accessible (some may be in local language)",
            "Verify modifications/specs are listed",
            "Score each candidate"
        ],
        "priority": story_num,
        "passes": False
    })
    story_num += 1

    stories.append({
        "id": f"DISC-{story_num:03d}",
        "title": "Add validated international sources",
        "acceptanceCriteria": [
            "Add all sources with score >= 0.4",
            "Include country/region in discovery metadata",
            "Generate international discovery report"
        ],
        "priority": story_num,
        "passes": False
    })

    return {
        "projectName": "Source Discovery - International Markets",
        "branchName": "main",
        "mode": "discovery",
        "targetNewSources": 20,
        "maxIterations": 60,
        "userStories": stories,
        "createdAt": datetime.now().isoformat(),
        "discoveryConfig": {
            "categories": get_international_categories(),
            "queriesPerCategory": 3,
            "minConfidenceScore": 0.4
        }
    }


def generate_targeted_prd(categories, target=5):
    """Generate a PRD targeting specific vehicle categories."""
    stories = []
    story_num = 1

    for category in categories:
        if category not in DISCOVERY_CATEGORIES:
            continue

        cat_info = DISCOVERY_CATEGORIES[category]
        stories.append({
            "id": f"DISC-{story_num:03d}",
            "title": f"Search: {cat_info['name']}",
            "acceptanceCriteria": [
                f"Execute 3 web searches for {cat_info['description'].lower()}",
                "Validate all promising results with webReader",
                "Score and document each candidate"
            ],
            "searchCategories": [category],
            "priority": story_num,
            "passes": False
        })
        story_num += 1

    # Validation story
    stories.append({
        "id": f"DISC-{story_num:03d}",
        "title": "Validate and add sources",
        "acceptanceCriteria": [
            "Run validation on all candidates",
            f"Add at least {target} new sources to queue",
            "Include discovery metadata"
        ],
        "priority": story_num,
        "passes": False
    })

    return {
        "projectName": f"Source Discovery - {', '.join(categories)}",
        "branchName": "main",
        "mode": "discovery",
        "targetNewSources": target,
        "maxIterations": 30,
        "userStories": stories,
        "createdAt": datetime.now().isoformat(),
        "discoveryConfig": {
            "categories": categories,
            "queriesPerCategory": 3,
            "minConfidenceScore": 0.4
        }
    }


def save_prd(prd):
    """Save PRD to file."""
    with open(PRD_FILE, 'w') as f:
        json.dump(prd, f, indent=2)
    return PRD_FILE


def main():
    parser = argparse.ArgumentParser(description="Generate Source Discovery PRD")
    parser.add_argument("--quick", "-q", action="store_true",
                       help="Quick discovery session (5 searches)")
    parser.add_argument("--deep", "-d", action="store_true",
                       help="Deep discovery session (all categories including international)")
    parser.add_argument("--international", "-i", action="store_true",
                       help="International markets only (17 countries)")
    parser.add_argument("--categories", "-c", nargs="+",
                       choices=list(DISCOVERY_CATEGORIES.keys()),
                       help="Target specific categories")
    parser.add_argument("--target", "-t", type=int, default=5,
                       help="Target number of new sources (default: 5)")
    parser.add_argument("--output", "-o", help="Output file (default: prd.json)")
    parser.add_argument("--print", "-p", action="store_true",
                       help="Print PRD instead of saving")
    parser.add_argument("--list-categories", action="store_true",
                       help="List all available categories")

    args = parser.parse_args()

    if args.list_categories:
        print("Available discovery categories:\n")
        print("=== GENERAL ===")
        for cat in get_general_categories():
            info = DISCOVERY_CATEGORIES[cat]
            print(f"  {cat}: {info['description']}")
        print("\n=== US VEHICLE-SPECIFIC ===")
        for cat in get_us_categories():
            info = DISCOVERY_CATEGORIES[cat]
            print(f"  {cat}: {info['description']}")
        print("\n=== INTERNATIONAL MARKETS ===")
        for cat in get_international_categories():
            info = DISCOVERY_CATEGORIES[cat]
            print(f"  {cat}: {info['description']}")
        return

    if args.quick:
        prd = generate_quick_prd()
    elif args.deep:
        prd = generate_deep_prd()
    elif args.international:
        prd = generate_international_prd()
    elif args.categories:
        prd = generate_targeted_prd(args.categories, args.target)
    else:
        prd = generate_standard_prd()

    if args.print:
        print(json.dumps(prd, indent=2))
    else:
        output = args.output or PRD_FILE
        with open(output, 'w') as f:
            json.dump(prd, f, indent=2)
        print(f"Generated discovery PRD: {output}")
        print(f"  Mode: {prd['projectName']}")
        print(f"  Stories: {len(prd['userStories'])}")
        print(f"  Target: {prd['targetNewSources']} new sources")
        print(f"  Categories: {', '.join(prd['discoveryConfig']['categories'])}")


if __name__ == "__main__":
    main()
