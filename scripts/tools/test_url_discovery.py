#!/usr/bin/env python3
"""
URL Discovery Test Framework for Ralph
Tests URL discovery scripts before marking them complete.

Usage:
 python scripts/tools/test_url_discovery.py data/source_name/
 
Returns exit code 0 if all tests pass, 1 if any fail.
"""

import sys
import os
import json
import re
from pathlib import Path
from urllib.parse import urlparse

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
NC = '\033[0m'

class TestResult:
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


def test_urls_json_exists(output_dir: Path, result: TestResult):
 """Test 1: urls.json file exists"""
 urls_file = output_dir / 'urls.json'
 if urls_file.exists():
 result.add_pass("urls.json exists", str(urls_file))
 return True
 else:
 result.add_fail("urls.json exists", "File not found")
 return False


def test_urls_json_valid(output_dir: Path, result: TestResult):
 """Test 2: urls.json is valid JSON with correct structure"""
 urls_file = output_dir / 'urls.json'
 try:
 with open(urls_file) as f:
 data = json.load(f)
 
 if 'urls' not in data:
 result.add_fail("urls.json structure", "Missing 'urls' array")
 return None
 
 if not isinstance(data['urls'], list):
 result.add_fail("urls.json structure", "'urls' is not an array")
 return None
 
 result.add_pass("urls.json valid JSON", f"Contains {len(data['urls'])} URLs")
 return data
 except json.JSONDecodeError as e:
 result.add_fail("urls.json valid JSON", f"Parse error: {e}")
 return None


def test_url_count(data: dict, result: TestResult):
 """Test 3: URLs array has sufficient URLs discovered"""
 urls = data.get('urls', [])
 count = len(urls)
 
 if count == 0:
 result.add_fail("URL count", "NO URLs discovered - RUN THE URL DISCOVERY SCRIPT!")
 elif count < 10:
 result.add_fail("URL count", f"Only {count} URLs - too few! Keep discovering more URLs")
 elif count < 50:
 result.add_warning("URL count", f"{count} URLs - seems low, verify this is complete")
 else:
 result.add_pass("URL count", f"{count} URLs discovered")
 
 return count


def test_url_validity(data: dict, result: TestResult):
 """Test 4: All URLs are valid HTTP/HTTPS URLs"""
 urls = data.get('urls', [])
 invalid = []
 
 for url in urls[:100]: # Check first 100
 parsed = urlparse(url)
 if not parsed.scheme in ['http', 'https']:
 invalid.append(url[:50])
 elif not parsed.netloc:
 invalid.append(url[:50])
 
 if not invalid:
 result.add_pass("URL validity", "All URLs are valid HTTP(S)")
 else:
 result.add_fail("URL validity", f"{len(invalid)} invalid URLs: {invalid[0]}...")


def test_url_uniqueness(data: dict, result: TestResult):
 """Test 5: No duplicate URLs"""
 urls = data.get('urls', [])
 unique = set(urls)
 duplicates = len(urls) - len(unique)
 
 if duplicates == 0:
 result.add_pass("URL uniqueness", "No duplicates")
 else:
 result.add_warning("URL uniqueness", f"{duplicates} duplicate URLs")


def test_url_patterns(data: dict, result: TestResult):
 """Test 6: URLs match expected patterns (not listing/category pages)"""
 urls = data.get('urls', [])
 
 # Bad patterns - listing pages, not individual items
 bad_patterns = [
 r'/page/\d+/?$', # Pagination pages
 r'/category/', # Category pages
 r'/tag/', # Tag pages
 r'/author/', # Author pages
 r'/search\?', # Search results
 r'\?page=', # Query param pagination
 ]
 
 bad_urls = []
 for url in urls[:100]: # Check first 100
 for pattern in bad_patterns:
 if re.search(pattern, url, re.IGNORECASE):
 bad_urls.append(url[:60])
 break
 
 if not bad_urls:
 result.add_pass("URL patterns", "URLs appear to be individual pages")
 else:
 result.add_warning("URL patterns", f"{len(bad_urls)} possible listing pages found")


def test_same_domain(data: dict, result: TestResult):
 """Test 7: All URLs are from the same domain"""
 urls = data.get('urls', [])
 if not urls:
 return
 
 domains = set()
 for url in urls:
 parsed = urlparse(url)
 domain = parsed.netloc.lower()
 # Normalize www
 if domain.startswith('www.'):
 domain = domain[4:]
 domains.add(domain)
 
 if len(domains) == 1:
 result.add_pass("Same domain", list(domains)[0])
 elif len(domains) <= 3:
 result.add_warning("Multiple domains", f"{len(domains)} domains: {', '.join(list(domains)[:3])}")
 else:
 result.add_fail("Multiple domains", f"{len(domains)} different domains found")


