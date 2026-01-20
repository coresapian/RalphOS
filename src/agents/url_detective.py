"""
URL Detective Agent for RalphOS

A specialized Claude Agent SDK subagent that discovers vehicle/build URLs
from websites. Uses custom MCP tools for pattern analysis, pagination
detection, and URL extraction.

Usage:
 # As a standalone agent
 from src.agents.url_detective import run_url_detective
 await run_url_detective(
 target_url="https://example.com/builds",
 output_dir="data/example_source",
 source_name="example_source"
 )

 # As a subagent within a parent agent
 options = ClaudeAgentOptions(
 allowed_tools=["Read", "Glob", "Task"],
 agents={
 "url-detective": URLDetectiveAgent.as_definition()
 }
 )
"""

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator, Optional

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

from .tools.url_tools import create_url_tools_server


# ============================================================================
# URL Detective Agent Definition
# ============================================================================

class URLDetectiveAgent:
 """
 URL Detective: A specialized agent for discovering build/vehicle URLs.

 This agent uses custom MCP tools to:
 1. Analyze URL patterns on target websites
 2. Detect pagination structure (numeric, infinite scroll, load-more)
 3. Extract all URLs matching the build/vehicle pattern
 4. Save URLs in RalphOS JSONL format for the html-scraper stage
 """

 # Agent system prompt defining behavior and expertise
 SYSTEM_PROMPT = """You are a URL Detective, a specialized agent for discovering vehicle/build URLs from automotive websites.

## Your Mission
Find ALL individual vehicle/build page URLs on a target website. These could be:
- Auction listings (Bring a Trailer, Barrett-Jackson)
- Build threads (forums like GolfMK7, TacomaWorld)
- Project pages (build showcases, garage features)
- Inventory pages (dealer listings)

## Available Tools

You have specialized tools for URL discovery:

1. **analyze_patterns**: Analyze HTML to discover URL patterns
 - Input: HTML content and base URL
 - Output: Pattern candidates with frequency and examples

2. **detect_pagination**: Identify pagination type and estimate total pages
 - Input: HTML content and current URL
 - Output: Pagination type, total pages/items, next page URL

3. **extract_urls**: Extract URLs matching a regex pattern
 - Input: HTML, base URL, and regex pattern
 - Output: List of matching URLs

4. **normalize_urls**: Deduplicate and clean a URL list
 - Input: List of URLs
 - Output: Normalized, deduplicated URLs

5. **save_urls**: Save URLs to JSONL format for the scraper
 - Input: URLs, output directory, source name
 - Output: Confirmation with file paths

## Workflow

1. **Fetch the target page** - Use browser tools or HTTP to get HTML
2. **Analyze patterns** - Call analyze_patterns to identify build URL structure
3. **Detect pagination** - Call detect_pagination to understand page structure
4. **Extract URLs** - For each page, extract URLs matching the build pattern
5. **Handle all pages** - If paginated, iterate through all pages
6. **Normalize & save** - Dedupe and save to urls.jsonl

## Output Format

Save URLs as JSONL with this structure per line:
```json
{"url": "https://example.com/build/123", "filename": "build-123-a1b2c3d4.html"}
```

## Rules

- Focus ONLY on URL discovery - do not scrape HTML content
- Save incrementally to prevent data loss
- If blocked (403/429), stop and report
- Always deduplicate before saving
- Report total URL count when complete

When finished, output: URL_DETECTIVE_DONE"""

 # Tools this agent can use
 ALLOWED_TOOLS = [
 "Read",
 "Glob",
 "Grep",
 "Bash",
 "WebFetch",
 "mcp__url_tools__analyze_patterns",
 "mcp__url_tools__detect_pagination",
 "mcp__url_tools__extract_urls",
 "mcp__url_tools__normalize_urls",
 "mcp__url_tools__save_urls",
 ]

 @classmethod
 def as_definition(cls) -> AgentDefinition:
 """
 Return this agent as an AgentDefinition for use as a subagent.

 Usage:
 options = ClaudeAgentOptions(
 allowed_tools=["Task"],
 agents={"url-detective": URLDetectiveAgent.as_definition()}
 )
 """
 if not SDK_AVAILABLE:
 raise ImportError("claude-agent-sdk not installed")

 return AgentDefinition(
 description=(
 "URL Detective agent for discovering vehicle/build URLs. "
 "Use this when you need to find all content URLs from a website's "
 "gallery, listing, or archive pages. Handles pagination automatically."
 ),
 prompt=cls.SYSTEM_PROMPT,
 tools=cls.ALLOWED_TOOLS,
 model="sonnet" # Use Sonnet for cost-effective URL discovery
 )

 @classmethod
 def get_options(
 cls,
 target_url: str,
 output_dir: str,
 source_name: str,
 **kwargs
 ) -> "ClaudeAgentOptions":
 """
 Get ClaudeAgentOptions configured for URL discovery.

 Args:
 target_url: The starting URL to discover build URLs from
 output_dir: Directory to save urls.jsonl
 source_name: Source identifier for metadata
 **kwargs: Additional options to pass to ClaudeAgentOptions
 """
 if not SDK_AVAILABLE:
 raise ImportError("claude-agent-sdk not installed")

 # Create the URL tools MCP server
 url_tools_server = create_url_tools_server()

 return ClaudeAgentOptions(
 system_prompt=cls.SYSTEM_PROMPT,
 mcp_servers={"url_tools": url_tools_server},
 allowed_tools=cls.ALLOWED_TOOLS,
 cwd=Path.cwd(),
 max_turns=50, # URL discovery may need many turns for pagination
 model=kwargs.get("model", "claude-sonnet-4-5"),
 **{k: v for k, v in kwargs.items() if k != "model"}
 )


