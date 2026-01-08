#!/usr/bin/env python3
"""Convert urls.jsonl to urls.json format for stealth_scraper.py"""
import json
import sys
from pathlib import Path
from datetime import datetime

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 convert_urls_format.py <input.jsonl> <output.json>")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if not input_file.exists():
        print(f"Error: {input_file} not found")
        sys.exit(1)
    
    # Read JSONL lines
    urls = []
    with open(input_file) as f:
        for line in f:
            if line.strip():
                urls.append(json.loads(line))
    
    # Write JSON array format
    output_data = {
        "urls": urls,
        "lastUpdated": datetime.now().isoformat(),
        "totalCount": len(urls)
    }
    
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)
    
    print(f"Converted {len(urls)} URLs from {input_file.name} to {output_file.name}")

if __name__ == "__main__":
    main()
