#!/usr/bin/env python3
"""
Deep Content Audit Script for RalphOS

Comprehensive validation of extracted data quality before marking a source complete.
This is the FINAL checkpoint in the pipeline - run after all stages.

Pipeline flow:
  URL Discovery → HTML Scraping → Build Extraction → Mod Extraction → **AUDIT**

Usage:
    # Full audit (recommended before marking complete)
    python scripts/tools/audit_extraction.py data/carandclassic/

    # Quick audit (skip slow checks)
    python scripts/tools/audit_extraction.py data/carandclassic/ --quick

    # Audit with HTML content sampling (verifies extraction accuracy)
    python scripts/tools/audit_extraction.py data/carandclassic/ --sample-html 10

    # JSON output for programmatic use
    python scripts/tools/audit_extraction.py data/carandclassic/ --json

Audit Checks:
    1. Pipeline Completeness - All stages have output files
    2. Cross-Reference Integrity - HTML files match extracted builds
    3. Data Quality - Required fields, valid values, no duplicates
    4. Extraction Accuracy - Sample verification against HTML content
    5. Modification Validation - Valid categories, reasonable counts
    6. Image Validation - URL format, no broken patterns
    7. Coverage Analysis - What % of URLs resulted in valid builds

Exit codes:
    0 - Audit PASSED (all critical checks passed)
    1 - Audit FAILED (critical issues found)
    2 - Audit WARNING (non-critical issues, manual review recommended)
    3 - Error during execution
"""

import argparse
import json
import re
import sys
import random
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse
from collections import Counter
import hashlib


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class AuditIssue:
    """Represents a single audit issue."""
    severity: str  # "critical", "warning", "info"
    category: str  # "completeness", "integrity", "quality", "accuracy", etc.
    message: str
    details: Optional[Dict] = None

    def __str__(self):
        icon = {"critical": "❌", "warning": "⚠️", "info": "ℹ️"}.get(self.severity, "•")
        return f"{icon} [{self.category}] {self.message}"


@dataclass
class AuditResult:
    """Complete audit result."""
    source_dir: Path
    timestamp: str
    duration_seconds: float
    passed: bool
    issues: List[AuditIssue] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    def add_issue(self, severity: str, category: str, message: str, details: Dict = None):
        self.issues.append(AuditIssue(severity, category, message, details))

    def to_dict(self) -> Dict:
        return {
            "source_dir": str(self.source_dir),
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "passed": self.passed,
            "summary": {
                "critical_issues": self.critical_count,
                "warnings": self.warning_count,
                "total_issues": len(self.issues)
            },
            "stats": self.stats,
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "message": i.message,
                    "details": i.details
                }
                for i in self.issues
            ]
        }


# ============================================================================
# Validation Constants
# ============================================================================

VALID_SOURCE_TYPES = {"listing", "auction", "build_thread", "project", "gallery", "article"}

VALID_BUILD_TYPES = {
    "OEM+", "Street", "Track", "Drift", "Rally", "Time Attack", "Drag", "Show",
    "Restomod", "Restoration", "Pro Touring", "Overland", "Off-Road", "Rock Crawler",
    "Prerunner", "Trophy Truck", "Lowrider", "Stance", "VIP", "Bosozoku", "Rat Rod",
    "Hot Rod", "Muscle", "Classic", "Modern Classic", "JDM", "Euro", "USDM",
    "Daily Driver", "Weekend Warrior", "Work Truck", "Tow Rig"
}

VALID_MOD_CATEGORIES = {
    "Forced Induction", "Oil", "Wheel", "Safety", "Lighting", "Storage",
    "Recovery", "Armor/Protection", "Suspension", "Fuel & Air",
    "Brake & Wheel Hub", "Engine", "Exhaust & Emission", "Interior",
    "Drivetrain", "Transmission-Manual", "Transmission-Automatic",
    "Electrical", "Cooling System", "Body & Lamp Assembly", "Steering",
    "Heat & Air Conditioning", "Ignition", "Belt Drive", "Wiper & Washer",
    "Aero", "Other"
}

