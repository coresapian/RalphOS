#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# RALPH - Autonomous AI Agent Loop
# ═══════════════════════════════════════════════════════════════

# Track child processes for cleanup
CHILD_PIDS=()
TIMER_PID=""

# Cleanup function - kills all child processes
cleanup() {
  echo ""
  echo -e "\033[1;31m⚠️  Ctrl+C received - shutting down Ralph...\033[0m"
  
  # Kill the timer process if running
  if [ -n "$TIMER_PID" ] && kill -0 "$TIMER_PID" 2>/dev/null; then
    kill "$TIMER_PID" 2>/dev/null || true
  fi
  
  # Kill any child processes
  for pid in "${CHILD_PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  
  # Kill any remaining background jobs
  jobs -p | xargs -r kill 2>/dev/null || true
  
  echo -e "\033[1;32m✓ Ralph stopped cleanly\033[0m"
  exit 130
}

# Set up signal traps - ensure Ctrl+C kills everything
trap cleanup SIGINT SIGTERM SIGHUP

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
NC='\033[0m' # No Color

# Feature flags
SCRAPE_ONLY=false
VERBOSE=false

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
START_TIME=$(date +%s)
LOG_FILE="$PROJECT_ROOT/logs/ralph_output.log"
PRD_FILE="$SCRIPT_DIR/prd.json"
PROGRESS_FILE="$SCRIPT_DIR/progress.txt"
SOURCES_FILE="$SCRIPT_DIR/sources.json"

# Track sources completed in this session
SOURCES_COMPLETED=0

# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

elapsed_time() {
  local elapsed=$(($(date +%s) - START_TIME))
  local mins=$((elapsed / 60))
  local secs=$((elapsed % 60))
  echo "${mins}m ${secs}s"
}

timestamp() {
  date "+%H:%M:%S"
}

log_status() {
  echo -e "${DIM}[$(timestamp)]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[$(timestamp)] ✓${NC} $1"
}

log_info() {
  echo -e "${CYAN}[$(timestamp)] ℹ${NC} $1"
}

log_warning() {
  echo -e "${YELLOW}[$(timestamp)] ⚠${NC} $1"
}

log_action() {
  echo -e "${MAGENTA}[$(timestamp)] ▶${NC} $1"
}

get_project_info() {
  if [ -f "$PRD_FILE" ]; then
    PROJECT_NAME=$(jq -r '.projectName // "Unknown"' "$PRD_FILE" 2>/dev/null)
    TARGET_URL=$(jq -r '.targetUrl // "Unknown"' "$PRD_FILE" 2>/dev/null)
    OUTPUT_DIR=$(jq -r '.outputDir // "Unknown"' "$PRD_FILE" 2>/dev/null)
    PIPELINE_STAGE=$(jq -r '.pipelineStage // "unknown"' "$PRD_FILE" 2>/dev/null)
    TOTAL_STORIES=$(jq '.userStories | length' "$PRD_FILE" 2>/dev/null)
    COMPLETED_STORIES=$(jq '[.userStories[] | select(.passes == true)] | length' "$PRD_FILE" 2>/dev/null)
    NEXT_STORY=$(jq -r '[.userStories[] | select(.passes == false)] | sort_by(.priority) | .[0] | "\(.id): \(.title)"' "$PRD_FILE" 2>/dev/null)
    
    # Get source ID from output dir
    SOURCE_ID=$(basename "$OUTPUT_DIR" 2>/dev/null)
    
    # Get pipeline counts from sources.json
    if [ -f "$SOURCES_FILE" ] && [ -n "$SOURCE_ID" ]; then
      URLS_FOUND=$(jq -r ".sources[] | select(.outputDir | endswith(\"$SOURCE_ID\")) | .pipeline.urlsFound // 0" "$SOURCES_FILE" 2>/dev/null)
      HTML_SCRAPED=$(jq -r ".sources[] | select(.outputDir | endswith(\"$SOURCE_ID\")) | .pipeline.htmlScraped // 0" "$SOURCES_FILE" 2>/dev/null)
      BUILDS_COUNT=$(jq -r ".sources[] | select(.outputDir | endswith(\"$SOURCE_ID\")) | .pipeline.builds // \"null\"" "$SOURCES_FILE" 2>/dev/null)
      MODS_COUNT=$(jq -r ".sources[] | select(.outputDir | endswith(\"$SOURCE_ID\")) | .pipeline.mods // \"null\"" "$SOURCES_FILE" 2>/dev/null)
    fi
    
    # Determine current stage name
    if [ "$NEXT_STORY" == "null: null" ]; then
      # In scrape-only mode, skip extraction stages
      if [ "$SCRAPE_ONLY" = true ]; then
        if [ "$HTML_SCRAPED" != "null" ] && [ "$URLS_FOUND" != "null" ] && [ "$HTML_SCRAPED" -ge "$URLS_FOUND" ] 2>/dev/null; then
          STAGE_NAME="✓ Scrape complete → pick next source"
        else
          STAGE_NAME="Stage 2: HTML Scraping"
        fi
      # Check if builds need extraction (null or 0)
      elif [ "$BUILDS_COUNT" == "null" ] || [ "$BUILDS_COUNT" == "0" ] || [ -z "$BUILDS_COUNT" ]; then
        STAGE_NAME="Stage 3: Build Extraction"
      # Check if mods need extraction (null or 0)  
      elif [ "$MODS_COUNT" == "null" ] || [ "$MODS_COUNT" == "0" ] || [ -z "$MODS_COUNT" ]; then
        STAGE_NAME="Stage 4: Mod Extraction"
      else
        STAGE_NAME="✓ All stages complete → pick next source"
      fi
      NEXT_STORY="PRD complete → $STAGE_NAME"
    fi
  fi
}

