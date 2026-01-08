#!/usr/bin/env python3
"""
RalphOS Stealth Scraper - Camoufox-based anti-detection scraping

Uses Camoufox (Firefox-based anti-detect browser) with:
- Automatic fingerprint generation via BrowserForge
- GeoIP auto-detection from proxy IP (if configured)
- Human-like cursor movement
- WebGL/Canvas anti-fingerprinting
- Session rotation to avoid blocks

Based on motormia-etl scraper infrastructure.

Usage:
    python scripts/tools/stealth_scraper.py --source custom_wheel_offset --limit 100
    python scripts/tools/stealth_scraper.py --source modified_rides --reset
    python scripts/tools/stealth_scraper.py --urls-file data/source/urls.json

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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import orjson
except ImportError:
    orjson = None  # Fall back to json

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


class StealthConfig:
    """Configuration for stealth scraping."""
    
    def __init__(
        self,
        output_dir: Path,
        min_delay: float = 2.0,
        max_delay: float = 5.0,
        timeout: int = 60000,
        headless: bool = True,
        rotate_every: int = 50,
        proxy_host: Optional[str] = None,
        proxy_port: Optional[int] = None,
        proxy_user: Optional[str] = None,
        proxy_pass: Optional[str] = None,
    ):
        self.output_dir = Path(output_dir)
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self.headless = headless
        self.rotate_every = rotate_every
        
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


class CheckpointManager:
    """Track processed URLs for resume capability."""
    
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
    
    def mark_failed(self, url: str):
        if url not in self.state["failed_urls"]:
            self.state["failed_urls"].append(url)
    
    def mark_blocked(self, url: str):
        if url not in self.state["blocked_urls"]:
            self.state["blocked_urls"].append(url)
    
    def reset(self):
        self.state = {
            "processed_urls": [],
            "failed_urls": [],
            "blocked_urls": [],
            "last_updated": None,
        }
        self.save()
    
    @property
    def stats(self) -> Dict[str, int]:
        return {
            "processed": len(self.state["processed_urls"]),
            "failed": len(self.state["failed_urls"]),
            "blocked": len(self.state["blocked_urls"]),
        }


def url_to_build_id(url: str) -> int:
    """Convert URL to unique build_id using MD5 hash."""
    md5 = hashlib.md5(url.strip().encode()).digest()
    return int.from_bytes(md5[:8], "little", signed=False) % (1 << 63)


def load_urls_from_json(json_path: Path) -> List[str]:
    """Load URLs from urls.json file (RalphOS format)."""
    with open(json_path, "r") as f:
        data = json.load(f)
    
    if isinstance(data, dict) and "urls" in data:
        return data["urls"]
    elif isinstance(data, list):
        return data
    else:
        raise ValueError(f"Unknown JSON format in {json_path}")


class StealthScraper:
    """
    Camoufox-based stealth scraper with anti-detection features.
    
    Features:
    - Automatic fingerprint rotation
    - Human-like delays and behavior
    - Session rotation on blocks
    - Checkpoint/resume support
    - Graceful shutdown handling
    """
    
    def __init__(self, config: StealthConfig, checkpoint: CheckpointManager):
        self.config = config
        self.checkpoint = checkpoint
        self.stats = {"processed": 0, "failed": 0, "blocked": 0}
        self._browser = None
        self._context = None
        self._page = None
        self._pages_used = 0
    
    async def _init_browser(self):
        """Initialize Camoufox browser with stealth settings."""
        launch_kwargs = {
            "headless": self.config.headless,
            "humanize": True,  # Human-like cursor movement
            "os": ["windows", "macos"],  # Random OS fingerprint
            "block_webrtc": True,  # Prevent WebRTC IP leaks
        }
        
        # Add canvas anti-fingerprinting
        launch_kwargs["config"] = {
            "canvas:aaOffset": 1,
            "canvas:aaCapOffset": True,
        }
        
        # Add proxy if configured
        if self.config.proxy_dict:
            launch_kwargs["proxy"] = self.config.proxy_dict
            launch_kwargs["geoip"] = True  # Auto timezone/locale from proxy IP
            logger.info(f"Using proxy: {self.config.proxy_host}:{self.config.proxy_port} with GeoIP")
        else:
            launch_kwargs["locale"] = "en-US"
            logger.info("No proxy configured - using direct connection")
        
        self._camoufox_ctx = AsyncCamoufox(**launch_kwargs)
        self._browser = await self._camoufox_ctx.__aenter__()
        self._context = await self._browser.new_context(ignore_https_errors=True)
        self._page = await self._context.new_page()
        self._pages_used = 0
        
        logger.info("Camoufox browser initialized with stealth settings")
    
    async def _rotate_session(self):
        """Rotate browser session to get new fingerprint/IP."""
        logger.info("Rotating browser session...")
        
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        
        self._context = await self._browser.new_context(ignore_https_errors=True)
        self._page = await self._context.new_page()
        self._pages_used = 0
        
        # Wait a bit after rotation
        await asyncio.sleep(random.uniform(2, 5))
        logger.info("Session rotated successfully")
    
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
    
    async def scrape_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape a single URL with stealth browser.
        
        Returns:
            Dict with url, build_id, html, scraped_at, or None on failure
        """
        try:
            response = await self._page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.config.timeout,
            )
            
            if not response:
                logger.warning(f"No response for {url}")
                return None
            
            status = response.status
            
            # Check for blocks
            if status == 403:
                logger.warning(f"BLOCKED (403) on {url}")
                self.checkpoint.mark_blocked(url)
                self.stats["blocked"] += 1
                return None
            elif status == 429:
                logger.warning(f"RATE LIMITED (429) on {url}")
                self.checkpoint.mark_blocked(url)
                self.stats["blocked"] += 1
                return None
            elif status >= 400:
                logger.warning(f"HTTP {status} on {url}")
                return None
            
            # Wait for JS to settle
            await asyncio.sleep(0.5)
            
            html = await self._page.content()
            
            if not html or len(html) < 500:
                logger.warning(f"Empty/short HTML for {url}")
                return None
            
            # Check for Cloudflare/captcha in content
            html_lower = html.lower()
            if "challenge" in html_lower and "cloudflare" in html_lower:
                logger.warning(f"Cloudflare challenge detected on {url}")
                self.checkpoint.mark_blocked(url)
                self.stats["blocked"] += 1
                return None
            
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
    
    async def run(self, urls: List[str], limit: Optional[int] = None) -> Dict[str, int]:
        """
        Run the scraper on a list of URLs.
        
        Args:
            urls: List of URLs to scrape
            limit: Optional limit on number of URLs
        
        Returns:
            Stats dict with processed/failed/blocked counts
        """
        if not CAMOUFOX_AVAILABLE:
            logger.error("Camoufox not installed! Run: pip install camoufox[geoip]")
            return self.stats
        
        # Filter already processed URLs
        pending = [u for u in urls if not self.checkpoint.is_processed(u)]
        
        if limit:
            pending = pending[:limit]
        
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
                # Progress bar
                if TQDM_AVAILABLE:
                    pbar = async_tqdm(total=len(pending), desc="Stealth Scraping")
                else:
                    pbar = None
                
                for i, url in enumerate(pending):
                    if shutdown_event.is_set():
                        logger.info("Shutdown requested, saving progress...")
                        break
                    
                    # Session rotation
                    if self._pages_used > 0 and self._pages_used % self.config.rotate_every == 0:
                        await self._rotate_session()
                    
                    # Also rotate after blocks
                    if self.stats["blocked"] > 0 and self.stats["blocked"] % 3 == 0:
                        logger.info("Multiple blocks detected, rotating session...")
                        await self._rotate_session()
                        await asyncio.sleep(10)  # Cool down after blocks
                    
                    # Human-like delay
                    delay = random.uniform(self.config.min_delay, self.config.max_delay)
                    await asyncio.sleep(delay)
                    
                    # Clear cookies periodically
                    if i > 0 and i % 100 == 0:
                        await self._context.clear_cookies()
                        logger.debug(f"Cleared cookies at URL #{i}")
                    
                    result = await self.scrape_url(url)
                    self._pages_used += 1
                    
                    if result:
                        # Save to JSONL
                        if orjson:
                            f.write(orjson.dumps(result) + b"\n")
                        else:
                            f.write(json.dumps(result).encode() + b"\n")
                        f.flush()
                        
                        # Also save HTML separately
                        html_file = html_dir / f"{result['build_id']}.html"
                        html_file.write_text(result["html"])
                        
                        self.checkpoint.mark_processed(url)
                        self.stats["processed"] += 1
                    else:
                        self.checkpoint.mark_failed(url)
                        self.stats["failed"] += 1
                    
                    # Update progress
                    if pbar:
                        pbar.update(1)
                        pbar.set_postfix(
                            ok=self.stats["processed"],
                            fail=self.stats["failed"],
                            block=self.stats["blocked"],
                        )
                    
                    # Checkpoint every 25 URLs
                    if (self.stats["processed"] + self.stats["failed"]) % 25 == 0:
                        self.checkpoint.save()
                
                if pbar:
                    pbar.close()
        
        finally:
            await self._close_browser()
            self.checkpoint.save()
        
        logger.info(f"\n{'='*60}")
        logger.info("Scraping complete!")
        logger.info(f"Processed: {self.stats['processed']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Blocked: {self.stats['blocked']}")
        logger.info(f"Output: {output_file}")
        logger.info(f"HTML files: {html_dir}")
        logger.info(f"{'='*60}")
        
        return self.stats


