#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
# URL DETECTIVE - Stage 1 Ralph
# Discovers all vehicle/build URLs from target websites
# ═══════════════════════════════════════════════════════════════

# Cleanup function
cleanup() {
  echo ""
  echo -e "\033[1;31m⚠️  Ctrl+C received - shutting down URL Detective...\033[0m"
  jobs -p | xargs -r kill 2>/dev/null || true
  echo -e "\033[1;32m✓ URL Detective stopped cleanly\033[0m"
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
LOG_FILE="$SCRIPT_DIR/logs/url_detective.log"

# Track sources completed
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

get_next_source() {
  if [ -f "$QUEUE_FILE" ]; then
    # First check for in_progress sources
    IN_PROGRESS=$(jq -r '[.sources[] | select(.status == "in_progress")] | .[0] | .id // empty' "$QUEUE_FILE" 2>/dev/null)
    if [ -n "$IN_PROGRESS" ]; then
      echo "$IN_PROGRESS"
      return
    fi
    # Then check for pending sources
    jq -r '[.sources[] | select(.status == "pending")] | sort_by(.priority) | .[0] | .id // empty' "$QUEUE_FILE" 2>/dev/null
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
  echo -e "${BLUE}╭─────────────────────── 🔍 URL Detective ───────────────────────╮${NC}"
  printf "${BLUE}│${NC}  📋 Pending Sources:  ${YELLOW}%-40s${NC} ${BLUE}│${NC}\n" "$PENDING"
  printf "${BLUE}│${NC}  ⏱️  Elapsed:          ${CYAN}%-40s${NC} ${BLUE}│${NC}\n" "$(elapsed_time)"
  echo -e "${BLUE}╰─────────────────────────────────────────────────────────────────╯${NC}"
}

# ═══════════════════════════════════════════════════════════════
# Usage
# ═══════════════════════════════════════════════════════════════

show_usage() {
  echo ""
  echo -e "${WHITE}${BOLD}URL Detective - Stage 1 Ralph${NC}"
  echo ""
  echo -e "${WHITE}Usage:${NC}"
  echo -e "  $0 <iterations>                    ${DIM}# Run N iterations${NC}"
  echo ""
  echo -e "${WHITE}Examples:${NC}"
  echo -e "  $0 25                              ${DIM}# Run 25 iterations${NC}"
  echo ""
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
echo -e "${CYAN}║${NC}   ${BOLD}🔍 URL DETECTIVE${NC}                                      ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${WHITE}Stage 1: URL Discovery${NC}                             ${CYAN}║${NC}"
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

  # Get next source
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
  SOURCE_URL=$(echo "$SOURCE_INFO" | jq -r '.url // "Unknown"')
  OUTPUT_DIR=$(echo "$SOURCE_INFO" | jq -r '.outputDir // "Unknown"')

  echo ""
  log_info "Source: ${WHITE}$SOURCE_NAME${NC} (${CYAN}$SOURCE_ID${NC})"
  log_info "URL: ${DIM}$SOURCE_URL${NC}"
  log_info "Output: ${DIM}$OUTPUT_DIR${NC}"
  echo ""

  # Mark source as in_progress
  mark_source_in_progress "$SOURCE_ID"

  log_action "Calling Claude CLI (streaming)..."
  CALL_START=$(date +%s)

  echo -e "${DIM}────────────────────── Claude Output ──────────────────────${NC}"

  # Build source context for Claude
  SOURCE_CONTEXT="Source ID: $SOURCE_ID
Name: $SOURCE_NAME
URL: $SOURCE_URL
Output Directory: $OUTPUT_DIR

Source Info:
$SOURCE_INFO"

  TEMP_OUTPUT=$(mktemp)

  # Run Claude CLI with the prompt and source context
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
  if [[ "$result" == *"URL_DETECTIVE_DONE"* ]]; then
    echo ""
    log_action "Validating output..."
    sleep 2  # Allow file writes to complete
    
    # Run validation script to prevent hallucinated completions
    # Use 60 min max age to allow for long-running iterations
    VALIDATION_RESULT=$(python3 "$PROJECT_ROOT/scripts/tools/validate_output.py" urls "$PROJECT_ROOT/$OUTPUT_DIR" 60 2>&1)
    if [ -z "$VALIDATION_RESULT" ] || ! echo "$VALIDATION_RESULT" | jq -e . >/dev/null 2>&1; then
      VALIDATION_RESULT='{"valid":false,"error":"Validation script error: '"${VALIDATION_RESULT:-empty output}"'"}'
    fi
    IS_VALID=$(echo "$VALIDATION_RESULT" | jq -r '.valid // false')
    URL_COUNT=$(echo "$VALIDATION_RESULT" | jq -r '.count // 0')
    VAL_ERROR=$(echo "$VALIDATION_RESULT" | jq -r '.error // "Unknown error"')
    
    if [ "$IS_VALID" == "true" ] && [ "$URL_COUNT" -gt 0 ]; then
      mark_source_completed "$SOURCE_ID"
      SOURCES_COMPLETED=$((SOURCES_COMPLETED + 1))
      echo ""
      echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
      echo -e "${GREEN}║${NC}                                                           ${GREEN}║${NC}"
      echo -e "${GREEN}║${NC}            ${WHITE}${BOLD}✅ Source Complete!${NC}                        ${GREEN}║${NC}"
      echo -e "${GREEN}║${NC}             ${CYAN}$SOURCE_NAME${NC}                                        ${GREEN}║${NC}"
      echo -e "${GREEN}║${NC}             ${DIM}$URL_COUNT URLs discovered${NC}                          ${GREEN}║${NC}"
      echo -e "${GREEN}║${NC}                                                           ${GREEN}║${NC}"
      echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"

      # Save to progress
      echo "" >> "$PROGRESS_FILE"
      echo "## $(date +%Y-%m-%d) - $SOURCE_ID" >> "$PROGRESS_FILE"
      echo "- URL Discovery complete: $URL_COUNT URLs" >> "$PROGRESS_FILE"
      echo "- Check $OUTPUT_DIR/urls.jsonl for results" >> "$PROGRESS_FILE"
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

You claimed URL_DETECTIVE_DONE but validation failed.

## Error
$VAL_ERROR

## Your Task NOW
1. Check if the output file exists: \`ls -la $OUTPUT_DIR/urls.jsonl $OUTPUT_DIR/urls.json 2>/dev/null\`
2. Check the file contents: \`head -5 $OUTPUT_DIR/urls.jsonl 2>/dev/null || head -20 $OUTPUT_DIR/urls.json 2>/dev/null\`
3. If empty or missing, YOU MUST ACTUALLY SCRAPE THE URLS using Claude-in-Chrome
4. Navigate to: $SOURCE_URL
5. Extract all vehicle/build URLs from the page
6. Write them to $OUTPUT_DIR/urls.jsonl (one JSON object per line)

DO NOT just say you did it. ACTUALLY USE YOUR TOOLS to:
- Navigate to the site
- Extract the URLs  
- Write the file

When truly complete, output: URL_DETECTIVE_DONE"

      RETRY_OUTPUT=$(mktemp)
      echo "$RETRY_PROMPT" | claude --print --dangerously-skip-permissions 2>&1 | tee "$RETRY_OUTPUT"
      
      retry_result=$(cat "$RETRY_OUTPUT" 2>/dev/null || echo "")
      rm -f "$RETRY_OUTPUT"
      
      echo -e "${DIM}─────────────────────────────────────────────────────────────${NC}"
      
      # Re-validate after retry
      if [[ "$retry_result" == *"URL_DETECTIVE_DONE"* ]]; then
        RETRY_VALIDATION=$(python3 "$PROJECT_ROOT/scripts/tools/validate_output.py" urls "$PROJECT_ROOT/$OUTPUT_DIR" 5 2>/dev/null || echo '{"valid":false}')
        RETRY_VALID=$(echo "$RETRY_VALIDATION" | jq -r '.valid // false')
        RETRY_COUNT=$(echo "$RETRY_VALIDATION" | jq -r '.count // 0')
        
        if [ "$RETRY_VALID" == "true" ] && [ "$RETRY_COUNT" -gt 0 ]; then
          mark_source_completed "$SOURCE_ID"
          SOURCES_COMPLETED=$((SOURCES_COMPLETED + 1))
          echo ""
          echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
          echo -e "${GREEN}║${NC}   ${WHITE}${BOLD}✅ Source Complete (after retry)!${NC}                   ${GREEN}║${NC}"
          echo -e "${GREEN}║${NC}   ${CYAN}$SOURCE_NAME${NC} - ${DIM}$RETRY_COUNT URLs${NC}                          ${GREEN}║${NC}"
          echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
          
          echo "" >> "$PROGRESS_FILE"
          echo "## $(date +%Y-%m-%d) - $SOURCE_ID (retry success)" >> "$PROGRESS_FILE"
          echo "- URL Discovery complete after retry: $RETRY_COUNT URLs" >> "$PROGRESS_FILE"
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
  fi

  echo ""
  log_status "⏳ Next iteration in 2s..."
  sleep 2
done

# Summary
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
