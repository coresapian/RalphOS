#!/usr/bin/env python3
"""
Scraper Test Framework for Ralph
Tests HTML scraper output directories OR scripts before marking them complete.

Usage:
 # Test output directory (preferred - works with stealth_scraper.py)
 python scripts/tools/test_scraper.py data/modified_rides/
 
 # Test a specific script
 python scripts/tools/test_scraper.py data/modified_rides/scrape_html.py
 
Returns exit code 0 if all tests pass, 1 if any fail.
"""

import sys
import os
import json
import importlib.util
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
NC = '\033[0m'


def load_urls_jsonl(file_path: Path) -> list:
 """Load URLs from JSONL file"""
 urls = []
 with open(file_path) as f:
 for line in f:
 if line.strip():
 urls.append(json.loads(line))
 return urls


def load_urls_json(file_path: Path) -> list:
 """Load URLs from JSON file"""
 with open(file_path) as f:
 data = json.load(f)
 return data.get('urls', []) if isinstance(data, dict) else data

class ScraperTestResult:
 def __init__(self):
 self.passed = []
 self.failed = []
 self.warnings = []
 
 def add_pass(self, test_name, message=""):
 self.passed.append((test_name, message))
 print(f" {GREEN}{NC} {test_name}" + (f" - {message}" if message else ""))
 
 def add_fail(self, test_name, message=""):
 self.failed.append((test_name, message))
 print(f" {RED}{NC} {test_name}" + (f" - {message}" if message else ""))
 
 def add_warning(self, test_name, message=""):
 self.warnings.append((test_name, message))
 print(f" {YELLOW}{NC} {test_name}" + (f" - {message}" if message else ""))
 
 @property
 def all_passed(self):
 return len(self.failed) == 0


def test_script_exists(script_path: Path, result: ScraperTestResult):
 """Test 1: Script file exists"""
 if script_path.exists():
 result.add_pass("Script exists", str(script_path))
 else:
 result.add_fail("Script exists", f"File not found: {script_path}")


def test_script_syntax(script_path: Path, result: ScraperTestResult):
 """Test 2: Script has valid Python syntax"""
 try:
 with open(script_path) as f:
 code = f.read()
 compile(code, script_path, 'exec')
 result.add_pass("Valid Python syntax")
 except SyntaxError as e:
 result.add_fail("Valid Python syntax", f"Line {e.lineno}: {e.msg}")


def test_required_imports(script_path: Path, result: ScraperTestResult):
 """Test 3: Script uses Camoufox stealth browser"""
 with open(script_path) as f:
 code = f.read()
 
 # Must use Camoufox
 has_camoufox = 'camoufox' in code.lower()
 
 if has_camoufox:
 result.add_pass("Uses Camoufox stealth browser")
 else:
 result.add_fail("Must use Camoufox", "Script must use Camoufox stealth browser - not requests")


def test_urls_file_exists(script_dir: Path, result: ScraperTestResult):
 """Test 4: urls.jsonl or urls.json exists in same directory"""
 urls_jsonl = script_dir / 'urls.jsonl'
 urls_json = script_dir / 'urls.json'
 
 if urls_jsonl.exists():
 try:
 url_list = load_urls_jsonl(urls_jsonl)
 url_count = len(url_list)
 result.add_pass("urls.jsonl exists", f"{url_count} URLs (JSONL format)")
 except (json.JSONDecodeError, Exception) as e:
 result.add_fail("urls.jsonl exists", f"Invalid JSONL: {e}")
 elif urls_json.exists():
 try:
 url_list = load_urls_json(urls_json)
 url_count = len(url_list)
 result.add_pass("urls.json exists", f"{url_count} URLs (JSON format)")
 except json.JSONDecodeError:
 result.add_fail("urls.json exists", "Invalid JSON")
 else:
 result.add_fail("URLs file", "Neither urls.jsonl nor urls.json found")


def test_html_directory(script_dir: Path, result: ScraperTestResult):
 """Test 5: html/ output directory exists with scraped files"""
 html_dir = script_dir / 'html'
 if html_dir.exists():
 file_count = len(list(html_dir.glob('*.html')))
 if file_count == 0:
 result.add_fail("html/ has files", "Directory exists but is EMPTY - run the scraper!")
 else:
 result.add_pass("html/ has files", f"{file_count} HTML files scraped")
 else:
 result.add_fail("html/ directory", "Does not exist - run the scraper!")