# Year validation
MIN_VALID_YEAR = 1885  # First automobile
MAX_VALID_YEAR = datetime.now().year + 2  # Allow next model year

# Common automotive makes for validation
COMMON_MAKES = {
    "ford", "chevrolet", "chevy", "toyota", "honda", "bmw", "mercedes", "audi",
    "porsche", "volkswagen", "vw", "nissan", "mazda", "subaru", "mitsubishi",
    "lexus", "acura", "infiniti", "dodge", "jeep", "chrysler", "ram", "gmc",
    "cadillac", "buick", "lincoln", "tesla", "hyundai", "kia", "volvo", "jaguar",
    "land rover", "ferrari", "lamborghini", "mclaren", "aston martin", "bentley",
    "rolls royce", "alfa romeo", "fiat", "mini", "saab", "lotus", "maserati"
}


# ============================================================================
# Audit Functions
# ============================================================================

def load_json_file(filepath: Path) -> Optional[Any]:
    """Safely load a JSON file."""
    if not filepath.exists():
        return None
    try:
        with open(filepath) as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def load_jsonl_file(filepath: Path) -> List[Dict]:
    """Load a JSONL file."""
    if not filepath.exists():
        return []
    records = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def audit_pipeline_completeness(source_dir: Path, result: AuditResult):
    """Check that all pipeline stages have output files."""

    # Stage 1: URL Discovery
    urls_json = source_dir / "urls.json"
    urls_jsonl = source_dir / "urls.jsonl"

    if not urls_json.exists() and not urls_jsonl.exists():
        result.add_issue("critical", "completeness", "No URL file found (urls.json or urls.jsonl)")
    else:
        url_file = urls_json if urls_json.exists() else urls_jsonl
        result.stats["url_file"] = str(url_file.name)

        if urls_json.exists():
            data = load_json_file(urls_json)
            if data:
                urls = data.get("urls", []) if isinstance(data, dict) else data
                result.stats["total_urls"] = len(urls)
        else:
            urls = load_jsonl_file(urls_jsonl)
            result.stats["total_urls"] = len(urls)

    # Stage 2: HTML Scraping
    html_dir = source_dir / "html"
    if not html_dir.exists():
        result.add_issue("critical", "completeness", "No html/ directory found")
    else:
        html_files = list(html_dir.glob("*.html"))
        result.stats["html_files"] = len(html_files)

        if len(html_files) == 0:
            result.add_issue("critical", "completeness", "html/ directory is empty")

    # Stage 3: Build Extraction
    builds_json = source_dir / "builds.json"
    builds_jsonl = source_dir / "builds.jsonl"

    if not builds_json.exists() and not builds_jsonl.exists():
        result.add_issue("critical", "completeness", "No builds file found (builds.json or builds.jsonl)")
    else:
        if builds_json.exists():
            data = load_json_file(builds_json)
            if data:
                builds = data.get("builds", data) if isinstance(data, dict) else data
                result.stats["total_builds"] = len(builds) if isinstance(builds, list) else 0
        else:
            builds = load_jsonl_file(builds_jsonl)
            result.stats["total_builds"] = len(builds)

    # Stage 4: Mod Extraction (optional - mods may be in builds.json)
    mods_json = source_dir / "mods.json"
    mods_jsonl = source_dir / "mods.jsonl"

    if mods_json.exists():
        data = load_json_file(mods_json)
        if data:
            mods = data.get("mods", data) if isinstance(data, dict) else data
            result.stats["total_mods_file"] = len(mods) if isinstance(mods, list) else 0
    elif mods_jsonl.exists():
        mods = load_jsonl_file(mods_jsonl)
        result.stats["total_mods_file"] = len(mods)


