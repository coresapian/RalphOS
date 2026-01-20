"""
HTML Scraper Agent for RalphOS

A specialized Claude Agent SDK subagent that downloads HTML content from
discovered URLs using httpx (simple sites) or Camoufox (anti-bot protected).
Handles rate limiting, block detection, and session rotation.

Usage:
    # As a standalone agent
    from src.agents.html_scraper import run_html_scraper
    await run_html_scraper(
        output_dir="data/example_source",
        source_name="example_source"
    )

    # As a subagent within a parent agent
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Task"],
        agents={
            "html-scraper": HTMLScraperAgent.as_definition()
        }
    )
"""

import asyncio
from pathlib import Path
from typing import Any, Optional

# Import SDK components - graceful fallback if not installed
try:
    from claude_agent_sdk import (
        query,
        ClaudeAgentOptions,
        AgentDefinition,
        AssistantMessage,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    # Stub classes for type hints when SDK not installed
    class AgentDefinition:
        def __init__(self, **kwargs): pass

from .tools.html_tools import create_html_tools_server


# ============================================================================
# HTML Scraper Agent Definition
# ============================================================================

class HTMLScraperAgent:
    """
    HTML Scraper: A specialized agent for downloading HTML content.

    This agent uses custom MCP tools to:
    1. Load URLs from urls.jsonl (output from url-detective)
    2. Fetch HTML using httpx (simple) or Camoufox (stealth)
    3. Detect and handle blocks (403, 429, Cloudflare, CAPTCHA)
    4. Save HTML files to html/ directory
    5. Track progress in scrape_progress.jsonl
    6. Rotate sessions when blocked or periodically
    """

    # Agent system prompt defining behavior and expertise
    SYSTEM_PROMPT = """You are an HTML Scraper, a specialized agent for downloading HTML content from vehicle/build websites.

## Your Mission
Download HTML content for all URLs in urls.jsonl and save them to the html/ directory. Handle anti-bot protection, rate limits, and blocks gracefully.

## CRITICAL: NO TALKING
DO NOT: Ask questions to the user, offer options or choices.
**JUST DO THE WORK SILENTLY.**
Make decisions autonomously. Never wait for user input.

## Available Tools

You have specialized tools for HTML scraping:

1. **load_urls**: Load URLs from urls.jsonl
   - Input: output_dir, skip_scraped (bool)
   - Output: URL list with pending count

2. **fetch_html**: Fetch HTML from a URL
   - Input: url, method ('httpx' or 'camoufox'), timeout
   - Output: HTML content, status_code, is_blocked

3. **save_html**: Save HTML to file
   - Input: output_dir, filename, html, url
   - Output: File path confirmation

4. **update_progress**: Track scraping progress
   - Input: output_dir, url, filename, status ('success'/'failed'/'blocked'), error
   - Output: Progress record confirmation

5. **check_blocked**: Analyze if response is blocked
   - Input: html, status_code
   - Output: is_blocked, block_type, recommendation

6. **rotate_session**: Request new browser session
   - Input: reason
   - Output: New session ID, recommended delay

7. **get_scrape_stats**: Get current statistics
   - Input: output_dir
   - Output: success/failed/blocked counts, completion %

## Primary Method: Stealth Scraper Script

For production scraping, prefer the existing stealth scraper:
```bash
python3 scripts/tools/stealth_scraper.py --source {source_id} --limit 100
```

This provides:
- Anti-detection fingerprinting via BrowserForge
- Human-like cursor movement
- WebRTC blocking to prevent IP leaks
- Session rotation every 50 pages
- Randomized delays: 2-5 seconds

## Workflow

1. **Load URLs** - Call load_urls to get pending URLs from urls.jsonl
2. **Check stats** - Call get_scrape_stats to see current progress
3. **Choose method**:
   - Simple sites: Use fetch_html with method='httpx'
   - Anti-bot sites: Run stealth_scraper.py via Bash tool
4. **For each URL** (if using tools directly):
   - Add delay (2-5 seconds randomized)
   - Fetch HTML with fetch_html
   - Check for blocks with check_blocked
   - If not blocked: save_html, update_progress with 'success'
   - If blocked: update_progress with 'blocked', consider rotate_session
5. **Monitor blocks** - If 3+ blocks, stop and report

## Rate Limiting

- **MINIMUM 2 seconds** between requests
- **Recommended 2-5 seconds** randomized delays
- Rotate session every 50 pages OR after any block
- Clear cookies periodically (every 100 pages)

## Block Detection

HTTP codes indicating blocks:
- 403 Forbidden
- 429 Too Many Requests

HTML indicators:
- Cloudflare challenge page
- CAPTCHA/reCAPTCHA/hCaptcha
- "Access denied" messages
- "Please enable JavaScript" pages

## Handling Blocks

When blocked (403/429/Cloudflare):
1. STOP immediately - continuing will get IP banned
2. Update progress with status='blocked'
3. Call rotate_session
4. If 3+ blocks in session: Output HTML_SCRAPER_BLOCKED and stop

## Output Files

- `{output_dir}/html/*.html` - One file per URL (using filename from urls.jsonl)
- `{output_dir}/scrape_progress.jsonl` - Progress tracking (JSONL format)

Progress format:
```json
{"url": "https://...", "filename": "build.html", "status": "success", "timestamp": "2026-01-07T12:00:00Z"}
{"url": "https://...", "filename": "other.html", "status": "blocked", "error": "403", "timestamp": "..."}
```

## Stop Conditions

- **Success**: All URLs scraped -> output `HTML_SCRAPER_DONE`
- **Blocked**: Hit anti-bot protection -> output `HTML_SCRAPER_BLOCKED`

## Rules

1. Focus ONLY on HTML downloading - do not extract data
2. Save HTML files as you scrape them (incremental)
3. Resume from scrape_progress.jsonl if it exists
4. NEVER continue scraping after detecting blocks
5. Prefer stealth_scraper.py for anti-bot sites
6. Always respect rate limits: 2-5 second delays

When finished, output: HTML_SCRAPER_DONE or HTML_SCRAPER_BLOCKED"""

    # Tools this agent can use
    ALLOWED_TOOLS = [
        # Standard file/system tools
        "Read",
        "Write",
        "Glob",
        "Grep",
        "Bash",
        "WebFetch",
        # Custom HTML scraping MCP tools
        "mcp__html_tools__load_urls",
        "mcp__html_tools__fetch_html",
        "mcp__html_tools__save_html",
        "mcp__html_tools__update_progress",
        "mcp__html_tools__check_blocked",
        "mcp__html_tools__rotate_session",
        "mcp__html_tools__get_scrape_stats",
    ]

    @classmethod
    def as_definition(cls) -> AgentDefinition:
        """
        Return this agent as an AgentDefinition for use as a subagent.

        Usage:
            options = ClaudeAgentOptions(
                allowed_tools=["Task"],
                agents={"html-scraper": HTMLScraperAgent.as_definition()}
            )
        """
        if not SDK_AVAILABLE:
            raise ImportError("claude-agent-sdk not installed")

        return AgentDefinition(
            description=(
                "HTML Scraper agent for downloading web page content. "
                "Use this when you need to fetch HTML from discovered URLs. "
                "Handles anti-bot protection, rate limiting, and session rotation."
            ),
            prompt=cls.SYSTEM_PROMPT,
            tools=cls.ALLOWED_TOOLS,
            model="sonnet"  # Use Sonnet for cost-effective scraping
        )

    @classmethod
    def get_options(
        cls,
        output_dir: str,
        source_name: str,
        use_stealth: bool = False,
        **kwargs
    ) -> "ClaudeAgentOptions":
        """
        Get ClaudeAgentOptions configured for HTML scraping.

        Args:
            output_dir: Directory containing urls.jsonl and for html/ output
            source_name: Source identifier for metadata
            use_stealth: If True, prefer Camoufox stealth browser
            **kwargs: Additional options to pass to ClaudeAgentOptions
        """
        if not SDK_AVAILABLE:
            raise ImportError("claude-agent-sdk not installed")

        # Create the HTML tools MCP server
        html_tools_server = create_html_tools_server()

        # Customize system prompt based on options
        system_prompt = cls.SYSTEM_PROMPT
        if use_stealth:
            system_prompt += "\n\n## STEALTH MODE ENABLED\nAlways use Camoufox (method='camoufox') or stealth_scraper.py for fetching."

        return ClaudeAgentOptions(
            system_prompt=system_prompt,
            mcp_servers={"html_tools": html_tools_server},
            allowed_tools=cls.ALLOWED_TOOLS,
            cwd=Path.cwd(),
            max_turns=100,  # HTML scraping may need many turns for large URL lists
            model=kwargs.get("model", "claude-sonnet-4-5"),
            **{k: v for k, v in kwargs.items() if k != "model"}
        )


# ============================================================================
# Standalone Runner
# ============================================================================

async def run_html_scraper(
    output_dir: str,
    source_name: str,
    use_stealth: bool = False,
    limit: Optional[int] = None,
    verbose: bool = True,
    **kwargs
) -> dict[str, Any]:
    """
    Run the HTML Scraper agent to download HTML from discovered URLs.

    Args:
        output_dir: Directory containing urls.jsonl (from url-detective)
        source_name: Source identifier (e.g., "bring_a_trailer")
        use_stealth: If True, use Camoufox stealth browser
        limit: Optional limit on number of URLs to scrape
        verbose: Print progress messages
        **kwargs: Additional options for ClaudeAgentOptions

    Returns:
        dict with keys:
            - success: bool
            - status: 'complete', 'blocked', or 'error'
            - scraped_count: int
            - failed_count: int
            - blocked_count: int
            - html_dir: str path to html/ directory
            - cost_usd: float total cost
            - error: str if failed

    Example:
        result = await run_html_scraper(
            output_dir="data/bring_a_trailer",
            source_name="bring_a_trailer",
            use_stealth=True,
            limit=100
        )
        print(f"Scraped {result['scraped_count']} pages")
    """
    if not SDK_AVAILABLE:
        return {
            "success": False,
            "error": "claude-agent-sdk not installed. Run: pip install claude-agent-sdk"
        }

    # Verify urls.jsonl exists
    urls_file = Path(output_dir) / "urls.jsonl"
    if not urls_file.exists():
        return {
            "success": False,
            "error": f"URLs file not found: {urls_file}. Run url-detective first."
        }

    # Count total URLs
    with open(urls_file) as f:
        total_urls = sum(1 for line in f if line.strip())

    # Construct the task prompt
    limit_clause = f"\nLimit: Process only the first {limit} pending URLs." if limit else ""

    prompt = f"""Download HTML for all URLs in urls.jsonl:

Output Directory: {output_dir}
Source Name: {source_name}
Total URLs: {total_urls}{limit_clause}
Use Stealth: {use_stealth}

Steps:
1. Check current progress with get_scrape_stats
2. Load pending URLs with load_urls
3. For anti-bot sites, run: python3 scripts/tools/stealth_scraper.py --source {source_name}
4. For simple sites, use fetch_html with method='httpx'
5. Save each HTML file and update progress
6. Handle any blocks by stopping immediately

Report final statistics when complete."""

    options = HTMLScraperAgent.get_options(
        output_dir=output_dir,
        source_name=source_name,
        use_stealth=use_stealth,
        **kwargs
    )

    result = {
        "success": False,
        "status": "error",
        "scraped_count": 0,
        "failed_count": 0,
        "blocked_count": 0,
        "html_dir": str(Path(output_dir) / "html"),
        "cost_usd": 0.0,
        "error": None
    }

    try:
        async for message in query(prompt=prompt, options=options):
            # Handle assistant messages
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and verbose:
                        text = block.text
                        if "HTML_SCRAPER_DONE" in text:
                            result["success"] = True
                            result["status"] = "complete"
                        elif "HTML_SCRAPER_BLOCKED" in text:
                            result["status"] = "blocked"
                        # Print truncated response
                        if len(text) > 200:
                            print(f"[HTML Scraper] {text[:200]}...")
                        else:
                            print(f"[HTML Scraper] {text}")
                    elif isinstance(block, ToolUseBlock) and verbose:
                        print(f"[Tool] {block.name}")

            # Handle result message with cost info
            elif isinstance(message, ResultMessage):
                result["cost_usd"] = message.total_cost_usd or 0.0
                if verbose:
                    print(f"[Cost] ${result['cost_usd']:.4f}")

        # Read final statistics from progress file
        progress_file = Path(output_dir) / "scrape_progress.jsonl"
        if progress_file.exists():
            import json
            with open(progress_file) as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        status = record.get("status")
                        if status == "success":
                            result["scraped_count"] += 1
                        elif status == "failed":
                            result["failed_count"] += 1
                        elif status == "blocked":
                            result["blocked_count"] += 1

        # Determine success based on stats
        if result["status"] != "blocked":
            html_dir = Path(output_dir) / "html"
            if html_dir.exists():
                html_count = len(list(html_dir.glob("*.html")))
                if html_count > 0:
                    result["success"] = True
                    result["status"] = "complete"

    except Exception as e:
        result["error"] = str(e)

    return result


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    """CLI entry point for HTML Scraper."""
    import argparse

    parser = argparse.ArgumentParser(
        description="HTML Scraper: Download HTML content from discovered URLs"
    )
    parser.add_argument(
        "--output-dir", "-o",
        required=True,
        help="Output directory (must contain urls.jsonl)"
    )
    parser.add_argument(
        "--source-name", "-s",
        required=True,
        help="Source identifier"
    )
    parser.add_argument(
        "--stealth",
        action="store_true",
        help="Use Camoufox stealth browser for anti-bot sites"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        help="Limit number of URLs to scrape"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress output"
    )

    args = parser.parse_args()

    result = asyncio.run(run_html_scraper(
        output_dir=args.output_dir,
        source_name=args.source_name,
        use_stealth=args.stealth,
        limit=args.limit,
        verbose=not args.quiet
    ))

    if result["success"]:
        print(f"\nHTML Scraper Complete")
        print(f"  Status: {result['status']}")
        print(f"  Scraped: {result['scraped_count']}")
        print(f"  Failed: {result['failed_count']}")
        print(f"  Blocked: {result['blocked_count']}")
        print(f"  Output: {result['html_dir']}")
        print(f"  Cost: ${result['cost_usd']:.4f}")
    else:
        print(f"\nHTML Scraper Failed")
        print(f"  Status: {result['status']}")
        if result.get("error"):
            print(f"  Error: {result['error']}")
        if result["blocked_count"] > 0:
            print(f"  Blocked URLs: {result['blocked_count']}")
        exit(1)


if __name__ == "__main__":
    main()
