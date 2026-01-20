# RalphOS Agent SDK Subagents

This directory contains Claude Agent SDK subagents that enhance RalphOS with AI-powered automation capabilities.

## Requirements

- Python 3.10 or higher
- Claude Agent SDK 0.1.19+
- Anthropic API key

## Installation

```bash
# Install the Agent SDK
pip install claude-agent-sdk>=0.1.19

# Or install all RalphOS requirements
pip install -r requirements.txt
```

## Environment Setup

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

Or create a `.env` file from the template:

```bash
cp .env.example .env
# Edit .env with your API key
```

## Available Agents

### URL Detective

A specialized agent for discovering vehicle/build URLs from automotive websites.

**Features:**
- Automatic URL pattern discovery
- Pagination detection (numeric, infinite scroll, load-more)
- URL extraction and normalization
- JSONL output format for the html-scraper stage

**Usage as standalone:**

```python
from src.agents.url_detective import run_url_detective

result = await run_url_detective(
    target_url="https://example.com/builds/gallery",
    output_dir="data/example_source",
    source_name="example_source"
)
print(f"Found {result['total_urls']} URLs")
```

**Usage as subagent:**

```python
from claude_agent_sdk import query, ClaudeAgentOptions
from src.agents.url_detective import URLDetectiveAgent

options = ClaudeAgentOptions(
    allowed_tools=["Task"],
    agents={"url-detective": URLDetectiveAgent.as_definition()}
)

async for message in query(prompt="Discover URLs from...", options=options):
    # Process messages
    pass
```

**CLI:**

```bash
python -m src.agents.url_detective \
    https://example.com/builds \
    --output-dir data/example \
    --source-name example
```

## Custom Tools

The agents use custom MCP tools defined in `tools/`:

| Tool | Description |
|------|-------------|
| `analyze_patterns` | Discover URL patterns from HTML |
| `detect_pagination` | Identify pagination type and total pages |
| `extract_urls` | Extract URLs matching a regex pattern |
| `normalize_urls` | Deduplicate and clean URL lists |
| `save_urls` | Save URLs to JSONL format |

## Examples

See `examples/` directory for complete usage examples:

- `run_url_detective.py` - Standalone agent usage
- `use_as_subagent.py` - Subagent delegation pattern

## Architecture

```
src/agents/
├── __init__.py           # Package exports
├── url_detective.py      # URL Detective agent
├── tools/
│   ├── __init__.py
│   └── url_tools.py      # Custom MCP tools
└── examples/
    ├── run_url_detective.py
    └── use_as_subagent.py
```

## Adding New Agents

To create a new agent:

1. Create `src/agents/new_agent.py` with an `AgentDefinition`
2. Define custom tools in `src/agents/tools/new_tools.py`
3. Export from `src/agents/__init__.py`
4. Add examples in `src/agents/examples/`

## Resources

- [Claude Agent SDK Documentation](https://docs.anthropic.com/en/api/agent-sdk/overview)
- [Python SDK Reference](https://docs.anthropic.com/en/api/agent-sdk/python)
- [Subagents Guide](https://docs.anthropic.com/en/api/agent-sdk/subagents)

Sources:
- [claude-agent-sdk on PyPI](https://pypi.org/project/claude-agent-sdk/)
- [GitHub: anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python)