def audit_cross_reference_integrity(source_dir: Path, result: AuditResult):
    """Verify HTML files match extracted builds."""

    html_dir = source_dir / "html"
    if not html_dir.exists():
        return

    # Get HTML file build_ids
    html_build_ids = set()
    for html_file in html_dir.glob("*.html"):
        # Extract build_id from filename (e.g., 1234567890.html)
        try:
            build_id = int(html_file.stem)
            html_build_ids.add(build_id)
        except ValueError:
            # Filename might be a slug, not a build_id
            pass

    # Get extracted build_ids
    builds = []
    builds_json = source_dir / "builds.json"
    builds_jsonl = source_dir / "builds.jsonl"

    if builds_json.exists():
        data = load_json_file(builds_json)
        if data:
            builds = data.get("builds", data) if isinstance(data, dict) else data
            if not isinstance(builds, list):
                builds = []
    elif builds_jsonl.exists():
        builds = load_jsonl_file(builds_jsonl)

    extracted_build_ids = set()
    for build in builds:
        bid = build.get("build_id")
        if bid:
            extracted_build_ids.add(int(bid) if isinstance(bid, str) else bid)

    result.stats["html_build_ids"] = len(html_build_ids)
    result.stats["extracted_build_ids"] = len(extracted_build_ids)

    # Cross-reference check
    if html_build_ids and extracted_build_ids:
        # HTML files without extracted builds
        missing_extraction = html_build_ids - extracted_build_ids
        if missing_extraction:
            pct = len(missing_extraction) / len(html_build_ids) * 100
            if pct > 20:
                result.add_issue(
                    "critical", "integrity",
                    f"{len(missing_extraction)} HTML files ({pct:.1f}%) have no extracted build",
                    {"sample": list(missing_extraction)[:5]}
                )
            elif pct > 5:
                result.add_issue(
                    "warning", "integrity",
                    f"{len(missing_extraction)} HTML files ({pct:.1f}%) have no extracted build",
                    {"sample": list(missing_extraction)[:5]}
                )

        # Extracted builds without HTML (shouldn't happen)
        orphan_builds = extracted_build_ids - html_build_ids
        if orphan_builds:
            result.add_issue(
                "warning", "integrity",
                f"{len(orphan_builds)} builds have no corresponding HTML file",
                {"sample": list(orphan_builds)[:5]}
            )

    # Calculate extraction rate
    if html_build_ids:
        extraction_rate = len(extracted_build_ids & html_build_ids) / len(html_build_ids) * 100
        result.stats["extraction_rate_pct"] = round(extraction_rate, 1)


