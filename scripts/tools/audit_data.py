#!/usr/bin/env python3
"""
Ralph Data Directory Audit Script - Deep Content Validation

Comprehensive audit including:
- HTML content validation (detect blocked, error pages, corrupted files)
- Build extraction quality checks (field validation, year ranges, image URLs)
- Modification validation (garbage detection, category validation)
- Cross-reference integrity (HTML ↔ builds ↔ mods)

Usage:
    python scripts/tools/audit_data.py [--verbose] [--json] [--deep]
    python scripts/tools/audit_data.py --source wheelspecialists --deep
    python scripts/tools/audit_data.py --report audit_report.json
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict, Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import random

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ANSI colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

def c(text: str, color: str) -> str:
    """Colorize text for terminal output."""
    return f"{color}{text}{Colors.RESET}"


# ============================================================================
# HTML Validation Patterns
# ============================================================================

# Patterns that indicate blocked/error responses
ERROR_PATTERNS = [
    # HTTP errors
    (r'\b403\s*(forbidden|error)?\b', 'http_403'),
    (r'\b404\s*(not\s*found|error)?\b', 'http_404'),
    (r'\b500\s*(internal\s*server|error)?\b', 'http_500'),
    (r'\b502\s*(bad\s*gateway)?\b', 'http_502'),
    (r'\b503\s*(service\s*unavailable)?\b', 'http_503'),

    # Anti-bot / WAF
    (r'cloudflare', 'cloudflare_blocked'),
    (r'please\s+enable\s+(javascript|cookies)', 'js_required'),
    (r'captcha|recaptcha|hcaptcha', 'captcha'),
    (r'access\s+denied', 'access_denied'),
    (r'blocked|firewall|waf', 'blocked'),
    (r'rate\s*limit(ed)?', 'rate_limited'),
    (r'too\s+many\s+requests', 'rate_limited'),
    (r'bot\s+detection|suspicious\s+activity', 'bot_detected'),
    (r'ddos[\-\s]protection', 'ddos_protection'),

    # Page not found / removed
    (r'page\s*(not\s*found|removed|deleted)', 'page_removed'),
    (r'(listing|item|vehicle)\s*(no\s*longer|has\s*been)\s*(available|sold|removed)', 'listing_removed'),
    (r'this\s+(page|listing)\s+(doesn.t|does\s*not)\s*exist', 'page_removed'),

    # Login required
    (r'(please\s+)?(log\s*in|sign\s*in)\s+(to\s+(view|access|continue)|required)', 'login_required'),
    (r'members?\s+only', 'login_required'),

    # Empty / placeholder
    (r'coming\s+soon', 'placeholder'),
    (r'under\s+construction', 'placeholder'),
]

# Compiled patterns for efficiency
COMPILED_ERROR_PATTERNS = [(re.compile(p, re.IGNORECASE), name) for p, name in ERROR_PATTERNS]

# Minimum content thresholds
MIN_HTML_SIZE = 500  # bytes - anything smaller is suspect
MIN_VALID_HTML_SIZE = 2000  # bytes - minimum for a real page with content
MAX_ERROR_PATTERN_MATCHES = 3  # More than this = likely an error page


# ============================================================================
# Build Validation
# ============================================================================

# Known car makes for validation
KNOWN_MAKES = {
    'acura', 'alfa romeo', 'amc', 'aston martin', 'audi', 'bentley', 'bmw',
    'bugatti', 'buick', 'cadillac', 'chevrolet', 'chevy', 'chrysler', 'citroen',
    'datsun', 'dodge', 'ferrari', 'fiat', 'ford', 'genesis', 'gmc', 'honda',
    'hummer', 'hyundai', 'infiniti', 'isuzu', 'jaguar', 'jeep', 'kia',
    'lamborghini', 'land rover', 'lexus', 'lincoln', 'lotus', 'maserati',
    'mazda', 'mclaren', 'mercedes', 'mercedes-benz', 'mercury', 'mini',
    'mitsubishi', 'nissan', 'oldsmobile', 'opel', 'pagani', 'peugeot',
    'plymouth', 'pontiac', 'porsche', 'ram', 'renault', 'rivian', 'rolls-royce',
    'saab', 'saturn', 'scion', 'seat', 'shelby', 'skoda', 'smart', 'subaru',
    'suzuki', 'tesla', 'toyota', 'triumph', 'vauxhall', 'volkswagen', 'vw',
    'volvo', 'willys'
}

# Year validation
MIN_VALID_YEAR = 1900
MAX_VALID_YEAR = 2027

# Garbage patterns in text fields
GARBAGE_PATTERNS = [
    r'^(null|none|undefined|n/a|na|tbd|test|xxx|asdf)$',
    r'^[\W\d]+$',  # Only symbols/numbers
    r'^.{0,2}$',  # Too short
    r'lorem\s+ipsum',
    r'placeholder',
    r'^(string|object|array|error)$',
]
COMPILED_GARBAGE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in GARBAGE_PATTERNS]


# ============================================================================
# Modification Validation
# ============================================================================

# Valid modification categories
VALID_CATEGORIES = {
    'engine', 'suspension', 'wheels/tires', 'wheels', 'tires', 'exterior',
    'interior', 'exhaust', 'brakes', 'electrical', 'drivetrain', 'cooling',
    'body', 'lighting', 'performance', 'audio', 'intake', 'turbo',
    'supercharger', 'fuel', 'transmission', 'differential', 'steering',
    'safety', 'aero', 'aerodynamics', 'other', 'wheel', 'brake & wheel hub',
    'exhaust & emission'
}


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class HTMLValidation:
    """Validation results for HTML files."""
    total_files: int = 0
    valid_files: int = 0
    empty_files: int = 0
    tiny_files: int = 0  # < MIN_HTML_SIZE
    small_files: int = 0  # < MIN_VALID_HTML_SIZE
    error_pages: int = 0
    total_bytes: int = 0

    # Error type breakdown
    error_types: dict = field(default_factory=lambda: defaultdict(int))

    # Sample bad files for reporting
    sample_errors: list = field(default_factory=list)

    @property
    def valid_pct(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (self.valid_files / self.total_files) * 100

    @property
    def error_pct(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (self.error_pages / self.total_files) * 100


@dataclass
class BuildValidation:
    """Validation results for build data."""
    total_builds: int = 0
    valid_builds: int = 0

    # Field completeness
    with_build_id: int = 0
    with_url: int = 0
    with_year: int = 0
    with_valid_year: int = 0
    with_make: int = 0
    with_known_make: int = 0
    with_model: int = 0
    with_title: int = 0
    with_story: int = 0
    with_images: int = 0
    with_mods_raw: int = 0

    # Issues
    duplicate_ids: int = 0
    invalid_years: list = field(default_factory=list)
    unknown_makes: list = field(default_factory=list)
    garbage_fields: list = field(default_factory=list)

    # Linked HTML check
    builds_with_html: int = 0
    builds_missing_html: int = 0

    @property
    def completeness_score(self) -> float:
        """Calculate field completeness score (0-100)."""
        if self.total_builds == 0:
            return 0.0

        weights = {
            'build_id': 1.0,
            'url': 1.0,
            'make': 1.0,
            'model': 1.0,
            'year': 0.5,
            'title': 0.3,
            'story': 0.3,
            'images': 0.5,
        }

        score = 0
        score += (self.with_build_id / self.total_builds) * weights['build_id']
        score += (self.with_url / self.total_builds) * weights['url']
        score += (self.with_make / self.total_builds) * weights['make']
        score += (self.with_model / self.total_builds) * weights['model']
        score += (self.with_year / self.total_builds) * weights['year']
        score += (self.with_title / self.total_builds) * weights['title']
        score += (self.with_story / self.total_builds) * weights['story']
        score += (self.with_images / self.total_builds) * weights['images']

        return (score / sum(weights.values())) * 100


@dataclass
class ModValidation:
    """Validation results for modification data."""
    total_mods: int = 0
    valid_mods: int = 0

    # Field completeness
    with_name: int = 0
    with_brand: int = 0
    with_category: int = 0
    with_valid_category: int = 0

    # Category distribution
    categories: dict = field(default_factory=lambda: defaultdict(int))
    unknown_categories: list = field(default_factory=list)

    # Issues
    garbage_names: list = field(default_factory=list)
    duplicate_mods: int = 0

    # Link to builds
    orphan_mods: int = 0  # Mods without matching build_id


@dataclass
class SourceAudit:
    """Complete audit results for a single source directory."""
    name: str
    path: str

    # File counts
    html_files: int = 0
    json_files: int = 0
    jsonl_files: int = 0
    python_files: int = 0
    other_files: int = 0
    total_bytes: int = 0

    # Pipeline stage indicators
    has_urls: bool = False
    has_html_dir: bool = False
    has_builds: bool = False
    has_mods: bool = False

    # URL stats
    url_count: int = 0

    # Deep validation results
    html_validation: HTMLValidation = field(default_factory=HTMLValidation)
    build_validation: BuildValidation = field(default_factory=BuildValidation)
    mod_validation: ModValidation = field(default_factory=ModValidation)

    # Overall issues
    issues: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def pipeline_stage(self) -> str:
        if self.has_builds and self.has_mods:
            return "complete"
        elif self.has_builds:
            return "stage3_partial"
        elif self.has_html_dir and self.html_files > 0:
            return "stage2_complete"
        elif self.has_urls:
            return "stage1_complete"
        else:
            return "empty"

    @property
    def overall_quality(self) -> float:
        """Combined quality score considering HTML, builds, and mods."""
        scores = []

        if self.html_validation.total_files > 0:
            scores.append(self.html_validation.valid_pct)

        if self.build_validation.total_builds > 0:
            scores.append(self.build_validation.completeness_score)

        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    @property
    def health_status(self) -> str:
        """Overall health status."""
        if self.overall_quality >= 80:
            return "healthy"
        elif self.overall_quality >= 60:
            return "warning"
        elif self.overall_quality >= 40:
            return "degraded"
        else:
            return "critical"


@dataclass
class AuditReport:
    """Complete audit report for the data directory."""
    timestamp: str
    data_dir: str
    deep_scan: bool = False

    # Summary stats
    total_sources: int = 0
    total_html_files: int = 0
    total_valid_html: int = 0
    total_error_html: int = 0
    total_builds: int = 0
    total_valid_builds: int = 0
    total_mods: int = 0
    total_bytes: int = 0

    # Pipeline status counts
    sources_empty: int = 0
    sources_stage1: int = 0
    sources_stage2: int = 0
    sources_stage3: int = 0
    sources_complete: int = 0

    # Health counts
    sources_healthy: int = 0
    sources_warning: int = 0
    sources_degraded: int = 0
    sources_critical: int = 0

    # Quality metrics
    avg_html_valid_pct: float = 0.0
    avg_build_completeness: float = 0.0
    total_issues: int = 0
    total_warnings: int = 0

    # Error breakdown across all sources
    html_error_types: dict = field(default_factory=lambda: defaultdict(int))

    # Detailed source audits
    sources: list = field(default_factory=list)

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024 * 1024 * 1024)


# ============================================================================
# Auditor Class
# ============================================================================

class DataAuditor:
    """Audits the Ralph data directory for content quality and integrity."""

    def __init__(self, data_dir: Path, verbose: bool = False, deep: bool = False,
                 sample_size: int = 100):
        self.data_dir = data_dir
        self.verbose = verbose
        self.deep = deep
        self.sample_size = sample_size  # Number of files to sample for deep scan
        self.report = AuditReport(
            timestamp=datetime.now().isoformat(),
            data_dir=str(data_dir),
            deep_scan=deep
        )

    def log(self, msg: str, level: str = "info"):
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            prefix = {
                "info": c("ℹ", Colors.BLUE),
                "warn": c("⚠", Colors.YELLOW),
                "error": c("✗", Colors.RED),
                "success": c("✓", Colors.GREEN)
            }.get(level, "")
            print(f"  {prefix} {msg}")

    def audit_source(self, source_dir: Path) -> SourceAudit:
        """Audit a single source directory with deep content validation."""
        audit = SourceAudit(
            name=source_dir.name,
            path=str(source_dir)
        )

        if not source_dir.is_dir():
            audit.issues.append(f"Not a directory: {source_dir}")
            return audit

        # Basic file scanning
        self._scan_files(source_dir, audit)
        self._check_pipeline_files(source_dir, audit)
        self._validate_urls(source_dir, audit)

        # Deep content validation
        if self.deep or self.verbose:
            self._validate_html_content(source_dir, audit)
            self._validate_builds_deep(source_dir, audit)
            self._validate_mods_deep(source_dir, audit)
            self._cross_validate(source_dir, audit)

        return audit

    def _scan_files(self, source_dir: Path, audit: SourceAudit):
        """Scan and categorize all files."""
        for item in source_dir.rglob('*'):
            if item.is_file():
                try:
                    size = item.stat().st_size
                except OSError:
                    continue

                audit.total_bytes += size
                suffix = item.suffix.lower()

                if suffix == '.html':
                    audit.html_files += 1
                elif suffix == '.json':
                    audit.json_files += 1
                elif suffix == '.jsonl':
                    audit.jsonl_files += 1
                elif suffix == '.py':
                    audit.python_files += 1
                else:
                    audit.other_files += 1

    def _check_pipeline_files(self, source_dir: Path, audit: SourceAudit):
        """Check for presence of pipeline stage files."""
        audit.has_urls = (source_dir / 'urls.json').exists() or (source_dir / 'urls.jsonl').exists()
        audit.has_html_dir = (source_dir / 'html').is_dir()
        audit.has_builds = (source_dir / 'builds.json').exists() or (source_dir / 'builds.jsonl').exists()
        audit.has_mods = (source_dir / 'mods.json').exists() or (source_dir / 'mods.jsonl').exists()

    def _validate_urls(self, source_dir: Path, audit: SourceAudit):
        """Validate URL files."""
        urls_file = source_dir / 'urls.json'
        if not urls_file.exists():
            return

        try:
            with open(urls_file, 'r') as f:
                data = json.load(f)

            if isinstance(data, dict) and 'urls' in data:
                urls = data['urls']
            elif isinstance(data, list):
                urls = data
            else:
                return

            audit.url_count = len(urls)

        except Exception as e:
            audit.issues.append(f"Error reading urls.json: {e}")

    def _validate_html_content(self, source_dir: Path, audit: SourceAudit):
        """Deep validation of HTML file contents."""
        html_dir = source_dir / 'html'
        if not html_dir.is_dir():
            return

        html_files = list(html_dir.glob('*.html'))
        audit.html_validation.total_files = len(html_files)

        # Sample files if there are too many
        if len(html_files) > self.sample_size:
            sampled_files = random.sample(html_files, self.sample_size)
            is_sampled = True
        else:
            sampled_files = html_files
            is_sampled = False

        valid_count = 0
        error_count = 0

        for html_file in sampled_files:
            try:
                size = html_file.stat().st_size
                audit.html_validation.total_bytes += size

                # Size checks
                if size == 0:
                    audit.html_validation.empty_files += 1
                    error_count += 1
                    continue
                elif size < MIN_HTML_SIZE:
                    audit.html_validation.tiny_files += 1
                elif size < MIN_VALID_HTML_SIZE:
                    audit.html_validation.small_files += 1

                # Content check
                with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(50000)  # Read first 50KB for pattern matching

                # Check for error patterns
                error_matches = []
                for pattern, error_type in COMPILED_ERROR_PATTERNS:
                    if pattern.search(content):
                        error_matches.append(error_type)
                        audit.html_validation.error_types[error_type] += 1

                # Determine if this is an error page
                if len(error_matches) >= MAX_ERROR_PATTERN_MATCHES:
                    audit.html_validation.error_pages += 1
                    error_count += 1

                    # Store sample for reporting
                    if len(audit.html_validation.sample_errors) < 5:
                        audit.html_validation.sample_errors.append({
                            'file': html_file.name,
                            'size': size,
                            'errors': error_matches[:5]
                        })
                else:
                    valid_count += 1

            except Exception as e:
                self.log(f"Error reading {html_file.name}: {e}", "error")

        # Extrapolate if sampled
        if is_sampled:
            ratio = len(html_files) / len(sampled_files)
            audit.html_validation.valid_files = int(valid_count * ratio)
            audit.html_validation.error_pages = int(error_count * ratio)
            audit.html_validation.empty_files = int(audit.html_validation.empty_files * ratio)
            audit.html_validation.tiny_files = int(audit.html_validation.tiny_files * ratio)
            audit.html_validation.small_files = int(audit.html_validation.small_files * ratio)
        else:
            audit.html_validation.valid_files = valid_count
            audit.html_validation.error_pages = error_count

        # Generate warnings
        error_pct = audit.html_validation.error_pct
        if error_pct > 50:
            audit.issues.append(f"CRITICAL: {error_pct:.0f}% of HTML files are error pages")
        elif error_pct > 20:
            audit.warnings.append(f"High error rate: {error_pct:.0f}% of HTML files are error pages")

        # Report top error types
        if audit.html_validation.error_types:
            top_errors = sorted(audit.html_validation.error_types.items(),
                              key=lambda x: x[1], reverse=True)[:3]
            if top_errors:
                error_summary = ', '.join(f"{e[0]}({e[1]})" for e in top_errors)
                audit.warnings.append(f"Top HTML errors: {error_summary}")

    def _validate_builds_deep(self, source_dir: Path, audit: SourceAudit):
        """Deep validation of build data."""
        builds = self._load_builds(source_dir)
        if not builds:
            return

        audit.build_validation.total_builds = len(builds)
        seen_ids = set()
        html_dir = source_dir / 'html'

        for build in builds:
            # Check build_id
            bid = build.get('build_id')
            if bid:
                audit.build_validation.with_build_id += 1
                if bid in seen_ids:
                    audit.build_validation.duplicate_ids += 1
                seen_ids.add(bid)

                # Check if HTML file exists
                if html_dir.is_dir():
                    html_file = html_dir / f"{bid}.html"
                    if html_file.exists():
                        audit.build_validation.builds_with_html += 1
                    else:
                        audit.build_validation.builds_missing_html += 1

            # Check URL
            url = build.get('source_url') or build.get('url')
            if url and isinstance(url, str) and url.startswith('http'):
                audit.build_validation.with_url += 1

            # Check year
            year = build.get('year')
            if year:
                audit.build_validation.with_year += 1
                try:
                    year_int = int(str(year)[:4])
                    if MIN_VALID_YEAR <= year_int <= MAX_VALID_YEAR:
                        audit.build_validation.with_valid_year += 1
                    else:
                        if len(audit.build_validation.invalid_years) < 5:
                            audit.build_validation.invalid_years.append(year)
                except (ValueError, TypeError):
                    if len(audit.build_validation.invalid_years) < 5:
                        audit.build_validation.invalid_years.append(year)

            # Check make
            make = build.get('make')
            if make and not self._is_garbage(make):
                audit.build_validation.with_make += 1
                if make.lower().strip() in KNOWN_MAKES:
                    audit.build_validation.with_known_make += 1
                else:
                    if len(audit.build_validation.unknown_makes) < 10:
                        audit.build_validation.unknown_makes.append(make)

            # Check model
            model = build.get('model')
            if model and not self._is_garbage(model):
                audit.build_validation.with_model += 1

            # Check title
            title = build.get('build_title')
            if title and not self._is_garbage(title):
                audit.build_validation.with_title += 1

            # Check story
            story = build.get('build_story')
            if story and len(str(story)) > 50:
                audit.build_validation.with_story += 1

            # Check images
            images = build.get('gallery_images', [])
            if images and len(images) > 0:
                audit.build_validation.with_images += 1

            # Check raw mods
            mods_raw = build.get('modifications_raw', [])
            if mods_raw and len(mods_raw) > 0:
                audit.build_validation.with_mods_raw += 1

        # Count valid builds (has required fields)
        audit.build_validation.valid_builds = min(
            audit.build_validation.with_build_id,
            audit.build_validation.with_url,
            audit.build_validation.with_make,
            audit.build_validation.with_model
        )

        # Generate warnings
        if audit.build_validation.duplicate_ids > 0:
            audit.warnings.append(
                f"Found {audit.build_validation.duplicate_ids} duplicate build IDs"
            )

        completeness = audit.build_validation.completeness_score
        if completeness < 50:
            audit.issues.append(f"Low build completeness: {completeness:.0f}%")
        elif completeness < 70:
            audit.warnings.append(f"Build completeness: {completeness:.0f}%")

    def _validate_mods_deep(self, source_dir: Path, audit: SourceAudit):
        """Deep validation of modification data."""
        mods = self._load_mods(source_dir)
        if not mods:
            return

        audit.mod_validation.total_mods = len(mods)
        seen_mods = set()
        build_ids = self._get_build_ids(source_dir)

        for mod in mods:
            # Check name
            name = mod.get('name')
            if name and not self._is_garbage(name):
                audit.mod_validation.with_name += 1
            else:
                if len(audit.mod_validation.garbage_names) < 5:
                    audit.mod_validation.garbage_names.append(name)

            # Check brand
            brand = mod.get('brand')
            if brand and not self._is_garbage(brand):
                audit.mod_validation.with_brand += 1

            # Check category
            category = mod.get('category')
            if category:
                audit.mod_validation.with_category += 1
                cat_lower = category.lower().strip()
                audit.mod_validation.categories[category] += 1

                if cat_lower in VALID_CATEGORIES:
                    audit.mod_validation.with_valid_category += 1
                else:
                    if category not in audit.mod_validation.unknown_categories:
                        audit.mod_validation.unknown_categories.append(category)

            # Check for duplicates
            mod_key = (mod.get('build_id'), name, category)
            if mod_key in seen_mods:
                audit.mod_validation.duplicate_mods += 1
            seen_mods.add(mod_key)

            # Check orphan mods
            bid = mod.get('build_id')
            if bid and build_ids and bid not in build_ids:
                audit.mod_validation.orphan_mods += 1

        # Count valid mods
        audit.mod_validation.valid_mods = min(
            audit.mod_validation.with_name,
            audit.mod_validation.with_category
        )

        # Generate warnings
        if audit.mod_validation.unknown_categories:
            audit.warnings.append(
                f"Unknown mod categories: {', '.join(audit.mod_validation.unknown_categories[:5])}"
            )

        if audit.mod_validation.orphan_mods > 0:
            audit.warnings.append(
                f"Found {audit.mod_validation.orphan_mods} mods without matching builds"
            )

    def _cross_validate(self, source_dir: Path, audit: SourceAudit):
        """Cross-validate data consistency between HTML, builds, and mods."""
        # Check HTML count vs build count
        if audit.html_files > 0 and audit.build_validation.total_builds > 0:
            ratio = audit.build_validation.total_builds / audit.html_files
            if ratio < 0.5:
                audit.warnings.append(
                    f"Low extraction rate: only {ratio*100:.0f}% of HTML files have builds"
                )
            elif ratio > 1.2:
                audit.warnings.append(
                    f"More builds ({audit.build_validation.total_builds}) than HTML files ({audit.html_files})"
                )

        # Check builds vs mods
        if audit.build_validation.total_builds > 0 and audit.mod_validation.total_mods > 0:
            mods_per_build = audit.mod_validation.total_mods / audit.build_validation.total_builds
            if mods_per_build < 0.5:
                audit.warnings.append(
                    f"Low mod extraction: avg {mods_per_build:.1f} mods per build"
                )

    def _load_builds(self, source_dir: Path) -> list:
        """Load builds from JSONL or JSON file."""
        builds = []

        jsonl_file = source_dir / 'builds.jsonl'
        json_file = source_dir / 'builds.json'

        if jsonl_file.exists():
            try:
                with open(jsonl_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            builds.append(json.loads(line))
            except Exception:
                pass

        elif json_file.exists():
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                if isinstance(data, dict) and 'builds' in data:
                    builds = data['builds']
                elif isinstance(data, list):
                    builds = data
            except Exception:
                pass

        return builds

    def _load_mods(self, source_dir: Path) -> list:
        """Load modifications from JSONL or JSON file."""
        mods = []

        jsonl_file = source_dir / 'mods.jsonl'
        json_file = source_dir / 'mods.json'

        if jsonl_file.exists():
            try:
                with open(jsonl_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            mods.append(json.loads(line))
            except Exception:
                pass

        elif json_file.exists():
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                if isinstance(data, dict) and 'mods' in data:
                    mods = data['mods']
                elif isinstance(data, list):
                    mods = data
            except Exception:
                pass

        return mods

    def _get_build_ids(self, source_dir: Path) -> set:
        """Get set of all build IDs."""
        builds = self._load_builds(source_dir)
        return {b.get('build_id') for b in builds if b.get('build_id')}

    def _is_garbage(self, value: str) -> bool:
        """Check if a value is garbage/placeholder."""
        if not value:
            return True
        value_str = str(value).strip()
        for pattern in COMPILED_GARBAGE_PATTERNS:
            if pattern.match(value_str):
                return True
        return False

    def run_audit(self, source_filter: Optional[str] = None) -> AuditReport:
        """Run complete audit of the data directory."""
        print(c("\n╔══════════════════════════════════════════════════════════════╗", Colors.CYAN))
        print(c("║        RALPH DATA AUDIT - DEEP CONTENT VALIDATION           ║", Colors.CYAN))
        print(c("╚══════════════════════════════════════════════════════════════╝", Colors.CYAN))
        print(f"\n{c('Data Directory:', Colors.DIM)} {self.data_dir}")
        print(f"{c('Deep Scan:', Colors.DIM)} {'Enabled' if self.deep else 'Disabled (use --deep)'}")
        print(f"{c('Timestamp:', Colors.DIM)} {self.report.timestamp}\n")

        # Find all source directories
        source_dirs = sorted([
            d for d in self.data_dir.iterdir()
            if d.is_dir() and not d.name.startswith('.')
        ])

        if source_filter:
            source_dirs = [d for d in source_dirs if source_filter.lower() in d.name.lower()]
            print(c(f"Filtered to {len(source_dirs)} sources matching '{source_filter}'", Colors.YELLOW))

        print(c(f"Scanning {len(source_dirs)} source directories...\n", Colors.BLUE))

        # Audit each source
        html_valid_pcts = []
        build_completeness_scores = []

        for i, source_dir in enumerate(source_dirs):
            if self.verbose:
                print(f"  [{i+1}/{len(source_dirs)}] {source_dir.name}...", end=" ", flush=True)

            audit = self.audit_source(source_dir)
            self.report.sources.append(audit)

            if self.verbose:
                status = c("✓", Colors.GREEN) if audit.health_status in ("healthy", "warning") else c("!", Colors.YELLOW)
                print(f"{status} {audit.overall_quality:.0f}%")

            # Update summary stats
            self.report.total_sources += 1
            self.report.total_html_files += audit.html_files
            self.report.total_valid_html += audit.html_validation.valid_files
            self.report.total_error_html += audit.html_validation.error_pages
            self.report.total_builds += audit.build_validation.total_builds
            self.report.total_valid_builds += audit.build_validation.valid_builds
            self.report.total_mods += audit.mod_validation.total_mods
            self.report.total_bytes += audit.total_bytes

            # Aggregate error types
            for error_type, count in audit.html_validation.error_types.items():
                self.report.html_error_types[error_type] += count

            # Pipeline stage counts
            stage = audit.pipeline_stage
            if stage == "empty":
                self.report.sources_empty += 1
            elif stage == "stage1_complete":
                self.report.sources_stage1 += 1
            elif stage in ("stage2_started", "stage2_complete"):
                self.report.sources_stage2 += 1
            elif stage == "stage3_partial":
                self.report.sources_stage3 += 1
            elif stage == "complete":
                self.report.sources_complete += 1

            # Health counts
            health = audit.health_status
            if health == "healthy":
                self.report.sources_healthy += 1
            elif health == "warning":
                self.report.sources_warning += 1
            elif health == "degraded":
                self.report.sources_degraded += 1
            else:
                self.report.sources_critical += 1

            # Track issues
            self.report.total_issues += len(audit.issues)
            self.report.total_warnings += len(audit.warnings)

            # Quality metrics
            if audit.html_validation.total_files > 0:
                html_valid_pcts.append(audit.html_validation.valid_pct)
            if audit.build_validation.total_builds > 0:
                build_completeness_scores.append(audit.build_validation.completeness_score)

        # Calculate averages
        if html_valid_pcts:
            self.report.avg_html_valid_pct = sum(html_valid_pcts) / len(html_valid_pcts)
        if build_completeness_scores:
            self.report.avg_build_completeness = sum(build_completeness_scores) / len(build_completeness_scores)

        return self.report

    def print_summary(self):
        """Print a formatted summary of the audit results."""
        r = self.report

        # Overall stats
        print(c("\n┌─────────────────────────────────────────────────────────────┐", Colors.BLUE))
        print(c("│                    SUMMARY STATISTICS                       │", Colors.BLUE))
        print(c("└─────────────────────────────────────────────────────────────┘", Colors.BLUE))

        print(f"\n  {c('Total Sources:', Colors.BOLD)} {r.total_sources}")
        print(f"  {c('Total Size:', Colors.BOLD)} {r.total_gb:.2f} GB")
        print(f"  {c('Total HTML Files:', Colors.BOLD)} {r.total_html_files:,}")
        print(f"  {c('Total Builds:', Colors.BOLD)} {r.total_builds:,}")
        print(f"  {c('Total Modifications:', Colors.BOLD)} {r.total_mods:,}")

        # HTML Health
        if self.deep and r.total_html_files > 0:
            print(c("\n┌─────────────────────────────────────────────────────────────┐", Colors.CYAN))
            print(c("│                    HTML CONTENT HEALTH                      │", Colors.CYAN))
            print(c("└─────────────────────────────────────────────────────────────┘", Colors.CYAN))

            valid_pct = (r.total_valid_html / r.total_html_files * 100) if r.total_html_files else 0
            error_pct = (r.total_error_html / r.total_html_files * 100) if r.total_html_files else 0

            valid_color = Colors.GREEN if valid_pct >= 80 else (Colors.YELLOW if valid_pct >= 60 else Colors.RED)
            error_color = Colors.GREEN if error_pct < 10 else (Colors.YELLOW if error_pct < 30 else Colors.RED)

            print(f"\n  {c('Valid HTML Files:', Colors.BOLD)} {r.total_valid_html:,} ({c(f'{valid_pct:.1f}%', valid_color)})")
            print(f"  {c('Error Pages:', Colors.BOLD)} {r.total_error_html:,} ({c(f'{error_pct:.1f}%', error_color)})")

            # Error breakdown
            if r.html_error_types:
                print(f"\n  {c('Error Types Detected:', Colors.BOLD)}")
                sorted_errors = sorted(r.html_error_types.items(), key=lambda x: x[1], reverse=True)
                for error_type, count in sorted_errors[:8]:
                    bar_len = min(int(count / max(r.html_error_types.values()) * 20), 20)
                    bar = "█" * bar_len
                    print(f"    {error_type:<20} {c(bar, Colors.RED)} {count:,}")

        # Build Quality
        if self.deep and r.total_builds > 0:
            print(c("\n┌─────────────────────────────────────────────────────────────┐", Colors.GREEN))
            print(c("│                    BUILD DATA QUALITY                       │", Colors.GREEN))
            print(c("└─────────────────────────────────────────────────────────────┘", Colors.GREEN))

            valid_pct = (r.total_valid_builds / r.total_builds * 100) if r.total_builds else 0
            completeness_color = Colors.GREEN if r.avg_build_completeness >= 80 else (
                Colors.YELLOW if r.avg_build_completeness >= 60 else Colors.RED
            )

            print(f"\n  {c('Valid Builds:', Colors.BOLD)} {r.total_valid_builds:,} / {r.total_builds:,} ({valid_pct:.1f}%)")
            print(f"  {c('Avg Completeness:', Colors.BOLD)} {c(f'{r.avg_build_completeness:.1f}%', completeness_color)}")

        # Health Status
        print(c("\n┌─────────────────────────────────────────────────────────────┐", Colors.HEADER))
        print(c("│                    SOURCE HEALTH STATUS                     │", Colors.HEADER))
        print(c("└─────────────────────────────────────────────────────────────┘", Colors.HEADER))

        max_count = max(r.sources_healthy, r.sources_warning, r.sources_degraded, r.sources_critical, 1)
        bar_width = 25

        health_data = [
            ("🟢 Healthy (80%+)", r.sources_healthy, Colors.GREEN),
            ("🟡 Warning (60-80%)", r.sources_warning, Colors.YELLOW),
            ("🟠 Degraded (40-60%)", r.sources_degraded, Colors.YELLOW),
            ("🔴 Critical (<40%)", r.sources_critical, Colors.RED),
        ]

        for name, count, color in health_data:
            bar_len = int((count / max_count) * bar_width) if max_count > 0 else 0
            bar = "█" * bar_len + "░" * (bar_width - bar_len)
            print(f"  {name:<22} {c(bar, color)} {count:3}")

        # Pipeline status
        print(c("\n┌─────────────────────────────────────────────────────────────┐", Colors.CYAN))
        print(c("│                    PIPELINE STATUS                          │", Colors.CYAN))
        print(c("└─────────────────────────────────────────────────────────────┘", Colors.CYAN))

        stages = [
            ("Empty", r.sources_empty, Colors.DIM),
            ("Stage 1 (URLs)", r.sources_stage1, Colors.YELLOW),
            ("Stage 2 (HTML)", r.sources_stage2, Colors.BLUE),
            ("Stage 3 (Builds)", r.sources_stage3, Colors.CYAN),
            ("Complete", r.sources_complete, Colors.GREEN),
        ]

        max_count = max(s[1] for s in stages) or 1
        for name, count, color in stages:
            bar_len = int((count / max_count) * bar_width) if max_count > 0 else 0
            bar = "█" * bar_len + "░" * (bar_width - bar_len)
            print(f"  {name:<18} {c(bar, color)} {count:3}")

        # Detailed source table
        print(c("\n┌─────────────────────────────────────────────────────────────┐", Colors.HEADER))
        print(c("│                    SOURCE DETAILS                           │", Colors.HEADER))
        print(c("└─────────────────────────────────────────────────────────────┘", Colors.HEADER))

        # Sort by issues/health
        sorted_sources = sorted(r.sources, key=lambda s: (
            -len(s.issues),
            s.overall_quality,
        ))

        print(f"\n  {'Source':<22} {'HTML':<12} {'Builds':<12} {'Quality':>8} {'Status':<10}")
        print(f"  {'-'*22} {'-'*12} {'-'*12} {'-'*8} {'-'*10}")

        for s in sorted_sources[:20]:
            html_info = f"{s.html_validation.valid_files}/{s.html_files}" if self.deep else str(s.html_files)
            build_info = f"{s.build_validation.valid_builds}/{s.build_validation.total_builds}" if self.deep else str(s.build_validation.total_builds)

            health_color = {
                "healthy": Colors.GREEN,
                "warning": Colors.YELLOW,
                "degraded": Colors.YELLOW,
                "critical": Colors.RED
            }.get(s.health_status, Colors.RESET)

            health_icon = {
                "healthy": "🟢",
                "warning": "🟡",
                "degraded": "🟠",
                "critical": "🔴"
            }.get(s.health_status, "⚪")

            print(f"  {s.name:<22} {html_info:<12} {build_info:<12} {s.overall_quality:>6.0f}% {health_icon}")

        # Critical issues
        critical_sources = [s for s in r.sources if s.issues]
        if critical_sources:
            print(c("\n┌─────────────────────────────────────────────────────────────┐", Colors.RED))
            print(c("│                    CRITICAL ISSUES                          │", Colors.RED))
            print(c("└─────────────────────────────────────────────────────────────┘", Colors.RED))

            for s in critical_sources[:10]:
                print(f"\n  {c(s.name, Colors.BOLD)}")
                for issue in s.issues:
                    print(f"    {c('✗', Colors.RED)} {issue}")

        # Recommendations
        print(c("\n┌─────────────────────────────────────────────────────────────┐", Colors.CYAN))
        print(c("│                    RECOMMENDATIONS                          │", Colors.CYAN))
        print(c("└─────────────────────────────────────────────────────────────┘", Colors.CYAN))

        recommendations = self._generate_recommendations()
        for i, rec in enumerate(recommendations, 1):
            print(f"\n  {i}. {rec}")

        print()

    def _generate_recommendations(self) -> list:
        """Generate recommendations based on audit findings."""
        r = self.report
        recommendations = []

        # Critical health sources
        if r.sources_critical > 0:
            critical_names = [s.name for s in r.sources if s.health_status == "critical"][:3]
            recommendations.append(
                f"🔴 {c('URGENT:', Colors.RED)} {r.sources_critical} sources have critical data quality issues: "
                f"{', '.join(critical_names)}{'...' if len(critical_names) < r.sources_critical else ''}"
            )

        # High error HTML
        if self.deep and r.total_html_files > 0:
            error_pct = r.total_error_html / r.total_html_files * 100
            if error_pct > 30:
                recommendations.append(
                    f"🔴 {error_pct:.0f}% of HTML files are error pages. Re-scrape with better anti-bot measures (Camoufox)."
                )

        # Low build completeness
        if r.avg_build_completeness < 70:
            recommendations.append(
                f"⚠️ Average build completeness is {r.avg_build_completeness:.0f}%. Review extraction logic."
            )

        # Stalled pipelines
        if r.sources_stage2 > 3:
            stage2_names = [s.name for s in r.sources if s.pipeline_stage in ("stage2_started", "stage2_complete")][:3]
            recommendations.append(
                f"📊 Run data extraction for {r.sources_stage2} sources: {', '.join(stage2_names)}..."
            )

        # Empty sources
        if r.sources_empty > 0:
            recommendations.append(
                f"🗑️ Remove {r.sources_empty} empty source directories."
            )

        if not recommendations:
            recommendations.append("✅ No critical issues found. Data directory is in good health!")

        return recommendations

    def export_json(self, filepath: Path):
        """Export full audit report to JSON file."""
        def convert(obj):
            if isinstance(obj, defaultdict):
                return dict(obj)
            return str(obj)

        report_dict = asdict(self.report)
        with open(filepath, 'w') as f:
            json.dump(report_dict, f, indent=2, default=convert)

        print(c(f"\n✓ Report exported to: {filepath}", Colors.GREEN))


def main():
    parser = argparse.ArgumentParser(
        description="Audit Ralph data directory with deep content validation"
    )
    parser.add_argument(
        '--data-dir', '-d',
        type=Path,
        default=PROJECT_ROOT / 'data',
        help='Path to data directory'
    )
    parser.add_argument(
        '--source', '-s',
        type=str,
        help='Filter to specific source'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--deep',
        action='store_true',
        help='Enable deep content validation (HTML parsing, field checks)'
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        default=100,
        help='Number of HTML files to sample per source (default: 100)'
    )
    parser.add_argument(
        '--json', '-j',
        action='store_true',
        help='Output as JSON only'
    )
    parser.add_argument(
        '--report', '-r',
        type=Path,
        help='Export full report to JSON file'
    )

    args = parser.parse_args()

    if not args.data_dir.exists():
        print(c(f"Error: Data directory not found: {args.data_dir}", Colors.RED))
        sys.exit(1)

    auditor = DataAuditor(
        args.data_dir,
        verbose=args.verbose,
        deep=args.deep,
        sample_size=args.sample_size
    )

    report = auditor.run_audit(source_filter=args.source)

    if args.json:
        def convert(obj):
            if isinstance(obj, defaultdict):
                return dict(obj)
            return str(obj)
        print(json.dumps(asdict(report), indent=2, default=convert))
    else:
        auditor.print_summary()

    if args.report:
        auditor.export_json(args.report)


if __name__ == '__main__':
    main()
