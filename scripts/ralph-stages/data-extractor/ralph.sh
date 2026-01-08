#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# DATA EXTRACTOR - Stage 3 Ralph
# Extracts builds + categorized mods in ONE PASS
# ═══════════════════════════════════════════════════════════════

# Cleanup function
cleanup() {
  echo ""
  echo -e "\033[1;31m⚠️  Ctrl+C received - shutting down Data Extractor...\033[0m"
  jobs -p | xargs -r kill 2>/dev/null || true
  echo -e "\033[1;32m✓ Data Extractor stopped cleanly\033[0m"
  exit 130
}

trap cleanup SIGINT SIGTERM SIGHUP

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
START_TIME=$(date +%s)
QUEUE_FILE="$SCRIPT_DIR/queue.json"
PROGRESS_FILE="$SCRIPT_DIR/progress.txt"
PROMPT_FILE="$SCRIPT_DIR/prompt.md"
LOG_FILE="$SCRIPT_DIR/logs/data_extractor.log"

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

log_action() {
  echo -e "${CYAN}[$(timestamp)] ▶${NC} $1"
}

log_warning() {
  echo -e "${YELLOW}[$(timestamp)] ⚠${NC} $1"
}

get_next_source() {
  if [ -f "$QUEUE_FILE" ]; then
    IN_PROGRESS=$(jq -r '[.sources[] | select(.status == "in_progress")] | .[0] | .id // empty' "$QUEUE_FILE" 2>/dev/null)
    if [ -n "$IN_PROGRESS" ]; then
      echo "$IN_PROGRESS"
      return
    fi
    jq -r '[.sources[] | select(.status == "pending")] | sort_by(.priority // 999) | .[0] | .id // empty' "$QUEUE_FILE" 2>/dev/null
  fi
}

get_source_info() {
  local source_id=$1
  if [ -f "$QUEUE_FILE" ]; then
    jq -r ".sources[] | select(.id == \"$source_id\")" "$QUEUE_FILE" 2>/dev/null
  fi
}

mark_source_in_progress() {
  local source_id=$1
  local tmp_file=$(mktemp)
  jq --arg id "$source_id" \
     '(.sources[] | select(.id == $id)).status = "in_progress"' \
     "$QUEUE_FILE" > "$tmp_file" && mv "$tmp_file" "$QUEUE_FILE"
}

mark_source_completed() {
  local source_id=$1
  local tmp_file=$(mktemp)
  jq --arg id "$source_id" \
     '(.sources[] | select(.id == $id)).status = "completed"' \
     "$QUEUE_FILE" > "$tmp_file" && mv "$tmp_file" "$QUEUE_FILE"
}

count_pending_sources() {
  if [ -f "$QUEUE_FILE" ]; then
    jq '[.sources[] | select(.status == "pending")] | length' "$QUEUE_FILE" 2>/dev/null || echo 0
  else
    echo 0
  fi
}

print_queue_status() {
  PENDING=$(count_pending_sources)
  echo ""
  echo -e "${BLUE}╭─────────────────── 🔍 Data Extractor ───────────────────────╮${NC}"
  printf "${BLUE}│${NC}  📋 Pending Sources:  ${YELLOW}%-40s${NC} ${BLUE}│${NC}\n" "$PENDING"
  printf "${BLUE}│${NC}  ⏱️  Elapsed:          ${CYAN}%-40s${NC} ${BLUE}│${NC}\n" "$(elapsed_time)"
  echo -e "${BLUE}╰─────────────────────────────────────────────────────────────────╯${NC}"
}

# ═══════════════════════════════════════════════════════════════
# Usage
# ═══════════════════════════════════════════════════════════════