def audit_data_quality(source_dir: Path, result: AuditResult):
    """Validate data quality of extracted builds."""

    builds = []
    builds_json = source_dir / "builds.json"
    builds_jsonl = source_dir / "builds.jsonl"

    if builds_json.exists():
        data = load_json_file(builds_json)
        if data:
            builds = data.get("builds", data) if isinstance(data, dict) else data
            if not isinstance(builds, list):
                builds = []
    elif builds_jsonl.exists():
        builds = load_jsonl_file(builds_jsonl)

    if not builds:
        return

    # Track issues
    missing_required = Counter()
    invalid_years = []
    invalid_source_types = []
    invalid_build_types = []
    duplicate_ids = []
    empty_makes = 0
    empty_models = 0
    unusual_makes = []

    seen_ids = set()
    required_fields = ["build_id", "source_url", "year", "make", "model"]

    for i, build in enumerate(builds):
        # Required fields
        for field in required_fields:
            if field not in build or build[field] is None or build[field] == "":
                missing_required[field] += 1

        # Duplicate IDs
        bid = build.get("build_id")
        if bid:
            if bid in seen_ids:
                duplicate_ids.append(bid)
            seen_ids.add(bid)

        # Year validation
        year = build.get("year")
        if year:
            try:
                year_int = int(str(year).strip())
                if year_int < MIN_VALID_YEAR or year_int > MAX_VALID_YEAR:
                    invalid_years.append({"index": i, "year": year})
            except (ValueError, TypeError):
                invalid_years.append({"index": i, "year": year})

        # Make validation
        make = build.get("make", "")
        if not make or str(make).strip() == "":
            empty_makes += 1
        elif str(make).lower().strip() not in COMMON_MAKES and len(unusual_makes) < 10:
            unusual_makes.append(make)

        # Model validation
        model = build.get("model", "")
        if not model or str(model).strip() == "":
            empty_models += 1

        # Source type validation
        source_type = build.get("source_type")
        if source_type and source_type not in VALID_SOURCE_TYPES:
            invalid_source_types.append(source_type)

        # Build type validation
        build_type = build.get("build_type")
        if build_type and build_type not in VALID_BUILD_TYPES:
            invalid_build_types.append(build_type)

    # Report issues
    total = len(builds)

    # Missing required fields
    for field, count in missing_required.items():
        pct = count / total * 100
        if pct > 10:
            result.add_issue(
                "critical", "quality",
                f"{count} builds ({pct:.1f}%) missing required field '{field}'"
            )
        elif pct > 0:
            result.add_issue(
                "warning", "quality",
                f"{count} builds ({pct:.1f}%) missing field '{field}'"
            )

    # Duplicates
    if duplicate_ids:
        result.add_issue(
            "critical", "quality",
            f"{len(duplicate_ids)} duplicate build_ids found",
            {"duplicates": duplicate_ids[:10]}
        )

    # Invalid years
    if invalid_years:
        result.add_issue(
            "warning", "quality",
            f"{len(invalid_years)} builds have invalid years",
            {"samples": invalid_years[:5]}
        )

    # Empty make/model
    if empty_makes > total * 0.1:
        result.add_issue("warning", "quality", f"{empty_makes} builds ({empty_makes/total*100:.1f}%) have empty make")
    if empty_models > total * 0.1:
        result.add_issue("warning", "quality", f"{empty_models} builds ({empty_models/total*100:.1f}%) have empty model")

    # Invalid enum values
    if invalid_source_types:
        unique_invalid = set(invalid_source_types)
        result.add_issue(
            "warning", "quality",
            f"{len(invalid_source_types)} builds have invalid source_type",
            {"invalid_values": list(unique_invalid)[:10]}
        )

    if invalid_build_types:
        unique_invalid = set(invalid_build_types)
        result.add_issue(
            "info", "quality",
            f"{len(invalid_build_types)} builds have non-standard build_type",
            {"values": list(unique_invalid)[:10]}
        )

    # Stats
    result.stats["builds_validated"] = total
    result.stats["unique_build_ids"] = len(seen_ids)

    # Make/Model stats
    makes = Counter(str(b.get("make", "")).lower().strip() for b in builds if b.get("make"))
    result.stats["unique_makes"] = len(makes)
    result.stats["top_makes"] = dict(makes.most_common(5))