# ============================================================================
# Standalone Runner
# ============================================================================

async def run_url_detective(
 target_url: str,
 output_dir: str,
 source_name: str,
 verbose: bool = True,
 **kwargs
) -> dict[str, Any]:
 """
 Run the URL Detective agent to discover URLs from a target website.

 Args:
 target_url: Starting URL (gallery, listing, or archive page)
 output_dir: Directory to save urls.jsonl and urls_meta.json
 source_name: Source identifier (e.g., "bring_a_trailer")
 verbose: Print progress messages
 **kwargs: Additional options for ClaudeAgentOptions

 Returns:
 dict with keys:
 - success: bool
 - total_urls: int
 - urls_file: str path to urls.jsonl
 - meta_file: str path to urls_meta.json
 - cost_usd: float total cost
 - error: str if failed

 Example:
 result = await run_url_detective(
 target_url="https://bringatrailer.com/auctions/",
 output_dir="data/bring_a_trailer",
 source_name="bring_a_trailer"
 )
 print(f"Found {result['total_urls']} URLs")
 """
 if not SDK_AVAILABLE:
 return {
 "success": False,
 "error": "claude-agent-sdk not installed. Run: pip install claude-agent-sdk"
 }

 # Construct the task prompt
 prompt = f"""Discover all vehicle/build URLs from this website:

Target URL: {target_url}
Output Directory: {output_dir}
Source Name: {source_name}

Steps:
1. Fetch the target URL and analyze the HTML
2. Use analyze_patterns to identify the build/vehicle URL pattern
3. Use detect_pagination to understand how content is paginated
4. Extract all matching URLs from all pages
5. Normalize and deduplicate the URLs
6. Save to {output_dir}/urls.jsonl using save_urls

Report the total number of URLs found when complete."""

 options = URLDetectiveAgent.get_options(
 target_url=target_url,
 output_dir=output_dir,
 source_name=source_name,
 **kwargs
 )

 result = {
 "success": False,
 "total_urls": 0,
 "urls_file": None,
 "meta_file": None,
 "cost_usd": 0.0,
 "error": None
 }

 try:
 async for message in query(prompt=prompt, options=options):
 # Handle assistant messages
 if isinstance(message, AssistantMessage):
 for block in message.content:
 if isinstance(block, TextBlock) and verbose:
 # Print Claude's responses
 text = block.text
 if "URL_DETECTIVE_DONE" in text:
 result["success"] = True
 print(f"[URL Detective] {text[:200]}...")
 elif isinstance(block, ToolUseBlock) and verbose:
 print(f"[Tool] {block.name}")

 # Handle result message with cost info
 elif isinstance(message, ResultMessage):
 result["cost_usd"] = message.total_cost_usd or 0.0
 if verbose:
 print(f"[Cost] ${result['cost_usd']:.4f}")

 # Check if URLs were saved
 urls_file = Path(output_dir) / "urls.jsonl"
 meta_file = Path(output_dir) / "urls_meta.json"

 if urls_file.exists():
 result["urls_file"] = str(urls_file)
 # Count URLs
 with open(urls_file) as f:
 result["total_urls"] = sum(1 for _ in f)
 result["success"] = True

 if meta_file.exists():
 result["meta_file"] = str(meta_file)

 except Exception as e:
 result["error"] = str(e)

 return result


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
 """CLI entry point for URL Detective."""
 import argparse

 parser = argparse.ArgumentParser(
 description="URL Detective: Discover vehicle/build URLs from websites"
 )
 parser.add_argument("target_url", help="Starting URL to discover from")
 parser.add_argument("--output-dir", "-o", required=True, help="Output directory")
 parser.add_argument("--source-name", "-s", required=True, help="Source identifier")
 parser.add_argument("--quiet", "-q", action="store_true", help="Suppress output")

 args = parser.parse_args()

 result = asyncio.run(run_url_detective(
 target_url=args.target_url,
 output_dir=args.output_dir,
 source_name=args.source_name,
 verbose=not args.quiet
 ))

 if result["success"]:
 print(f"\n Found {result['total_urls']} URLs")
 print(f" Saved to: {result['urls_file']}")
 print(f" Cost: ${result['cost_usd']:.4f}")
 else:
 print(f"\n Failed: {result.get('error', 'Unknown error')}")
 exit(1)


if __name__ == "__main__":
 main()
