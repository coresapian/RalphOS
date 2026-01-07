#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# RALPH PARALLEL - Run multiple Ralph workers simultaneously
# ═══════════════════════════════════════════════════════════════

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SOURCES_FILE="$SCRIPT_DIR/sources.json"
WORKERS_DIR="$SCRIPT_DIR/workers"
START_TIME=$(date +%s)

# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

timestamp() {
  date "+%H:%M:%S"
}

log_info() {
  echo -e "${CYAN}[$(timestamp)]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[$(timestamp)] ✓${NC} $1"
}

log_action() {
  echo -e "${MAGENTA}[$(timestamp)] ▶${NC} $1"
}

log_warning() {
  echo -e "${YELLOW}[$(timestamp)] ⚠${NC} $1"
}

elapsed_time() {
  local elapsed=$(($(date +%s) - START_TIME))
  local mins=$((elapsed / 60))
  local secs=$((elapsed % 60))
  echo "${mins}m ${secs}s"
}

get_pending_sources() {
  jq -r '.sources[] | select(.status == "pending") | .id' "$SOURCES_FILE" 2>/dev/null
}

get_source_name() {
  local source_id=$1
  jq -r --arg id "$source_id" '.sources[] | select(.id == $id) | .name' "$SOURCES_FILE" 2>/dev/null
}

get_source_url() {
  local source_id=$1
  jq -r --arg id "$source_id" '.sources[] | select(.id == $id) | .url' "$SOURCES_FILE" 2>/dev/null
}

get_source_output_dir() {
  local source_id=$1
  jq -r --arg id "$source_id" '.sources[] | select(.id == $id) | .outputDir' "$SOURCES_FILE" 2>/dev/null
}

lock_source() {
  local source_id=$1
  local temp_file=$(mktemp)
  jq --arg id "$source_id" '(.sources[] | select(.id == $id) | .status) = "in_progress"' "$SOURCES_FILE" > "$temp_file"
  mv "$temp_file" "$SOURCES_FILE"
}

# Create worker-specific PRD for a source
create_worker_prd() {
  local source_id=$1
  local worker_dir="$WORKERS_DIR/$source_id"
  local prd_file="$worker_dir/prd.json"
  
  mkdir -p "$worker_dir"
  
  local name=$(get_source_name "$source_id")
  local url=$(get_source_url "$source_id")
  local output_dir=$(get_source_output_dir "$source_id")
  
  cat > "$prd_file" << EOF
{
  "projectName": "$name Scraper",
  "branchName": "main",
  "targetUrl": "$url",
  "outputDir": "$output_dir",
  "sourceId": "$source_id",
  "userStories": [
    {
      "id": "US-001",
      "title": "Create directory structure",
      "acceptanceCriteria": [
        "Create $output_dir directory",
        "Create $output_dir/urls.json with empty structure",
        "Create $output_dir/html subdirectory"
      ],
      "priority": 1,
      "passes": false
    },
    {
      "id": "US-002",
      "title": "Discover all vehicle/build URLs",
      "acceptanceCriteria": [
        "Analyze site structure and pagination",
        "Find total expected URLs if possible",
        "Scrape all vehicle/build page URLs",
        "Save to urls.json with totalCount"
      ],
      "priority": 2,
      "passes": false
    },
    {
      "id": "US-003",
      "title": "Scrape HTML for all URLs",
      "acceptanceCriteria": [
        "Create scraping script with retry logic",
        "Download HTML for each URL",
        "Track progress in scrape_progress.json",
        "Handle rate limiting (1-2s delays)"
      ],
      "priority": 3,
      "passes": false
    },
    {
      "id": "US-004",
      "title": "Verify completion and update sources",
      "acceptanceCriteria": [
        "Verify all URLs have been scraped",
        "Update sources.json pipeline counts",
        "Create manifest.json with metadata"
      ],
      "priority": 4,
      "passes": false
    }
  ]
}
EOF

  # Create worker-specific prompt that references the worker PRD
  cat > "$worker_dir/prompt.md" << 'PROMPT_EOF'
# Ralph Worker Instructions

You are Ralph, an autonomous worker scraping a specific source.

## Your Workspace

Your PRD is at: `WORKER_PRD_PATH`
Your source ID is: `WORKER_SOURCE_ID`

## Task

1. Read your PRD file at the path above
2. Read `scripts/ralph/progress.txt` for patterns
3. Pick the highest priority story where `passes: false`
4. Implement that ONE story completely
5. Commit changes: `feat: [WORKER_SOURCE_ID] [ID] - [Title]`
6. Update your PRD: set `passes: true`
7. Update `scripts/ralph/sources.json` pipeline counts for your source

## Directory Structure

Save all data to the `outputDir` specified in your PRD:
```
{outputDir}/
├── urls.json           # Discovered URLs
├── html/               # Downloaded HTML files  
├── scrape_progress.json # Progress tracking
└── manifest.json       # Final metadata
```

## Pipeline Fields to Update

After each story, update your source in sources.json:
```json
{
  "pipeline": {
    "expectedUrls": <total if known>,
    "urlsFound": <count from urls.json>,
    "htmlScraped": <count of html files>,
    "builds": null,
    "mods": null
  }
}
```

## Stop Condition

When ALL stories have `passes: true`, output:
```
RALPH_DONE
```

## Rules

1. Complete ONE story per iteration
2. Always commit after implementation
3. Update your PRD to mark stories complete
4. Update sources.json pipeline counts
5. Rate limit: 1-2 second delays between requests
6. Don't ask questions - make decisions and proceed
7. Reuse existing scraping patterns from progress.txt

PROMPT_EOF

  # Replace placeholders
  sed -i '' "s|WORKER_PRD_PATH|$prd_file|g" "$worker_dir/prompt.md"
  sed -i '' "s|WORKER_SOURCE_ID|$source_id|g" "$worker_dir/prompt.md"
  
  echo "$worker_dir"
}

