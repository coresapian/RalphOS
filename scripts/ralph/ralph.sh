#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# RALPH - Autonomous AI Agent Loop
# ═══════════════════════════════════════════════════════════════

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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
START_TIME=$(date +%s)
LOG_FILE="$PROJECT_ROOT/ralph_output.log"
PRD_FILE="$SCRIPT_DIR/prd.json"
PROGRESS_FILE="$SCRIPT_DIR/progress.txt"
SOURCES_FILE="$SCRIPT_DIR/sources.json"

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
    TOTAL_STORIES=$(jq '.userStories | length' "$PRD_FILE" 2>/dev/null)
    COMPLETED_STORIES=$(jq '[.userStories[] | select(.passes == true)] | length' "$PRD_FILE" 2>/dev/null)
    NEXT_STORY=$(jq -r '[.userStories[] | select(.passes == false)] | sort_by(.priority) | .[0] | "\(.id): \(.title)"' "$PRD_FILE" 2>/dev/null)
  fi
}

print_project_status() {
  get_project_info
  echo ""
  echo -e "${BLUE}╭─────────────────────── 📋 Project Status ───────────────────────╮${NC}"
  printf "${BLUE}│${NC}  📁 Project:    ${WHITE}%-44s${NC} ${BLUE}│${NC}\n" "$PROJECT_NAME"
  printf "${BLUE}│${NC}  🌐 Target:     ${DIM}%-44s${NC} ${BLUE}│${NC}\n" "${TARGET_URL:0:44}"
  printf "${BLUE}│${NC}  📊 Progress:   ${GREEN}$COMPLETED_STORIES${NC}/${CYAN}$TOTAL_STORIES${NC} stories complete                          ${BLUE}│${NC}\n"
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

# ═══════════════════════════════════════════════════════════════
# Usage
# ═══════════════════════════════════════════════════════════════

if [ -z "$1" ]; then
  echo -e "${RED}Usage:${NC} $0 <iterations>"
  echo -e "${DIM}Example: $0 25${NC}"
  exit 1
fi

# ═══════════════════════════════════════════════════════════════
# Banner
# ═══════════════════════════════════════════════════════════════

clear
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
log_info "Max iterations: ${CYAN}$1${NC}"
log_info "Sources queued: ${CYAN}$PENDING_SOURCES${NC} pending"
log_info "Log file: ${DIM}$LOG_FILE${NC}"

print_project_status

cd "$PROJECT_ROOT"

# ═══════════════════════════════════════════════════════════════
# Main Loop
# ═══════════════════════════════════════════════════════════════

for ((i=1; i<=$1; i++)); do
  echo ""
  echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
  echo -e "${YELLOW}═══ ${WHITE}${BOLD}Iteration $i of $1${NC} ${DIM}│ $(elapsed_time) elapsed${NC} ${YELLOW}═══════════════════${NC}"
  echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
  
  # Show current story being worked on
  get_project_info
  echo ""
  log_info "Working on: ${YELLOW}$NEXT_STORY${NC}"
  log_info "Progress: ${GREEN}$COMPLETED_STORIES${NC}/${CYAN}$TOTAL_STORIES${NC} stories"
  echo ""
  
  log_action "Calling Claude CLI (streaming)..."
  CALL_START=$(date +%s)
  
  echo -e "${DIM}────────────────────── Claude Output ──────────────────────${NC}"
  
  TEMP_OUTPUT=$(mktemp)
  
  # Start a background process to show elapsed time every 10 seconds
  (
    while true; do
      sleep 10
      elapsed=$(($(date +%s) - CALL_START))
      echo -e "\r${DIM}[$(timestamp)] ⏱️  Still working... ${elapsed}s elapsed${NC}" >&2
    done
  ) &
  TIMER_PID=$!
  
  # Use --print with --verbose for more output visibility
  cat "$SCRIPT_DIR/prompt.md" | claude --print --verbose --dangerously-skip-permissions 2>&1 | tee "$TEMP_OUTPUT"
  
  # Kill the timer
  kill $TIMER_PID 2>/dev/null || true
  
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

  # Check for completion
  if [[ "$result" == *"<promise>COMPLETE</promise>"* ]] || [[ "$result" == *"RALPH_DONE"* ]]; then
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}                                                           ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}                  ${WHITE}${BOLD}✅ All Tasks Complete!${NC}                   ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}                                                           ${GREEN}║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}╭──────────────────── 📈 Session Summary ────────────────────╮${NC}"
    printf "${BLUE}│${NC}  ⏱️  Duration       ${CYAN}%-38s${NC} ${BLUE}│${NC}\n" "$(elapsed_time)"
    printf "${BLUE}│${NC}  🔄 Iterations     ${YELLOW}%-38s${NC} ${BLUE}│${NC}\n" "$i"
    printf "${BLUE}│${NC}  📁 Project        ${WHITE}%-38s${NC} ${BLUE}│${NC}\n" "$PROJECT_NAME"
    echo -e "${BLUE}╰────────────────────────────────────────────────────────────╯${NC}"
    
    # Archive completed PRD
    ARCHIVE_DIR="$SCRIPT_DIR/archive"
    mkdir -p "$ARCHIVE_DIR"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    PROJECT_SLUG=$(echo "$PROJECT_NAME" | tr ' ' '_' | tr -cd '[:alnum:]_-')
    ARCHIVE_NAME="${TIMESTAMP}_${PROJECT_SLUG}"
    
    echo ""
    log_action "Archiving completed project..."
    cp "$SCRIPT_DIR/prd.json" "$ARCHIVE_DIR/${ARCHIVE_NAME}_prd.json"
    cp "$SCRIPT_DIR/progress.txt" "$ARCHIVE_DIR/${ARCHIVE_NAME}_progress.txt"
    log_success "Archived to: ${DIM}$ARCHIVE_DIR/${ARCHIVE_NAME}_*${NC}"
    
    # Check for more sources
    PENDING_SOURCES=$(count_pending_sources)
    if [ "$PENDING_SOURCES" -gt 0 ]; then
      echo ""
      log_info "${CYAN}$PENDING_SOURCES${NC} more sources in queue"
      log_info "Run ralph.sh again to continue with next source"
    fi
    
    # Send notification if tt is available
    if command -v tt &> /dev/null; then
      tt notify "Ralph: $PROJECT_NAME complete after $i iterations ($(elapsed_time))"
    fi
    
    exit 0
  fi
  
  echo ""
  log_status "⏳ Next iteration in 2s..."
  sleep 2
done

# Max iterations reached
echo ""
echo -e "${RED}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║${NC}                                                           ${RED}║${NC}"
echo -e "${RED}║${NC}              ${WHITE}${BOLD}⚠️  Max Iterations Reached${NC}                   ${RED}║${NC}"
echo -e "${RED}║${NC}                                                           ${RED}║${NC}"
echo -e "${RED}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
print_project_status
echo ""
echo -e "${BLUE}╭──────────────────── 📈 Session Summary ────────────────────╮${NC}"
printf "${BLUE}│${NC}  ⏱️  Duration       ${CYAN}%-38s${NC} ${BLUE}│${NC}\n" "$(elapsed_time)"
printf "${BLUE}│${NC}  🔄 Iterations     ${YELLOW}%-38s${NC} ${BLUE}│${NC}\n" "$1"
echo -e "${BLUE}╰────────────────────────────────────────────────────────────╯${NC}"
echo ""
log_warning "Check progress.txt and prd.json for status"

# Send notification if tt is available
if command -v tt &> /dev/null; then
  tt notify "Ralph: Max iterations ($1) reached after $(elapsed_time)"
fi

exit 1
