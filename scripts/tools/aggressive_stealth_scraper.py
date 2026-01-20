#!/usr/bin/env python3
"""
RalphOS Aggressive Stealth Scraper - For highly protected sites like PistonHeads

This scraper is designed for sites with aggressive anti-bot measures:
- Much longer delays (8-20 seconds between requests)
- Exponential backoff on rate limits (5-30 minute cooldowns)
- Frequent session rotation (every 10-15 requests)
- Daily request limits to avoid patterns
- Smart timing variation to appear human

Usage:
 python scripts/tools/aggressive_stealth_scraper.py --source pistonheads_auctions --limit 50
 python scripts/tools/aggressive_stealth_scraper.py --source pistonheads_auctions --daily-limit 100
 python scripts/tools/aggressive_stealth_scraper.py --urls-file data/pistonheads/urls.json

Requirements:
 pip install camoufox[geoip] orjson tqdm python-dotenv
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import random
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
 import orjson
except ImportError:
 orjson = None

try:
 from camoufox.async_api import AsyncCamoufox
 CAMOUFOX_AVAILABLE = True
except ImportError:
 CAMOUFOX_AVAILABLE = False
 print("WARNING: camoufox not installed. Run: pip install camoufox[geoip]")

try:
 from tqdm.asyncio import tqdm as async_tqdm
 TQDM_AVAILABLE = True
except ImportError:
 TQDM_AVAILABLE = False

try:
 from dotenv import load_dotenv
 load_dotenv()
except ImportError:
 pass

# Setup logging
logging.basicConfig(
 level=logging.INFO,
 format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Shutdown handling
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
 if shutdown_event.is_set():
 sys.exit(1)
 logger.info("\nGraceful shutdown requested... (Ctrl+C again to force)")
 shutdown_event.set()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class AggressiveStealthConfig:
 """Configuration for aggressive stealth scraping."""
 
 def __init__(
 self,
 output_dir: Path,
 # Much longer delays for protected sites
 min_delay: float = 8.0,
 max_delay: float = 20.0,
 # Initial backoff time in seconds (5 minutes)
 initial_backoff: int = 300,
 # Maximum backoff time (30 minutes)
 max_backoff: int = 1800,
 # Rotate session more frequently
 rotate_every: int = 12,
 # Daily limit to avoid detection patterns
 daily_limit: Optional[int] = None,
 # Timeout per page
 timeout: int = 60000,
 headless: bool = True,
 # Proxy settings
 proxy_host: Optional[str] = None,
 proxy_port: Optional[int] = None,
 proxy_user: Optional[str] = None,
 proxy_pass: Optional[str] = None,
 ):
 self.output_dir = Path(output_dir)
 self.min_delay = min_delay
 self.max_delay = max_delay
 self.initial_backoff = initial_backoff
 self.max_backoff = max_backoff
 self.rotate_every = rotate_every
 self.daily_limit = daily_limit
 self.timeout = timeout
 self.headless = headless
 
 # Proxy from args or env
 self.proxy_host = proxy_host or os.environ.get("BRIGHTDATA_PROXY_HOST", "brd.superproxy.io")
 self.proxy_port = proxy_port or int(os.environ.get("BRIGHTDATA_PROXY_PORT", "33335"))
 self.proxy_user = proxy_user or os.environ.get("BRIGHTDATA_PROXY_USER", "")
 self.proxy_pass = proxy_pass or os.environ.get("BRIGHTDATA_PROXY_PASS", "")
 
 @property
 def proxy_dict(self) -> Optional[Dict[str, str]]:
 """Get Playwright-compatible proxy config if credentials available."""
 if not self.proxy_user or not self.proxy_pass:
 return None
 return {
 "server": f"http://{self.proxy_host}:{self.proxy_port}",
 "username": self.proxy_user,
 "password": self.proxy_pass,
 }


class SmartCheckpointManager:
 """Track processed URLs with daily limits and rate limit detection."""
 
 def __init__(self, checkpoint_path: Path):
 self.path = checkpoint_path
 self.state = self._load()
 
 def _load(self) -> Dict[str, Any]:
 if self.path.exists():
 try:
 with open(self.path, "rb") as f:
 if orjson:
 return orjson.loads(f.read())
 else:
 return json.load(f)
 except Exception as e:
 logger.warning(f"Error loading checkpoint: {e}")
 return {
 "processed_urls": [],
 "failed_urls": [],
 "blocked_urls": [],
 "rate_limited_count": 0,
 "consecutive_blocks": 0,
 "last_block_time": None,
 "current_backoff": 0,
 "daily_counts": {}, # {"2026-01-16": 50}
 "last_updated": None,
 }
 
 def save(self):
 self.path.parent.mkdir(parents=True, exist_ok=True)
 self.state["last_updated"] = datetime.now().isoformat()
 with open(self.path, "wb") as f:
 if orjson:
 f.write(orjson.dumps(self.state, option=orjson.OPT_INDENT_2))
 else:
 f.write(json.dumps(self.state, indent=2).encode())
 
 def is_processed(self, url: str) -> bool:
 return url in self.state["processed_urls"]
 
 def mark_processed(self, url: str):
 if url not in self.state["processed_urls"]:
 self.state["processed_urls"].append(url)
 # Reset consecutive blocks on success
 self.state["consecutive_blocks"] = 0
 # Track daily count
 today = datetime.now().strftime("%Y-%m-%d")
 self.state["daily_counts"][today] = self.state["daily_counts"].get(today, 0) + 1
 
 def mark_failed(self, url: str):
 if url not in self.state["failed_urls"]:
 self.state["failed_urls"].append(url)
 
 def mark_blocked(self, url: str, backoff: int):
 if url not in self.state["blocked_urls"]:
 self.state["blocked_urls"].append(url)
 self.state["rate_limited_count"] += 1
 self.state["consecutive_blocks"] += 1
 self.state["last_block_time"] = datetime.now().isoformat()
 self.state["current_backoff"] = backoff
 
 def get_today_count(self) -> int:
 today = datetime.now().strftime("%Y-%m-%d")
 return self.state["daily_counts"].get(today, 0)
 
 def should_stop_for_day(self, daily_limit: Optional[int]) -> bool:
 if daily_limit is None:
 return False
 return self.get_today_count() >= daily_limit
 
 def reset(self):
 self.state = {
 "processed_urls": [],
 "failed_urls": [],
 "blocked_urls": [],
 "rate_limited_count": 0,
 "consecutive_blocks": 0,
 "last_block_time": None,
 "current_backoff": 0,
 "daily_counts": {},
 "last_updated": None,
 }
 self.save()
 
 @property
 def stats(self) -> Dict[str, int]:
 return {
 "processed": len(self.state["processed_urls"]),
 "failed": len(self.state["failed_urls"]),
 "blocked": len(self.state["blocked_urls"]),
 "rate_limited_total": self.state["rate_limited_count"],
 "consecutive_blocks": self.state["consecutive_blocks"],
 "today_count": self.get_today_count(),
 }


def url_to_build_id(url: str) -> int:
 """Convert URL to unique build_id using MD5 hash."""
 md5 = hashlib.md5(url.strip().encode()).digest()
 return int.from_bytes(md5[:8], "little", signed=False) % (1 << 63)


def load_urls_from_json(json_path: Path) -> List[str]:
 """Load URLs from urls.json file."""
 with open(json_path, "r") as f:
 data = json.load(f)
 
 if isinstance(data, dict) and "urls" in data:
 urls_data = data["urls"]
 if isinstance(urls_data, list) and len(urls_data) > 0:
 if isinstance(urls_data[0], dict):
 return [item["url"] for item in urls_data if isinstance(item, dict) and "url" in item]
 else:
 return urls_data
 return []
 elif isinstance(data, list):
 return data
 else:
 raise ValueError(f"Unknown JSON format in {json_path}")


class AggressiveStealthScraper:
 """
 Stealth scraper with aggressive anti-detection for protected sites.
 
 Key features:
 - Exponential backoff on rate limits
 - Very long delays between requests
 - Frequent session rotation
 - Daily scraping limits
 - Human-like timing variations
 """
 
 def __init__(self, config: AggressiveStealthConfig, checkpoint: SmartCheckpointManager):
 self.config = config
 self.checkpoint = checkpoint
 self.stats = {"processed": 0, "failed": 0, "blocked": 0}
 self._browser = None
 self._context = None
 self._page = None
 self._pages_used = 0
 self._current_backoff = config.initial_backoff
 
 async def _init_browser(self):
 """Initialize Camoufox browser with aggressive stealth settings."""
 # Randomize OS for each session
 os_choice = random.choice(["windows", "macos", "linux"])
 
 launch_kwargs = {
 "headless": self.config.headless,
 "humanize": True,
 "os": os_choice,
 "block_webrtc": True,
 "block_images": False, # Keep images to look more natural
 }
 
 # More aggressive canvas fingerprint variation
 launch_kwargs["config"] = {
 "canvas:aaOffset": random.randint(1, 5),
 "canvas:aaCapOffset": True,
 }
 
 if self.config.proxy_dict:
 launch_kwargs["proxy"] = self.config.proxy_dict
 launch_kwargs["geoip"] = True
 logger.info(f"Using proxy: {self.config.proxy_host}:{self.config.proxy_port}")
 else:
 # Randomize locale when no proxy
 locales = ["en-US", "en-GB", "en-CA", "en-AU"]
 launch_kwargs["locale"] = random.choice(locales)
 logger.info("No proxy - using direct connection (recommend using residential proxy)")
 
 self._camoufox_ctx = AsyncCamoufox(**launch_kwargs)
 self._browser = await self._camoufox_ctx.__aenter__()
 self._context = await self._browser.new_context(
 ignore_https_errors=True,
 # Add some randomized viewport
 viewport={
 "width": random.randint(1280, 1920),
 "height": random.randint(800, 1080),
 }
 )
 self._page = await self._context.new_page()
 self._pages_used = 0
 
 logger.info(f"Camoufox browser initialized (OS: {os_choice})")
 
 async def _rotate_session(self):
 """Rotate browser session with random delay."""
 logger.info("Rotating browser session...")
 
 # Random delay before rotation
 await asyncio.sleep(random.uniform(3, 8))
 
 if self._page:
 await self._page.close()
 if self._context:
 await self._context.close()
 
 # New context with fresh fingerprint
 self._context = await self._browser.new_context(
 ignore_https_errors=True,
 viewport={
 "width": random.randint(1280, 1920),
 "height": random.randint(800, 1080),
 }
 )
 self._page = await self._context.new_page()
 self._pages_used = 0
 
 # Longer delay after rotation
 await asyncio.sleep(random.uniform(5, 10))
 logger.info("Session rotated")
 
 async def _close_browser(self):
 """Clean up browser resources."""
 if self._page:
 try:
 await self._page.close()
 except:
 pass
 if self._context:
 try:
 await self._context.close()
 except:
 pass
 if self._camoufox_ctx:
 try:
 await self._camoufox_ctx.__aexit__(None, None, None)
 except:
 pass
 logger.info("Browser closed")
 
 async def _handle_rate_limit(self) -> bool:
 """
 Handle rate limit with exponential backoff.
 Returns True if should continue, False if should stop.
 """
 consecutive = self.checkpoint.state["consecutive_blocks"]
 
 # Calculate backoff with exponential increase
 backoff = min(
 self.config.initial_backoff * (2 ** consecutive),
 self.config.max_backoff
 )
 
 self._current_backoff = backoff
 
 logger.warning(f"Rate limited! Consecutive blocks: {consecutive}")
 logger.warning(f"Backing off for {backoff // 60} minutes...")
 
 # If too many consecutive blocks, suggest stopping
 if consecutive >= 5:
 logger.error("Too many consecutive blocks (5+). Stopping to avoid ban.")
 logger.error("RECOMMENDATION: Wait 24 hours before retrying, or use a proxy.")
 return False
 
 # Rotate session before waiting
 await self._rotate_session()
 
 # Wait with progress updates
 for i in range(backoff):
 if shutdown_event.is_set():
 return False
 if i % 60 == 0:
 remaining = (backoff - i) // 60
 logger.info(f"Backoff: {remaining} minutes remaining...")
 await asyncio.sleep(1)
 
 return True
 
 async def scrape_url(self, url: str) -> Optional[Dict[str, Any]]:
 """Scrape a single URL with enhanced anti-detection."""
 try:
 # Add random referrer
 referrers = [
 "https://www.google.com/",
 "https://www.google.co.uk/",
 "https://www.bing.com/",
 "https://duckduckgo.com/",
 "", # No referrer sometimes
 ]
 await self._page.set_extra_http_headers({
 "Referer": random.choice(referrers),
 "Accept-Language": "en-GB,en;q=0.9,en-US;q=0.8",
 })
 
 response = await self._page.goto(
 url,
 wait_until="domcontentloaded",
 timeout=self.config.timeout,
 )
 
 if not response:
 logger.warning(f"No response for {url}")
 return None
 
 status = response.status
 
 # Handle rate limiting
 if status == 429:
 logger.warning(f"RATE LIMITED (429) on {url}")
 self.checkpoint.mark_blocked(url, self._current_backoff)
 self.stats["blocked"] += 1
 return {"rate_limited": True}
 
 # Handle other blocks
 if status == 403:
 logger.warning(f"BLOCKED (403) on {url}")
 self.checkpoint.mark_blocked(url, self._current_backoff)
 self.stats["blocked"] += 1
 return {"rate_limited": True}
 
 if status >= 400:
 logger.warning(f"HTTP {status} on {url}")
 return None
 
 # Wait for JS to settle - longer wait
 await asyncio.sleep(random.uniform(1.0, 2.5))
 
 html = await self._page.content()
 
 if not html or len(html) < 500:
 logger.warning(f"Empty/short HTML for {url}")
 return None
 
 # Check for Cloudflare/captcha
 html_lower = html.lower()
 if "challenge" in html_lower and "cloudflare" in html_lower:
 logger.warning(f"Cloudflare challenge on {url}")
 self.checkpoint.mark_blocked(url, self._current_backoff)
 self.stats["blocked"] += 1
 return {"rate_limited": True}
 
 # Check for "too many requests" in content
 if "too many requests" in html_lower or "rate limit" in html_lower:
 logger.warning(f"Rate limit message in content on {url}")
 self.checkpoint.mark_blocked(url, self._current_backoff)
 self.stats["blocked"] += 1
 return {"rate_limited": True}
 
 return {
 "build_id": url_to_build_id(url),
 "url": url,
 "html": html,
 "scraped_at": datetime.now().isoformat(),
 "status_code": status,
 }
 
 except Exception as e:
 logger.error(f"Error scraping {url}: {e}")
 return None
 
 def _human_delay(self) -> float:
 """Generate human-like delay with variation."""
 # Base delay
 base = random.uniform(self.config.min_delay, self.config.max_delay)
 
 # Sometimes add extra "thinking" time (20% chance)
 if random.random() < 0.2:
 base += random.uniform(5, 15)
 
 # Sometimes very short pause (10% chance, simulating quick navigation)
 if random.random() < 0.1:
 base = random.uniform(3, 5)
 
 return base
 
 async def run(self, urls: List[str], limit: Optional[int] = None) -> Dict[str, int]:
 """Run the aggressive stealth scraper."""
 if not CAMOUFOX_AVAILABLE:
 logger.error("Camoufox not installed! Run: pip install camoufox[geoip]")
 return self.stats
 
 # Check daily limit
 if self.checkpoint.should_stop_for_day(self.config.daily_limit):
 today_count = self.checkpoint.get_today_count()
 logger.info(f"Daily limit reached ({today_count}/{self.config.daily_limit}). Try again tomorrow!")
 return self.stats
 
 # Filter already processed URLs
 pending = [u for u in urls if not self.checkpoint.is_processed(u)]
 
 if limit:
 pending = pending[:limit]
 
 # Apply daily limit
 if self.config.daily_limit:
 remaining_today = self.config.daily_limit - self.checkpoint.get_today_count()
 pending = pending[:remaining_today]
 
 logger.info(f"URLs to process: {len(pending)} (skipping {len(urls) - len(pending)} already done)")
 
 if not pending:
 logger.info("All URLs already processed!")
 return self.stats
 
 # Setup output
 self.config.output_dir.mkdir(parents=True, exist_ok=True)
 html_dir = self.config.output_dir / "html"
 html_dir.mkdir(exist_ok=True)
 
 timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
 output_file = self.config.output_dir / f"scraped_{timestamp}.jsonl"
 
 try:
 await self._init_browser()
 
 with open(output_file, "ab") as f:
 if TQDM_AVAILABLE:
 pbar = async_tqdm(total=len(pending), desc="Aggressive Stealth Scraping")
 else:
 pbar = None
 
 for i, url in enumerate(pending):
 if shutdown_event.is_set():
 logger.info("Shutdown requested, saving progress...")
 break
 
 # Check daily limit again
 if self.checkpoint.should_stop_for_day(self.config.daily_limit):
 logger.info("Daily limit reached. Stopping for today.")
 break
 
 # Session rotation - more frequent
 if self._pages_used > 0 and self._pages_used % self.config.rotate_every == 0:
 await self._rotate_session()
 
 # Human-like delay
 delay = self._human_delay()
 logger.debug(f"Waiting {delay:.1f}s before next request...")
 await asyncio.sleep(delay)
 
 # Clear cookies periodically
 if i > 0 and i % 50 == 0:
 await self._context.clear_cookies()
 logger.info("Cleared cookies")
 
 result = await self.scrape_url(url)
 self._pages_used += 1
 
 if result and result.get("rate_limited"):
 # Handle rate limit
 should_continue = await self._handle_rate_limit()
 if not should_continue:
 logger.error("Stopping due to repeated rate limits")
 break
 continue
 
 if result and "html" in result:
 # Save to JSONL (without HTML for space)
 result_meta = {k: v for k, v in result.items() if k != "html"}
 if orjson:
 f.write(orjson.dumps(result_meta) + b"\n")
 else:
 f.write(json.dumps(result_meta).encode() + b"\n")
 f.flush()
 
 # Save HTML separately
 html_file = html_dir / f"{result['build_id']}.html"
 html_file.write_text(result["html"])
 
 self.checkpoint.mark_processed(url)
 self.stats["processed"] += 1
 
 # Reset backoff on success
 self._current_backoff = self.config.initial_backoff
 else:
 self.checkpoint.mark_failed(url)
 self.stats["failed"] += 1
 
 if pbar:
 pbar.update(1)
 pbar.set_postfix(
 ok=self.stats["processed"],
 fail=self.stats["failed"],
 block=self.stats["blocked"],
 today=self.checkpoint.get_today_count(),
 )
 
 # Checkpoint every 10 URLs (more frequent for aggressive scraping)
 if (self.stats["processed"] + self.stats["failed"]) % 10 == 0:
 self.checkpoint.save()
 
 if pbar:
 pbar.close()
 
 finally:
 await self._close_browser()
 self.checkpoint.save()
 
 logger.info(f"\n{'='*60}")
 logger.info("Scraping session complete!")
 logger.info(f"Processed: {self.stats['processed']}")
 logger.info(f"Failed: {self.stats['failed']}")
 logger.info(f"Blocked: {self.stats['blocked']}")
 logger.info(f"Today's total: {self.checkpoint.get_today_count()}")
 logger.info(f"Output: {output_file}")
 
 if self.stats["blocked"] > 0:
 logger.warning("\n RECOMMENDATIONS TO AVOID BLOCKS:")
 logger.warning(" 1. Use a residential proxy (BrightData, Oxylabs)")
 logger.warning(" 2. Set --daily-limit 50-100 to spread over days")
 logger.warning(" 3. Run during off-peak hours (night/weekend)")
 logger.warning(" 4. Wait 24+ hours if heavily rate limited")
 
 logger.info(f"{'='*60}")
 
 return self.stats


async def main():
 parser = argparse.ArgumentParser(
 description="Aggressive Stealth Scraper for protected sites",
 formatter_class=argparse.RawDescriptionHelpFormatter,
 epilog="""