get_stage_emoji() {
  case $1 in
    1) echo "🔍" ;;  # URL Discovery
    2) echo "📥" ;;  # HTML Scraping
    3) echo "🏗️" ;;   # Build Extraction
    4) echo "🔧" ;;  # Mod Extraction
    *) echo "📋" ;;
  esac
}

print_project_status() {
  get_project_info
  echo ""
  echo -e "${BLUE}╭─────────────────────── 📋 Project Status ───────────────────────╮${NC}"
  printf "${BLUE}│${NC}  📁 Project:    ${WHITE}%-44s${NC} ${BLUE}│${NC}\n" "$PROJECT_NAME"
  printf "${BLUE}│${NC}  🌐 Target:     ${DIM}%-44s${NC} ${BLUE}│${NC}\n" "${TARGET_URL:0:44}"
  printf "${BLUE}│${NC}  📊 Stories:    ${GREEN}$COMPLETED_STORIES${NC}/${CYAN}$TOTAL_STORIES${NC} complete                                 ${BLUE}│${NC}\n"
  echo -e "${BLUE}│${NC}  ────────────────────────────────────────────────────────────── ${BLUE}│${NC}"
  printf "${BLUE}│${NC}  🔍 URLs:       ${CYAN}%-10s${NC}  📥 HTML: ${CYAN}%-10s${NC}                  ${BLUE}│${NC}\n" "${URLS_FOUND:-0}" "${HTML_SCRAPED:-0}"
  printf "${BLUE}│${NC}  🏗️  Builds:     ${CYAN}%-10s${NC}  🔧 Mods: ${CYAN}%-10s${NC}                  ${BLUE}│${NC}\n" "${BUILDS_COUNT:-null}" "${MODS_COUNT:-null}"
  echo -e "${BLUE}│${NC}  ────────────────────────────────────────────────────────────── ${BLUE}│${NC}"
  printf "${BLUE}│${NC}  ▶️  Next:       ${YELLOW}%-44s${NC} ${BLUE}│${NC}\n" "${NEXT_STORY:0:44}"
  echo -e "${BLUE}╰──────────────────────────────────────────────────────────────────╯${NC}"
}

count_pending_sources() {
  if [ -f "$SOURCES_FILE" ]; then
    jq '[.sources[] | select(.status == "pending")] | length' "$SOURCES_FILE" 2>/dev/null
  else
    echo "0"
  fi
}

