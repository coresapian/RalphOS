#!/usr/bin/env python3
"""Import all CSV files from input/ to Ralph sources format."""
import csv
import json
import os
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
SOURCES_FILE = PROJECT_ROOT / "scripts/ralph/sources.json"
INPUT_DIR = PROJECT_ROOT / "input"  # CSV source files live here

# CSV files and their URL column name
CSV_CONFIGS = {
    "carandclassic.csv": {"url_col": "url", "name": "Car and Classic", "url": "https://carandclassic.com"},
    "audiocityusa.csv": {"url_col": "url", "name": "AudioCityUSA", "url": "https://audiocityusa.com"},
    "hennesseyperformance.csv": {"url_col": "url", "name": "Hennessey Performance", "url": "https://hennesseyperformance.com"},
    "tunedbyanton.csv": {"url_col": "url", "name": "Tuned By Anton", "url": "https://tunedbyanton.com"},
    "pistonheads-auctions.csv": {"url_col": "Link_root__9Sxss href", "name": "PistonHeads Auctions", "url": "https://pistonheads.com"},
    "goo-net-exchange.csv": {"url_col": "url", "name": "Goo-net Exchange", "url": "https://goo-net-exchange.com"},
    "autotempest.csv": {"url_col": "url", "name": "AutoTempest", "url": "https://autotempest.com"},
    "rebornbuilds_85_builds.csv": {"url_col": None, "name": "Reborn Builds", "url": "https://rebornbuilds.com"},  # No URL col, skip
    "roushperformance.csv": {"url_col": "url", "name": "Roush Performance", "url": "https://roushperformance.com"},
    "amc_ebay.csv": {"url_col": "url", "name": "AMC eBay", "url": "https://ebay.com"},
    "hamann-motorsport.csv": {"url_col": "portfolio-item-image href", "name": "Hamann Motorsport", "url": "https://hamann-motorsport.com"},
    "twostepperformance.csv": {"url_col": "article-item__image-container href", "name": "Two Step Performance", "url": "https://twostepperformance.com"},
    "paramount-performance.csv": {"url_col": "btn href", "name": "Paramount Performance", "url": "https://paramount-performance.com"},
    "manhart-automotive.csv": {"url_col": "card href", "name": "Manhart Automotive", "url": "https://manhart-automotive.de"},
}

def csv_to_source_id(csv_name):
    """Convert CSV filename to source ID."""
    return csv_name.replace(".csv", "").replace("-", "_").replace(" ", "_").lower()

def extract_urls_from_csv(csv_path, url_col):
    """Extract URLs from CSV file."""
    urls = []
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if url_col and url_col in row:
                url = row[url_col].strip()
                if url and url.startswith('http'):
                    urls.append(url)
    return list(set(urls))  # Dedupe

def create_urls_json(output_dir, urls):
    """Create urls.json in Ralph format."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "html").mkdir(exist_ok=True)
    
    urls_data = {
        "urls": sorted(urls),
        "totalCount": len(urls),
        "lastUpdated": datetime.utcnow().isoformat() + "Z"
    }
    
    with open(output_dir / "urls.json", 'w') as f:
        json.dump(urls_data, f, indent=2)
    
    return len(urls)

def main():
    # Load existing sources.json
    with open(SOURCES_FILE, 'r') as f:
        sources_data = json.load(f)
    
    existing_ids = {s["id"] for s in sources_data["sources"]}
    new_sources = []
    
    for csv_name, config in CSV_CONFIGS.items():
        csv_path = INPUT_DIR / csv_name
        if not csv_path.exists():
            print(f"  SKIP: {csv_name} not found in input/")
            continue
        
        source_id = csv_to_source_id(csv_name)
        output_dir = PROJECT_ROOT / "data" / source_id
        
        # Extract URLs
        url_col = config["url_col"]
        if url_col is None:
            print(f"  SKIP: {csv_name} - no URL column defined")
            continue
            
        urls = extract_urls_from_csv(csv_path, url_col)
        
        if not urls:
            print(f"  SKIP: {csv_name} - no URLs extracted")
            continue
        
        # Create urls.json
        count = create_urls_json(output_dir, urls)
        print(f"  OK: {source_id} - {count} URLs -> data/{source_id}/urls.json")
        
        # Add to sources if not exists
        if source_id not in existing_ids:
            new_sources.append({
                "id": source_id,
                "name": config["name"],
                "url": config["url"],
                "outputDir": f"data/{source_id}",
                "status": "pending",
                "priority": 5,
                "attempted": 0,
                "lastAttempted": None,
                "pipeline": {
                    "expectedUrls": count,
                    "urlsFound": count,
                    "htmlScraped": 0,
                    "htmlFailed": 0,
                    "htmlBlocked": 0,
                    "builds": None,
                    "mods": None
                }
            })
    
    # Add new sources to sources.json
    if new_sources:
        sources_data["sources"].extend(new_sources)
        with open(SOURCES_FILE, 'w') as f:
            json.dump(sources_data, f, indent=2)
        print(f"\nAdded {len(new_sources)} new sources to sources.json")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
