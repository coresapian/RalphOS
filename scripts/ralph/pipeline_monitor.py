#!/usr/bin/env python3
"""
Pipeline Monitor - Tracks sub-ralph progress and triggers

Monitors output files and returns trigger signals for the cascading pipeline.
Each sub-ralph triggers the next after 20 items are ready.

Usage:
    # Check all triggers for a source
    python pipeline_monitor.py --source custom_wheel_offset
    
    # Check specific stage
    python pipeline_monitor.py --source custom_wheel_offset --stage html
    
    # JSON output for scripting
    python pipeline_monitor.py --source custom_wheel_offset --json
    
    # Watch mode (continuous monitoring)
    python pipeline_monitor.py --source custom_wheel_offset --watch
"""

import json
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# Configuration
TRIGGER_THRESHOLD = 20  # Items needed before next stage starts
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent


def count_urls(source_id: str) -> int:
    """Count URLs in urls.json"""
    urls_file = PROJECT_ROOT / "scraped_builds" / source_id / "urls.json"
    if not urls_file.exists():
        return 0
    try:
        with open(urls_file) as f:
            data = json.load(f)
        return len(data.get("urls", []))
    except (json.JSONDecodeError, KeyError):
        return 0


def count_html_files(source_id: str) -> int:
    """Count HTML files in html/ directory"""
    html_dir = PROJECT_ROOT / "scraped_builds" / source_id / "html"
    if not html_dir.exists():
        return 0
    return len(list(html_dir.glob("*.html")))


def count_builds(source_id: str) -> int:
    """Count builds in builds.json"""
    builds_file = PROJECT_ROOT / "scraped_builds" / source_id / "builds.json"
    if not builds_file.exists():
        return 0
    try:
        with open(builds_file) as f:
            data = json.load(f)
        return len(data.get("builds", []))
    except (json.JSONDecodeError, KeyError):
        return 0


def count_mods(source_id: str) -> int:
    """Count mods in mods.json"""
    mods_file = PROJECT_ROOT / "scraped_builds" / source_id / "mods.json"
    if not mods_file.exists():
        return 0
    try:
        with open(mods_file) as f:
            data = json.load(f)
        return len(data.get("mods", []))
    except (json.JSONDecodeError, KeyError):
        return 0


def get_source_status(source_id: str) -> dict:
    """Get current source status from sources.json"""
    sources_file = SCRIPT_DIR / "sources.json"
    if not sources_file.exists():
        return {}
    try:
        with open(sources_file) as f:
            data = json.load(f)
        for source in data.get("sources", []):
            if source.get("id") == source_id:
                return source
    except (json.JSONDecodeError, KeyError):
        pass
    return {}


def check_triggers(source_id: str) -> dict:
    """Check all pipeline triggers for a source.
    
    Returns dict with:
        - counts: current item counts per stage
        - triggers: which stages should start
        - stages: status of each stage (not_started, in_progress, complete)
    """
    urls_count = count_urls(source_id)
    html_count = count_html_files(source_id)
    builds_count = count_builds(source_id)
    mods_count = count_mods(source_id)
    
    # Get expected counts from sources.json
    source = get_source_status(source_id)
    pipeline = source.get("pipeline", {})
    expected_urls = pipeline.get("expectedUrls") or 0
    urls_found = pipeline.get("urlsFound") or 0
    
    # Determine stage status
    def get_stage_status(current: int, expected: int, started: bool) -> str:
        if current == 0 and not started:
            return "not_started"
        elif expected > 0 and current >= expected:
            return "complete"
        else:
            return "in_progress"
    
    # URL stage is always started (it's first)
    url_stage = get_stage_status(urls_count, expected_urls, True)
    
    # HTML stage starts after 20 URLs
    html_started = html_count > 0 or urls_count >= TRIGGER_THRESHOLD
    html_stage = get_stage_status(html_count, urls_found, html_started)
    
    # Build stage starts after 20 HTMLs
    builds_started = builds_count > 0 or html_count >= TRIGGER_THRESHOLD
    build_stage = get_stage_status(builds_count, html_count, builds_started)
    
    # Mod stage starts after 20 builds
    mods_started = mods_count > 0 or builds_count >= TRIGGER_THRESHOLD
    mod_stage = get_stage_status(mods_count, builds_count, mods_started)
    
    return {
        "source_id": source_id,
        "timestamp": datetime.now().isoformat(),
        "threshold": TRIGGER_THRESHOLD,
        "counts": {
            "urls": urls_count,
            "html": html_count,
            "builds": builds_count,
            "mods": mods_count
        },
        "expected": {
            "urls": expected_urls,
            "html": urls_found,
            "builds": html_count,
            "mods": builds_count
        },
        "triggers": {
            "start_url_detective": True,  # Always start
            "start_html_scraper": urls_count >= TRIGGER_THRESHOLD,
            "start_build_extractor": html_count >= TRIGGER_THRESHOLD,
            "start_mod_extractor": builds_count >= TRIGGER_THRESHOLD
        },
        "stages": {
            "url_detective": url_stage,
            "html_scraper": html_stage,
            "build_extractor": build_stage,
            "mod_extractor": mod_stage
        },
        "pipeline_complete": all([
            url_stage == "complete",
            html_stage == "complete",
            build_stage == "complete",
            mod_stage == "complete"
        ])
    }