show_usage() {
  echo ""
  echo -e "${WHITE}${BOLD}Data Extractor - Stage 3 Ralph${NC}"
  echo -e "${DIM}Extracts builds + categorized mods in ONE PASS${NC}"
  echo ""
  echo -e "${WHITE}Usage:${NC}"
  echo -e "  $0 <iterations>                    ${DIM}# Run N iterations${NC}"
  echo ""
  echo -e "${WHITE}Examples:${NC}"
  echo -e "  $0 50                              ${DIM}# Run 50 iterations${NC}"
  echo ""
  echo -e "${YELLOW}NOTE:${NC} Run ${CYAN}html-scraper${NC} first to create HTML files"
}

if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
  show_usage
  exit 0
fi

if [ -z "$1" ]; then
  show_usage
  exit 1
fi

if ! [[ "$1" =~ ^[0-9]+$ ]]; then
  echo -e "${RED}Error:${NC} Invalid argument '$1'"
  show_usage
  exit 1
fi

ITERATIONS="$1"

# ═══════════════════════════════════════════════════════════════
# Banner
# ═══════════════════════════════════════════════════════════════

clear || true
echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}                                                           ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${BOLD}🔍 DATA EXTRACTOR${NC}                                      ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${WHITE}Stage 3: Builds + Mods Extraction${NC}                      ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}                                                           ${CYAN}║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

log_info "Max iterations: ${CYAN}$ITERATIONS${NC}"
log_info "Queue file: ${DIM}$QUEUE_FILE${NC}"
log_info "Progress file: ${DIM}$PROGRESS_FILE${NC}"

print_queue_status

cd "$PROJECT_ROOT"

# ═══════════════════════════════════════════════════════════════
# Main Loop
# ═══════════════════════════════════════════════════════════════

for ((i=1; i<=$ITERATIONS; i++)); do
  echo ""

  echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
  echo -e "${YELLOW}═══ ${WHITE}${BOLD}Iteration $i of $ITERATIONS${NC} ${DIM}│ $(elapsed_time) elapsed${NC} ${YELLOW}═══════════════════${NC}"
  echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"

  SOURCE_ID=$(get_next_source)

  if [ -z "$SOURCE_ID" ] || [ "$SOURCE_ID" == "null" ]; then
    echo ""
    echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║${NC}                                                           ${YELLOW}║${NC}"
    echo -e "${YELLOW}║${NC}              ${WHITE}${BOLD}⏱️  No More Sources${NC}                       ${YELLOW}║${NC}"
    echo -e "${YELLOW}║${NC}                                                           ${YELLOW}║${NC}"
    echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    log_info "Add sources to ${DIM}queue.json${NC} to continue"
    break
  fi

  SOURCE_INFO=$(get_source_info "$SOURCE_ID")
  SOURCE_NAME=$(echo "$SOURCE_INFO" | jq -r '.name // "Unknown"')
  OUTPUT_DIR=$(echo "$SOURCE_INFO" | jq -r '.outputDir // "Unknown"')
  HTML_COUNT=$(find "$PROJECT_ROOT/$OUTPUT_DIR/html" -name "*.html" 2>/dev/null | wc -l | tr -d ' ')

  echo ""
  log_info "Source: ${WHITE}$SOURCE_NAME${NC} (${CYAN}$SOURCE_ID${NC})"
  log_info "Output: ${DIM}$OUTPUT_DIR${NC}"
  log_info "HTML files: ${CYAN}$HTML_COUNT${NC}"
  echo ""

  # Check if HTML files exist
  if [ "$HTML_COUNT" -eq 0 ]; then
    log_warning "No HTML files found - run html-scraper first"
    mark_source_blocked "$SOURCE_ID"
    continue
  fi

  mark_source_in_progress "$SOURCE_ID"

  log_action "Calling Claude CLI (streaming)..."
  CALL_START=$(date +%s)

  echo -e "${DIM}────────────────────── Claude Output ──────────────────────${NC}"

  SOURCE_CONTEXT="Source ID: $SOURCE_ID
Name: $SOURCE_NAME
Output Directory: $OUTPUT_DIR
HTML Files: $HTML_COUNT

