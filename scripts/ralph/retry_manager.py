#!/usr/bin/env python3
"""
Retry Manager for Blocked Sources

Automatically retries blocked sources with stealth scraper and proxy rotation.
"""
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Configuration
RALPH_DIR = Path(__file__).parent
SOURCES_FILE = RALPH_DIR / "sources.json"
LOG_FILE = RALPH_DIR / "retry_log.txt"


class RetryManager:
 """Manage retry logic for blocked sources."""
 
 def __init__(self):
 self.sources_file = SOURCES_FILE
 self.log_file = LOG_FILE
 self._full_data = self._load_full_data()
 self.sources = self._full_data.get("sources", [])
 
 def _load_full_data(self) -> Dict:
 """Load full sources.json including metadata."""
 with open(self.sources_file) as f:
 return json.load(f)
 
 def _load_sources(self) -> List[Dict]:
 """Load sources from sources.json."""
 return self._full_data.get("sources", [])
 
 def _save_sources(self):
 """Save updated sources back to file, preserving metadata."""
 # Update sources in the full data structure
 self._full_data["sources"] = self.sources
 with open(self.sources_file, 'w') as f:
 json.dump(self._full_data, f, indent=2)
 
 def _log(self, message: str):
 """Log retry activity."""
 timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
 log_line = f"[{timestamp}] {message}\n"
 with open(self.log_file, 'a') as f:
 f.write(log_line)
 print(log_line.strip())
 
 def get_blocked_sources(self) -> List[Dict]:
 """Get list of blocked sources."""
 blocked = []
 for source in self.sources:
 if source.get("status") == "blocked":
 blocked.append(source)
 return blocked
 
 def get_sources_with_failures(self, threshold: int = 10) -> List[Dict]:
 """Get sources with high failure rates."""
 failed_sources = []
 for source in self.sources:
 pipeline = source.get("pipeline", {})
 urls_found = pipeline.get("urlsFound", 0)
 html_failed = pipeline.get("htmlFailed", 0)
 html_blocked = pipeline.get("htmlBlocked", 0)
 
 total_failures = html_failed + html_blocked
 if total_failures > threshold and urls_found > 0:
 failed_sources.append({
 "source": source,
 "failures": total_failures,
 "total": urls_found
 })
 return failed_sources
 
 def retry_source(self, source_id: str, force: bool = False):
 """
 Retry a blocked or failed source using Camoufox stealth scraper.
 
 Args:
 source_id: Source ID to retry
 force: Retry even if not blocked
 """
 # Find source
 source = None
 for s in self.sources:
 if s["id"] == source_id:
 source = s
 break
 
 if not source:
 print(f" Source '{source_id}' not found")
 return False
 
 # Check if should retry
 if not force and source["status"] != "blocked":
 print(f" Source '{source_id}' is not blocked (status: {source['status']})")
 print(" Use --force to retry anyway")
 return False
 
 self._log(f"Retrying source: {source_id} (using Camoufox)")
 
 # Update source status
 source["status"] = "in_progress"
 
 # Add retry metadata
 if "retryMetadata" not in source:
 source["retryMetadata"] = {"attempts": 0}
 source["retryMetadata"]["attempts"] += 1
 source["retryMetadata"]["lastAttempt"] = datetime.now().isoformat()
 source["retryMetadata"]["lastMethod"] = "camoufox"
 
 # Save changes
 self._save_sources()
 
 # Run stealth scraper (Camoufox)
 self._log(f"Running Camoufox stealth scraper for {source_id}...")
 result = self._run_stealth_scraper(source_id)
 
 if result:
 self._log(f" Camoufox scraper completed for {source_id}")
 source["status"] = "in_progress"
 self._save_sources()
 return True
 else:
 self._log(f" Camoufox scraper failed for {source_id}")
 source["status"] = "blocked"
 self._save_sources()
 return False
 
 def _run_stealth_scraper(self, source_id: str) -> bool:
 """Run stealth scraper for source."""
 stealth_scraper = RALPH_DIR.parent / "tools" / "stealth_scraper.py"
 
 if not stealth_scraper.exists():
 self._log(f" Stealth scraper not found: {stealth_scraper}")
 return False
 
 cmd = ["python3", str(stealth_scraper), "--source", source_id]
 
 try:
 result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
 
 if result.returncode == 0:
 self._log(f"Stealth scraper output: {result.stdout[-200:]}")
 return True
 else:
 self._log(f"Stealth scraper error: {result.stderr}")
 return False
 except subprocess.TimeoutExpired:
 self._log(f" Stealth scraper timed out (1 hour)")
 return False
 except Exception as e:
 self._log(f" Stealth scraper exception: {e}")
 return False
 
 def print_blocked_status(self):
 """Print status of blocked sources."""
 blocked = self.get_blocked_sources()
 
 print("\n" + "=" * 60)
 print("Blocked Sources Status")
 print("=" * 60)
 
 if not blocked:
 print(" No blocked sources")
 else:
 for source in blocked:
 pipeline = source.get("pipeline", {})
 urls = pipeline.get("urlsFound", 0)
 scraped = pipeline.get("htmlScraped", 0)
 blocked = pipeline.get("htmlBlocked", 0)
 
 print(f"\n {source['id']}")
 print(f" URLs: {urls}, Scraped: {scraped}, Blocked: {blocked}")
 print(f" Output: {source.get('outputDir', 'N/A')}")
 
 # Check retry metadata
 retry_meta = source.get("retryMetadata", {})
 if retry_meta:
 attempts = retry_meta.get("attempts", 0)
 last_attempt = retry_meta.get("lastAttempt", "Never")
 print(f" Retries: {attempts}, Last: {last_attempt}")
 
 print("\n" + "=" * 60 + "\n")
 
 def auto_retry_all(self):
 """Automatically retry all blocked sources using Camoufox."""
 blocked = self.get_blocked_sources()
 
 if not blocked:
 print(" No blocked sources to retry")
 return
 
 print(f"\nAuto-retrying {len(blocked)} blocked sources with Camoufox...")
 
 for source in blocked:
 print(f"\n{'=' * 60}")
 print(f"Retrying: {source['id']}")
 print('=' * 60)
 
 success = self.retry_source(source["id"])
 
 if not success:
 print(f"\n {source['id']} still blocked, continuing to next source...")
 
 print(f"\n{'=' * 60}")
 print("Auto-retry complete")
 print('=' * 60)


def main():
 """CLI interface for retry management."""
 import argparse
 
¬ parser = argparse.ArgumentParser(description="RalphOS Retry Manager (Camoufox)")
 parser.add_argument("command", choices=["status", "retry", "auto-retry", "list"],
 help="Retry command")
 parser.add_argument("--source", "-s", type=str, help="Source ID to retry")
 parser.add_argument("--force", "-f", action="store_true", help="Force retry even if not blocked")
 
 args = parser.parse_args()
 
 rm = RetryManager()
 
 if args.command == "status":
 rm.print_blocked_status()
 
 elif args.command == "list":
 blocked = rm.get_blocked_sources()
 print(f"Blocked sources ({len(blocked)}):")
 for s in blocked:
 print(f" - {s['id']}")
 
 elif args.command == "retry":
 if not args.source:
 print(" --source is required for retry command")
 sys.exit(1)
 
 success = rm.retry_source(args.source, force=args.force)
 sys.exit(0 if success else 1)
 
 elif args.command == "auto-retry":
 rm.auto_retry_all()


if __name__ == "__main__":
 main()