def audit_modification_quality(source_dir: Path, result: AuditResult):
    """Validate modification data quality."""

    # Collect all mods (from mods.json or embedded in builds)
    all_mods = []

    # From standalone mods file
    mods_json = source_dir / "mods.json"
    mods_jsonl = source_dir / "mods.jsonl"

    if mods_json.exists():
        data = load_json_file(mods_json)
        if data:
            mods = data.get("mods", data) if isinstance(data, dict) else data
            if isinstance(mods, list):
                all_mods.extend(mods)
    elif mods_jsonl.exists():
        all_mods.extend(load_jsonl_file(mods_jsonl))

    # From builds
    builds_json = source_dir / "builds.json"
    builds_jsonl = source_dir / "builds.jsonl"
    builds = []

    if builds_json.exists():
        data = load_json_file(builds_json)
        if data:
            builds = data.get("builds", data) if isinstance(data, dict) else data
            if not isinstance(builds, list):
                builds = []
    elif builds_jsonl.exists():
        builds = load_jsonl_file(builds_jsonl)

    builds_with_mods = 0
    for build in builds:
        mods = build.get("modifications", [])
        if mods:
            builds_with_mods += 1
            all_mods.extend(mods)

    if not all_mods:
        result.add_issue("info", "mods", "No modifications found in extraction")
        return

    result.stats["total_mods"] = len(all_mods)
    result.stats["builds_with_mods"] = builds_with_mods

    # Validate mods
    missing_name = 0
    missing_category = 0
    invalid_categories = Counter()
    categories = Counter()

    for mod in all_mods:
        if not isinstance(mod, dict):
            continue

        # Name validation
        name = mod.get("name") or mod.get("part_name") or mod.get("modification")
        if not name or str(name).strip() == "":
            missing_name += 1

        # Category validation
        category = mod.get("category")
        if not category:
            missing_category += 1
        else:
            categories[category] += 1
            if category not in VALID_MOD_CATEGORIES:
                invalid_categories[category] += 1

    # Report issues
    total_mods = len(all_mods)

    if missing_name > total_mods * 0.1:
        result.add_issue(
            "warning", "mods",
            f"{missing_name} mods ({missing_name/total_mods*100:.1f}%) missing name"
        )

    if missing_category > total_mods * 0.3:
        result.add_issue(
            "warning", "mods",
            f"{missing_category} mods ({missing_category/total_mods*100:.1f}%) missing category"
        )

    if invalid_categories:
        result.add_issue(
            "info", "mods",
            f"{sum(invalid_categories.values())} mods have non-standard categories",
            {"categories": dict(invalid_categories.most_common(10))}
        )

    # Stats
    result.stats["unique_categories"] = len(categories)
    result.stats["top_categories"] = dict(categories.most_common(5))

    # Mod per build ratio
    if builds:
        avg_mods = len(all_mods) / len(builds)
        result.stats["avg_mods_per_build"] = round(avg_mods, 1)


def audit_image_urls(source_dir: Path, result: AuditResult):
    """Validate image URLs in builds."""

    builds = []
    builds_json = source_dir / "builds.json"
    builds_jsonl = source_dir / "builds.jsonl"

    if builds_json.exists():
        data = load_json_file(builds_json)
        if data:
            builds = data.get("builds", data) if isinstance(data, dict) else data
            if not isinstance(builds, list):
                builds = []
    elif builds_jsonl.exists():
        builds = load_jsonl_file(builds_jsonl)

    if not builds:
        return

    total_images = 0
    builds_with_images = 0
    invalid_urls = 0
    placeholder_images = 0

    # Patterns for placeholder/broken images
    placeholder_patterns = [
        r'placeholder', r'no-image', r'noimage', r'default', r'missing',
        r'blank\.', r'1x1\.', r'spacer', r'transparent'
    ]
    placeholder_re = re.compile('|'.join(placeholder_patterns), re.IGNORECASE)

    for build in builds:
        images = build.get("gallery_images") or build.get("images") or []
        if not isinstance(images, list):
            images = [images] if images else []

        if images:
            builds_with_images += 1

        for img in images:
            if not img or not isinstance(img, str):
                continue

            total_images += 1

            # URL format validation
            parsed = urlparse(img)
            if not parsed.scheme or not parsed.netloc:
                invalid_urls += 1
                continue

            # Placeholder detection
            if placeholder_re.search(img):
                placeholder_images += 1

    result.stats["total_images"] = total_images
    result.stats["builds_with_images"] = builds_with_images

    if total_images > 0:
        result.stats["avg_images_per_build"] = round(total_images / len(builds), 1)

        if invalid_urls > total_images * 0.1:
            result.add_issue(
                "warning", "images",
                f"{invalid_urls} image URLs ({invalid_urls/total_images*100:.1f}%) have invalid format"
            )

        if placeholder_images > total_images * 0.2:
            result.add_issue(
                "warning", "images",
                f"{placeholder_images} images ({placeholder_images/total_images*100:.1f}%) appear to be placeholders"
            )

    # Coverage
    if builds:
        img_coverage = builds_with_images / len(builds) * 100
        result.stats["image_coverage_pct"] = round(img_coverage, 1)

        if img_coverage < 50:
            result.add_issue(
                "info", "images",
                f"Only {img_coverage:.1f}% of builds have images"
            )