Source Info:
$SOURCE_INFO"

  TEMP_OUTPUT=$(mktemp)

  {
    echo "# Current Source"
    echo "$SOURCE_CONTEXT"
    echo ""
    echo "---"
    echo ""
    cat "$PROMPT_FILE"
  } | claude --print --verbose --dangerously-skip-permissions 2>&1 | tee "$TEMP_OUTPUT"

  result=$(cat "$TEMP_OUTPUT" 2>/dev/null || echo "")
  rm -f "$TEMP_OUTPUT"

  echo -e "${DIM}─────────────────────────────────────────────────────────────${NC}"

  CALL_END=$(date +%s)
  CALL_DURATION=$((CALL_END - CALL_START))

  echo ""
  log_success "Iteration completed in ${CYAN}${CALL_DURATION}s${NC}"

  # Check for completion signal
  if [[ "$result" == *"DATA_EXTRACTOR_DONE"* ]]; then
    echo ""
    log_action "Validating output..."
    
    sleep 2  # Allow file writes to complete
    
    # Check for builds.jsonl and mods.jsonl
    BUILDS_FILE="$PROJECT_ROOT/$OUTPUT_DIR/builds.jsonl"
    MODS_FILE="$PROJECT_ROOT/$OUTPUT_DIR/mods.jsonl"
    
    BUILDS_COUNT=0
    MODS_COUNT=0
    IS_VALID=false
    
    if [ -f "$BUILDS_FILE" ]; then
      BUILDS_COUNT=$(wc -l < "$BUILDS_FILE" | tr -d ' ')
    fi
    
    if [ -f "$MODS_FILE" ]; then
      MODS_COUNT=$(wc -l < "$MODS_FILE" | tr -d ' ')
    fi
    
    if [ "$BUILDS_COUNT" -gt 0 ]; then
      IS_VALID=true
    fi
    
    if [ "$IS_VALID" == "true" ]; then
      mark_source_completed "$SOURCE_ID"
      SOURCES_COMPLETED=$((SOURCES_COMPLETED + 1))
      echo ""
      echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
      echo -e "${GREEN}║${NC}                                                           ${GREEN}║${NC}"
      echo -e "${GREEN}║${NC}            ${WHITE}${BOLD}✅ Source Complete!${NC}                        ${GREEN}║${NC}"
      echo -e "${GREEN}║${NC}             ${CYAN}$SOURCE_NAME${NC}                                        ${GREEN}║${NC}"
      echo -e "${GREEN}║${NC}             ${DIM}$BUILDS_COUNT builds, $MODS_COUNT mods${NC}                          ${GREEN}║${NC}"
      echo -e "${GREEN}║${NC}                                                           ${GREEN}║${NC}"
      echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"

      echo "" >> "$PROGRESS_FILE"
      echo "## $(date +%Y-%m-%d) - $SOURCE_ID" >> "$PROGRESS_FILE"
      echo "- Extraction complete: $BUILDS_COUNT builds, $MODS_COUNT mods" >> "$PROGRESS_FILE"
      echo "- Check $OUTPUT_DIR/builds.jsonl and mods.jsonl" >> "$PROGRESS_FILE"
      echo "" >> "$PROGRESS_FILE"
    else
      echo ""
      echo -e "${RED}╔═══════════════════════════════════════════════════════════╗${NC}"
      echo -e "${RED}║${NC}                                                           ${RED}║${NC}"
      echo -e "${RED}║${NC}            ${WHITE}${BOLD}❌ VALIDATION FAILED${NC}                        ${RED}║${NC}"
      echo -e "${RED}║${NC}             ${CYAN}$SOURCE_NAME${NC}                                        ${RED}║${NC}"
      echo -e "${RED}║${NC}             ${DIM}builds.jsonl: $BUILDS_COUNT lines${NC}                    ${RED}║${NC}"
      echo -e "${RED}║${NC}                                                           ${RED}║${NC}"
      echo -e "${RED}╚═══════════════════════════════════════════════════════════╝${NC}"
      
      # Send retry prompt
      echo ""
      log_action "Sending diagnostic retry prompt..."
      echo -e "${DIM}────────────────────── Retry Output ──────────────────────${NC}"
      
      RETRY_PROMPT="# VALIDATION FAILED - IMMEDIATE RETRY REQUIRED