run_worker() {
  local source_id=$1
  local iterations=$2
  local worker_dir="$WORKERS_DIR/$source_id"
  local log_file="$worker_dir/output.log"
  
  echo "" >> "$log_file"
  echo "═══════════════════════════════════════════════════════════════" >> "$log_file"
  echo "Worker started at $(date)" >> "$log_file"
  echo "═══════════════════════════════════════════════════════════════" >> "$log_file"
  
  cd "$PROJECT_ROOT"
  
  for ((i=1; i<=iterations; i++)); do
    echo "" >> "$log_file"
    echo "--- Iteration $i of $iterations ---" >> "$log_file"
    
    # Run Claude with worker-specific prompt
    cat "$worker_dir/prompt.md" | claude --print --dangerously-skip-permissions 2>&1 >> "$log_file"
    
    # Check for completion
    if grep -q "RALPH_DONE" "$log_file" 2>/dev/null; then
      echo "Worker completed at $(date)" >> "$log_file"
      break
    fi
    
    sleep 2
  done
}

# ═══════════════════════════════════════════════════════════════
# Usage
# ═══════════════════════════════════════════════════════════════

usage() {
  echo -e "${WHITE}${BOLD}RALPH PARALLEL${NC} - Run multiple workers simultaneously"
  echo ""
  echo -e "${YELLOW}Usage:${NC}"
  echo "  $0 <workers> <iterations_per_worker>"
  echo ""
  echo -e "${YELLOW}Examples:${NC}"
  echo "  $0 3 10    # Run 3 workers, 10 iterations each"
  echo "  $0 5 25    # Run 5 workers, 25 iterations each"
  echo ""
  echo -e "${YELLOW}Commands:${NC}"
  echo "  $0 status  # Show worker status"
  echo "  $0 logs    # Tail all worker logs"
  echo "  $0 stop    # Stop all workers"
  exit 1
}

if [ -z "$1" ]; then
  usage
fi

# ═══════════════════════════════════════════════════════════════
# Commands
# ═══════════════════════════════════════════════════════════════

if [ "$1" == "status" ]; then
  echo ""
  echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
  echo -e "${CYAN}║${NC}              ${WHITE}${BOLD}RALPH PARALLEL STATUS${NC}                       ${CYAN}║${NC}"
  echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
  echo ""
  
  if [ -d "$WORKERS_DIR" ]; then
    for worker_dir in "$WORKERS_DIR"/*/; do
      if [ -d "$worker_dir" ]; then
        source_id=$(basename "$worker_dir")
        log_file="$worker_dir/output.log"
        prd_file="$worker_dir/prd.json"
        
        # Get status
        if [ -f "$prd_file" ]; then
          completed=$(jq '[.userStories[] | select(.passes == true)] | length' "$prd_file" 2>/dev/null || echo "0")
          total=$(jq '.userStories | length' "$prd_file" 2>/dev/null || echo "0")
        else
          completed=0
          total=0
        fi
        
        # Check if done
        if [ -f "$log_file" ] && grep -q "RALPH_DONE" "$log_file" 2>/dev/null; then
          status="${GREEN}✓ Complete${NC}"
        elif pgrep -f "workers/$source_id/prompt.md" > /dev/null 2>&1; then
          status="${YELLOW}⟳ Running${NC}"
        else
          status="${DIM}○ Stopped${NC}"
        fi
        
        printf "  ${WHITE}%-25s${NC} ${status}  ${GREEN}%d${NC}/${CYAN}%d${NC} stories\n" "$source_id" "$completed" "$total"
      fi
    done
  else
    echo -e "  ${DIM}No workers found${NC}"
  fi
  echo ""
  exit 0
fi

if [ "$1" == "logs" ]; then
  if [ -d "$WORKERS_DIR" ]; then
    tail -f "$WORKERS_DIR"/*/output.log
  else
    echo "No worker logs found"
  fi
  exit 0
fi