def audit_extraction_accuracy(source_dir: Path, result: AuditResult, sample_size: int = 5):
    """
    Sample HTML files and verify extraction accuracy.

    This performs spot-checks by loading HTML content and verifying
    that extracted year/make/model actually appear in the source.
    """

    html_dir = source_dir / "html"
    if not html_dir.exists():
        return

    # Load builds indexed by build_id
    builds = []
    builds_json = source_dir / "builds.json"
    builds_jsonl = source_dir / "builds.jsonl"

    if builds_json.exists():
        data = load_json_file(builds_json)
        if data:
            builds = data.get("builds", data) if isinstance(data, dict) else data
            if not isinstance(builds, list):
                builds = []
    elif builds_jsonl.exists():
        builds = load_jsonl_file(builds_jsonl)

    if not builds:
        return

    # Index by build_id
    builds_by_id = {}
    for build in builds:
        bid = build.get("build_id")
        if bid:
            builds_by_id[str(bid)] = build

    # Sample HTML files that have corresponding builds
    html_files = list(html_dir.glob("*.html"))
    matched_files = [f for f in html_files if f.stem in builds_by_id]

    if not matched_files:
        return

    # Random sample
    sample_files = random.sample(matched_files, min(sample_size, len(matched_files)))

    accuracy_checks = []

    for html_file in sample_files:
        build = builds_by_id.get(html_file.stem)
        if not build:
            continue

        try:
            html_content = html_file.read_text(encoding='utf-8', errors='ignore').lower()
        except Exception:
            continue

        # Check if year appears in HTML
        year = str(build.get("year", ""))
        year_found = year and year in html_content

        # Check if make appears in HTML
        make = str(build.get("make", "")).lower()
        make_found = make and make in html_content

        # Check if model appears in HTML
        model = str(build.get("model", "")).lower()
        model_found = model and model in html_content

        check = {
            "build_id": html_file.stem,
            "year": {"value": year, "found": year_found},
            "make": {"value": make, "found": make_found},
            "model": {"value": model, "found": model_found},
            "all_found": year_found and make_found and model_found
        }
        accuracy_checks.append(check)

    # Calculate accuracy
    if accuracy_checks:
        fully_accurate = sum(1 for c in accuracy_checks if c["all_found"])
        accuracy_pct = fully_accurate / len(accuracy_checks) * 100

        result.stats["sample_accuracy_pct"] = round(accuracy_pct, 1)
        result.stats["samples_checked"] = len(accuracy_checks)

        if accuracy_pct < 70:
            result.add_issue(
                "warning", "accuracy",
                f"Only {accuracy_pct:.1f}% of sampled builds have year/make/model in HTML",
                {"failed_samples": [c for c in accuracy_checks if not c["all_found"]][:3]}
            )
        elif accuracy_pct < 90:
            result.add_issue(
                "info", "accuracy",
                f"{accuracy_pct:.1f}% extraction accuracy on {len(accuracy_checks)} samples"
            )


def audit_coverage(source_dir: Path, result: AuditResult):
    """Calculate overall pipeline coverage/success rate."""

    urls_count = result.stats.get("total_urls", 0)
    html_count = result.stats.get("html_files", 0)
    builds_count = result.stats.get("total_builds", 0)

    if urls_count > 0:
        # HTML scraping coverage
        scrape_coverage = html_count / urls_count * 100
        result.stats["scrape_coverage_pct"] = round(scrape_coverage, 1)

        if scrape_coverage < 50:
            result.add_issue(
                "critical", "coverage",
                f"Only {scrape_coverage:.1f}% of URLs were scraped ({html_count}/{urls_count})"
            )
        elif scrape_coverage < 80:
            result.add_issue(
                "warning", "coverage",
                f"{scrape_coverage:.1f}% scrape coverage ({html_count}/{urls_count})"
            )

    if html_count > 0:
        # Build extraction coverage
        extract_coverage = builds_count / html_count * 100
        result.stats["extract_coverage_pct"] = round(extract_coverage, 1)

        if extract_coverage < 50:
            result.add_issue(
                "critical", "coverage",
                f"Only {extract_coverage:.1f}% of HTML files yielded builds ({builds_count}/{html_count})"
            )
        elif extract_coverage < 80:
            result.add_issue(
                "warning", "coverage",
                f"{extract_coverage:.1f}% extraction coverage ({builds_count}/{html_count})"
            )

    # Overall pipeline success rate
    if urls_count > 0 and builds_count > 0:
        overall = builds_count / urls_count * 100
        result.stats["overall_success_pct"] = round(overall, 1)


