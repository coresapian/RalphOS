# 🤖 RalphOS

**An autonomous AI agent loop system for executing multi-step tasks without human intervention.**

RalphOS wraps Claude CLI in a bash loop, enabling fully autonomous execution of complex, multi-step projects. Define your tasks in a simple JSON file, and Ralph works through them one by one—reading files, writing code, scraping websites, analyzing data, committing changes, and learning from each iteration.

```
╔═══════════════════════════════════════════════════════════╗
║   ██████╗  █████╗ ██╗     ██████╗ ██╗  ██╗              ║
║   ██╔══██╗██╔══██╗██║     ██╔══██╗██║  ██║              ║
║   ██████╔╝███████║██║     ██████╔╝███████║              ║
║   ██╔══██╗██╔══██║██║     ██╔═══╝ ██╔══██║              ║
║   ██║  ██║██║  ██║███████╗██║     ██║  ██║              ║
║   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝              ║
║            🤖 Autonomous AI Agent Loop                  ║
╚═══════════════════════════════════════════════════════════╝
```

## 🚀 Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/RalphOS.git
cd RalphOS

# 2. Ensure Claude CLI is installed
claude --version

# 3. Define your task in scripts/ralph/prd.json

# 4. Run Ralph
./scripts/ralph/ralph.sh 25  # Run up to 25 iterations
```

## 📁 Project Structure

```
RalphOS/
├── scripts/ralph/
│   ├── ralph.sh          # Main loop script
│   ├── prompt.md         # Agent instructions
│   ├── prd.json          # Current project tasks
│   ├── progress.txt      # Learnings & patterns
│   ├── sources.json      # Queue of projects (optional)
│   └── archive/          # Completed project archives
├── scraped_builds/       # Output directory (example)
│   ├── source_a/
│   ├── source_b/
│   └── ...
└── README.md
```

## 🎯 How It Works

### The Loop

1. **Read** → Ralph reads `prd.json` to find pending tasks
2. **Execute** → Picks highest priority task with `passes: false`
3. **Implement** → Completes the task (writes code, fetches data, etc.)
4. **Commit** → Commits changes to git
5. **Update** → Marks task as `passes: true`
6. **Learn** → Appends learnings to `progress.txt`
7. **Repeat** → Loops until all tasks complete or max iterations

### Task Definition (prd.json)

```json
{
  "projectName": "My Awesome Project",
  "branchName": "main",
  "outputDir": "output/my_project",
  "userStories": [
    {
      "id": "US-001",
      "title": "Setup project structure",
      "acceptanceCriteria": [
        "Create output directory",
        "Initialize config file"
      ],
      "priority": 1,
      "passes": false,
      "notes": "First step"
    },
    {
      "id": "US-002",
      "title": "Fetch data from API",
      "acceptanceCriteria": [
        "Call API endpoint",
        "Save response to JSON",
        "Handle errors gracefully"
      ],
      "priority": 2,
      "passes": false,
      "notes": "Requires API key in .env"
    }
  ]
}
```

### Progress Tracking (progress.txt)

Ralph accumulates learnings across iterations:

```markdown
# Ralph Progress Log

## Codebase Patterns
- API calls need 1.5s delay for rate limiting
- JSON files should use ISO8601 timestamps
- Always check if directory exists before writing

---

## [2026-01-06] - US-001
- Created project structure
- Files: output/my_project/config.json
- **Learnings:**
  - Git doesn't track empty directories
  - Use .gitkeep for empty folders

---

## [2026-01-06] - US-002
- Fetched data from API
- Files: output/my_project/data.json
- **Learnings:**
  - API returns paginated results
  - Need to handle 429 rate limit errors
```

## 🔧 Configuration

### prompt.md

Customize agent behavior by editing `scripts/ralph/prompt.md`. This file contains:
- Task execution instructions
- Directory structure conventions
- Stop conditions
- Rules and constraints

### sources.json (Multi-Project Queue)

For processing multiple projects sequentially:

```json
{
  "sources": [
    {
      "id": "project_a",
      "name": "Project A",
      "url": "https://example.com/a",
      "outputDir": "output/project_a",
      "status": "completed"
    },
    {
      "id": "project_b",
      "name": "Project B", 
      "url": "https://example.com/b",
      "outputDir": "output/project_b",
      "status": "in_progress"
    },
    {
      "id": "project_c",
      "name": "Project C",
      "url": "https://example.com/c",
      "outputDir": "output/project_c",
      "status": "pending"
    }
  ]
}
```

## 📊 Terminal Output

Ralph provides rich terminal output:

```
╭─────────────────────── 📋 Project Status ───────────────────────╮
│  📁 Project:    My Awesome Project                              │
│  🌐 Target:     https://api.example.com                         │
│  📊 Progress:   2/4 stories complete                            │
│  ▶️  Next:       US-003: Process and analyze data                │
╰──────────────────────────────────────────────────────────────────╯

═══ Iteration 3 of 25 │ 5m 23s elapsed ═══════════════════

[15:32:01] ℹ Working on: US-003: Process and analyze data
[15:32:01] ℹ Progress: 2/4 stories
[15:32:01] ▶ Calling Claude CLI (streaming)...

────────────────────── Claude Output ──────────────────────
...
─────────────────────────────────────────────────────────────

[15:33:45] ✓ Iteration completed in 104s
[15:33:45] ℹ Updated progress: 3/4 stories
```

## 🗄️ Archiving

When a project completes, Ralph automatically archives:
- `prd.json` → `archive/{timestamp}_{project}_prd.json`
- `progress.txt` → `archive/{timestamp}_{project}_progress.txt`

## 🎮 Commands

```bash
# Run with 10 iterations (default)
./scripts/ralph/ralph.sh 10

# Run with 50 iterations
./scripts/ralph/ralph.sh 50

# View logs
cat ralph_output.log

# Check current status
cat scripts/ralph/prd.json | jq '.userStories[] | {id, title, passes}'
```

## 💡 Use Cases

RalphOS excels at:

- **Web Scraping** - Scrape multiple sources, handle pagination, save HTML
- **Data Collection** - Gather data from APIs, databases, files
- **Code Generation** - Generate boilerplate, migrations, tests
- **Research & Analysis** - Analyze documents, extract insights
- **Content Processing** - Transform, clean, and organize content
- **Automation** - Any multi-step task that can be broken into stories

## 📚 Examples

Check out the `examples/` directory for ready-to-use templates:

### [📈 Earnings Analysis](examples/earnings_analysis/)

Autonomously research and analyze quarterly earnings reports:
- Fetch earnings calendar and dates
- Collect historical EPS, revenue data
- Scrape earnings call transcripts
- Generate investment insights report

```bash
# Run the earnings analysis example
cp examples/earnings_analysis/*.json scripts/ralph/
cp examples/earnings_analysis/progress.txt scripts/ralph/
./scripts/ralph/ralph.sh 25
```

## 🔐 Requirements

- **Claude CLI** - Install via `npm install -g @anthropic-ai/claude-code`
- **jq** - For JSON parsing in bash
- **Git** - For version control and commits
- **Bash 4+** - For the loop script

## ⚠️ Important Notes

1. **Permissions**: Ralph runs with `--dangerously-skip-permissions` - only use in trusted environments
2. **Rate Limiting**: Add delays for API calls and web scraping
3. **Iterations**: Set max iterations appropriate for your task complexity
4. **Monitoring**: Watch the terminal output and `ralph_output.log` for progress

## 📄 License

MIT License - Use freely, modify as needed.

---

**Built for autonomous AI workflows.** 🤖

