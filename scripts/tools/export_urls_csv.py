#!/usr/bin/env python3
"""Export all source URLs to CSV files for motormia-etl"""
import csv
import json
from pathlib import Path

DATA_DIR = Path("data")
OUTPUT_DIR = Path("/Users/core/Downloads/motormia/motormia-etl/data/input")

for source_dir in sorted(DATA_DIR.iterdir()):
    if not source_dir.is_dir():
        continue
    
    urls = []
    source_name = source_dir.name
    
    # Prefer JSONL format
    jsonl_file = source_dir / "urls.jsonl"
    json_file = source_dir / "urls.json"
    
    if jsonl_file.exists():
        with open(jsonl_file) as f:
            for line in f:
                if line.strip():
                    urls.append(json.loads(line)["url"])
    elif json_file.exists():
        with open(json_file) as f:
            data = json.load(f)
        urls = data.get("urls", data if isinstance(data, list) else [])
    
    if urls:
        # Create output folder
        output_folder = OUTPUT_DIR / source_name
        output_folder.mkdir(parents=True, exist_ok=True)
        
        # Write CSV
        csv_file = output_folder / f"{source_name}_urls.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["url"])
            for url in urls:
                writer.writerow([url])
        print(f"{source_name}: {len(urls)} URLs -> {csv_file}")

