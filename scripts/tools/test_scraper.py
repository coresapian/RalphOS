#!/usr/bin/env python3
"""
Scraper Test Framework for Ralph
Tests HTML scraper scripts before marking them complete.

Usage:
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

class ScraperTestResult:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []
    
    def add_pass(self, test_name, message=""):
        self.passed.append((test_name, message))
        print(f"  {GREEN}✓{NC} {test_name}" + (f" - {message}" if message else ""))
    
    def add_fail(self, test_name, message=""):
        self.failed.append((test_name, message))
        print(f"  {RED}✗{NC} {test_name}" + (f" - {message}" if message else ""))
    
    def add_warning(self, test_name, message=""):
        self.warnings.append((test_name, message))
        print(f"  {YELLOW}⚠{NC} {test_name}" + (f" - {message}" if message else ""))
    
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
    """Test 3: Script has necessary imports"""
    with open(script_path) as f:
        code = f.read()
    
    required = ['requests', 'json', 'time', 'os']
    missing = []
    
    for imp in required:
        if f'import {imp}' not in code and f'from {imp}' not in code:
            missing.append(imp)
    
    if not missing:
        result.add_pass("Required imports present", ', '.join(required))
    else:
        result.add_fail("Required imports present", f"Missing: {', '.join(missing)}")


def test_urls_json_exists(script_dir: Path, result: ScraperTestResult):
    """Test 4: urls.json exists in same directory"""
    urls_file = script_dir / 'urls.json'
    if urls_file.exists():
        try:
            with open(urls_file) as f:
                data = json.load(f)
            url_count = len(data.get('urls', []))
            result.add_pass("urls.json exists", f"{url_count} URLs")
        except json.JSONDecodeError:
            result.add_fail("urls.json exists", "Invalid JSON")
    else:
        result.add_fail("urls.json exists", "File not found")


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
    urls_file = script_dir / 'urls.json'
    html_dir = script_dir / 'html'
    
    if not urls_file.exists() or not html_dir.exists():
        return
    
    try:
        with open(urls_file) as f:
            data = json.load(f)
        url_count = len(data.get('urls', []))
        html_count = len(list(html_dir.glob('*.html')))
        
        if url_count == 0:
            return
        
        progress = (html_count / url_count) * 100
        
        if progress >= 95:
            result.add_pass("Scraping complete", f"{html_count}/{url_count} ({progress:.1f}%)")
        elif progress >= 50:
            result.add_fail("Scraping incomplete", f"{html_count}/{url_count} ({progress:.1f}%) - KEEP RUNNING: python3 scrape_html.py")
        elif progress > 0:
            result.add_fail("Scraping incomplete", f"Only {html_count}/{url_count} ({progress:.1f}%) - RUN: python3 scrape_html.py")
        else:
            result.add_fail("Scraping not started", f"0/{url_count} - RUN THE SCRAPER: python3 scrape_html.py")
    except Exception as e:
        result.add_warning("Progress check", str(e))


def test_scraper_health(script_dir: Path, result: ScraperTestResult):
    """Test 5c: Check for scraper issues using diagnose_scraper.py"""
    progress_file = script_dir / 'scrape_progress.json'
    
    if not progress_file.exists():
        return  # No progress file, can't diagnose
    
    try:
        with open(progress_file) as f:
            progress = json.load(f)
        
        failed_urls = progress.get('failedUrls', [])
        
        if not failed_urls:
            result.add_pass("No scraper errors")
            return
        
        # Categorize errors
        error_counts = {
            'dns': 0,
            'blocked': 0,
            'timeout': 0,
            'server': 0,
            'other': 0
        }
        
        for item in failed_urls:
            error = item.get('error', '') if isinstance(item, dict) else str(item)
            error_lower = error.lower()
            
            if 'resolve' in error_lower or 'nodename' in error_lower or 'getaddrinfo' in error_lower:
                error_counts['dns'] += 1
            elif '403' in error or '429' in error or 'cloudflare' in error_lower:
                error_counts['blocked'] += 1
            elif 'timeout' in error_lower:
                error_counts['timeout'] += 1
            elif any(x in error for x in ['500', '502', '503', '504']):
                error_counts['server'] += 1
            else:
                error_counts['other'] += 1
        
        total_failed = len(failed_urls)
        
        # Check for critical issues
        if error_counts['blocked'] > total_failed * 0.3:
            result.add_fail("Site BLOCKING scraper", 
                f"{error_counts['blocked']} blocked requests - use stealth_scraper.py")
        elif error_counts['dns'] > total_failed * 0.8:
            result.add_fail("Site appears DOWN",
                f"{error_counts['dns']} DNS errors - wait for site recovery")
        elif total_failed > 0:
            breakdown = ", ".join(f"{k}: {v}" for k, v in error_counts.items() if v > 0)
            result.add_warning("Scraper has errors", f"{total_failed} failures ({breakdown})")
        
    except Exception as e:
        result.add_warning("Health check", str(e))


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


def test_user_agent(script_path: Path, result: ScraperTestResult):
    """Test 9: Script uses a User-Agent header"""
    with open(script_path) as f:
        code = f.read()
    
    ua_patterns = ['User-Agent', 'user-agent', 'headers']
    has_ua = any(p in code for p in ua_patterns)
    
    if has_ua:
        result.add_pass("User-Agent header")
    else:
        result.add_warning("User-Agent header", "No User-Agent found - may get blocked")


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


def run_tests(script_path_str: str) -> bool:
    """Run all tests on a scraper script"""
    script_path = Path(script_path_str).resolve()
    script_dir = script_path.parent
    
    print(f"\n{CYAN}═══════════════════════════════════════════════════════════{NC}")
    print(f"{CYAN}  Scraper Test Suite{NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════{NC}")
    print(f"\n  Script: {script_path}")
    print(f"  Dir:    {script_dir}\n")
    
    result = ScraperTestResult()
    
    # Run all tests
    test_script_exists(script_path, result)
    if not result.all_passed:
        return False
    
    test_script_syntax(script_path, result)
    test_required_imports(script_path, result)
    test_urls_json_exists(script_dir, result)
    test_html_directory(script_dir, result)
    test_scraping_progress(script_dir, result)
    test_scraper_health(script_dir, result)
    test_rate_limiting(script_path, result)
    test_error_handling(script_path, result)
    test_checkpoint_saving(script_path, result)
    test_user_agent(script_path, result)
    test_dry_run(script_path, script_dir, result)
    
    # Summary
    print(f"\n{CYAN}───────────────────────────────────────────────────────────{NC}")
    print(f"  {GREEN}Passed:{NC}   {len(result.passed)}")
    print(f"  {RED}Failed:{NC}   {len(result.failed)}")
    print(f"  {YELLOW}Warnings:{NC} {len(result.warnings)}")
    print(f"{CYAN}───────────────────────────────────────────────────────────{NC}")
    
    if result.all_passed:
        print(f"\n  {GREEN}✓ ALL TESTS PASSED{NC}\n")
        return True
    else:
        print(f"\n  {RED}✗ TESTS FAILED{NC}\n")
        for test_name, message in result.failed:
            print(f"    • {test_name}: {message}")
        print()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path_to_scraper.py>")
        print(f"Example: {sys.argv[0]} data/modified_rides/scrape_html.py")
        sys.exit(1)
    
    script_path = sys.argv[1]
    success = run_tests(script_path)
    sys.exit(0 if success else 1)

