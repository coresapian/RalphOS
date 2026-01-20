#!/usr/bin/env python3
"""
Synchronizes progress between the filesystem data/ directory and the master sources.json.
"""
import json
from pathlib import Path


def count_files(directory, extension):
    if not directory.exists():
        return 0
    return len(list(directory.glob(f"*.{extension}")))


def main():
    project_root = Path(__file__).parent.parent.parent
    sources_path = project_root / "scripts/ralph/sources.json"
    data_dir = project_root / "data"

    if not sources_path.exists():
        print(f"Error: {sources_path} not found")
        return

    with open(sources_path, "r") as f:
        data = json.load(f)

    sources = data.get("sources", [])

    print("--- Syncing progress from filesystem to sources.json ---")
    for s in sources:
        source_id = s["id"]
        source_data_dir = data_dir / source_id

        if not source_data_dir.exists():
            continue

        pipeline = s.get("pipeline", {})

        # 1. Check URLs
        urls_jsonl = source_data_dir / "urls.jsonl"
        urls_json = source_data_dir / "urls.json"
        urls_count = 0
        if urls_jsonl.exists():
            with open(urls_jsonl, "r") as f:
                urls_count = sum(1 for line in f if line.strip())
        elif urls_json.exists():
            try:
                with open(urls_json, "r") as f:
                    u_data = json.load(f)
                urls_count = len(u_data.get("urls", []))
            except:
                pass

        if urls_count > 0:
            pipeline["urlsFound"] = urls_count

        # 2. Check HTML
        html_dir = source_data_dir / "html"
        html_count = count_files(html_dir, "html")
        if html_count > 0:
            pipeline["htmlScraped"] = html_count

        # 3. Check Builds
        builds_jsonl = source_data_dir / "builds.jsonl"
        builds_json = source_data_dir / "builds.json"
        builds_count = 0
        if builds_jsonl.exists():
            with open(builds_jsonl, "r") as f:
                builds_count = sum(1 for line in f if line.strip())
        elif builds_json.exists():
            try:
                with open(builds_json, "r") as f:
                    b_data = json.load(f)
                builds_count = len(b_data.get("builds", b_data if isinstance(b_data, list) else []))
            except:
                pass

        if builds_count > 0:
            pipeline["builds"] = builds_count

        # 4. Check Mods
        mods_jsonl = source_data_dir / "mods.jsonl"
        mods_count = 0
        if mods_jsonl.exists():
            with open(mods_jsonl, "r") as f:
                mods_count = sum(1 for line in f if line.strip())

        if mods_count > 0:
            pipeline["mods"] = mods_count

        # Update status if completed
        if builds_count > 0 and s["status"] != "completed":
            s["status"] = "completed"
            print(f"  {source_id} marked as completed")
        elif html_count > 0 and urls_count > 0 and html_count >= urls_count and s["status"] == "pending":
            s["status"] = "in_progress"

        s["pipeline"] = pipeline

    # Save master sources.json
    with open(sources_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Updated {sources_path}")


if __name__ == "__main__":
    main()