Examples:
 # Scrape pistonheads with daily limit
 python aggressive_stealth_scraper.py --source pistonheads_auctions --daily-limit 50
 
 # Scrape with longer delays
 python aggressive_stealth_scraper.py --source mysite --min-delay 15 --max-delay 30
 
 # Use with proxy (set BRIGHTDATA_PROXY_USER and BRIGHTDATA_PROXY_PASS env vars)
 python aggressive_stealth_scraper.py --source mysite --daily-limit 200

TIPS FOR AVOIDING BLOCKS:
 - Use residential proxies (BrightData, Oxylabs, SmartProxy)
 - Spread scraping over multiple days with --daily-limit
 - Run during off-peak hours
 - If blocked, wait 24+ hours before retrying
 """
 )
 
 input_group = parser.add_mutually_exclusive_group(required=True)
 input_group.add_argument("--source", "-s", type=str, help="Source ID from sources.json")
 input_group.add_argument("--urls-file", "-f", type=Path, help="Path to urls.json file")
 
 parser.add_argument("--limit", "-l", type=int, help="Limit URLs to scrape this session")
 parser.add_argument("--daily-limit", type=int, default=50, help="Max URLs per day (default: 50)")
 parser.add_argument("--reset", action="store_true", help="Reset checkpoint")
 parser.add_argument("--no-headless", action="store_true", help="Show browser window")
 
 # Timing (with higher defaults)
 parser.add_argument("--min-delay", type=float, default=8.0, help="Min delay between requests (default: 8s)")
 parser.add_argument("--max-delay", type=float, default=20.0, help="Max delay between requests (default: 20s)")
 parser.add_argument("--rotate-every", type=int, default=12, help="Rotate session every N pages (default: 12)")
 
 # Backoff
 parser.add_argument("--initial-backoff", type=int, default=300, help="Initial backoff in seconds (default: 300 = 5min)")
 parser.add_argument("--max-backoff", type=int, default=1800, help="Max backoff in seconds (default: 1800 = 30min)")
 
 args = parser.parse_args()
 
 script_dir = Path(__file__).parent
 project_root = script_dir.parent.parent
 
 if args.source:
 sources_file = project_root / "scripts" / "ralph" / "sources.json"
 with open(sources_file) as f:
 sources_data = json.load(f)
 
 source = None
 for s in sources_data["sources"]:
 if s["id"] == args.source:
 source = s
 break
 
 if not source:
 logger.error(f"Source '{args.source}' not found in sources.json")
 sys.exit(1)
 
 output_dir = project_root / source["outputDir"]
 urls_file = output_dir / "urls.json"
 
 if not urls_file.exists():
 logger.error(f"URLs file not found: {urls_file}")
 sys.exit(1)
 else:
 urls_file = args.urls_file
 output_dir = urls_file.parent
 
 urls = load_urls_from_json(urls_file)
 logger.info(f"Loaded {len(urls)} URLs from {urls_file}")
 
 config = AggressiveStealthConfig(
 output_dir=output_dir,
 min_delay=args.min_delay,
 max_delay=args.max_delay,
 initial_backoff=args.initial_backoff,
 max_backoff=args.max_backoff,
 rotate_every=args.rotate_every,
 daily_limit=args.daily_limit,
 headless=not args.no_headless,
 )
 
 checkpoint_path = output_dir / "aggressive_checkpoint.json"
 checkpoint = SmartCheckpointManager(checkpoint_path)
 
 if args.reset:
 logger.info("Resetting checkpoint...")
 checkpoint.reset()
 
 logger.info(f"\n{'='*60}")
 logger.info("AGGRESSIVE STEALTH SCRAPER")
 logger.info(f"Delays: {config.min_delay}-{config.max_delay}s")
 logger.info(f"Session rotation: every {config.rotate_every} pages")
 logger.info(f"Daily limit: {config.daily_limit}")
 logger.info(f"Initial backoff: {config.initial_backoff // 60} minutes")
 if config.proxy_dict:
 logger.info(f"Proxy: {config.proxy_host}:{config.proxy_port}")
 else:
 logger.warning(" No proxy configured - higher risk of blocks")
 logger.info(f"{'='*60}\n")
 
 scraper = AggressiveStealthScraper(config, checkpoint)
 await scraper.run(urls, limit=args.limit)


if __name__ == "__main__":
 asyncio.run(main())