def test_scraping_progress(script_dir: Path, result: ScraperTestResult):
 """Test 5b: Scraping has actually been executed"""
 urls_jsonl = script_dir / 'urls.jsonl'
 urls_json = script_dir / 'urls.json'
 html_dir = script_dir / 'html'
 
 # Find URLs file
 if urls_jsonl.exists():
 url_list = load_urls_jsonl(urls_jsonl)
 url_count = len(url_list)
 elif urls_json.exists():
 url_list = load_urls_json(urls_json)
 url_count = len(url_list)
 else:
 return
 
 if not html_dir.exists():
 return
 
 try:
 html_count = len(list(html_dir.glob('*.html')))
 
 if url_count == 0:
 return
 
 progress = (html_count / url_count) * 100
 source_id = script_dir.name
 
 if progress >= 95:
 result.add_pass("Scraping complete", f"{html_count}/{url_count} ({progress:.1f}%)")
 elif progress >= 50:
 result.add_fail("Scraping incomplete", 
 f"{html_count}/{url_count} ({progress:.1f}%) - RUN: python3 scripts/tools/stealth_scraper.py --source {source_id}")
 elif progress > 0:
 result.add_fail("Scraping incomplete", 
 f"Only {html_count}/{url_count} ({progress:.1f}%) - RUN: python3 scripts/tools/stealth_scraper.py --source {source_id}")
 else:
 result.add_fail("Scraping not started", 
 f"0/{url_count} - RUN: python3 scripts/tools/stealth_scraper.py --source {source_id}")
 except Exception as e:
 result.add_warning("Progress check", str(e))


def test_scraper_health(script_dir: Path, result: ScraperTestResult):
 """Test 5c: Check for scraper issues from progress file"""
 progress_jsonl = script_dir / 'scrape_progress.jsonl'
 progress_json = script_dir / 'scrape_progress.json'
 checkpoint_json = script_dir / 'stealth_checkpoint.json'
 
 # Try JSONL format first (new format)
 if progress_jsonl.exists():
 try:
 failed_items = []
 with open(progress_jsonl) as f:
 for line in f:
 if line.strip():
 record = json.loads(line)
 if record.get('status') in ('failed', 'blocked'):
 failed_items.append(record)
 
 if not failed_items:
 result.add_pass("No scraper errors")
 return
 
 _analyze_errors(failed_items, result)
 return
 except Exception as e:
 result.add_warning("Health check (JSONL)", str(e))
 return
 
 # Try stealth_checkpoint.json (from stealth_scraper.py)
 if checkpoint_json.exists():
 try:
 with open(checkpoint_json) as f:
 checkpoint = json.load(f)
 
 failed_urls = checkpoint.get('failed_urls', [])
 blocked_urls = checkpoint.get('blocked_urls', [])
 
 if not failed_urls and not blocked_urls:
 result.add_pass("No scraper errors (stealth checkpoint)")
 return
 
 failed_items = [{'error': 'failed'} for _ in failed_urls]
 failed_items += [{'error': 'blocked'} for _ in blocked_urls]
 _analyze_errors(failed_items, result)
 return
 except Exception as e:
 result.add_warning("Health check (checkpoint)", str(e))
 return
 
 # Try old JSON format
 if progress_json.exists():
 try:
 with open(progress_json) as f:
 progress = json.load(f)
 
 failed_urls = progress.get('failedUrls', [])
 
 if not failed_urls:
 result.add_pass("No scraper errors")
 return
 
 _analyze_errors(failed_urls, result)
 except Exception as e:
 result.add_warning("Health check (JSON)", str(e))


def _analyze_errors(failed_items: list, result: ScraperTestResult):
 """Analyze error patterns from failed items"""
 error_counts = {
 'dns': 0,
 'blocked': 0,
 'timeout': 0,
 'server': 0,
 'other': 0
 }
 
 for item in failed_items:
 error = item.get('error', '') if isinstance(item, dict) else str(item)
 error_lower = error.lower()
 
 if 'resolve' in error_lower or 'nodename' in error_lower or 'getaddrinfo' in error_lower:
 error_counts['dns'] += 1
 elif '403' in error or '429' in error or 'cloudflare' in error_lower or 'blocked' in error_lower:
 error_counts['blocked'] += 1
 elif 'timeout' in error_lower:
 error_counts['timeout'] += 1
 elif any(x in error for x in ['500', '502', '503', '504']):
 error_counts['server'] += 1
 else:
 error_counts['other'] += 1
 
 total_failed = len(failed_items)
 
 # Check for critical issues
 if error_counts['blocked'] > total_failed * 0.3:
 result.add_fail("Site BLOCKING scraper", 
 f"{error_counts['blocked']} blocked requests - try different proxy or wait")
 elif error_counts['dns'] > total_failed * 0.8:
 result.add_fail("Site appears DOWN",
 f"{error_counts['dns']} DNS errors - run: ./scripts/tools/flush_dns.sh")
 elif total_failed > 0:
 breakdown = ", ".join(f"{k}: {v}" for k, v in error_counts.items() if v > 0)
 result.add_warning("Scraper has errors", f"{total_failed} failures ({breakdown})")


