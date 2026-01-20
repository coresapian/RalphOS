#!/usr/bin/env python3
"""
Example: Use URL Detective as a subagent within a parent agent.

This shows the Agent SDK pattern for defining subagents that the
parent agent can delegate to via the Task tool.

Prerequisites:
    pip install claude-agent-sdk>=0.1.19
    export ANTHROPIC_API_KEY=your_api_key

Usage:
    python src/agents/examples/use_as_subagent.py
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
from src.agents.tools.url_tools import create_url_tools_server


async def main():
    """
    Example: Orchestrator agent that delegates URL discovery to subagent.

    The parent agent has access to the Task tool which allows it to
    spawn subagents like url-detective for specialized work.
    """

    # Create URL tools MCP server (shared with subagent)
    url_tools_server = create_url_tools_server()

    # Configure parent agent with subagent definitions
    options = ClaudeAgentOptions(
        system_prompt="""You are a RalphOS orchestrator agent that manages
web scraping pipelines. You delegate specialized tasks to subagents:

- url-detective: Discovers URLs from websites (use for Stage 1)

When asked to scrape a source, first use the url-detective subagent
to discover all content URLs, then report the results.""",

        # Task tool is REQUIRED to invoke subagents
        allowed_tools=["Read", "Write", "Bash", "Task"],

        # MCP servers available to both parent and subagents
        mcp_servers={"url_tools": url_tools_server},

        # Define available subagents
        agents={
            "url-detective": URLDetectiveAgent.as_definition()
        },

        max_turns=20,
    )

    # Run the orchestrator with a task that requires the subagent
    prompt = """Discover all vehicle URLs from this test source:

Target: https://example.com/builds/
Output: data/test_source/
Source name: test_source

Use the url-detective subagent to handle the URL discovery."""

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