count_blocked_sources() {
  if [ -f "$SOURCES_FILE" ]; then
    jq '[.sources[] | select(.status == "blocked")] | length' "$SOURCES_FILE" 2>/dev/null
  else
    echo "0"
  fi
}

count_sources_needing_work() {
  if [ -f "$SOURCES_FILE" ]; then
    # Count sources that need work: pending, in_progress, blocked, or incomplete pipeline
    jq '[.sources[] | select(
      .status == "pending" or 
      .status == "in_progress" or
      .status == "blocked" or
      .pipeline.urlsFound == null or
      (.pipeline.urlsFound != null and .pipeline.htmlScraped == null) or
      (.pipeline.urlsFound != null and .pipeline.htmlScraped != null and .pipeline.htmlScraped < .pipeline.urlsFound) or
      (.pipeline.htmlScraped != null and .pipeline.builds == null)
    )] | length' "$SOURCES_FILE" 2>/dev/null
  else
    echo "0"
  fi
}

get_next_source() {
  if [ -f "$SOURCES_FILE" ]; then
    # First check for in_progress sources
    IN_PROGRESS=$(jq -r '[.sources[] | select(.status == "in_progress")] | .[0] | .name // empty' "$SOURCES_FILE" 2>/dev/null)
    if [ -n "$IN_PROGRESS" ]; then
      echo "$IN_PROGRESS"
      return
    fi
    # Then check for pending sources
    jq -r '[.sources[] | select(.status == "pending")] | .[0] | .name // empty' "$SOURCES_FILE" 2>/dev/null
  fi
}

archive_completed_project() {
  ARCHIVE_DIR="$SCRIPT_DIR/archive"
  mkdir -p "$ARCHIVE_DIR"
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  PROJECT_SLUG=$(echo "$PROJECT_NAME" | tr ' ' '_' | tr -cd '[:alnum:]_-')
  ARCHIVE_NAME="${TIMESTAMP}_${PROJECT_SLUG}"
  
  log_action "Archiving completed project..."
  cp "$SCRIPT_DIR/prd.json" "$ARCHIVE_DIR/${ARCHIVE_NAME}_prd.json"
  log_success "Archived to: ${DIM}$ARCHIVE_DIR/${ARCHIVE_NAME}_prd.json${NC}"
  
  SOURCES_COMPLETED=$((SOURCES_COMPLETED + 1))
}

# ═══════════════════════════════════════════════════════════════
# Usage
# ═══════════════════════════════════════════════════════════════

show_usage() {
  echo ""
  echo -e "${WHITE}${BOLD}Ralph - Autonomous AI Agent Loop${NC}"
  echo ""
  echo -e "${WHITE}Usage:${NC}"
  echo -e "  $0 <iterations>                    ${DIM}# Classic mode - run N iterations${NC}"
  echo -e "  $0 <iterations> --scrape-only      ${DIM}# Only URL discovery + HTML scrape${NC}"
  echo -e "  $0 --pipeline <source_id>          ${DIM}# Pipeline mode - 4 sub-ralphs${NC}"
  echo -e "  $0 --pipeline-all                  ${DIM}# Pipeline mode - all pending sources${NC}"
  echo ""
  echo -e "${WHITE}Examples:${NC}"
  echo -e "  $0 25                              ${DIM}# Run 25 iterations (all 4 stages)${NC}"
  echo -e "  $0 50 --scrape-only                ${DIM}# Only scrape, skip extraction${NC}"
  echo -e "  $0 --pipeline custom_wheel_offset  ${DIM}# Pipeline for specific source${NC}"
  echo -e "  $0 --pipeline-all                  ${DIM}# Pipeline all pending sources${NC}"
  echo ""
  echo -e "${WHITE}Flags:${NC}"
  echo -e "  ${CYAN}--scrape-only${NC}    Only do Stage 1 (URL discovery) and Stage 2 (HTML scrape)"
  echo -e "                   Skip Stage 3 (build extraction) and Stage 4 (mod extraction)"
  echo -e "  ${CYAN}--verbose, -v${NC}    Show full Claude output (no progress timer)"
  echo ""
  echo -e "${WHITE}Pipeline Mode:${NC}"
  echo -e "  Uses 4 specialized sub-ralphs that work in parallel:"
  echo -e "    ${CYAN}url-detective${NC}    → Discovers all URLs"
  echo -e "    ${CYAN}html-scraper${NC}     → Downloads HTML content"
  echo -e "    ${CYAN}build-extractor${NC}  → Extracts vehicle data"
  echo -e "    ${CYAN}mod-extractor${NC}    → Extracts modifications"
  echo -e ""
  echo -e "  Each sub-ralph triggers the next after 20 items are ready."
  echo ""
}

