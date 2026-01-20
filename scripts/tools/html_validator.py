#!/usr/bin/env python3
"""
HTML Validation and Cleanup Utility for RalphOS

Detects and optionally cleans up corrupted HTML files caused by:
- Brotli/gzip compressed responses saved without decompression
- Binary data saved as HTML
- Empty or truncated files
- Cloudflare challenge pages

Usage:
    # Check for corrupted files (dry run)
    python scripts/tools/html_validator.py data/carandclassic/

    # Delete corrupted files
    python scripts/tools/html_validator.py data/carandclassic/ --delete

    # Validate single file
    python scripts/tools/html_validator.py --file data/carandclassic/html/12345.html

The validator checks:
1. File is not empty
2. Content is valid UTF-8 (not binary garbage)
3. Content starts with <!doctype or <html (not compressed bytes)
4. Content doesn't contain high concentration of non-printable characters
5. Content isn't a Cloudflare challenge page

Exit codes:
    0 - All files valid (or corrupted files deleted successfully)
    1 - Corrupted files found (dry run)
    2 - Error during execution
"""

import argparse
import sys
from pathlib import Path
from typing import List, Tuple, NamedTuple, Optional
import json
from datetime import datetime


class ValidationResult(NamedTuple):
    """Result of validating a single HTML file."""
    path: Path
    valid: bool
    reason: str
    size: int


# Magic bytes for compressed formats
BROTLI_MAGIC = bytes([0x1b])  # Brotli often starts with 0x1b
GZIP_MAGIC = bytes([0x1f, 0x8b])
ZSTD_MAGIC = bytes([0x28, 0xb5, 0x2f, 0xfd])


def is_valid_html(content: str, filepath: Path) -> Tuple[bool, str]:
    """
    Validate that content is proper HTML, not binary/compressed data.

    Returns:
        Tuple of (is_valid, reason)
    """
    if not content:
        return False, "empty file"

    # Check for proper HTML structure at start (ignore leading whitespace)
    content_stripped = content.lstrip()[:500].lower()

    # Valid HTML should start with doctype or html tag
    valid_starts = ('<!doctype', '<html', '<?xml')
    has_valid_start = any(content_stripped.startswith(s) for s in valid_starts)

    if not has_valid_start:
        # Check if it's wrapped in html but has garbage content
        # Pattern: <html><head></head><body>[GARBAGE]
        if content_stripped.startswith('<html><head></head><body>'):
            # This is the signature of binary data wrapped by browser
            # Check if the content after <body> is mostly non-printable
            body_start = content.find('<body>') + 6
            body_content = content[body_start:body_start + 200]

            # Count non-printable/non-ASCII characters
            non_ascii = sum(1 for c in body_content if ord(c) > 127 or ord(c) < 32)
            ratio = non_ascii / len(body_content) if body_content else 0

            if ratio > 0.3:  # More than 30% garbage = corrupted
                return False, f"binary data wrapped in HTML tags ({ratio*100:.0f}% non-ASCII)"

        return False, "missing doctype/html tag at start"

    # Check for excessive non-printable characters (sign of binary data)
    sample = content[:2000]
    non_printable = sum(1 for c in sample if ord(c) < 32 and c not in '\n\r\t')
    non_ascii = sum(1 for c in sample if ord(c) > 127)

    # Allow some UTF-8 (accented chars, etc) but flag if mostly garbage
    garbage_ratio = (non_printable + non_ascii * 0.5) / len(sample) if sample else 0

    if garbage_ratio > 0.15:  # 15% threshold
        return False, f"high garbage content ratio ({garbage_ratio*100:.0f}%)"

    # Check for Cloudflare challenge (these should be re-scraped)
    if 'cloudflare' in content_stripped and 'challenge' in content_stripped:
        return False, "cloudflare challenge page"

    return True, "valid"


def validate_html_bytes(raw_bytes: bytes, filepath: Path) -> Tuple[bool, str]:
    """
    Validate raw bytes before attempting to decode as HTML.
    Catches compressed data that wasn't decompressed.

    Returns:
        Tuple of (is_valid, reason)
    """
    if not raw_bytes:
        return False, "empty file"

    if len(raw_bytes) < 50:
        return False, f"file too small ({len(raw_bytes)} bytes)"

    # Check magic bytes for compressed formats
    if raw_bytes[:2] == GZIP_MAGIC:
        return False, "gzip compressed data (not decompressed)"

    if raw_bytes[:4] == ZSTD_MAGIC:
        return False, "zstd compressed data (not decompressed)"

    # Brotli detection is trickier - check for high entropy in first bytes
    if raw_bytes[0] == BROTLI_MAGIC[0]:
        # Could be brotli - check if it decodes as valid UTF-8
        try:
            text = raw_bytes[:100].decode('utf-8')
            # If we got here, it's UTF-8 but check if it's HTML
            if not text.lstrip()[:20].lower().startswith(('<!doctype', '<html', '<?xml', '<')):
                # Starts with 0x1b and isn't HTML - likely brotli
                return False, "likely brotli compressed data"
        except UnicodeDecodeError:
            return False, "brotli compressed data (not decompressed)"

    # Try to decode as UTF-8
    try:
        content = raw_bytes.decode('utf-8')
        return is_valid_html(content, filepath)
    except UnicodeDecodeError as e:
        return False, f"invalid UTF-8 encoding: {e}"


