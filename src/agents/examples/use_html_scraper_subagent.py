#!/usr/bin/env python3
"""
Example: Use HTML Scraper as a subagent within a parent agent.

This shows the Agent SDK pattern for using HTML Scraper with URL Detective
in a pipeline - first discover URLs, then scrape HTML.

Prerequisites:
    pip install claude-agent-sdk>=0.1.19
    pip install camoufox[geoip]
    python3 -m camoufox fetch
    export ANTHROPIC_API_KEY=your_api_key

Usage:
    python src/agents/examples/use_html_scraper_subagent.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
)
from src.agents.url_detective import URLDetectiveAgent
from src.agents.html_scraper import HTMLScraperAgent
from src.agents.tools.url_tools import create_url_tools_server
from src.agents.tools.html_tools import create_html_tools_server


async def main():
    """
    Example: Orchestrator agent that runs a full scraping pipeline.

    The parent agent has access to the Task tool which allows it to
    spawn subagents for specialized work:
    - url-detective: Discovers URLs from websites (Stage 1)
    - html-scraper: Downloads HTML content (Stage 2)
    """

    # Create MCP servers for subagents
    url_tools_server = create_url_tools_server()
    html_tools_server = create_html_tools_server()

    # Configure parent agent with both subagent definitions
    options = ClaudeAgentOptions(
        system_prompt="""You are a RalphOS orchestrator agent that manages
web scraping pipelines. You delegate specialized tasks to subagents:

- url-detective: Discovers URLs from websites (use for Stage 1)
- html-scraper: Downloads HTML content using Camoufox stealth browser (use for Stage 2)

When asked to scrape a source:
1. First use the url-detective subagent to discover all content URLs
2. Then use the html-scraper subagent to download HTML for those URLs
3. Report the results from both stages

Always complete Stage 1 before starting Stage 2.""",

        # Task tool is REQUIRED to invoke subagents
        allowed_tools=["Read", "Write", "Bash", "Task"],

        # MCP servers available to both parent and subagents
        mcp_servers={
            "url_tools": url_tools_server,
            "html_tools": html_tools_server,
        },

        # Define available subagents
        agents={
            "url-detective": URLDetectiveAgent.as_definition(),
            "html-scraper": HTMLScraperAgent.as_definition(),
        },

        max_turns=30,
    )

    # Run the orchestrator with a task that requires both subagents
    prompt = """Run a complete scraping pipeline for this test source:

Target URL: https://example.com/builds/
Output Directory: data/test_source/
Source Name: test_source
Limit: 5 URLs (for testing)

Pipeline:
1. Stage 1: Use url-detective to discover all build/vehicle URLs
2. Stage 2: Use html-scraper to download HTML for the discovered URLs

Report results from both stages when complete."""

    print("Starting orchestrator agent...")
    print("-" * 50)

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"[Orchestrator] {block.text}")

        elif isinstance(message, ResultMessage):
            print("-" * 50)
            print(f"Total cost: ${message.total_cost_usd:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
