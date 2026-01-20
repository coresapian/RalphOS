#!/usr/bin/env python3
"""
Scraper Diagnostic Tool for Ralph
Analyzes scrape_progress.json to detect issues and suggest fixes.

Usage:
 python scripts/tools/diagnose_scraper.py data/modified_rides/
 
Returns:
 Exit code 0 = healthy
 Exit code 1 = issues found (needs attention)
 Exit code 2 = critical (scraper broken)
"""

import json
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta
import re

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
NC = '\033[0m'


def analyze_errors(failed_urls: list) -> dict:
 """Categorize errors by type"""
 categories = {
 'dns': [], # DNS resolution failures
 'timeout': [], # Connection timeouts
 'blocked_403': [], # 403 Forbidden (anti-bot)
 'blocked_429': [], # 429 Too Many Requests
 'cloudflare': [], # Cloudflare challenges
 'server_5xx': [], # Server errors
 'not_found': [], # 404 Not Found
 'ssl': [], # SSL/TLS errors
 'connection': [], # General connection errors
 'other': [] # Unknown errors
 }
 
 for item in failed_urls:
 if isinstance(item, dict):
 error = item.get('error', '')
 url = item.get('url', '')
 else:
 error = str(item)
 url = ''error_lower = error.lower()
 
 if 'resolve' in error_lower or 'nodename' in error_lower or 'getaddrinfo' in error_lower:
 categories['dns'].append({'url': url, 'error': error})
 elif 'timeout' in error_lower or 'timed out' in error_lower:
 categories['timeout'].append({'url': url, 'error': error})
 elif '403' in error:
 categories['blocked_403'].append({'url': url, 'error': error})
 elif '429' in error:
 categories['blocked_429'].append({'url': url, 'error': error})
 elif 'cloudflare' in error_lower or 'captcha' in error_lower:
 categories['cloudflare'].append({'url': url, 'error': error})
 elif re.search(r'50[0-4]', error):
 categories['server_5xx'].append({'url': url, 'error': error})
 elif '404' in error:
 categories['not_found'].append({'url': url, 'error': error})
 elif 'ssl' in error_lower or 'certificate' in error_lower:
 categories['ssl'].append({'url': url, 'error': error})
 elif 'connection' in error_lower or 'connect' in error_lower:
 categories['connection'].append({'url': url, 'error': error})
 else:
 categories['other'].append({'url': url, 'error': error})
 
 return categories


def get_fix_suggestion(category: str, count: int, total_failed: int) -> str:
 """Get fix suggestion for error category"""
 suggestions = {
 'dns': "DNS errors - site may be down. Wait and retry later, or check if domain changed.",
 'timeout': "Timeouts - increase timeout in scraper (currently 30s, try 60s) or add delays.",
 'blocked_403': "403 Forbidden - site is blocking. Use stealth_scraper.py with Camoufox.",
 'blocked_429': "Rate limited - increase delay between requests (try 3-5 seconds).",
 'cloudflare': "Cloudflare blocking - requires stealth_scraper.py with browser automation.",
 'server_5xx': "Server errors - site having issues. Retry failed URLs later.",
 'not_found': "404 errors - URLs may be invalid. Check URL discovery for bad patterns.",
 'ssl': "SSL errors - add verify=False or update certificates.",
 'connection': "Connection errors - check network, add retry logic.",
 'other': "Unknown errors - review error messages manually."
 }
 return suggestions.get(category, "Unknown issue")


