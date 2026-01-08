#!/usr/bin/env python3
"""
Stage Validation Script for RalphOS

Validates output from each pipeline stage before proceeding to the next.
Ensures data integrity and catches errors early.

Usage:
    python validate_stage.py <stage> <source_dir>
    python validate_stage.py 1 data/total_cost_involved/     # Validate URL discovery
    python validate_stage.py 2 data/total_cost_involved/     # Validate HTML scraping
    python validate_stage.py 3 data/total_cost_involved/     # Validate build extraction
    python validate_stage.py 4 data/total_cost_involved/     # Validate mod extraction
    python validate_stage.py all data/total_cost_involved/   # Validate all stages
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from urllib.parse import urlparse

# Project paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SCHEMA_FILE = PROJECT_ROOT / "schema" / "build_extraction_schema.json"
COMPONENTS_FILE = PROJECT_ROOT / "schema" / "Vehicle_Componets.json"


class ValidationResult:
    """Holds validation results."""
    def __init__(self, stage: int, passed: bool, errors: List[str], warnings: List[str], stats: Dict):
        self.stage = stage
        self.passed = passed
        self.errors = errors
        self.warnings = warnings
        self.stats = stats
    
    def __str__(self):
        status = "PASSED" if self.passed else "FAILED"
        lines = [f"Stage {self.stage}: {status}"]
        
        if self.stats:
            lines.append("  Stats:")
            for k, v in self.stats.items():
                lines.append(f"    {k}: {v}")
        
        if self.errors:
            lines.append("  Errors:")
            for e in self.errors[:10]:  # Limit to 10
                lines.append(f"    ✗ {e}")
            if len(self.errors) > 10:
                lines.append(f"    ... and {len(self.errors) - 10} more errors")
        
        if self.warnings:
            lines.append("  Warnings:")
            for w in self.warnings[:5]:
                lines.append(f"    ⚠ {w}")
            if len(self.warnings) > 5:
                lines.append(f"    ... and {len(self.warnings) - 5} more warnings")
        
        return "\n".join(lines)


def validate_stage_1(source_dir: Path) -> ValidationResult:
    """
    Validate Stage 1: URL Discovery
    
    Checks:
    - urls.json exists and is valid JSON
    - URLs array is present and non-empty
    - All URLs are valid format
    - No duplicate URLs
    - totalCount matches actual count
    """
    errors = []
    warnings = []
    stats = {}
    
    urls_file = source_dir / "urls.json"
    
    # Check file exists
    if not urls_file.exists():
        return ValidationResult(1, False, ["urls.json not found"], [], {})
    
    # Load and parse JSON
    try:
        with open(urls_file, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return ValidationResult(1, False, [f"Invalid JSON: {e}"], [], {})
    
    # Check structure
    if not isinstance(data, dict):
        errors.append("urls.json must be an object")
        return ValidationResult(1, False, errors, warnings, {})
    
    urls = data.get("urls", [])
    if not isinstance(urls, list):
        errors.append("'urls' field must be an array")
        return ValidationResult(1, False, errors, warnings, {})
    
    stats["total_urls"] = len(urls)
    
    if len(urls) == 0:
        errors.append("No URLs found (empty array)")
        return ValidationResult(1, False, errors, warnings, stats)
    
    # Validate each URL (handle both string and object formats)
    valid_urls = set()
    invalid_count = 0
    
    for i, url_entry in enumerate(urls):
        # Handle both formats: string or {"url": "...", "filename": "..."}
        if isinstance(url_entry, str):
            url = url_entry
        elif isinstance(url_entry, dict) and "url" in url_entry:
            url = url_entry["url"]
        else:
            errors.append(f"URL at index {i} has invalid format")
            invalid_count += 1
            continue
        
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            if invalid_count < 5:  # Limit error messages
                errors.append(f"Invalid URL format: {url[:50]}...")
            invalid_count += 1
            continue
        
        if url in valid_urls:
            warnings.append(f"Duplicate URL: {url[:50]}...")
        else:
            valid_urls.add(url)
    
    stats["valid_urls"] = len(valid_urls)
    stats["invalid_urls"] = invalid_count
    stats["duplicates"] = len(urls) - len(valid_urls) - invalid_count
    
    # Check totalCount field
    if "totalCount" in data:
        if data["totalCount"] != len(urls):
            warnings.append(f"totalCount ({data['totalCount']}) doesn't match actual count ({len(urls)})")
    else:
        warnings.append("Missing 'totalCount' field")
    
    # Check lastUpdated field
    if "lastUpdated" not in data:
        warnings.append("Missing 'lastUpdated' field")
    
    passed = len(errors) == 0 and len(valid_urls) > 0
    return ValidationResult(1, passed, errors, warnings, stats)


def validate_stage_2(source_dir: Path) -> ValidationResult:
    """
    Validate Stage 2: HTML Scraping
    
    Checks:
    - html/ directory exists
    - HTML files are present
    - Files are non-empty
    - Files contain valid HTML markers
    - Scraped count roughly matches URL count
    """
    errors = []
    warnings = []
    stats = {}
    
    html_dir = source_dir / "html"
    urls_file = source_dir / "urls.json"
    
    # Check directory exists
    if not html_dir.exists():
        return ValidationResult(2, False, ["html/ directory not found"], [], {})
    
    if not html_dir.is_dir():
        return ValidationResult(2, False, ["html is not a directory"], [], {})
    
    # Count HTML files
    html_files = list(html_dir.glob("*.html"))
    stats["html_files"] = len(html_files)
    
    if len(html_files) == 0:
        errors.append("No HTML files found in html/ directory")
        return ValidationResult(2, False, errors, warnings, stats)
    
    # Validate HTML files
    empty_files = 0
    invalid_html = 0
    total_size = 0
    
    for html_file in html_files:
        size = html_file.stat().st_size
        total_size += size
        
        if size == 0:
            empty_files += 1
            if empty_files <= 5:
                errors.append(f"Empty file: {html_file.name}")
            continue
        
        # Quick HTML validation (check for basic tags)
        try:
            content = html_file.read_text(encoding='utf-8', errors='ignore')[:1000]
            if not ('<html' in content.lower() or '<!doctype' in content.lower() or '<head' in content.lower()):
                invalid_html += 1
                if invalid_html <= 3:
                    warnings.append(f"May not be valid HTML: {html_file.name}")
        except Exception:
            pass
    
    stats["empty_files"] = empty_files
    stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)
    stats["avg_size_kb"] = round(total_size / len(html_files) / 1024, 1) if html_files else 0
    
    # Compare to URL count
    if urls_file.exists():
        try:
            with open(urls_file, 'r') as f:
                url_data = json.load(f)
            url_count = len(url_data.get("urls", []))
            stats["url_count"] = url_count
            
            completion_pct = (len(html_files) / url_count * 100) if url_count > 0 else 0
            stats["completion_pct"] = round(completion_pct, 1)
            
            if completion_pct < 50:
                warnings.append(f"Only {completion_pct:.1f}% of URLs scraped ({len(html_files)}/{url_count})")
            elif completion_pct < 90:
                warnings.append(f"{completion_pct:.1f}% complete ({len(html_files)}/{url_count})")
        except:
            pass
    
    if empty_files > 5:
        errors.append(f"{empty_files} empty HTML files found")
    
    passed = len(errors) == 0 and len(html_files) > 0
    return ValidationResult(2, passed, errors, warnings, stats)


def validate_stage_3(source_dir: Path) -> ValidationResult:
    """
    Validate Stage 3: Build Extraction
    
    Checks:
    - builds.json exists
    - Valid JSON structure
    - Required fields present in each build
    - Enum values are valid
    - build_id is unique
    """
    errors = []
    warnings = []
    stats = {}
    
    builds_file = source_dir / "builds.json"
    
    if not builds_file.exists():
        return ValidationResult(3, False, ["builds.json not found"], [], {})
    
    # Load JSON
    try:
        with open(builds_file, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return ValidationResult(3, False, [f"Invalid JSON: {e}"], [], {})
    
    # Handle both formats
    if isinstance(data, list):
        builds = data
    elif isinstance(data, dict):
        builds = data.get("builds", [])
    else:
        return ValidationResult(3, False, ["Invalid builds.json structure"], [], {})
    
    stats["total_builds"] = len(builds)
    
    if len(builds) == 0:
        errors.append("No builds found")
        return ValidationResult(3, False, errors, warnings, stats)
    
    # Required fields
    required_fields = ["build_id", "source_type", "build_type", "source_url", "year", "make", "model"]
    
    # Valid enums
    valid_source_types = ["listing", "auction", "build_thread", "project", "gallery", "article"]
    valid_build_types = [
        "OEM+", "Street", "Track", "Drift", "Rally", "Time Attack", "Drag", "Show",
        "Restomod", "Restoration", "Pro Touring", "Overland", "Off-Road", "Rock Crawler",
        "Prerunner", "Trophy Truck", "Lowrider", "Stance", "VIP", "Bosozoku", "Rat Rod",
        "Hot Rod", "Muscle", "Classic", "Modern Classic", "JDM", "Euro", "USDM",
        "Daily Driver", "Weekend Warrior", "Work Truck", "Tow Rig"
    ]
    
    missing_fields = 0
    invalid_enums = 0
    build_ids = set()
    duplicate_ids = 0
    
    for i, build in enumerate(builds):
        if not isinstance(build, dict):
            errors.append(f"Build at index {i} is not an object")
            continue
        
        # Check required fields
        for field in required_fields:
            if field not in build or build[field] is None:
                missing_fields += 1
                if missing_fields <= 3:
                    errors.append(f"Build {i}: missing required field '{field}'")
        
        # Check enums
        if build.get("source_type") and build["source_type"] not in valid_source_types:
            invalid_enums += 1
            if invalid_enums <= 3:
                warnings.append(f"Build {i}: invalid source_type '{build['source_type']}'")
        
        if build.get("build_type") and build["build_type"] not in valid_build_types:
            invalid_enums += 1
            if invalid_enums <= 3:
                warnings.append(f"Build {i}: invalid build_type '{build['build_type']}'")
        
        # Check duplicate build_ids
        bid = build.get("build_id")
        if bid:
            if bid in build_ids:
                duplicate_ids += 1
            else:
                build_ids.add(bid)
    
    stats["missing_fields"] = missing_fields
    stats["invalid_enums"] = invalid_enums
    stats["duplicate_ids"] = duplicate_ids
    stats["unique_build_ids"] = len(build_ids)
    
    # Count builds with modifications
    with_mods = sum(1 for b in builds if b.get("modifications") and len(b.get("modifications", [])) > 0)
    stats["builds_with_mods"] = with_mods
    
    if missing_fields > 0:
        errors.append(f"{missing_fields} total missing required fields")
    
    if duplicate_ids > 0:
        errors.append(f"{duplicate_ids} duplicate build_ids found")
    
    passed = len(errors) == 0 and len(builds) > 0
    return ValidationResult(3, passed, errors, warnings, stats)


def validate_stage_4(source_dir: Path) -> ValidationResult:
    """
    Validate Stage 4: Mod Extraction
    
    Checks:
    - mods.json exists OR modifications in builds.json
    - Each mod has name and category
    - Categories are valid
    - Mods are linked to builds
    """
    errors = []
    warnings = []
    stats = {}
    
    mods_file = source_dir / "mods.json"
    builds_file = source_dir / "builds.json"
    
    # Load valid categories
    valid_categories = set()
    if COMPONENTS_FILE.exists():
        try:
            with open(COMPONENTS_FILE, 'r') as f:
                components = json.load(f)
            valid_categories = set(components.keys())
        except:
            warnings.append("Could not load Vehicle_Componets.json for category validation")
    
    # Add keyword-based categories
    valid_categories.update([
        "Forced Induction", "Oil", "Wheel", "Safety", "Lighting", "Storage",
        "Recovery", "Armor/Protection", "Suspension", "Fuel & Air", 
        "Brake & Wheel Hub", "Engine", "Exhaust & Emission", "Interior",
        "Drivetrain", "Transmission-Manual", "Transmission-Automatic",
        "Electrical", "Cooling System", "Body & Lamp Assembly", "Steering",
        "Heat & Air Conditioning", "Ignition", "Belt Drive", "Wiper & Washer",
        "Aero", "Other"
    ])
    
    all_mods = []
    
    # Check standalone mods.json
    if mods_file.exists():
        try:
            with open(mods_file, 'r') as f:
                mods_data = json.load(f)
            
            if isinstance(mods_data, list):
                all_mods = mods_data
            elif isinstance(mods_data, dict):
                all_mods = mods_data.get("mods", [])
        except json.JSONDecodeError as e:
            errors.append(f"Invalid mods.json: {e}")
    
    # Also check modifications in builds.json
    if builds_file.exists():
        try:
            with open(builds_file, 'r') as f:
                builds_data = json.load(f)
            
            builds = builds_data if isinstance(builds_data, list) else builds_data.get("builds", [])
            
            for build in builds:
                mods = build.get("modifications", [])
                if mods:
                    all_mods.extend(mods)
        except:
            pass
    
    stats["total_mods"] = len(all_mods)
    
    if len(all_mods) == 0:
        if not mods_file.exists() and not builds_file.exists():
            errors.append("Neither mods.json nor builds.json found")
        else:
            warnings.append("No modifications extracted yet")
        return ValidationResult(4, False, errors, warnings, stats)
    
    # Validate mods
    missing_name = 0
    missing_category = 0
    invalid_category = 0
    categories_found = {}
    
    for mod in all_mods:
        if not isinstance(mod, dict):
            continue
        
        if not mod.get("name"):
            missing_name += 1
        
        category = mod.get("category")
        if not category:
            missing_category += 1
        elif valid_categories and category not in valid_categories:
            invalid_category += 1
            if invalid_category <= 3:
                warnings.append(f"Unknown category: {category}")
        else:
            categories_found[category] = categories_found.get(category, 0) + 1
    
    stats["missing_name"] = missing_name
    stats["missing_category"] = missing_category
    stats["invalid_category"] = invalid_category
    stats["unique_categories"] = len(categories_found)
    
    # Top categories
    top_cats = sorted(categories_found.items(), key=lambda x: x[1], reverse=True)[:5]
    stats["top_categories"] = dict(top_cats)
    
    if missing_name > 0:
        errors.append(f"{missing_name} mods missing 'name' field")
    
    if missing_category > len(all_mods) * 0.5:  # More than 50% missing
        errors.append(f"{missing_category} mods missing 'category' field")
    elif missing_category > 0:
        warnings.append(f"{missing_category} mods missing category")
    
    passed = len(errors) == 0 and len(all_mods) > 0
    return ValidationResult(4, passed, errors, warnings, stats)


def validate_all(source_dir: Path) -> List[ValidationResult]:
    """Validate all stages for a source."""
    results = []
    
    # Stage 1
    result1 = validate_stage_1(source_dir)
    results.append(result1)
    
    # Stage 2 (only if stage 1 passed or has data)
    result2 = validate_stage_2(source_dir)
    results.append(result2)
    
    # Stage 3
    result3 = validate_stage_3(source_dir)
    results.append(result3)
    
    # Stage 4
    result4 = validate_stage_4(source_dir)
    results.append(result4)
    
    return results


def main():
    parser = argparse.ArgumentParser(description="RalphOS Stage Validator")
    parser.add_argument("stage", help="Stage to validate (1, 2, 3, 4, or 'all')")
    parser.add_argument("source_dir", help="Path to source data directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    source_dir = Path(args.source_dir)
    if not source_dir.exists():
        print(f"Error: Directory not found: {source_dir}")
        return 1
    
    print(f"\nValidating: {source_dir}")
    print("=" * 60)
    
    if args.stage == "all":
        results = validate_all(source_dir)
        
        if args.json:
            output = [{
                "stage": r.stage,
                "passed": r.passed,
                "errors": r.errors,
                "warnings": r.warnings,
                "stats": r.stats
            } for r in results]
            print(json.dumps(output, indent=2))
        else:
            all_passed = True
            for result in results:
                print(result)
                print()
                if not result.passed:
                    all_passed = False
            
            print("=" * 60)
            if all_passed:
                print("All stages PASSED")
            else:
                failed = [r.stage for r in results if not r.passed]
                print(f"FAILED stages: {failed}")
        
        return 0 if all(r.passed for r in results) else 1
    
    else:
        try:
            stage = int(args.stage)
        except ValueError:
            print(f"Error: Invalid stage '{args.stage}'. Use 1, 2, 3, 4, or 'all'")
            return 1
        
        if stage not in [1, 2, 3, 4]:
            print(f"Error: Stage must be 1, 2, 3, or 4")
            return 1
        
        validators = {
            1: validate_stage_1,
            2: validate_stage_2,
            3: validate_stage_3,
            4: validate_stage_4
        }
        
        result = validators[stage](source_dir)
        
        if args.json:
            print(json.dumps({
                "stage": result.stage,
                "passed": result.passed,
                "errors": result.errors,
                "warnings": result.warnings,
                "stats": result.stats
            }, indent=2))
        else:
            print(result)
        
        return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())