# Check for help
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
  show_usage
  exit 0

# Check for pipeline mode
elif [ "$1" == "--pipeline" ]; then
  if [ -z "$2" ]; then
    echo -e "${RED}Error:${NC} --pipeline requires a source_id"
    echo -e "${DIM}Example: $0 --pipeline custom_wheel_offset${NC}"
    exit 1
  fi
  
  # Run pipeline for specific source
  exec "$SCRIPT_DIR/pipeline.sh" "$2"
  
elif [ "$1" == "--pipeline-all" ]; then
  # Run pipeline for all pending/in_progress sources
  echo ""
  echo -e "${CYAN}Running pipeline for all pending sources...${NC}"
  echo ""
  
  # Get list of sources that need work
  SOURCES=$(jq -r '.sources[] | select(.status == "pending" or .status == "in_progress") | .id' "$SOURCES_FILE" 2>/dev/null)
  
  if [ -z "$SOURCES" ]; then
    echo -e "${YELLOW}No pending sources found.${NC}"
    exit 0
  fi
  
  for source in $SOURCES; do
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}Starting pipeline for: ${WHITE}$source${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    
    "$SCRIPT_DIR/pipeline.sh" "$source"
    
    echo ""
    echo -e "${GREEN}✓ Completed: $source${NC}"
  done
  
  echo ""
  echo -e "${GREEN}All sources processed!${NC}"
  exit 0
  
elif [ -z "$1" ]; then
  show_usage
  exit 1
  
elif ! [[ "$1" =~ ^[0-9]+$ ]]; then
  echo -e "${RED}Error:${NC} Invalid argument '$1'"
  show_usage
  exit 1
fi

# Parse additional flags
ITERATIONS="$1"
shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scrape-only)
      SCRAPE_ONLY=true
      shift
      ;;
    --verbose|-v)
      VERBOSE=true
      shift
      ;;
    *)
      echo -e "${RED}Error:${NC} Unknown flag '$1'"
      show_usage
      exit 1
      ;;
  esac
done

# ═══════════════════════════════════════════════════════════════
# Banner
# ═══════════════════════════════════════════════════════════════

clear || true
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
echo -e "${CYAN}║${NC}            ${YELLOW}🤖 Autonomous AI Agent Loop${NC}                  ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}                                                           ${CYAN}║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

PENDING_SOURCES=$(count_pending_sources)
BLOCKED_SOURCES=$(count_blocked_sources)
WORK_SOURCES=$(count_sources_needing_work)
log_info "Max iterations: ${CYAN}$ITERATIONS${NC}"
if [ "$SCRAPE_ONLY" = true ]; then
  log_info "Mode: ${YELLOW}SCRAPE-ONLY${NC} (Stages 1-2 only, skip extraction)"
fi
if [ "$VERBOSE" = true ]; then
  log_info "Mode: ${CYAN}VERBOSE${NC} (Full Claude output, no progress timer)"
fi
log_info "Sources: ${CYAN}$PENDING_SOURCES${NC} pending, ${RED}$BLOCKED_SOURCES${NC} blocked, ${CYAN}$WORK_SOURCES${NC} total need work"
log_info "Log file: ${DIM}$LOG_FILE${NC}"