def print_status(status: dict, use_json: bool = False):
    """Print pipeline status"""
    if use_json:
        print(json.dumps(status, indent=2))
        return
    
    # Colors
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    DIM = "\033[2m"
    NC = "\033[0m"
    
    def status_color(s: str) -> str:
        if s == "complete":
            return f"{GREEN}●{NC}"
        elif s == "in_progress":
            return f"{YELLOW}●{NC}"
        else:
            return f"{DIM}○{NC}"
    
    print(f"\n{'='*60}")
    print(f"Pipeline Status: {status['source_id']}")
    print(f"{'='*60}")
    print(f"Threshold: {status['threshold']} items to trigger next stage\n")
    
    stages = [
        ("url_detective", "URLs", "urls"),
        ("html_scraper", "HTML", "html"),
        ("build_extractor", "Builds", "builds"),
        ("mod_extractor", "Mods", "mods")
    ]
    
    for stage_id, label, count_key in stages:
        stage_status = status["stages"][stage_id]
        count = status["counts"][count_key]
        expected = status["expected"].get(count_key, "?")
        trigger_key = f"start_{stage_id}"
        triggered = status["triggers"].get(trigger_key, False)
        
        icon = status_color(stage_status)
        trigger_indicator = f"{GREEN}▶{NC}" if triggered else f"{DIM}○{NC}"
        
        print(f"  {icon} {label:12} {count:>5}/{expected:<5}  {trigger_indicator} {'READY' if triggered else 'waiting'}")
    
    print()
    if status["pipeline_complete"]:
        print(f"  {GREEN}✓ Pipeline complete!{NC}")
    else:
        # Show next action
        for stage_id, label, _ in stages:
            if status["stages"][stage_id] == "in_progress":
                print(f"  {YELLOW}→ {label} in progress...{NC}")
                break
    print()


def watch_mode(source_id: str, interval: int = 5):
    """Continuously monitor pipeline status"""
    print(f"Watching pipeline for {source_id} (Ctrl+C to stop)...")
    try:
        while True:
            status = check_triggers(source_id)
            # Clear screen
            print("\033[2J\033[H", end="")
            print_status(status)
            
            if status["pipeline_complete"]:
                print("Pipeline complete! Exiting watch mode.")
                break
            
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped watching.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor sub-ralph pipeline progress")
    parser.add_argument("--source", "-s", required=True, help="Source ID to monitor")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--watch", "-w", action="store_true", help="Continuous monitoring")
    parser.add_argument("--interval", "-i", type=int, default=5, help="Watch interval in seconds")
    parser.add_argument("--stage", choices=["url", "html", "build", "mod"], 
                        help="Check specific stage trigger only")
    
    args = parser.parse_args()
    
    if args.watch:
        watch_mode(args.source, args.interval)
    else:
        status = check_triggers(args.source)
        
        if args.stage:
            # Return just the trigger status for a specific stage
            trigger_map = {
                "url": "start_url_detective",
                "html": "start_html_scraper",
                "build": "start_build_extractor",
                "mod": "start_mod_extractor"
            }
            triggered = status["triggers"][trigger_map[args.stage]]
            if args.json:
                print(json.dumps({"triggered": triggered}))
            else:
                print("yes" if triggered else "no")
            sys.exit(0 if triggered else 1)
        
        print_status(status, use_json=args.json)
        
        # Exit code based on pipeline completion
        sys.exit(0 if status["pipeline_complete"] else 1)