# ============================================================================
# Main Audit Function
# ============================================================================

def run_audit(
    source_dir: Path,
    quick: bool = False,
    sample_html: int = 5
) -> AuditResult:
    """
    Run comprehensive audit on extracted data.

    Args:
        source_dir: Path to source data directory
        quick: Skip slow checks (HTML sampling)
        sample_html: Number of HTML files to sample for accuracy check

    Returns:
        AuditResult with all findings
    """
    start_time = datetime.now()

    result = AuditResult(
        source_dir=source_dir,
        timestamp=start_time.isoformat(),
        duration_seconds=0,
        passed=True
    )

    print(f"\n{'='*60}")
    print(f"🔍 DEEP CONTENT AUDIT: {source_dir.name}")
    print(f"{'='*60}\n")

    # Run all audit checks
    print("Checking pipeline completeness...")
    audit_pipeline_completeness(source_dir, result)

    print("Checking cross-reference integrity...")
    audit_cross_reference_integrity(source_dir, result)

    print("Validating data quality...")
    audit_data_quality(source_dir, result)

    print("Validating modifications...")
    audit_modification_quality(source_dir, result)

    print("Validating image URLs...")
    audit_image_urls(source_dir, result)

    if not quick and sample_html > 0:
        print(f"Sampling {sample_html} HTML files for accuracy...")
        audit_extraction_accuracy(source_dir, result, sample_html)

    print("Calculating coverage metrics...")
    audit_coverage(source_dir, result)

    # Determine pass/fail
    result.passed = result.critical_count == 0

    # Calculate duration
    result.duration_seconds = (datetime.now() - start_time).total_seconds()

    return result


def print_result(result: AuditResult):
    """Print audit result in human-readable format."""

    print(f"\n{'='*60}")
    print("📊 AUDIT RESULTS")
    print(f"{'='*60}\n")

    # Stats summary
    print("Pipeline Stats:")
    for key, value in result.stats.items():
        if not key.startswith("_"):
            print(f"  • {key}: {value}")

    print()

    # Issues by severity
    if result.issues:
        print("Issues Found:")

        for severity in ["critical", "warning", "info"]:
            issues = [i for i in result.issues if i.severity == severity]
            if issues:
                print(f"\n  {severity.upper()} ({len(issues)}):")
                for issue in issues:
                    print(f"    {issue}")
    else:
        print("✅ No issues found!")

    # Final verdict
    print(f"\n{'='*60}")
    if result.passed:
        print("✅ AUDIT PASSED - Source ready for completion")
    elif result.critical_count > 0:
        print(f"❌ AUDIT FAILED - {result.critical_count} critical issues found")
    else:
        print(f"⚠️ AUDIT WARNING - {result.warning_count} warnings, manual review recommended")
    print(f"{'='*60}")
    print(f"Duration: {result.duration_seconds:.1f}s")


def main():
    parser = argparse.ArgumentParser(
        description="Deep content audit for RalphOS extractions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "source_dir",
        type=Path,
        help="Source directory to audit (e.g., data/carandclassic/)"
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip slow checks (HTML content sampling)"
    )

    parser.add_argument(
        "--sample-html",
        type=int,
        default=5,
        help="Number of HTML files to sample for accuracy verification (default: 5)"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    if not args.source_dir.exists():
        print(f"Error: Directory not found: {args.source_dir}")
        return 3

    result = run_audit(
        args.source_dir,
        quick=args.quick,
        sample_html=0 if args.quick else args.sample_html
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print_result(result)

    # Exit codes
    if result.critical_count > 0:
        return 1
    elif result.warning_count > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