def validate_file(filepath: Path) -> ValidationResult:
    """Validate a single HTML file."""
    if not filepath.exists():
        return ValidationResult(filepath, False, "file not found", 0)

    try:
        raw_bytes = filepath.read_bytes()
        size = len(raw_bytes)

        valid, reason = validate_html_bytes(raw_bytes, filepath)
        return ValidationResult(filepath, valid, reason, size)

    except Exception as e:
        return ValidationResult(filepath, False, f"read error: {e}", 0)


def validate_directory(html_dir: Path) -> List[ValidationResult]:
    """Validate all HTML files in a directory."""
    results = []

    html_files = sorted(html_dir.glob("*.html"))

    for filepath in html_files:
        result = validate_file(filepath)
        results.append(result)

    return results


def cleanup_corrupted(results: List[ValidationResult], delete: bool = False) -> Tuple[int, int]:
    """
    Report and optionally delete corrupted files.

    Returns:
        Tuple of (corrupted_count, deleted_count)
    """
    corrupted = [r for r in results if not r.valid]
    deleted = 0

    if corrupted:
        print(f"\n{'='*60}")
        print(f"Found {len(corrupted)} corrupted HTML files:")
        print(f"{'='*60}")

        # Group by reason
        by_reason = {}
        for r in corrupted:
            by_reason.setdefault(r.reason, []).append(r)

        for reason, files in sorted(by_reason.items(), key=lambda x: -len(x[1])):
            print(f"\n{reason} ({len(files)} files):")
            for r in files[:5]:  # Show first 5
                print(f"  - {r.path.name} ({r.size:,} bytes)")
            if len(files) > 5:
                print(f"  ... and {len(files) - 5} more")

        if delete:
            print(f"\n{'='*60}")
            print("Deleting corrupted files...")
            for r in corrupted:
                try:
                    r.path.unlink()
                    deleted += 1
                except Exception as e:
                    print(f"  Error deleting {r.path.name}: {e}")
            print(f"Deleted {deleted} files")

    return len(corrupted), deleted


def update_progress_file(source_dir: Path, corrupted_files: List[ValidationResult]):
    """
    Remove corrupted file entries from scrape_progress.jsonl.
    This allows Ralph to re-scrape them.
    """
    progress_file = source_dir / "scrape_progress.jsonl"
    if not progress_file.exists():
        return

    # Build set of corrupted filenames
    corrupted_names = {r.path.name for r in corrupted_files if not r.valid}

    # Read and filter progress entries
    valid_entries = []
    removed_count = 0

    with open(progress_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                filename = entry.get("filename", "")
                if filename in corrupted_names:
                    removed_count += 1
                else:
                    valid_entries.append(line)
            except json.JSONDecodeError:
                valid_entries.append(line)

    if removed_count > 0:
        # Backup original
        backup_path = progress_file.with_suffix('.jsonl.bak')
        progress_file.rename(backup_path)

        # Write filtered entries
        with open(progress_file, 'w') as f:
            for entry in valid_entries:
                f.write(entry + '\n')

        print(f"Removed {removed_count} entries from scrape_progress.jsonl (backup: {backup_path.name})")


def main():
    parser = argparse.ArgumentParser(
        description="Validate and cleanup corrupted HTML files in RalphOS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "source_dir",
        nargs="?",
        type=Path,
        help="Source directory (e.g., data/carandclassic/)"
    )

    parser.add_argument(
        "--file",
        type=Path,
        help="Validate a single file instead of a directory"
    )

    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete corrupted files (default: dry run)"
    )

    parser.add_argument(
        "--update-progress",
        action="store_true",
        help="Also remove corrupted entries from scrape_progress.jsonl"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    # Single file validation
    if args.file:
        result = validate_file(args.file)

        if args.json:
            print(json.dumps({
                "path": str(result.path),
                "valid": result.valid,
                "reason": result.reason,
                "size": result.size
            }, indent=2))
        else:
            status = "✓ VALID" if result.valid else "✗ CORRUPTED"
            print(f"{status}: {result.path.name}")
            print(f"  Reason: {result.reason}")
            print(f"  Size: {result.size:,} bytes")

        return 0 if result.valid else 1

    # Directory validation
    if not args.source_dir:
        parser.error("Either source_dir or --file is required")

    html_dir = args.source_dir / "html"

    if not html_dir.exists():
        print(f"Error: HTML directory not found: {html_dir}")
        return 2

    print(f"Validating HTML files in: {html_dir}")

    results = validate_directory(html_dir)

    valid_count = sum(1 for r in results if r.valid)
    corrupted_count = sum(1 for r in results if not r.valid)

    print(f"\nResults:")
    print(f"  Total files: {len(results)}")
    print(f"  Valid: {valid_count}")
    print(f"  Corrupted: {corrupted_count}")

    if args.json:
        output = {
            "source_dir": str(args.source_dir),
            "html_dir": str(html_dir),
            "total_files": len(results),
            "valid_count": valid_count,
            "corrupted_count": corrupted_count,
            "corrupted_files": [
                {
                    "path": str(r.path),
                    "reason": r.reason,
                    "size": r.size
                }
                for r in results if not r.valid
            ]
        }
        print(json.dumps(output, indent=2))
        return 0 if corrupted_count == 0 else 1

    corrupted, deleted = cleanup_corrupted(results, delete=args.delete)

    if args.delete and args.update_progress and corrupted > 0:
        update_progress_file(args.source_dir, results)

    if corrupted > 0 and not args.delete:
        print(f"\nRun with --delete to remove corrupted files")
        print(f"Run with --delete --update-progress to also reset scrape progress")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