# Run completion checker to validate source statuses
if [ -x "$SCRIPT_DIR/check_completion.sh" ]; then
  echo ""
  log_action "Validating source statuses..."
  
  # Check for mismatched statuses (silently get count)
  MISMATCHED=$(cat "$SOURCES_FILE" | jq -c '.sources[]' | while read source; do
    id=$(echo "$source" | jq -r '.id')
    status=$(echo "$source" | jq -r '.status')
    found=$(echo "$source" | jq -r '.pipeline.urlsFound // 0')
    scraped=$(echo "$source" | jq -r '.pipeline.htmlScraped // 0')
    blocked=$(echo "$source" | jq -r '.pipeline.htmlBlocked // 0')
    builds=$(echo "$source" | jq -r '.pipeline.builds')
    
    [[ "$found" == "null" ]] && found=0
    [[ "$scraped" == "null" ]] && scraped=0
    [[ "$blocked" == "null" ]] && blocked=0
    
    # Calculate correct status
    if [[ "$found" -eq 0 ]]; then
      correct="pending"
    elif [[ "$blocked" -gt 0 ]]; then
      correct="blocked"
    elif [[ "$scraped" -lt "$found" ]]; then
      correct="in_progress"
    elif [[ "$builds" != "null" && -n "$builds" ]]; then
      correct="completed"
    else
      correct="in_progress"
    fi
    
    if [[ "$status" != "$correct" ]]; then
      echo "$id"
    fi
  done | wc -l | tr -d ' ')
  
  if [ "$MISMATCHED" -gt 0 ]; then
    log_warning "${RED}$MISMATCHED${NC} sources have incorrect status!"
    log_warning "Run: ${YELLOW}./scripts/ralph/check_completion.sh --fix${NC} to correct"
  else
    log_success "All source statuses validated ✓"
  fi
fi

if [ "$BLOCKED_SOURCES" -gt 0 ]; then
  echo ""
  log_warning "${RED}$BLOCKED_SOURCES${NC} blocked sources need stealth scraper intervention:"
  # List blocked sources with commands
  jq -r '.sources[] | select(.status == "blocked") | "  → python scripts/tools/stealth_scraper.py --source \(.id)"' "$SOURCES_FILE" 2>/dev/null | head -5
  if [ "$BLOCKED_SOURCES" -gt 5 ]; then
    echo -e "  ${DIM}... and $((BLOCKED_SOURCES - 5)) more${NC}"
  fi
fi

print_project_status

cd "$PROJECT_ROOT"

# ═══════════════════════════════════════════════════════════════
# Main Loop
# ═══════════════════════════════════════════════════════════════