You claimed DATA_EXTRACTOR_DONE but validation failed.

## Error
builds.jsonl has $BUILDS_COUNT lines (expected > 0)

## Your Task NOW
1. List HTML files: \`ls $OUTPUT_DIR/html/ | head -5\`
2. Read a sample HTML to understand structure
3. Use chrome_evaluate to analyze DOM patterns
4. Create extraction script with correct selectors
5. ACTUALLY RUN the extraction script

DO NOT just say you did it. ACTUALLY CREATE AND RUN the extraction script.

When truly complete with builds.jsonl created, output: DATA_EXTRACTOR_DONE"

      RETRY_OUTPUT=$(mktemp)
      echo "$RETRY_PROMPT" | claude --print --dangerously-skip-permissions 2>&1 | tee "$RETRY_OUTPUT"
      
      retry_result=$(cat "$RETRY_OUTPUT" 2>/dev/null || echo "")
      rm -f "$RETRY_OUTPUT"
      
      echo -e "${DIM}─────────────────────────────────────────────────────────────${NC}"
      
      # Re-validate after retry
      if [[ "$retry_result" == *"DATA_EXTRACTOR_DONE"* ]]; then
        sleep 2
        if [ -f "$BUILDS_FILE" ]; then
          RETRY_BUILDS=$(wc -l < "$BUILDS_FILE" | tr -d ' ')
          RETRY_MODS=$(wc -l < "$MODS_FILE" 2>/dev/null | tr -d ' ' || echo 0)
          
          if [ "$RETRY_BUILDS" -gt 0 ]; then
            mark_source_completed "$SOURCE_ID"
            SOURCES_COMPLETED=$((SOURCES_COMPLETED + 1))
            echo ""
            echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
            echo -e "${GREEN}║${NC}   ${WHITE}${BOLD}✅ Source Complete (after retry)!${NC}                   ${GREEN}║${NC}"
            echo -e "${GREEN}║${NC}   ${CYAN}$SOURCE_NAME${NC} - ${DIM}$RETRY_BUILDS builds, $RETRY_MODS mods${NC}             ${GREEN}║${NC}"
            echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
            
            echo "" >> "$PROGRESS_FILE"
            echo "## $(date +%Y-%m-%d) - $SOURCE_ID (retry success)" >> "$PROGRESS_FILE"
            echo "- Extraction complete after retry: $RETRY_BUILDS builds, $RETRY_MODS mods" >> "$PROGRESS_FILE"
            echo "" >> "$PROGRESS_FILE"
          fi
        fi
      fi
    fi
  fi

  echo ""
  log_status "⏳ Next iteration in 2s..."
  sleep 2
done

echo ""
echo -e "${BLUE}╭──────────────────── 📈 Session Summary ────────────────────╮${NC}"
printf "${BLUE}│${NC}  ⏱️  Duration          ${CYAN}%-34s${NC} ${BLUE}│${NC}\n" "$(elapsed_time)"
printf "${BLUE}│${NC}  🔄 Iterations         ${YELLOW}%-34s${NC} ${BLUE}│${NC}\n" "$ITERATIONS"
printf "${BLUE}│${NC}  📦 Sources Completed  ${GREEN}%-34s${NC} ${BLUE}│${NC}\n" "$SOURCES_COMPLETED"
PENDING=$(count_pending_sources)
printf "${BLUE}│${NC}  📋 Sources Remaining  ${CYAN}%-34s${NC} ${BLUE}│${NC}\n" "$PENDING"
echo -e "${BLUE}╰────────────────────────────────────────────────────────────╯${NC}"
echo ""
log_info "Run ${CYAN}./ralph.sh $ITERATIONS${NC} to continue"

exit 0

