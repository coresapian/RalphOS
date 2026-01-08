#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# HTML SCRAPER - Stage 2 Ralph
# Downloads HTML content for discovered URLs
# ═══════════════════════════════════════════════════════════════

# Cleanup function
cleanup() {
  echo ""
  echo -e "\033[1;31m⚠️  Ctrl+C received - shutting down HTML Scraper...\033[0m"
  jobs -p | xargs -r kill 2>/dev/null || true
  echo -e "\033[1;32m✓ HTML Scraper stopped cleanly\033[0m"
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
LOG_FILE="$SCRIPT_DIR/logs/html_scraper.log"

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

mark_source_blocked() {
  local source_id=$1
  local tmp_file=$(mktemp)
  jq --arg id "$source_id" \
     '(.sources[] | select(.id == $id)).status = "blocked"' \
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
  echo -e "${BLUE}╭─────────────────────── 📥 HTML Scraper ───────────────────────╮${NC}"
  printf "${BLUE}│${NC}  📋 Pending Sources:  ${YELLOW}%-40s${NC} ${BLUE}│${NC}\n" "$PENDING"
  printf "${BLUE}│${NC}  ⏱️  Elapsed:          ${CYAN}%-40s${NC} ${BLUE}│${NC}\n" "$(elapsed_time)"
  echo -e "${BLUE}╰─────────────────────────────────────────────────────────────────╯${NC}"
}

# ═══════════════════════════════════════════════════════════════
# Usage
# ═══════════════════════════════════════════════════════════════

show_usage() {
  echo ""
  echo -e "${WHITE}${BOLD}HTML Scraper - Stage 2 Ralph${NC}"
  echo ""
  echo -e "${WHITE}Usage:${NC}"
  echo -e "  $0 <iterations>                    ${DIM}# Run N iterations${NC}"
  echo ""
  echo -e "${WHITE}Examples:${NC}"
  echo -e "  $0 50                              ${DIM}# Run 50 iterations${NC}"
  echo ""
  echo -e "${YELLOW}NOTE:${NC} Run ${CYAN}url-detective${NC} first to create urls.json files"
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
echo -e "${CYAN}║${NC}   ${BOLD}📥 HTML SCRAPER${NC}                                        ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${WHITE}Stage 2: HTML Download${NC}                               ${CYAN}║${NC}"
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
  URLS_FOUND=$(echo "$SOURCE_INFO" | jq -r '.urlsFound // 0')

  echo ""
  log_info "Source: ${WHITE}$SOURCE_NAME${NC} (${CYAN}$SOURCE_ID${NC})"
  log_info "Output: ${DIM}$OUTPUT_DIR${NC}"
  log_info "URLs to scrape: ${CYAN}$URLS_FOUND${NC}"
  echo ""

  # Check if urls.jsonl or urls.json exists
  if [ ! -f "$PROJECT_ROOT/$OUTPUT_DIR/urls.jsonl" ] && [ ! -f "$PROJECT_ROOT/$OUTPUT_DIR/urls.json" ]; then
    log_warning "No urls.jsonl or urls.json found - run url-detective first"
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
URLs Found: $URLS_FOUND

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

  # Check for completion or blocked signal
  if [[ "$result" == *"HTML_SCRAPER_DONE"* ]]; then
    echo ""
    log_action "Validating output..."
    
    # Run validation script to prevent hallucinated completions
    sleep 2  # Allow file writes to complete
    VALIDATION_RESULT=$(python3 "$PROJECT_ROOT/scripts/tools/validate_output.py" html "$PROJECT_ROOT/$OUTPUT_DIR" 60 2>&1)
    if [ -z "$VALIDATION_RESULT" ] || ! echo "$VALIDATION_RESULT" | jq -e . >/dev/null 2>&1; then
      VALIDATION_RESULT='{"valid":false,"error":"Validation error: '"${VALIDATION_RESULT:-empty}"'"}'
    fi
    IS_VALID=$(echo "$VALIDATION_RESULT" | jq -r '.valid // false')
    HTML_COUNT=$(echo "$VALIDATION_RESULT" | jq -r '.count // 0')
    RECENT_COUNT=$(echo "$VALIDATION_RESULT" | jq -r '.recent // 0')
    VAL_ERROR=$(echo "$VALIDATION_RESULT" | jq -r '.error // "Unknown error"')
    
    if [ "$IS_VALID" == "true" ] && [ "$HTML_COUNT" -gt 0 ]; then
      mark_source_completed "$SOURCE_ID"
      SOURCES_COMPLETED=$((SOURCES_COMPLETED + 1))
      echo ""
      echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
      echo -e "${GREEN}║${NC}                                                           ${GREEN}║${NC}"
      echo -e "${GREEN}║${NC}            ${WHITE}${BOLD}✅ Source Complete!${NC}                        ${GREEN}║${NC}"
      echo -e "${GREEN}║${NC}             ${CYAN}$SOURCE_NAME${NC}                                        ${GREEN}║${NC}"
      echo -e "${GREEN}║${NC}             ${DIM}$HTML_COUNT HTML files ($RECENT_COUNT new)${NC}                    ${GREEN}║${NC}"
      echo -e "${GREEN}║${NC}                                                           ${GREEN}║${NC}"
      echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"

      echo "" >> "$PROGRESS_FILE"
      echo "## $(date +%Y-%m-%d) - $SOURCE_ID" >> "$PROGRESS_FILE"
      echo "- HTML scraping complete: $HTML_COUNT files" >> "$PROGRESS_FILE"
      echo "- Check $OUTPUT_DIR/html/ for results" >> "$PROGRESS_FILE"
      echo "" >> "$PROGRESS_FILE"
    else
      echo ""
      echo -e "${RED}╔═══════════════════════════════════════════════════════════╗${NC}"
      echo -e "${RED}║${NC}                                                           ${RED}║${NC}"
      echo -e "${RED}║${NC}            ${WHITE}${BOLD}❌ VALIDATION FAILED${NC}                        ${RED}║${NC}"
      echo -e "${RED}║${NC}             ${CYAN}$SOURCE_NAME${NC}                                        ${RED}║${NC}"
      echo -e "${RED}║${NC}             ${DIM}$VAL_ERROR${NC}                          ${RED}║${NC}"
      echo -e "${RED}║${NC}                                                           ${RED}║${NC}"
      echo -e "${RED}╚═══════════════════════════════════════════════════════════╝${NC}"
      
      # Send retry prompt to Claude with diagnostic instructions
      echo ""
      log_action "Sending diagnostic retry prompt..."
      echo -e "${DIM}────────────────────── Retry Output ──────────────────────${NC}"
      
      RETRY_PROMPT="# VALIDATION FAILED - IMMEDIATE RETRY REQUIRED

You claimed HTML_SCRAPER_DONE but validation failed.

## Error
$VAL_ERROR

## Your Task NOW
1. Check HTML directory: \`ls -la $OUTPUT_DIR/html/ | head -10\`
2. Count existing files: \`find $OUTPUT_DIR/html -name '*.html' | wc -l\`
3. Check urls.jsonl for URLs to scrape: \`wc -l < $OUTPUT_DIR/urls.jsonl 2>/dev/null || jq '.urls | length' $OUTPUT_DIR/urls.json\`
4. If HTML files are missing, YOU MUST ACTUALLY SCRAPE THEM using webReader or Claude-in-Chrome
5. For each URL in urls.jsonl, fetch the HTML and save to $OUTPUT_DIR/html/

DO NOT just say you did it. ACTUALLY USE YOUR TOOLS to fetch HTML.

When truly complete with new HTML files saved, output: HTML_SCRAPER_DONE"

      RETRY_OUTPUT=$(mktemp)
      echo "$RETRY_PROMPT" | claude --print --dangerously-skip-permissions 2>&1 | tee "$RETRY_OUTPUT"
      
      retry_result=$(cat "$RETRY_OUTPUT" 2>/dev/null || echo "")
      rm -f "$RETRY_OUTPUT"
      
      echo -e "${DIM}─────────────────────────────────────────────────────────────${NC}"
      
      # Re-validate after retry
      if [[ "$retry_result" == *"HTML_SCRAPER_DONE"* ]]; then
        RETRY_VALIDATION=$(python3 "$PROJECT_ROOT/scripts/tools/validate_output.py" html "$PROJECT_ROOT/$OUTPUT_DIR" 5 2>/dev/null || echo '{"valid":false}')
        RETRY_VALID=$(echo "$RETRY_VALIDATION" | jq -r '.valid // false')
        RETRY_COUNT=$(echo "$RETRY_VALIDATION" | jq -r '.count // 0')
        
        if [ "$RETRY_VALID" == "true" ] && [ "$RETRY_COUNT" -gt 0 ]; then
          mark_source_completed "$SOURCE_ID"
          SOURCES_COMPLETED=$((SOURCES_COMPLETED + 1))
          echo ""
          echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
          echo -e "${GREEN}║${NC}   ${WHITE}${BOLD}✅ Source Complete (after retry)!${NC}                   ${GREEN}║${NC}"
          echo -e "${GREEN}║${NC}   ${CYAN}$SOURCE_NAME${NC} - ${DIM}$RETRY_COUNT HTML files${NC}                      ${GREEN}║${NC}"
          echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
          
          echo "" >> "$PROGRESS_FILE"
          echo "## $(date +%Y-%m-%d) - $SOURCE_ID (retry success)" >> "$PROGRESS_FILE"
          echo "- HTML scraping complete after retry: $RETRY_COUNT files" >> "$PROGRESS_FILE"
          echo "" >> "$PROGRESS_FILE"
        else
          echo ""
          echo -e "${RED}║${NC}   ${YELLOW}Retry also failed. Source stays in_progress.${NC}         ${RED}║${NC}"
          
          echo "" >> "$PROGRESS_FILE"
          echo "## $(date +%Y-%m-%d) - $SOURCE_ID - RETRY FAILED" >> "$PROGRESS_FILE"
          echo "- Initial error: $VAL_ERROR" >> "$PROGRESS_FILE"
          echo "- Retry also failed validation" >> "$PROGRESS_FILE"
          echo "" >> "$PROGRESS_FILE"
        fi
      fi
    fi

  elif [[ "$result" == *"HTML_SCRAPER_BLOCKED"* ]]; then
    mark_source_blocked "$SOURCE_ID"
    echo ""
    echo -e "${RED}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║${NC}                                                           ${RED}║${NC}"
    echo -e "${RED}║${NC}            ${WHITE}${BOLD}⚠️  Source BLOCKED${NC}                          ${RED}║${NC}"
    echo -e "${RED}║${NC}             ${CYAN}$SOURCE_NAME${NC}                                        ${RED}║${NC}"
    echo -e "${RED}║${NC}                                                           ${RED}║${NC}"
    echo -e "${RED}║${NC}     Use stealth_scraper.py to bypass anti-bot${NC}         ${RED}║${NC}"
    echo -e "${RED}║${NC}                                                           ${RED}║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════════════════════════╝${NC}"

    echo "" >> "$PROGRESS_FILE"
    echo "## $(date +%Y-%m-%d) - $SOURCE_ID - BLOCKED" >> "$PROGRESS_FILE"
    echo "- Scraping blocked by anti-bot protection" >> "$PROGRESS_FILE"
    echo "- Run: python scripts/tools/stealth_scraper.py --source $SOURCE_ID" >> "$PROGRESS_FILE"
    echo "" >> "$PROGRESS_FILE"
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