if [ "$1" == "stop" ]; then
  log_warning "Stopping all Ralph workers..."
  pkill -f "workers/.*/prompt.md" 2>/dev/null || true
  log_success "All workers stopped"
  exit 0
fi

# ═══════════════════════════════════════════════════════════════
# Main - Start Workers
# ═══════════════════════════════════════════════════════════════

if [ -z "$2" ]; then
  usage
fi

NUM_WORKERS=$1
ITERATIONS=$2

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}                                                           ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${WHITE}${BOLD}██████╗  █████╗ ██╗     ██████╗ ██╗  ██╗${NC}            ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${WHITE}${BOLD}██╔══██╗██╔══██╗██║     ██╔══██╗██║  ██║${NC}             ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${WHITE}${BOLD}██████╔╝███████║██║     ██████╔╝███████║${NC}              ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${WHITE}${BOLD}██╔══██╗██╔══██║██║     ██╔═══╝ ██╔══██║${NC}              ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${WHITE}${BOLD}██║  ██║██║  ██║███████╗██║     ██║  ██║${NC}              ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${WHITE}${BOLD}╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝${NC}              ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}                                                           ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}              ${YELLOW}🤖 PARALLEL MODE${NC}                            ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}                                                           ${CYAN}║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get pending sources
PENDING_SOURCES=($(get_pending_sources))
TOTAL_PENDING=${#PENDING_SOURCES[@]}

if [ $TOTAL_PENDING -eq 0 ]; then
  log_warning "No pending sources found!"
  exit 1
fi

# Limit workers to available sources
if [ $NUM_WORKERS -gt $TOTAL_PENDING ]; then
  NUM_WORKERS=$TOTAL_PENDING
  log_info "Limiting to ${CYAN}$NUM_WORKERS${NC} workers (only $TOTAL_PENDING pending sources)"
fi

log_info "Starting ${CYAN}$NUM_WORKERS${NC} parallel workers"
log_info "Each worker gets ${CYAN}$ITERATIONS${NC} iterations"
log_info "Total pending sources: ${CYAN}$TOTAL_PENDING${NC}"
echo ""

mkdir -p "$WORKERS_DIR"

# Start workers
WORKER_PIDS=()
for ((w=0; w<NUM_WORKERS; w++)); do
  source_id="${PENDING_SOURCES[$w]}"
  source_name=$(get_source_name "$source_id")
  
  log_action "Worker $((w+1)): ${WHITE}$source_name${NC} (${DIM}$source_id${NC})"
  
  # Lock the source
  lock_source "$source_id"
  
  # Create worker workspace
  worker_dir=$(create_worker_prd "$source_id")
  
  # Start worker in background
  run_worker "$source_id" "$ITERATIONS" &
  WORKER_PIDS+=($!)
  
  # Small delay between starts to avoid race conditions
  sleep 1
done

echo ""
log_success "All workers started!"
echo ""
echo -e "${BLUE}╭────────────────────────────────────────────────────────────╮${NC}"
echo -e "${BLUE}│${NC}  ${WHITE}${BOLD}Monitor Commands:${NC}                                        ${BLUE}│${NC}"
echo -e "${BLUE}│${NC}                                                            ${BLUE}│${NC}"
echo -e "${BLUE}│${NC}  ${CYAN}$0 status${NC}     Show worker progress             ${BLUE}│${NC}"
echo -e "${BLUE}│${NC}  ${CYAN}$0 logs${NC}       Tail all worker logs             ${BLUE}│${NC}"
echo -e "${BLUE}│${NC}  ${CYAN}$0 stop${NC}       Stop all workers                 ${BLUE}│${NC}"
echo -e "${BLUE}│${NC}                                                            ${BLUE}│${NC}"
echo -e "${BLUE}│${NC}  ${DIM}Logs: $WORKERS_DIR/<source>/output.log${NC}     ${BLUE}│${NC}"
echo -e "${BLUE}╰────────────────────────────────────────────────────────────╯${NC}"
echo ""

# Wait for all workers
log_info "Waiting for workers to complete..."
for pid in "${WORKER_PIDS[@]}"; do
  wait $pid 2>/dev/null || true
done

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}                                                           ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}              ${WHITE}${BOLD}✅ All Workers Complete!${NC}                    ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}                                                           ${GREEN}║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}╭──────────────────── 📈 Session Summary ────────────────────╮${NC}"
printf "${BLUE}│${NC}  ⏱️  Duration          ${CYAN}%-34s${NC} ${BLUE}│${NC}\n" "$(elapsed_time)"
printf "${BLUE}│${NC}  👷 Workers            ${YELLOW}%-34s${NC} ${BLUE}│${NC}\n" "$NUM_WORKERS"
printf "${BLUE}│${NC}  🔄 Iterations/Worker  ${YELLOW}%-34s${NC} ${BLUE}│${NC}\n" "$ITERATIONS"
echo -e "${BLUE}╰────────────────────────────────────────────────────────────╯${NC}"
echo ""

# Show final status
$0 status


