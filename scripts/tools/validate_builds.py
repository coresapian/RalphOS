#!/usr/bin/env python3
"""
Build Validation Script for RalphOS

Validates builds.json files against the build_extraction_schema.json schema.
Reports validation errors and provides suggestions for fixes.

Usage:
    python validate_builds.py data/source_name/builds.json
    python validate_builds.py --all  # Validate all builds.json files
    python validate_builds.py --fix data/source_name/builds.json  # Auto-fix common issues
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Schema location
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SCHEMA_FILE = PROJECT_ROOT / "schema" / "build_extraction_schema.json"
DATA_DIR = PROJECT_ROOT / "data"

# Required fields from schema
REQUIRED_FIELDS = ["build_id", "source_type", "build_type", "build_source", "source_url", "year", "make", "model"]

# Valid enum values
VALID_SOURCE_TYPES = ["listing", "auction", "build_thread", "project", "gallery", "article"]
VALID_BUILD_TYPES = [
    "OEM+", "Street", "Track", "Drift", "Rally", "Time Attack", "Drag", "Show",
    "Restomod", "Restoration", "Pro Touring", "Overland", "Off-Road", "Rock Crawler",
    "Prerunner", "Trophy Truck", "Lowrider", "Stance", "VIP", "Bosozoku", "Rat Rod",
    "Hot Rod", "Muscle", "Classic", "Modern Classic", "JDM", "Euro", "USDM", 
    "Daily Driver", "Weekend Warrior", "Work Truck", "Tow Rig"
]
VALID_TRANSMISSIONS = ["Manual", "Automatic", "DCT", "CVT", "Sequential", None]
VALID_DRIVETRAINS = ["RWD", "FWD", "AWD", "4WD", None]
VALID_MOD_LEVELS = ["Stock", "Lightly Modified", "Moderately Modified", "Heavily Modified"]


class ValidationError:
    """Represents a validation error."""
    def __init__(self, build_id: int, field: str, message: str, severity: str = "error"):
        self.build_id = build_id
        self.field = field
        self.message = message
        self.severity = severity  # "error", "warning", "info"
    
    def __str__(self):
        icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}[self.severity]
        return f"{icon} Build {self.build_id} - {self.field}: {self.message}"


def load_builds(filepath: Path) -> Tuple[List[Dict], Optional[str]]:
    """Load builds from JSON file."""
    if not filepath.exists():
        return [], f"File not found: {filepath}"
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Handle both formats: {"builds": [...]} and raw [...]
        if isinstance(data, list):
            return data, None
        elif isinstance(data, dict) and "builds" in data:
            return data["builds"], None
        else:
            return [], "Invalid format: expected list or {builds: [...]}"
    
    except json.JSONDecodeError as e:
        return [], f"JSON parse error: {e}"


def validate_build(build: Dict, index: int) -> List[ValidationError]:
    """Validate a single build record."""
    errors = []
    build_id = build.get("build_id", f"index_{index}")
    
    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in build or build[field] is None:
            errors.append(ValidationError(build_id, field, f"Required field missing or null"))
    
    # Validate build_id
    if "build_id" in build and build["build_id"] is not None:
        if not isinstance(build["build_id"], int):
            errors.append(ValidationError(build_id, "build_id", "Must be an integer"))
    
    # Validate source_type enum
    if "source_type" in build and build["source_type"] is not None:
        if build["source_type"] not in VALID_SOURCE_TYPES:
            errors.append(ValidationError(
                build_id, "source_type", 
                f"Invalid value '{build['source_type']}'. Valid: {VALID_SOURCE_TYPES}"
            ))
    
    # Validate build_type enum
    if "build_type" in build and build["build_type"] is not None:
        if build["build_type"] not in VALID_BUILD_TYPES:
            errors.append(ValidationError(
                build_id, "build_type",
                f"Invalid value '{build['build_type']}'. See schema for valid types.",
                severity="warning"
            ))
    
    # Validate transmission enum
    if "transmission" in build and build["transmission"] is not None:
        if build["transmission"] not in [t for t in VALID_TRANSMISSIONS if t]:
            errors.append(ValidationError(
                build_id, "transmission",
                f"Invalid value '{build['transmission']}'. Valid: {[t for t in VALID_TRANSMISSIONS if t]}"
            ))
    
    # Validate drivetrain enum
    if "drivetrain" in build and build["drivetrain"] is not None:
        if build["drivetrain"] not in [d for d in VALID_DRIVETRAINS if d]:
            errors.append(ValidationError(
                build_id, "drivetrain",
                f"Invalid value '{build['drivetrain']}'. Valid: {[d for d in VALID_DRIVETRAINS if d]}"
            ))
    
    # Validate modification_level enum
    if "modification_level" in build and build["modification_level"] is not None:
        if build["modification_level"] not in VALID_MOD_LEVELS:
            errors.append(ValidationError(
                build_id, "modification_level",
                f"Invalid value '{build['modification_level']}'. Valid: {VALID_MOD_LEVELS}"
            ))
    
    # Validate year format (4-digit string)
    if "year" in build and build["year"] is not None:
        year_str = str(build["year"])
        if not re.match(r"^\d{4}$", year_str):
            errors.append(ValidationError(build_id, "year", f"Must be 4-digit year, got '{year_str}'"))
        else:
            year_int = int(year_str)
            if year_int < 1885 or year_int > datetime.now().year + 2:
                errors.append(ValidationError(
                    build_id, "year", f"Year {year_int} seems invalid",
                    severity="warning"
                ))
    
    # Validate source_url format
    if "source_url" in build and build["source_url"] is not None:
        url = build["source_url"]
        if not url.startswith(("http://", "https://")):
            errors.append(ValidationError(build_id, "source_url", "Must be a valid URL"))
    
    # Validate VIN format (17 characters, specific pattern)
    if "vin" in build and build["vin"] is not None:
        vin = build["vin"]
        if not re.match(r"^[A-HJ-NPR-Z0-9]{17}$", vin):
            errors.append(ValidationError(
                build_id, "vin", f"Invalid VIN format: {vin}",
                severity="warning"
            ))
    
    # Validate extraction_confidence range
    if "extraction_confidence" in build and build["extraction_confidence"] is not None:
        conf = build["extraction_confidence"]
        if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
            errors.append(ValidationError(
                build_id, "extraction_confidence",
                f"Must be between 0.0 and 1.0, got {conf}"
            ))
    
    # Validate modifications array
    if "modifications" in build and build["modifications"] is not None:
        if not isinstance(build["modifications"], list):
            errors.append(ValidationError(build_id, "modifications", "Must be an array"))
        else:
            for i, mod in enumerate(build["modifications"]):
                if not isinstance(mod, dict):
                    errors.append(ValidationError(
                        build_id, f"modifications[{i}]", "Each modification must be an object"
                    ))
                elif "name" not in mod or "category" not in mod:
                    errors.append(ValidationError(
                        build_id, f"modifications[{i}]",
                        "Missing required fields 'name' and/or 'category'"
                    ))
    
    # Validate sale_data presence based on source_type
    source_type = build.get("source_type")
    sale_data = build.get("sale_data")
    
    if source_type in ["listing", "auction"]:
        if sale_data is None:
            errors.append(ValidationError(
                build_id, "sale_data",
                f"Should be present for source_type '{source_type}'",
                severity="warning"
            ))
    elif source_type in ["build_thread", "project", "gallery", "article"]:
        if sale_data is not None:
            errors.append(ValidationError(
                build_id, "sale_data",
                f"Should be null for source_type '{source_type}'",
                severity="info"
            ))
    
    # Check modification_level matches mod count
    mods = build.get("modifications", [])
    mod_level = build.get("modification_level")
    if mod_level and mods:
        mod_count = len(mods)
        expected_level = calculate_mod_level(mod_count)
        if mod_level != expected_level:
            errors.append(ValidationError(
                build_id, "modification_level",
                f"'{mod_level}' doesn't match mod count ({mod_count}). Expected: '{expected_level}'",
                severity="info"
            ))
    
    return errors


def calculate_mod_level(mod_count: int) -> str:
    """Calculate modification level from count."""
    if mod_count <= 1:
        return "Stock"
    elif mod_count <= 5:
        return "Lightly Modified"
    elif mod_count <= 15:
        return "Moderately Modified"
    else:
        return "Heavily Modified"


def validate_file(filepath: Path, fix: bool = False) -> Tuple[int, int, int]:
    """
    Validate a builds.json file.
    
    Returns:
        Tuple of (error_count, warning_count, info_count)
    """
    print(f"\n{'='*60}")
    print(f"Validating: {filepath}")
    print('='*60)
    
    builds, load_error = load_builds(filepath)
    
    if load_error:
        print(f"✗ {load_error}")
        return 1, 0, 0
    
    if not builds:
        print("ℹ No builds found in file")
        return 0, 0, 1
    
    print(f"Found {len(builds)} builds")
    
    all_errors = []
    for i, build in enumerate(builds):
        errors = validate_build(build, i)
        all_errors.extend(errors)
    
    # Count by severity
    error_count = sum(1 for e in all_errors if e.severity == "error")
    warning_count = sum(1 for e in all_errors if e.severity == "warning")
    info_count = sum(1 for e in all_errors if e.severity == "info")
    
    if not all_errors:
        print("✓ All builds valid!")
    else:
        # Group errors by build_id
        by_build = {}
        for error in all_errors:
            by_build.setdefault(error.build_id, []).append(error)
        
        for build_id, errors in by_build.items():
            print(f"\nBuild {build_id}:")
            for error in errors:
                print(f"  {error}")
    
    print(f"\nSummary: {error_count} errors, {warning_count} warnings, {info_count} info")
    
    # Auto-fix if requested
    if fix and (error_count > 0 or warning_count > 0):
        fixed = auto_fix_builds(builds, filepath)
        if fixed:
            print(f"✓ Applied {fixed} auto-fixes")
    
    return error_count, warning_count, info_count


def auto_fix_builds(builds: List[Dict], filepath: Path) -> int:
    """Apply automatic fixes to common issues."""
    fix_count = 0
    
    for build in builds:
        # Fix year format (convert int to string)
        if "year" in build and isinstance(build["year"], int):
            build["year"] = str(build["year"])
            fix_count += 1
        
        # Fix modification_level based on mod count
        mods = build.get("modifications", [])
        if mods:
            expected_level = calculate_mod_level(len(mods))
            if build.get("modification_level") != expected_level:
                build["modification_level"] = expected_level
                fix_count += 1
        
        # Ensure sale_data is null for non-listing/auction types
        source_type = build.get("source_type")
        if source_type in ["build_thread", "project", "gallery", "article"]:
            if build.get("sale_data") is not None:
                build["sale_data"] = None
                fix_count += 1
    
    if fix_count > 0:
        # Save fixed builds
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            data = builds
        else:
            data["builds"] = builds
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    return fix_count


def validate_all() -> Tuple[int, int, int]:
    """Validate all builds.json files in data directory."""
    total_errors = 0
    total_warnings = 0
    total_info = 0
    files_validated = 0
    
    for source_dir in DATA_DIR.iterdir():
        if not source_dir.is_dir():
            continue
        
        builds_file = source_dir / "builds.json"
        if builds_file.exists():
            errors, warnings, info = validate_file(builds_file)
            total_errors += errors
            total_warnings += warnings
            total_info += info
            files_validated += 1
    
    print(f"\n{'='*60}")
    print(f"TOTAL: Validated {files_validated} files")
    print(f"       {total_errors} errors, {total_warnings} warnings, {total_info} info")
    print('='*60)
    
    return total_errors, total_warnings, total_info


def main():
    parser = argparse.ArgumentParser(description="Validate builds.json files")
    parser.add_argument("filepath", nargs="?", help="Path to builds.json file")
    parser.add_argument("--all", "-a", action="store_true", help="Validate all builds.json files")
    parser.add_argument("--fix", "-f", action="store_true", help="Auto-fix common issues")
    
    args = parser.parse_args()
    
    if args.all:
        errors, _, _ = validate_all()
        return 1 if errors > 0 else 0
    
    if not args.filepath:
        print("Usage: python validate_builds.py <builds.json>")
        print("       python validate_builds.py --all")
        return 1
    
    filepath = Path(args.filepath)
    errors, _, _ = validate_file(filepath, fix=args.fix)
    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

