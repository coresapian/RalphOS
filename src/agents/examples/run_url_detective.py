#!/usr/bin/env python3
"""
Example: Run the URL Detective agent standalone.

This example shows how to use the URL Detective to discover
vehicle/build URLs from a website.

Prerequisites:
    pip install claude-agent-sdk>=0.1.19
    export ANTHROPIC_API_KEY=your_api_key

Usage:
    python src/agents/examples/run_url_detective.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.agents.url_detective import run_url_detective


async def main():
    """Example: Discover URLs from a sample source."""

    # Example: Discover URLs from a builds gallery
    # Replace with your actual target URL
    result = await run_url_detective(
        target_url="https://example.com/builds/gallery",
        output_dir="data/example_source",
        source_name="example_source",
        verbose=True
    )

    if result["success"]:
        print("\n" + "=" * 50)
        print("URL Discovery Complete!")
        print("=" * 50)
        print(f"Total URLs found: {result['total_urls']}")
        print(f"URLs file: {result['urls_file']}")
        print(f"Meta file: {result['meta_file']}")
        print(f"Total cost: ${result['cost_usd']:.4f}")
    else:
        print(f"\nError: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