async def main():
    parser = argparse.ArgumentParser(
        description="RalphOS Stealth Scraper with Camoufox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape a source by ID
  python stealth_scraper.py --source custom_wheel_offset --limit 100
  
  # Scrape from a URLs file
  python stealth_scraper.py --urls-file data/mysite/urls.json
  
  # Reset checkpoint and start fresh  
  python stealth_scraper.py --source modified_rides --reset
  
  # Show browser (for debugging)
  python stealth_scraper.py --source mysite --no-headless --limit 5
        """
    )
    
    # Input sources
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--source", "-s",
        type=str,
        help="Source ID from sources.json",
    )
    input_group.add_argument(
        "--urls-file", "-f",
        type=Path,
        help="Path to urls.json file",
    )
    
    # Scraping options
    parser.add_argument("--limit", "-l", type=int, help="Limit URLs to scrape")
    parser.add_argument("--reset", action="store_true", help="Reset checkpoint")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    
    # Timing
    parser.add_argument("--min-delay", type=float, default=2.0, help="Min delay between requests")
    parser.add_argument("--max-delay", type=float, default=5.0, help="Max delay between requests")
    parser.add_argument("--rotate-every", type=int, default=50, help="Rotate session every N pages")
    
    args = parser.parse_args()
    
    # Determine output dir and URLs file
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    
    if args.source:
        # Load from sources.json
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
            logger.error("Run URL discovery first!")
            sys.exit(1)
    else:
        urls_file = args.urls_file
        output_dir = urls_file.parent
    
    # Load URLs
    urls = load_urls_from_json(urls_file)
    logger.info(f"Loaded {len(urls)} URLs from {urls_file}")
    
    # Setup config
    config = StealthConfig(
        output_dir=output_dir,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        rotate_every=args.rotate_every,
        headless=not args.no_headless,
    )
    
    # Setup checkpoint
    checkpoint_path = output_dir / "stealth_checkpoint.json"
    checkpoint = CheckpointManager(checkpoint_path)
    
    if args.reset:
        logger.info("Resetting checkpoint...")
        checkpoint.reset()
    
    # Run scraper
    scraper = StealthScraper(config, checkpoint)
    stats = await scraper.run(urls, limit=args.limit)
    
    # Update sources.json with results
    if args.source and stats["processed"] > 0:
        logger.info("Updating sources.json pipeline counts...")
        try:
            with open(sources_file, "r") as f:
                sources_data = json.load(f)
            
            for s in sources_data["sources"]:
                if s["id"] == args.source:
                    # Count actual HTML files
                    html_dir = output_dir / "html"
                    html_count = len(list(html_dir.glob("*.html"))) if html_dir.exists() else 0
                    
                    s["pipeline"]["htmlScraped"] = html_count
                    s["status"] = "in_progress" if stats["blocked"] > 0 else s["status"]
                    s["notes"] = f"Stealth scraped {html_count} pages. Blocked: {stats['blocked']}"
                    break
            
            with open(sources_file, "w") as f:
                json.dump(sources_data, f, indent=2)
            
            logger.info(f"Updated {args.source} in sources.json")
        except Exception as e:
            logger.warning(f"Failed to update sources.json: {e}")


if __name__ == "__main__":
    asyncio.run(main())