def diagnose(output_dir: Path) -> int:
 """Run diagnostics on scraper output"""
 print(f"\n{CYAN}{''* 60}{NC}")
 print(f"{CYAN} Scraper Diagnostic Report{NC}")
 print(f"{CYAN}{''* 60}{NC}")
 print(f"\n Directory: {output_dir}\n")
 
 progress_file = output_dir / "scrape_progress.json"
 html_dir = output_dir / "html"
 urls_file = output_dir / "urls.json"
 
 # Check files exist
 if not progress_file.exists():
 print(f" {RED} No scrape_progress.json found{NC}")
 print(f" → Scraper hasn't been run yet")
 return 2
 
 # Load progress
 with open(progress_file) as f:
 progress = json.load(f)
 
 total_urls = progress.get('totalUrls', 0)
 completed = progress.get('completedUrls', 0)
 failed_urls = progress.get('failedUrls', [])
 last_index = progress.get('lastUrlIndex', 0)
 last_updated = progress.get('lastUpdated', '')
 
 # Get actual HTML count
 html_count = len(list(html_dir.glob('*.html'))) if html_dir.exists() else 0
 
 # Calculate stats
 failed_count = len(failed_urls)
 attempted = completed + failed_count
 remaining = total_urls - last_index
 progress_pct = (html_count / total_urls * 100) if total_urls > 0 else 0
 
 # Status section
 print(f" {BOLD}Status:{NC}")
 print(f" Total URLs: {total_urls}")
 print(f" HTML files: {html_count}")
 print(f" Completed: {completed}")
 print(f" Failed: {failed_count}")
 print(f" Remaining: {remaining}")
 print(f" Progress: {progress_pct:.1f}%")
 print(f" Last updated: {last_updated[:19] if last_updated else 'Never'}")
 
 # Determine health
 issues = []
 critical = False
 
 if total_urls == 0:
 issues.append("No URLs to scrape")
 critical = True
 
 if failed_count > 0:
 # Analyze errors
 categories = analyze_errors(failed_urls)
 
 print(f"\n {BOLD}Error Analysis:{NC}")
 
 for cat, items in categories.items():
 if items:
 count = len(items)
 pct = (count / failed_count * 100)
 
 if cat in ['blocked_403', 'blocked_429', 'cloudflare']:
 color = RED
 critical = True
 elif cat == 'dns':
 color = YELLOW
 else:
 color = YELLOW
 
 print(f" {color}• {cat}: {count} ({pct:.0f}%){NC}")
 issues.append(f"{cat}: {count}")
 
 # Suggest fixes
 print(f"\n {BOLD}Recommended Actions:{NC}")
 
 action_num = 1
 for cat, items in categories.items():
 if items:
 suggestion = get_fix_suggestion(cat, len(items), failed_count)
 print(f" {CYAN}{action_num}. {suggestion}{NC}")
 action_num += 1
 
 # Check if mostly DNS errors (site down)
 dns_count = len(categories.get('dns', []))
 if dns_count > failed_count * 0.8:
 print(f"\n {YELLOW} Site appears to be DOWN (80%+ DNS errors){NC}")
 print(f" Wait for site to recover, then retry failed URLs.")
 
 # Check if blocked
 blocked = len(categories.get('blocked_403', [])) + len(categories.get('blocked_429', [])) + len(categories.get('cloudflare', []))
 if blocked > failed_count * 0.5:
 print(f"\n {RED} Site is BLOCKING scraper (50%+ blocked){NC}")
 print(f" Use: python scripts/tools/stealth_scraper.py --source {output_dir.name}")
 critical = True
 
 # Check for stale progress
 if last_updated:
 try:
 last_dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
 age = datetime.now(last_dt.tzinfo) - last_dt if last_dt.tzinfo else datetime.now() - datetime.fromisoformat(last_updated[:19])
 if age > timedelta(minutes=10) and remaining > 0:
 print(f"\n {YELLOW} Scraper appears STALLED (no update in {age}){NC}")
 issues.append("stalled")
 except:
 pass
 
 # Summary
 print(f"\n{CYAN}{''* 60}{NC}")
 
 if critical:
 print(f" {RED}{BOLD}CRITICAL: Scraper needs intervention{NC}")
 return 2
 elif issues:
 print(f" {YELLOW}{BOLD}ISSUES FOUND: {len(issues)} problem(s){NC}")
 return 1
 elif progress_pct >= 95:
 print(f" {GREEN}{BOLD}HEALTHY: Scraping complete ({progress_pct:.1f}%){NC}")
 return 0
 else:
 print(f" {GREEN}{BOLD}HEALTHY: Scraping in progress ({progress_pct:.1f}%){NC}")
 return 0


def main():
 if len(sys.argv) < 2:
 print(f"Usage: {sys.argv[0]} <output_directory>")
 print(f"Example: {sys.argv[0]} data/modified_rides/")
 sys.exit(1)
 
 output_dir = Path(sys.argv[1])
 if not output_dir.exists():
 print(f"{RED}Error: Directory not found: {output_dir}{NC}")
 sys.exit(2)
 
 exit_code = diagnose(output_dir)
 print()
 sys.exit(exit_code)


if __name__ == "__main__":
 main()