for ((i=1; i<=$ITERATIONS; i++)); do
  echo ""
  
  # Sync progress from disk to sources.json (silent)
  python3 "$PROJECT_ROOT/scripts/tools/sync_progress.py" >/dev/null 2>&1 || true
  
  echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
  echo -e "${YELLOW}═══ ${WHITE}${BOLD}Iteration $i of $ITERATIONS${NC} ${DIM}│ $(elapsed_time) elapsed${NC} ${YELLOW}═══════════════════${NC}"
  echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
  
  # Show current story being worked on
  get_project_info
  echo ""
  log_info "Source: ${WHITE}$SOURCE_ID${NC}"
  log_info "Pipeline: URLs=${CYAN}$URLS_FOUND${NC} HTML=${CYAN}$HTML_SCRAPED${NC} Builds=${CYAN}$BUILDS_COUNT${NC} Mods=${CYAN}$MODS_COUNT${NC}"
  log_info "Working on: ${YELLOW}$NEXT_STORY${NC}"
  echo ""
  
  log_action "Calling Claude CLI (streaming)..."
  CALL_START=$(date +%s)
  
  echo -e "${DIM}────────────────────── Claude Output ──────────────────────${NC}"
  
  TEMP_OUTPUT=$(mktemp)
  TIMER_PID=""
  
  # Start a background process to show detailed status every 10 seconds (unless verbose)
  if [ "$VERBOSE" != true ]; then
    (
      trap 'exit 0' SIGTERM SIGINT
      while true; do
        sleep 10
        elapsed=$(($(date +%s) - CALL_START))
        
        # Get current file counts for progress indication
        if [ -d "$PROJECT_ROOT/$OUTPUT_DIR/html" ]; then
          html_count=$(find "$PROJECT_ROOT/$OUTPUT_DIR/html" -name "*.html" 2>/dev/null | wc -l | tr -d ' ')
        else
          html_count=0
        fi
        
        if [ -f "$PROJECT_ROOT/$OUTPUT_DIR/urls.json" ]; then
          url_count=$(jq -r '.urls | length' "$PROJECT_ROOT/$OUTPUT_DIR/urls.json" 2>/dev/null || echo 0)
        else
          url_count=0
        fi
        
        if [ -f "$PROJECT_ROOT/$OUTPUT_DIR/builds.json" ]; then
          # Handle both {"builds": [...]} and raw [...] array formats
          build_count=$(jq -r 'if type == "array" then length else (.builds | length) end' "$PROJECT_ROOT/$OUTPUT_DIR/builds.json" 2>/dev/null || echo 0)
        else
          build_count=0
        fi
        
        echo -e "\r${DIM}[$(date +%H:%M:%S)] ⏱️  ${elapsed}s │ ${CYAN}$SOURCE_ID${NC} │ URLs:${GREEN}$url_count${NC} HTML:${GREEN}$html_count${NC} Builds:${GREEN}$build_count${NC}${NC}" >&2
      done
    ) &
    TIMER_PID=$!
    CHILD_PIDS+=("$TIMER_PID")
  fi
  
  # Use --print with --verbose for more output visibility
  # Prepend scrape-only mode instruction if flag is set
  if [ "$SCRAPE_ONLY" = true ]; then
    {
      echo "## MODE: SCRAPE-ONLY"
      echo ""
      echo "**IMPORTANT: Only perform Stage 1 (URL Discovery) and Stage 2 (HTML Scraping).**"
      echo "Do NOT proceed to Stage 3 (Build Extraction) or Stage 4 (Mod Extraction)."
      echo "When all URLs are discovered and all HTML is scraped, mark the current PRD complete and move to the next source."
      echo ""
      echo "---"
      echo ""
      cat "$SCRIPT_DIR/prompt.md"
    } | claude --print --verbose --dangerously-skip-permissions 2>&1 | tee "$TEMP_OUTPUT"
  else
    cat "$SCRIPT_DIR/prompt.md" | claude --print --verbose --dangerously-skip-permissions 2>&1 | tee "$TEMP_OUTPUT"
  fi
  
  # Kill the timer (if running)
  if [ -n "$TIMER_PID" ]; then
    kill $TIMER_PID 2>/dev/null || true
  fi
  
  result=$(cat "$TEMP_OUTPUT" 2>/dev/null || echo "")
  rm -f "$TEMP_OUTPUT"
  
  echo -e "${DIM}─────────────────────────────────────────────────────────────${NC}"
  
  CALL_END=$(date +%s)
  CALL_DURATION=$((CALL_END - CALL_START))
  
  echo ""
  log_success "Iteration completed in ${CYAN}${CALL_DURATION}s${NC}"
  
  # Save to log
  echo "=== Iteration $i (${CALL_DURATION}s) - $(date) ===" >> "$LOG_FILE"
  echo "$result" >> "$LOG_FILE"
  echo "" >> "$LOG_FILE"
  
  # Show updated status
  get_project_info
  log_info "Updated progress: ${GREEN}$COMPLETED_STORIES${NC}/${CYAN}$TOTAL_STORIES${NC} stories"

  # Check for completion signal
  if [[ "$result" == *"<promise>COMPLETE</promise>"* ]] || [[ "$result" == *"RALPH_DONE"* ]]; then
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}                                                           ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}                  ${WHITE}${BOLD}✅ Source Complete!${NC}                      ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}                                                           ${GREEN}║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    
    # Archive completed PRD
    archive_completed_project
    
    # Check for more sources that need work
    PENDING_SOURCES=$(count_pending_sources)
    WORK_SOURCES=$(count_sources_needing_work)
    
    if [ "$WORK_SOURCES" -gt 0 ]; then
      NEXT_SOURCE=$(get_next_source)
      echo ""
      log_info "${CYAN}$WORK_SOURCES${NC} sources still need work"
      log_action "Auto-continuing to next source: ${WHITE}$NEXT_SOURCE${NC}"
      echo ""
      
      # Small delay before continuing
      sleep 2
      
      # Continue the loop - don't exit!
      # Ralph will pick up the next source automatically via prompt.md logic
      continue
    else
      # All sources complete!
      echo ""
      echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
      echo -e "${GREEN}║${NC}                                                           ${GREEN}║${NC}"
      echo -e "${GREEN}║${NC}             ${WHITE}${BOLD}🎉 ALL SOURCES COMPLETE! 🎉${NC}                  ${GREEN}║${NC}"
      echo -e "${GREEN}║${NC}                                                           ${GREEN}║${NC}"
      echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
      echo ""
      echo -e "${BLUE}╭──────────────────── 📈 Session Summary ────────────────────╮${NC}"
      printf "${BLUE}│${NC}  ⏱️  Duration          ${CYAN}%-34s${NC} ${BLUE}│${NC}\n" "$(elapsed_time)"
      printf "${BLUE}│${NC}  🔄 Iterations         ${YELLOW}%-34s${NC} ${BLUE}│${NC}\n" "$i"
      printf "${BLUE}│${NC}  📦 Sources Completed  ${GREEN}%-34s${NC} ${BLUE}│${NC}\n" "$SOURCES_COMPLETED"
      echo -e "${BLUE}╰────────────────────────────────────────────────────────────╯${NC}"
      
      # Send notification if tt is available
      if command -v tt &> /dev/null; then
        tt notify "Ralph: All sources complete! $SOURCES_COMPLETED sources in $(elapsed_time)"
      fi
      
      exit 0
    fi
  fi
  
  echo ""
  log_status "⏳ Next iteration in 2s..."
  sleep 2
