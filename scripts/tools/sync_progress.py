#!/usr/bin/env python3
"""
Sync Progress - Updates sources.json with actual file counts from disk.
Run this periodically to keep sources.json accurate.

Usage:
    python scripts/tools/sync_progress.py              # Sync all sources
    python scripts/tools/sync_progress.py modified_rides  # Sync specific source
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
NC = '\033[0m'

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SOURCES_FILE = PROJECT_ROOT / "scripts" / "ralph" / "sources.json"
DATA_DIR = PROJECT_ROOT / "data"


def count_html_files(output_dir: Path) -> int:
    """Count HTML files in output_dir/html/"""
    html_dir = output_dir / "html"
    if html_dir.exists():
        return len(list(html_dir.glob("*.html")))
    return 0


def count_urls(output_dir: Path) -> int:
    """Count URLs in output_dir/urls.json"""
    urls_file = output_dir / "urls.json"
    if urls_file.exists():
        try:
            with open(urls_file) as f:
                data = json.load(f)
            return len(data.get("urls", []))
        except:
            pass
    return 0


def count_builds(output_dir: Path) -> int:
    """Count builds in output_dir/builds.json"""
    builds_file = output_dir / "builds.json"
    if builds_file.exists():
        try:
            with open(builds_file) as f:
                data = json.load(f)
            # Handle both formats: raw array or {"builds": [...]}
            if isinstance(data, list):
                return len(data)
            return len(data.get("builds", []))
        except:
            pass
    return 0


def count_mods(output_dir: Path) -> int:
    """Count mods in output_dir/mods.json"""
    mods_file = output_dir / "mods.json"
    if mods_file.exists():
        try:
            with open(mods_file) as f:
                data = json.load(f)
            if isinstance(data, list):
                return len(data)
            return len(data.get("mods", []))
        except:
            pass
    return 0


def get_failed_count(output_dir: Path) -> tuple:
    """Get failed and blocked counts from scrape_progress.json"""
    progress_file = output_dir / "scrape_progress.json"
    failed = 0
    blocked = 0
    if progress_file.exists():
        try:
            with open(progress_file) as f:
                data = json.load(f)
            failed_urls = data.get("failedUrls", [])
            if isinstance(failed_urls, list):
                for item in failed_urls:
                    if isinstance(item, dict):
                        error = item.get("error", "")
                        if "403" in error or "Cloudflare" in error or "blocked" in error.lower():
                            blocked += 1
                        else:
                            failed += 1
                    else:
                        failed += 1
        except:
            pass
    return failed, blocked


def sync_source(source: dict, sources_data: dict) -> bool:
    """Sync a single source with actual file counts. Returns True if changed."""
    source_id = source.get("id", "unknown")
    output_dir_str = source.get("outputDir", "")
    
    if not output_dir_str:
        return False
    
    output_dir = PROJECT_ROOT / output_dir_str
    if not output_dir.exists():
        return False
    
    # Get actual counts
    url_count = count_urls(output_dir)
    html_count = count_html_files(output_dir)
    build_count = count_builds(output_dir)
    mod_count = count_mods(output_dir)
    failed_count, blocked_count = get_failed_count(output_dir)
    
    # Get current pipeline values
    pipeline = source.get("pipeline", {})
    old_urls = pipeline.get("urlsFound")
    old_html = pipeline.get("htmlScraped")
    old_builds = pipeline.get("builds")
    old_mods = pipeline.get("mods")
    old_failed = pipeline.get("htmlFailed")
    old_blocked = pipeline.get("htmlBlocked")
    
    # Check for changes
    changes = []
    
    if url_count > 0 and url_count != old_urls:
        changes.append(f"urlsFound: {old_urls} → {url_count}")
        pipeline["urlsFound"] = url_count
    
    if html_count > 0 and html_count != old_html:
        changes.append(f"htmlScraped: {old_html} → {html_count}")
        pipeline["htmlScraped"] = html_count
    
    if build_count > 0 and build_count != old_builds:
        changes.append(f"builds: {old_builds} → {build_count}")
        pipeline["builds"] = build_count
    
    if mod_count > 0 and mod_count != old_mods:
        changes.append(f"mods: {old_mods} → {mod_count}")
        pipeline["mods"] = mod_count
    
    if failed_count > 0 and failed_count != old_failed:
        changes.append(f"htmlFailed: {old_failed} → {failed_count}")
        pipeline["htmlFailed"] = failed_count
    
    if blocked_count > 0 and blocked_count != old_blocked:
        changes.append(f"htmlBlocked: {old_blocked} → {blocked_count}")
        pipeline["htmlBlocked"] = blocked_count
    
    if changes:
        source["pipeline"] = pipeline
        print(f"  {GREEN}✓{NC} {source_id}:")
        for change in changes:
            print(f"      {CYAN}{change}{NC}")
        return True
    else:
        print(f"  {YELLOW}○{NC} {source_id}: no changes")
        return False


def main():
    print(f"\n{CYAN}═══════════════════════════════════════════════════════════{NC}")
    print(f"{CYAN}  Sync Progress - Update sources.json from disk{NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════{NC}\n")
    
    # Load sources.json
    if not SOURCES_FILE.exists():
        print(f"{RED}Error: sources.json not found{NC}")
        sys.exit(1)
    
    with open(SOURCES_FILE) as f:
        sources_data = json.load(f)
    
    sources = sources_data.get("sources", [])
    
    # Filter to specific source if provided
    target_source = sys.argv[1] if len(sys.argv) > 1 else None
    
    if target_source:
        sources = [s for s in sources if s.get("id") == target_source]
        if not sources:
            print(f"{RED}Error: Source '{target_source}' not found{NC}")
            sys.exit(1)
    
    # Sync each source
    changed_count = 0
    for source in sources:
        if sync_source(source, sources_data):
            changed_count += 1
    
    # Save if changed
    if changed_count > 0:
        with open(SOURCES_FILE, 'w') as f:
            json.dump(sources_data, f, indent=2)
        print(f"\n{GREEN}✓ Updated {changed_count} source(s) in sources.json{NC}\n")
    else:
        print(f"\n{YELLOW}No changes needed{NC}\n")


if __name__ == "__main__":
    main()

