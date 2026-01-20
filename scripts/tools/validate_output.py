#!/usr/bin/env python3
"""
Output Validation Script for Ralph Stages
Validates that output files actually contain data and were recently modified.
Prevents hallucinated task completion.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

def validate_urls(output_dir: str, max_age_minutes: int = 10) -> dict:
    """
    Validate URL discovery output.
    Returns: {"valid": bool, "error": str|None, "count": int}
    """
    output_path = Path(output_dir)
    
    # Check for JSONL format first (new format)
    jsonl_file = output_path / "urls.jsonl"
    json_file = output_path / "urls.json"
    
    if jsonl_file.exists():
        return _validate_jsonl(jsonl_file, max_age_minutes, "url")
    elif json_file.exists():
        return _validate_json(json_file, max_age_minutes, ["urls", "totalCount"])
    else:
        return {"valid": False, "error": "No urls.jsonl or urls.json found", "count": 0}


def validate_html_scrape(output_dir: str, max_age_minutes: int = 10) -> dict:
    """
    Validate HTML scraping output.
    Returns: {"valid": bool, "error": str|None, "count": int}
    """
    output_path = Path(output_dir)
    html_dir = output_path / "html"
    
    if not html_dir.exists():
        return {"valid": False, "error": "No html/ directory found", "count": 0}
    
    html_files = list(html_dir.glob("*.html"))
    if len(html_files) == 0:
        return {"valid": False, "error": "No HTML files in html/ directory", "count": 0}
    
    # Check if any files were recently modified
    now = datetime.now()
    cutoff = now - timedelta(minutes=max_age_minutes)
    recent_files = [f for f in html_files if datetime.fromtimestamp(f.stat().st_mtime) > cutoff]
    
    if len(recent_files) == 0:
        return {"valid": False, "error": f"No HTML files modified in last {max_age_minutes} minutes", "count": len(html_files)}
    
    return {"valid": True, "error": None, "count": len(html_files), "recent": len(recent_files)}


def validate_builds(output_dir: str, max_age_minutes: int = 10) -> dict:
    """
    Validate build extraction output.
    Returns: {"valid": bool, "error": str|None, "count": int}
    """
    output_path = Path(output_dir)
    
    # Check for JSONL format first (new format)
    jsonl_file = output_path / "builds.jsonl"
    json_file = output_path / "builds.json"
    
    if jsonl_file.exists():
        return _validate_jsonl(jsonl_file, max_age_minutes, "build_id")
    elif json_file.exists():
        return _validate_json(json_file, max_age_minutes, ["builds"])
    else:
        return {"valid": False, "error": "No builds.jsonl or builds.json found", "count": 0}


def validate_mods(output_dir: str, max_age_minutes: int = 10) -> dict:
    """
    Validate mod extraction output.
    Returns: {"valid": bool, "error": str|None, "count": int}
    """
    output_path = Path(output_dir)
    
    # Check for JSONL format first (new format)
    jsonl_file = output_path / "mods.jsonl"
    json_file = output_path / "mods.json"
    
    if jsonl_file.exists():
        return _validate_jsonl(jsonl_file, max_age_minutes, "name")
    elif json_file.exists():
        return _validate_json(json_file, max_age_minutes, ["mods"])
    else:
        return {"valid": False, "error": "No mods.jsonl or mods.json found", "count": 0}


def _validate_jsonl(file_path: Path, max_age_minutes: int, required_field: str) -> dict:
    """Validate a JSONL file."""
    # Check file was recently modified
    now = datetime.now()
    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
    age_minutes = (now - mtime).total_seconds() / 60
    
    if age_minutes > max_age_minutes:
        return {
            "valid": False, 
            "error": f"File not modified recently (age: {age_minutes:.1f} min, max: {max_age_minutes} min)",
            "count": 0
        }
    
    # Count valid lines
    count = 0
    try:
        with open(file_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    obj = json.loads(line)
                    if required_field in obj:
                        count += 1
    except json.JSONDecodeError as e:
        return {"valid": False, "error": f"Invalid JSON: {e}", "count": 0}
    except Exception as e:
        return {"valid": False, "error": f"Error reading file: {e}", "count": 0}
    
    if count == 0:
        return {"valid": False, "error": "File contains 0 valid records", "count": 0}
    
    return {"valid": True, "error": None, "count": count}


def _validate_json(file_path: Path, max_age_minutes: int, required_keys: list) -> dict:
    """Validate a JSON file."""
    # Check file was recently modified
    now = datetime.now()
    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
    age_minutes = (now - mtime).total_seconds() / 60
    
    if age_minutes > max_age_minutes:
        return {
            "valid": False,
            "error": f"File not modified recently (age: {age_minutes:.1f} min, max: {max_age_minutes} min)",
            "count": 0
        }
    
    # Parse and validate
    try:
        with open(file_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return {"valid": False, "error": f"Invalid JSON: {e}", "count": 0}
    except Exception as e:
        return {"valid": False, "error": f"Error reading file: {e}", "count": 0}
    
    # Check required keys exist
    for key in required_keys:
        if key not in data:
            return {"valid": False, "error": f"Missing required key: {key}", "count": 0}
    
    # Get count from various possible fields
    count = 0
    if "totalCount" in data:
        count = data["totalCount"]
    elif "urls" in data and isinstance(data["urls"], list):
        count = len(data["urls"])
    elif "builds" in data and isinstance(data["builds"], list):
        count = len(data["builds"])
    elif "mods" in data and isinstance(data["mods"], list):
        count = len(data["mods"])
    
    if count == 0:
        return {"valid": False, "error": "File contains 0 records", "count": 0}
    
    return {"valid": True, "error": None, "count": count}


def main():
    if len(sys.argv) < 3:
        print("Usage: validate_output.py <stage> <output_dir> [max_age_minutes]")
        print("Stages: urls, html, builds, mods")
        sys.exit(1)
    
    stage = sys.argv[1]
    output_dir = sys.argv[2]
    max_age = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    
    validators = {
        "urls": validate_urls,
        "html": validate_html_scrape,
        "builds": validate_builds,
        "mods": validate_mods
    }
    
    if stage not in validators:
        print(f"Unknown stage: {stage}")
        sys.exit(1)
    
    result = validators[stage](output_dir, max_age)
    
    # Output result as JSON for easy parsing
    print(json.dumps(result))
    
    # Exit with appropriate code
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()