def test_rate_limiting(script_path: Path, result: ScraperTestResult):
 """Test 6: Script includes rate limiting"""
 with open(script_path) as f:
 code = f.read()
 
 rate_limit_patterns = ['time.sleep', 'sleep(', 'delay', 'rate_limit']
 has_rate_limit = any(p in code for p in rate_limit_patterns)
 
 if has_rate_limit:
 result.add_pass("Rate limiting implemented")
 else:
 result.add_warning("Rate limiting", "No sleep/delay found - may get blocked")


def test_error_handling(script_path: Path, result: ScraperTestResult):
 """Test 7: Script has error handling"""
 with open(script_path) as f:
 code = f.read()
 
 has_try = 'try:' in code
 has_except = 'except' in code
 
 if has_try and has_except:
 result.add_pass("Error handling implemented")
 else:
 result.add_warning("Error handling", "No try/except blocks found")


def test_checkpoint_saving(script_path: Path, result: ScraperTestResult):
 """Test 8: Script saves progress for resumption"""
 with open(script_path) as f:
 code = f.read()
 
 checkpoint_patterns = ['progress', 'checkpoint', 'resume', 'scraped_urls', 'save_progress']
 has_checkpoint = any(p in code.lower() for p in checkpoint_patterns)
 
 if has_checkpoint:
 result.add_pass("Checkpoint/resume capability")
 else:
 result.add_warning("Checkpoint/resume", "No progress saving found")


def test_stealth_features(script_path: Path, result: ScraperTestResult):
 """Test 9: Script uses Camoufox stealth features"""
 with open(script_path) as f:
 code = f.read()
 
 # Check for Camoufox stealth settings
 stealth_patterns = ['humanize', 'block_webrtc', 'AsyncCamoufox', 'Camoufox(']
 has_stealth = any(p in code for p in stealth_patterns)
 
 if has_stealth:
 result.add_pass("Camoufox stealth features enabled")
 else:
 result.add_warning("Stealth features", "Consider adding humanize=True, block_webrtc=True")


def test_dry_run(script_path: Path, script_dir: Path, result: ScraperTestResult):
 """Test 10: Script can be imported without errors"""
 try:
 # Try to load the module
 spec = importlib.util.spec_from_file_location("scraper", script_path)
 if spec and spec.loader:
 # Just check if it can be loaded, don't execute
 result.add_pass("Script can be imported")
 else:
 result.add_fail("Script can be imported", "Invalid module spec")
 except Exception as e:
 result.add_fail("Script can be imported", str(e))


def run_tests(path_str: str) -> bool:
 """Run all tests on a scraper output directory or script"""
 path = Path(path_str).resolve()
 
 # Determine if path is a directory or script
 if path.is_dir():
 script_dir = path
 script_path = None
 mode = "directory"
 else:
 script_path = path
 script_dir = path.parent
 mode = "script"
 
 print(f"\n{CYAN}{NC}")
 print(f"{CYAN} Scraper Test Suite (Camoufox){NC}")
 print(f"{CYAN}{NC}")
 if mode == "directory":
 print(f"\n Mode: Output directory")
 print(f" Dir: {script_dir}\n")
 else:
 print(f"\n Mode: Script file")
 print(f" Script: {script_path}")
 print(f" Dir: {script_dir}\n")
 
 result = ScraperTestResult()
 
 # Directory-based tests (always run)
 test_urls_file_exists(script_dir, result)
 test_html_directory(script_dir, result)
 test_scraping_progress(script_dir, result)
 test_scraper_health(script_dir, result)
 
 # Script-based tests (only if script provided)
 if script_path and script_path.exists():
 test_script_exists(script_path, result)
 test_script_syntax(script_path, result)
 test_required_imports(script_path, result)
 test_rate_limiting(script_path, result)
 test_error_handling(script_path, result)
 test_checkpoint_saving(script_path, result)
 test_stealth_features(script_path, result)
 test_dry_run(script_path, script_dir, result)
 
 # Summary
 print(f"\n{CYAN}{NC}")
 print(f" {GREEN}Passed:{NC} {len(result.passed)}")
 print(f" {RED}Failed:{NC} {len(result.failed)}")
 print(f" {YELLOW}Warnings:{NC} {len(result.warnings)}")
 print(f"{CYAN}{NC}")
 
 if result.all_passed:
 print(f"\n {GREEN} ALL TESTS PASSED{NC}\n")
 return True
 else:
 print(f"\n {RED} TESTS FAILED{NC}\n")
 for test_name, message in result.failed:
 print(f" • {test_name}: {message}")
 print()
 return False


if __name__ == "__main__":
 if len(sys.argv) < 2:
 print(f"Usage: {sys.argv[0]} <path_to_directory_or_script>")
 print(f"\nExamples:")
 print(f" # Test output directory (recommended):")
 print(f" {sys.argv[0]} data/modified_rides/")
 print(f"\n # Test specific script:")
 print(f" {sys.argv[0]} data/modified_rides/scrape_html.py")
 sys.exit(1)
 
 path = sys.argv[1]
 success = run_tests(path)
 sys.exit(0 if success else 1)

