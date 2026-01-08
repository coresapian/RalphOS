#!/usr/bin/env python3
"""
Synchronizes progress between the filesystem data/ directory and the master sources.json,
and then updates all stage-specific queue.json files.
"""
import json
import os
from pathlib import Path
from datetime import datetime

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
            print(f"  ✓ {source_id} marked as completed")
        elif html_count > 0 and urls_count > 0 and html_count >= urls_count and s["status"] == "pending":
            s["status"] = "in_progress"
            
        s["pipeline"] = pipeline

    # Save master sources.json
    with open(sources_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Updated {sources_path}")

    # Now update stage queues
    print("\n--- Updating stage-specific queues ---")
    
    # 1. URL Detective Queue
    url_detective_queue_path = project_root / "scripts/ralph-stages/url-detective/queue.json"
    url_detective_sources = []
    for s in sources:
        pipeline = s.get("pipeline", {})
        if s.get("status") in ["pending", "in_progress"] and pipeline.get("urlsFound", 0) == 0:
            url_detective_sources.append({
                "id": s["id"],
                "name": s["name"],
                "url": s["url"],
                "outputDir": s["outputDir"],
                "status": "pending" if s["status"] == "pending" else "in_progress",
                "priority": s.get("priority", 5)
            })
    
    if url_detective_queue_path.exists():
        with open(url_detective_queue_path, "r") as f:
            q = json.load(f)
        q["sources"] = url_detective_sources
        with open(url_detective_queue_path, "w") as f:
            json.dump(q, f, indent=2)
        print(f"Updated {url_detective_queue_path} with {len(url_detective_sources)} sources")

    # 2. HTML Scraper Queue
    html_scraper_queue_path = project_root / "scripts/ralph-stages/html-scraper/queue.json"
    html_scraper_sources = []
    for s in sources:
        pipeline = s.get("pipeline", {})
        urls_found = pipeline.get("urlsFound", 0)
        html_scraped = pipeline.get("htmlScraped", 0)
        
        if urls_found > 0 and (html_scraped < urls_found or s.get("status") == "blocked"):
            html_scraper_sources.append({
                "id": s["id"],
                "name": s["name"],
                "outputDir": s["outputDir"],
                "urlsFound": urls_found,
                "status": "blocked" if s.get("status") == "blocked" else "pending",
                "priority": s.get("priority", 5)
            })
            
    if html_scraper_queue_path.exists():
        with open(html_scraper_queue_path, "r") as f:
            q = json.load(f)
        q["sources"] = html_scraper_sources
        with open(html_scraper_queue_path, "w") as f:
            json.dump(q, f, indent=2)
        print(f"Updated {html_scraper_queue_path} with {len(html_scraper_sources)} sources")

    # 3. Data Extractor Queue
    data_extractor_queue_path = project_root / "scripts/ralph-stages/data-extractor/queue.json"
    data_extractor_sources = []
    for s in sources:
        pipeline = s.get("pipeline", {})
        html_scraped = pipeline.get("htmlScraped", 0)
        builds = pipeline.get("builds", 0)
        
        if html_scraped > 0 and (builds == 0 or builds is None) and s.get("status") != "blocked":
            data_extractor_sources.append({
                "id": s["id"],
                "name": s["name"],
                "outputDir": s["outputDir"],
                "htmlCount": html_scraped,
                "status": "pending",
                "priority": s.get("priority", 5)
            })
            
    if data_extractor_queue_path.exists():
        with open(data_extractor_queue_path, "r") as f:
            q = json.load(f)
        q["sources"] = data_extractor_sources
        with open(data_extractor_queue_path, "w") as f:
            json.dump(q, f, indent=2)
        print(f"Updated {data_extractor_queue_path} with {len(data_extractor_sources)} sources")

if __name__ == "__main__":
    main()
