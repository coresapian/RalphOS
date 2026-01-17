#!/usr/bin/env python3
"""
RalphOS Cloudflare Bypass Scraper - FREE Auto-Solve (No Proxy/Service Required)

This scraper uses camoufox-captcha to automatically solve Cloudflare challenges:
- NO proxy required (works from home IP)
- NO paid CAPTCHA services needed
- Automatic Cloudflare Interstitial solving
- Automatic Turnstile checkbox clicking
- Shadow DOM traversal for hidden elements
- Cookie persistence for session reuse

How it works:
1. camoufox-captcha navigates the closed Shadow DOM
2. Finds the hidden checkbox in security iframes
3. Clicks it with human-like interaction
4. Verifies the challenge is solved

Usage:
    # Install dependencies
    pip install "camoufox[geoip]>=0.4.11" camoufox-captcha orjson tqdm

    # Basic usage
    python scripts/tools/cloudflare_bypass_scraper.py --source audiocityusa --limit 50

    # Non-headless mode (see what's happening)
    python scripts/tools/cloudflare_bypass_scraper.py --source audiocityusa --no-headless

Requirements:
    pip install "camoufox[geoip]>=0.4.11" camoufox-captcha orjson tqdm
    python -m camoufox fetch
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import random
import re
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    import orjson
except ImportError:
    orjson = None

try:
    from camoufox.async_api import AsyncCamoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False
    print("ERROR: camoufox not installed. Run:")
    print("  pip install 'camoufox[geoip]>=0.4.11'")
    print("  python -m camoufox fetch")

try:
    from camoufox_captcha import solve_captcha
    CAPTCHA_SOLVER_AVAILABLE = True
except ImportError:
    CAPTCHA_SOLVER_AVAILABLE = False
    print("WARNING: camoufox-captcha not installed. Run:")
    print("  pip install camoufox-captcha")

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


# ============================================================================
# Cloudflare Detection Patterns
# ============================================================================

CF_CHALLENGE_PATTERNS = [
    r'<title>Just a moment\.\.\.</title>',
    r'cloudflare\.com/cdn-cgi/challenge-platform',
    r'cf-chl-bypass',
    r'cf_chl_opt',
    r'turnstile\.cloudflare\.com',
    r'challenges\.cloudflare\.com',
    r'Checking your browser',
    r'Enable JavaScript and cookies',
    r'Verify you are human',
]

CF_TURNSTILE_PATTERNS = [
    r'cf-turnstile',
    r'turnstile/v0/api\.js',
    r'challenges\.cloudflare\.com/turnstile',
]

CF_SUCCESS_INDICATORS = [
    # Signs that CF challenge is complete
    r'cf_clearance',  # Cookie set after passing
]


def detect_cloudflare_state(html: str) -> Dict[str, Any]:
    """Detect Cloudflare protection state from HTML content."""
    result = {
        "is_challenge": False,
        "is_turnstile": False,
        "challenge_type": None,
    }

    # Check for challenge page (interstitial)
    for pattern in CF_CHALLENGE_PATTERNS:
        if re.search(pattern, html, re.IGNORECASE):
            result["is_challenge"] = True
            result["challenge_type"] = "interstitial"
            break

    # Check for Turnstile widget
    for pattern in CF_TURNSTILE_PATTERNS:
        if re.search(pattern, html, re.IGNORECASE):
            result["is_turnstile"] = True
            result["challenge_type"] = "turnstile"
            break

    return result


# ============================================================================
# Configuration
# ============================================================================

class ScraperConfig:
    """Configuration for Cloudflare bypass scraping."""

    def __init__(
        self,
        output_dir: Path,
        min_delay: float = 3.0,
        max_delay: float = 10.0,
        rotate_every: int = 30,
        headless: bool = True,
        timeout: int = 60000,
        daily_limit: Optional[int] = None,
        # Captcha solving settings
        solve_attempts: int = 3,
        solve_click_delay: float = 2.0,
    ):
        self.output_dir = Path(output_dir)
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.rotate_every = rotate_every
        self.headless = headless
        self.timeout = timeout
        self.daily_limit = daily_limit
        self.solve_attempts = solve_attempts
        self.solve_click_delay = solve_click_delay

    @property
    def user_data_dir(self) -> Path:
        return self.output_dir / ".browser_profile"


# ============================================================================
# Checkpoint Manager
# ============================================================================

class CheckpointManager:
    """Track processed URLs with cookie persistence."""

    def __init__(self, checkpoint_path: Path):
        self.path = checkpoint_path
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                with open(self.path, "rb") as f:
                    return orjson.loads(f.read()) if orjson else json.load(f)
            except Exception as e:
                logger.warning(f"Error loading checkpoint: {e}")
        return {
            "processed_urls": [],
            "failed_urls": [],
            "cf_solved_urls": [],
            "daily_counts": {},
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
            today = datetime.now().strftime("%Y-%m-%d")
            self.state["daily_counts"][today] = self.state["daily_counts"].get(today, 0) + 1

    def mark_failed(self, url: str):
        if url not in self.state["failed_urls"]:
            self.state["failed_urls"].append(url)

    def mark_cf_solved(self, url: str):
        if url not in self.state["cf_solved_urls"]:
            self.state["cf_solved_urls"].append(url)

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
            "cf_solved_urls": [],
            "daily_counts": {},
            "last_updated": None,
        }
        self.save()

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "processed": len(self.state["processed_urls"]),
            "failed": len(self.state["failed_urls"]),
            "cf_solved": len(self.state["cf_solved_urls"]),
            "today_count": self.get_today_count(),
        }


# ============================================================================
# Main Scraper
# ============================================================================

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


class CloudflareBypassScraper:
    """
    Scraper with FREE automatic Cloudflare bypass using camoufox-captcha.

    No proxy required - works from home IP (residential).
    No paid CAPTCHA services - uses browser-based auto-solving.

    Key features:
    - Automatic CF interstitial challenge solving
    - Automatic Turnstile checkbox clicking
    - Shadow DOM traversal for hidden elements
    - Persistent browser profile for cookie reuse
    - Human-like cursor movement
    """

    def __init__(self, config: ScraperConfig, checkpoint: CheckpointManager):
        self.config = config
        self.checkpoint = checkpoint
        self.stats = {"processed": 0, "failed": 0, "cf_solved": 0, "cf_failed": 0}
        self._browser = None
        self._page = None
        self._pages_used = 0
        self._camoufox_ctx = None

    async def _init_browser(self):
        """
        Initialize Camoufox with settings required for captcha solving.

        CRITICAL: forceScopeAccess and disable_coop are REQUIRED for
        camoufox-captcha to traverse the closed Shadow DOM.
        """
        # Randomize OS
        os_choice = random.choice(["windows", "macos", "linux"])

        # Build launch kwargs with captcha-solving requirements
        launch_kwargs = {
            # Anti-detection basics
            "os": os_choice,
            "humanize": True,  # Human-like cursor movement
            "block_webrtc": True,  # Prevent IP leak

            # REQUIRED for camoufox-captcha to work
            "config": {"forceScopeAccess": True},  # Shadow DOM access
            "disable_coop": True,  # Cross-origin bypass

            # Display mode
            "headless": self.config.headless,

            # Persistent profile for cookie reuse
            "persistent_context": True,
            "user_data_dir": str(self.config.user_data_dir),
        }

        # Random locale
        launch_kwargs["locale"] = random.choice(["en-US", "en-GB", "en-CA", "en-AU"])

        self.config.user_data_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"🦊 Initializing Camoufox (OS: {os_choice})...")
        logger.info(f"   forceScopeAccess: True (Shadow DOM access)")
        logger.info(f"   disable_coop: True (CF challenge bypass)")
        logger.info(f"   humanize: True (natural cursor movement)")
        logger.info(f"   Profile: {self.config.user_data_dir}")

        self._camoufox_ctx = AsyncCamoufox(**launch_kwargs)
        self._browser = await self._camoufox_ctx.__aenter__()
        self._page = await self._browser.new_page()
        self._pages_used = 0

        logger.info("✅ Browser initialized")

    async def _rotate_session(self):
        """Rotate page while preserving cookies in persistent context."""
        logger.info("🔄 Rotating session...")

        if self._page:
            await self._page.close()

        await asyncio.sleep(random.uniform(2, 5))

        self._page = await self._browser.new_page()
        self._pages_used = 0

        logger.info("✅ Session rotated (cookies preserved)")

    async def _close_browser(self):
        """Clean up browser resources."""
        try:
            if self._page:
                await self._page.close()
            if self._camoufox_ctx:
                await self._camoufox_ctx.__aexit__(None, None, None)
        except Exception as e:
            logger.debug(f"Browser cleanup error: {e}")
        logger.info("Browser closed")

    async def _solve_cloudflare(self, url: str, cf_state: Dict) -> bool:
        """
        Solve Cloudflare challenge using camoufox-captcha (FREE).

        This uses browser-based solving - no external services needed.
        """
        if not CAPTCHA_SOLVER_AVAILABLE:
            logger.error("camoufox-captcha not installed!")
            logger.error("Run: pip install camoufox-captcha")
            return False

        challenge_type = cf_state.get("challenge_type", "interstitial")
        logger.info(f"🛡️  Cloudflare {challenge_type} detected - auto-solving...")

        try:
            # Use camoufox-captcha to solve
            success = await solve_captcha(
                self._page,
                captcha_type="cloudflare",
                challenge_type=challenge_type,
                solve_attempts=self.config.solve_attempts,
                solve_click_delay=self.config.solve_click_delay,
                checkbox_click_attempts=3,
                wait_checkbox_attempts=5,
                wait_checkbox_delay=1.0,
            )

            if success:
                logger.info("✅ Cloudflare challenge SOLVED!")
                self.stats["cf_solved"] += 1
                self.checkpoint.mark_cf_solved(url)
                return True
            else:
                logger.warning("❌ Cloudflare solve failed")
                self.stats["cf_failed"] += 1
                return False

        except Exception as e:
            logger.error(f"Error solving Cloudflare: {e}")
            self.stats["cf_failed"] += 1
            return False

    async def scrape_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape a single URL with automatic Cloudflare solving."""
        try:
            # Random referrer
            referrers = [
                "https://www.google.com/",
                "https://www.bing.com/",
                "https://duckduckgo.com/",
                "",
            ]
            await self._page.set_extra_http_headers({
                "Referer": random.choice(referrers),
                "Accept-Language": "en-GB,en;q=0.9,en-US;q=0.8",
            })

            # Navigate
            response = await self._page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.config.timeout,
            )

            if not response:
                logger.warning(f"No response for {url}")
                return None

            status = response.status

            # Wait for page to settle
            await asyncio.sleep(random.uniform(1.5, 3.0))

            # Get HTML and check for Cloudflare
            html = await self._page.content()
            cf_state = detect_cloudflare_state(html)

            # Handle Cloudflare challenges
            if cf_state["is_challenge"] or cf_state["is_turnstile"]:
                solved = await self._solve_cloudflare(url, cf_state)

                if solved:
                    # Wait for redirect/reload after solving
                    await asyncio.sleep(3)
                    try:
                        await self._page.wait_for_load_state("networkidle", timeout=15000)
                    except:
                        pass

                    # Re-fetch content
                    html = await self._page.content()
                    cf_state = detect_cloudflare_state(html)

                    if cf_state["is_challenge"]:
                        logger.warning(f"Still seeing CF challenge after solve for {url}")
                        return {"cf_failed": True}
                else:
                    return {"cf_failed": True}

            # Handle HTTP errors
            if status >= 400:
                logger.warning(f"HTTP {status} on {url}")
                return None

            # Final content check
            html = await self._page.content()

            if not html or len(html) < 500:
                logger.warning(f"Empty/short HTML for {url}")
                return None

            # Double-check not still on CF page
            if "Just a moment" in html and "Checking your browser" in html:
                logger.warning(f"Still on CF page for {url}")
                return {"cf_failed": True}

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
        """Generate human-like delay."""
        base = random.uniform(self.config.min_delay, self.config.max_delay)

        # Occasional longer pause (15% chance)
        if random.random() < 0.15:
            base += random.uniform(3, 8)

        # Occasional quick action (10% chance)
        if random.random() < 0.1:
            base = random.uniform(1.5, 3)

        return base

    async def run(self, urls: List[str], limit: Optional[int] = None) -> Dict[str, int]:
        """Run the Cloudflare bypass scraper."""
        if not CAMOUFOX_AVAILABLE:
            logger.error("Camoufox not installed!")
            return self.stats

        if not CAPTCHA_SOLVER_AVAILABLE:
            logger.warning("⚠️  camoufox-captcha not installed - CF solving disabled")
            logger.warning("   Run: pip install camoufox-captcha")

        # Check daily limit
        if self.checkpoint.should_stop_for_day(self.config.daily_limit):
            logger.info(f"Daily limit reached. Try again tomorrow!")
            return self.stats

        # Filter processed URLs
        pending = [u for u in urls if not self.checkpoint.is_processed(u)]

        if limit:
            pending = pending[:limit]

        if self.config.daily_limit:
            remaining = self.config.daily_limit - self.checkpoint.get_today_count()
            pending = pending[:remaining]

        logger.info(f"URLs to process: {len(pending)}")

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
                pbar = async_tqdm(total=len(pending), desc="CF Bypass Scraping") if TQDM_AVAILABLE else None

                for i, url in enumerate(pending):
                    if shutdown_event.is_set():
                        logger.info("Shutdown requested...")
                        break

                    if self.checkpoint.should_stop_for_day(self.config.daily_limit):
                        logger.info("Daily limit reached. Stopping.")
                        break

                    # Session rotation
                    if self._pages_used > 0 and self._pages_used % self.config.rotate_every == 0:
                        await self._rotate_session()

                    # Human delay
                    delay = self._human_delay()
                    await asyncio.sleep(delay)

                    result = await self.scrape_url(url)
                    self._pages_used += 1

                    if result and result.get("cf_failed"):
                        # Rotate session after CF failure
                        await self._rotate_session()
                        self.checkpoint.mark_failed(url)
                        self.stats["failed"] += 1
                        continue

                    if result and "html" in result:
                        # Save metadata
                        result_meta = {k: v for k, v in result.items() if k != "html"}
                        if orjson:
                            f.write(orjson.dumps(result_meta) + b"\n")
                        else:
                            f.write(json.dumps(result_meta).encode() + b"\n")
                        f.flush()

                        # Save HTML
                        html_file = html_dir / f"{result['build_id']}.html"
                        html_file.write_text(result["html"])

                        self.checkpoint.mark_processed(url)
                        self.stats["processed"] += 1
                    else:
                        self.checkpoint.mark_failed(url)
                        self.stats["failed"] += 1

                    if pbar:
                        pbar.update(1)
                        pbar.set_postfix(
                            ok=self.stats["processed"],
                            fail=self.stats["failed"],
                            cf=self.stats["cf_solved"],
                        )

                    # Checkpoint periodically
                    if (self.stats["processed"] + self.stats["failed"]) % 10 == 0:
                        self.checkpoint.save()

                if pbar:
                    pbar.close()

        finally:
            await self._close_browser()
            self.checkpoint.save()

        # Summary
        logger.info(f"\n{'='*60}")
        logger.info("✅ Scraping session complete!")
        logger.info(f"   Processed: {self.stats['processed']}")
        logger.info(f"   Failed: {self.stats['failed']}")
        logger.info(f"   CF Solved: {self.stats['cf_solved']}")
        logger.info(f"   CF Failed: {self.stats['cf_failed']}")
        logger.info(f"   Output: {output_file}")
        logger.info(f"{'='*60}")

        return self.stats