done

# Max iterations reached
echo ""
echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║${NC}                                                           ${YELLOW}║${NC}"
echo -e "${YELLOW}║${NC}              ${WHITE}${BOLD}⏱️  Max Iterations Reached${NC}                   ${YELLOW}║${NC}"
echo -e "${YELLOW}║${NC}                                                           ${YELLOW}║${NC}"
echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
print_project_status
echo ""

PENDING_SOURCES=$(count_pending_sources)
WORK_SOURCES=$(count_sources_needing_work)

echo -e "${BLUE}╭──────────────────── 📈 Session Summary ────────────────────╮${NC}"
printf "${BLUE}│${NC}  ⏱️  Duration          ${CYAN}%-34s${NC} ${BLUE}│${NC}\n" "$(elapsed_time)"
printf "${BLUE}│${NC}  🔄 Iterations         ${YELLOW}%-34s${NC} ${BLUE}│${NC}\n" "$ITERATIONS"
printf "${BLUE}│${NC}  📦 Sources Completed  ${GREEN}%-34s${NC} ${BLUE}│${NC}\n" "$SOURCES_COMPLETED"
printf "${BLUE}│${NC}  📋 Sources Remaining  ${CYAN}%-34s${NC} ${BLUE}│${NC}\n" "$WORK_SOURCES"
if [ "$SCRAPE_ONLY" = true ]; then
printf "${BLUE}│${NC}  🔧 Mode               ${YELLOW}%-34s${NC} ${BLUE}│${NC}\n" "SCRAPE-ONLY (Stages 1-2)"
fi
echo -e "${BLUE}╰────────────────────────────────────────────────────────────╯${NC}"
echo ""
log_info "Run ${CYAN}./scripts/ralph/ralph.sh $ITERATIONS${NC} to continue"

# Send notification if tt is available
if command -v tt &> /dev/null; then
  tt notify "Ralph: Max iterations ($ITERATIONS) reached. $SOURCES_COMPLETED sources completed, $WORK_SOURCES remaining."
fi

exit 0