def test_no_media_urls(data: dict, result: TestResult):
 """Test 8: URLs are not media/attachment pages"""
 urls = data.get('urls', [])
 
 # Bad patterns - media files, not content pages
 media_patterns = [
 r'/media/',
 r'/attachment',
 r'/uploads/',
 r'/images/',
 r'\.(jpg|jpeg|png|gif|webp|pdf|mp4|mp3)$',
 ]
 
 media_urls = []
 for url in urls:
 for pattern in media_patterns:
 if re.search(pattern, url, re.IGNORECASE):
 media_urls.append(url[:60])
 break
 
 media_percent = (len(media_urls) / len(urls) * 100) if urls else 0
 
 if media_percent == 0:
 result.add_pass("No media URLs", "All URLs are content pages")
 elif media_percent < 10:
 result.add_warning("Media URLs", f"{len(media_urls)} media URLs ({media_percent:.1f}%)")
 else:
 result.add_fail("Media URLs", f"{len(media_urls)} media URLs ({media_percent:.1f}%) - should be content pages!")


def test_total_count_field(data: dict, result: TestResult):
 """Test 9: totalCount field matches array length"""
 urls = data.get('urls', [])
 total_count = data.get('totalCount')
 
 if total_count is None:
 result.add_warning("totalCount field", "Missing - add for tracking")
 elif total_count != len(urls):
 result.add_warning("totalCount field", f"Mismatch: totalCount={total_count}, actual={len(urls)}")
 else:
 result.add_pass("totalCount field", f"Matches: {total_count}")


def test_last_updated_field(data: dict, result: TestResult):
 """Test 10: lastUpdated timestamp exists"""
 last_updated = data.get('lastUpdated')
 
 if last_updated is None:
 result.add_warning("lastUpdated field", "Missing - add for tracking")
 else:
 result.add_pass("lastUpdated field", str(last_updated)[:19])


def test_sources_json_updated(output_dir: Path, result: TestResult):
 """Test 11: Check if sources.json has been updated with URL counts"""
 # Find sources.json
 sources_file = output_dir.parent.parent / 'scripts' / 'ralph' / 'sources.json'
 if not sources_file.exists():
 sources_file = output_dir.parent.parent.parent / 'scripts' / 'ralph' / 'sources.json'
 
 if not sources_file.exists():
 result.add_warning("sources.json update", "Could not find sources.json")
 return
 
 try:
 with open(sources_file) as f:
 sources_data = json.load(f)
 
 # Find matching source by outputDir
 source_id = output_dir.name
 matching_source = None
 for source in sources_data.get('sources', []):
 if source.get('outputDir', '').endswith(source_id):
 matching_source = source
 break
 
 if not matching_source:
 result.add_warning("sources.json update", f"Source '{source_id}' not found in sources.json")
 return
 
 pipeline = matching_source.get('pipeline', {})
 urls_found = pipeline.get('urlsFound')
 expected = pipeline.get('expectedUrls')
 
 if urls_found is None or urls_found == 0:
 result.add_fail("sources.json urlsFound", "urlsFound is null/0 - UPDATE sources.json with discovered count!")
 elif expected is not None and urls_found < expected:
 result.add_fail("sources.json incomplete", f"urlsFound={urls_found} but expectedUrls={expected} - KEEP DISCOVERING!")
 else:
 result.add_pass("sources.json updated", f"urlsFound={urls_found}" + (f", expected={expected}" if expected else ""))
 except Exception as e:
 result.add_warning("sources.json check", str(e))


def run_tests(output_dir_str: str) -> bool:
 """Run all tests on URL discovery output"""
 output_dir = Path(output_dir_str).resolve()
 
 print(f"\n{CYAN}{NC}")
 print(f"{CYAN} URL Discovery Test Suite{NC}")
 print(f"{CYAN}{NC}")
 print(f"\n Directory: {output_dir}\n")
 
 result = TestResult()
 
 # Test 1: urls.json exists
 if not test_urls_json_exists(output_dir, result):
 return False
 
 # Test 2: Valid JSON structure
 data = test_urls_json_valid(output_dir, result)
 if data is None:
 return False
 
 # Run remaining tests
 test_url_count(data, result)
 test_url_validity(data, result)
 test_url_uniqueness(data, result)
 test_url_patterns(data, result)
 test_same_domain(data, result)
 test_no_media_urls(data, result)
 test_total_count_field(data, result)
 test_last_updated_field(data, result)
 test_sources_json_updated(output_dir, result)
 
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
 print(f"Usage: {sys.argv[0]} <output_directory>")
 print(f"Example: {sys.argv[0]} data/modified_rides/")
 sys.exit(1)
 
 output_dir = sys.argv[1]
 success = run_tests(output_dir)
 sys.exit(0 if success else 1)

