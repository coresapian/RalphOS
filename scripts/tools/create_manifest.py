#!/usr/bin/env python3
"""
Create manifest.json from scrape progress data.
"""

import json
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime

PROGRESS_FILE = Path("scraped_builds/scrape_progress.json")
MANIFEST_FILE = Path("scraped_builds/manifest.json")
HTML_DIR = Path("scraped_builds/html")


def get_slug_from_url(url: str) -> str:
    """Extract slug from URL for filename."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if path.startswith("build-threads/"):
        path = path.replace("build-threads/", "")
    return path.replace("/", "-") + ".html"


def main():
    # Load progress data
    with open(PROGRESS_FILE) as f:
        progress = json.load(f)

    completed_urls = progress.get("completed", [])
    finished_at = progress.get("finishedAt", progress.get("lastUpdated"))

    # Create manifest entries
    manifest_entries = []
    for url in completed_urls:
        slug = get_slug_from_url(url)
        html_path = HTML_DIR / slug

        entry = {
            "url": url,
            "filename": slug,
            "scraped_at": finished_at
        }

        # Add file size if file exists
        if html_path.exists():
            entry["file_size_bytes"] = html_path.stat().st_size
        else:
            entry["file_exists"] = False

        manifest_entries.append(entry)

    # Create manifest
    manifest = {
        "scrape_started": progress.get("startedAt"),
        "scrape_finished": finished_at,
        "total_urls": len(completed_urls),
        "failed_urls": len(progress.get("failed", [])),
        "entries": manifest_entries
    }

    # Write manifest
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Created manifest.json with {len(manifest_entries)} entries")
    print(f"Total scraped: {len(completed_urls)}")
    print(f"Failed: {len(progress.get('failed', []))}")
    print(f"Manifest saved to: {MANIFEST_FILE}")


if __name__ == "__main__":
    main()