async def main():
    parser = argparse.ArgumentParser(
        description="FREE Cloudflare Bypass Scraper (No Proxy/Service Required)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This scraper uses camoufox-captcha for FREE automatic Cloudflare solving.
NO proxy required - works from your home IP.
NO paid services - browser-based auto-solving.

Examples:
    # Basic usage
    python cloudflare_bypass_scraper.py --source audiocityusa --limit 100

    # See what's happening (non-headless)
    python cloudflare_bypass_scraper.py --source audiocityusa --no-headless --limit 10

    # Fresh start (clear cookies/profile)
    python cloudflare_bypass_scraper.py --source audiocityusa --reset

Install:
    pip install "camoufox[geoip]>=0.4.11" camoufox-captcha orjson tqdm
    python -m camoufox fetch
        """
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--source", "-s", type=str, help="Source ID from sources.json")
    input_group.add_argument("--urls-file", "-f", type=Path, help="Path to urls.json")

    parser.add_argument("--limit", "-l", type=int, help="Limit URLs to scrape")
    parser.add_argument("--daily-limit", type=int, help="Max URLs per day")
    parser.add_argument("--reset", action="store_true", help="Reset checkpoint and browser profile")
    parser.add_argument("--no-headless", action="store_true", help="Show browser (useful for debugging)")

    # Timing
    parser.add_argument("--min-delay", type=float, default=3.0, help="Min delay (default: 3s)")
    parser.add_argument("--max-delay", type=float, default=10.0, help="Max delay (default: 10s)")
    parser.add_argument("--rotate-every", type=int, default=30, help="Rotate every N pages")

    # Captcha solving
    parser.add_argument("--solve-attempts", type=int, default=3, help="CF solve attempts (default: 3)")

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
            logger.error(f"Source '{args.source}' not found")
            sys.exit(1)

        output_dir = project_root / source["outputDir"]
        urls_file = output_dir / "urls.json"
    else:
        urls_file = args.urls_file
        output_dir = urls_file.parent

    urls = load_urls_from_json(urls_file)
    logger.info(f"Loaded {len(urls)} URLs from {urls_file}")

    config = ScraperConfig(
        output_dir=output_dir,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        rotate_every=args.rotate_every,
        headless=not args.no_headless,
        daily_limit=args.daily_limit,
        solve_attempts=args.solve_attempts,
    )

    checkpoint = CheckpointManager(output_dir / "cf_checkpoint.json")

    if args.reset:
        checkpoint.reset()
        # Also clear browser profile
        if config.user_data_dir.exists():
            import shutil
            shutil.rmtree(config.user_data_dir)
            logger.info("Cleared browser profile")

    logger.info(f"\n{'='*60}")
    logger.info("🦊 CLOUDFLARE BYPASS SCRAPER (FREE - No Proxy/Service)")
    logger.info(f"{'='*60}")
    logger.info(f"   Solver: camoufox-captcha (browser-based, FREE)")
    logger.info(f"   Proxy: NOT REQUIRED (using home IP)")
    logger.info(f"   Delays: {config.min_delay}-{config.max_delay}s")
    logger.info(f"   Headless: {config.headless}")
    logger.info(f"   Solve attempts: {config.solve_attempts}")
    logger.info(f"{'='*60}\n")

    scraper = CloudflareBypassScraper(config, checkpoint)
    await scraper.run(urls, limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
