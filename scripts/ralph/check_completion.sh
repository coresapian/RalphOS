#!/bin/bash
# check_completion.sh - Calculate and display completion status for Ralph sources
#
# Usage:
# ./check_completion.sh # Show all sources
# ./check_completion.sh <source_id> # Show specific source
# ./check_completion.sh --fix # Fix incorrect statuses in sources.json
# ./check_completion.sh --blocked # Show only blocked sources
# ./check_completion.sh --summary # Show summary counts only

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCES_FILE="$SCRIPT_DIR/sources.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Check dependencies
if ! command -v jq &> /dev/null; then
 echo -e "${RED}Error: jq is required but not installed.${NC}"
 echo "Install with: brew install jq"
 exit 1
fi

# Parse arguments
SOURCE_ID=""FIX_MODE=false
BLOCKED_ONLY=false
SUMMARY_ONLY=false

for arg in "$@"; do
 case $arg in
 --fix)
 FIX_MODE=true
 ;;
 --blocked)
 BLOCKED_ONLY=true
 ;;
 --summary)
 SUMMARY_ONLY=true
 ;;
 -h|--help)
 echo "Usage: $0 [source_id] [--fix] [--blocked] [--summary]"
 echo ""echo "Options:"
 echo " source_id Show completion for specific source"
 echo " --fix Fix incorrect statuses in sources.json"
 echo " --blocked Show only blocked sources with stealth command"
 echo " --summary Show summary counts only"
 echo " -h, --help Show this help"
 exit 0
 ;;
 *)
 SOURCE_ID="$arg"
 ;;
 esac
done

# Calculate completion status for a source
# Returns: completed|blocked|in_progress|pending
calculate_status() {
 local urls_found="$1"
 local html_scraped="$2"
 local html_failed="$3"
 local html_blocked="$4"
 local builds="$5"
 local current_status="$6"
 local mods="$7"
 
 # Handle null/empty values
 urls_found=${urls_found:-0}
 html_scraped=${html_scraped:-0}
 html_failed=${html_failed:-0}
 html_blocked=${html_blocked:-0}
 
 # Convert "null" string to 0
 [[ "$urls_found" == "null" ]] && urls_found=0
 [[ "$html_scraped" == "null" ]] && html_scraped=0
 [[ "$html_failed" == "null" ]] && html_failed=0
 [[ "$html_blocked" == "null" ]] && html_blocked=0
 [[ "$builds" == "null" ]] && builds=""[[ "$mods" == "null" ]] && mods=""# Pending: no URLs discovered yet
 if [[ "$urls_found" -eq 0 ]]; then
 echo "pending"
 return
 fi
 
 # Calculate attempted
 local attempted=$((html_scraped + html_failed + html_blocked))
 
 # If blocked count > 0, status is blocked
 if [[ "$html_blocked" -gt 0 ]]; then
 echo "blocked"
 return
 fi
 
 # If not all URLs attempted, in_progress
 if [[ "$attempted" -lt "$urls_found" ]]; then
 echo "in_progress"
 return
 fi
 
 # COMPLETED requires BOTH builds AND mods extracted (mods > 0)
 if [[ -n "$builds" && "$builds" != "null" && "$builds" -gt 0 && \
 -n "$mods" && "$mods" != "null" && "$mods" -gt 0 ]]; then
 echo "completed"
 else
 echo "in_progress"
 fi
}

# Format percentage with color
format_percent() {
 local numerator="$1"
 local denominator="$2"
 
 if [[ "$denominator" == "null" || "$denominator" -eq 0 ]]; then
 echo -e "${YELLOW}N/A${NC}"
 return
 fi
 
 numerator=${numerator:-0}
 [[ "$numerator" == "null" ]] && numerator=0
 
 local percent=$(echo "scale=1; $numerator * 100 / $denominator" | bc)
 
 if (( $(echo "$percent >= 100" | bc -l) )); then
 echo -e "${GREEN}${percent}%${NC}"
 elif (( $(echo "$percent >= 50" | bc -l) )); then
 echo -e "${YELLOW}${percent}%${NC}"
 else
 echo -e "${RED}${percent}%${NC}"
 fi
}

# Status with color
format_status() {
 local status="$1"
 case $status in
 completed)
 echo -e "${GREEN}${NC} completed"
 ;;
 blocked)
 echo -e "${RED}${NC} blocked"
 ;;
 in_progress)
 echo -e "${YELLOW}${NC} in_progress"
 ;;
 pending)
 echo -e "${BLUE}${NC} pending"
 ;;
 *)
 echo -e "${NC} $status"
 ;;
 esac
}

# Show single source details
show_source() {
 local source="$1"
 
 local id=$(echo "$source" | jq -r '.id')
 local name=$(echo "$source" | jq -r '.name')
 local current_status=$(echo "$source" | jq -r '.status')
 local expected=$(echo "$source" | jq -r '.pipeline.expectedUrls')
 local found=$(echo "$source" | jq -r '.pipeline.urlsFound')
 local scraped=$(echo "$source" | jq -r '.pipeline.htmlScraped')
 local failed=$(echo "$source" | jq -r '.pipeline.htmlFailed')
 local blocked=$(echo "$source" | jq -r '.pipeline.htmlBlocked')
 local builds=$(echo "$source" | jq -r '.pipeline.builds')
 local mods=$(echo "$source" | jq -r '.pipeline.mods')
 local notes=$(echo "$source" | jq -r '.notes // ""')
 
 # Calculate correct status
 local correct_status=$(calculate_status "$found" "$scraped" "$failed" "$blocked" "$builds" "$current_status" "$mods")
 
 # Calculate attempted
 local attempted=0
 [[ "$scraped" != "null" ]] && attempted=$((attempted + scraped))
 [[ "$failed" != "null" ]] && attempted=$((attempted + failed))
 [[ "$blocked" != "null" ]] && attempted=$((attempted + blocked))
 
 echo -e "${BOLD}$name${NC} ($id)"
 echo -e " Status: $(format_status "$current_status")"
 
 if [[ "$current_status" != "$correct_status" ]]; then
 echo -e " ${RED}Should be:${NC} $(format_status "$correct_status") ${RED}← MISMATCH${NC}"
 fi
 
 echo ""echo -e " URLs Expected: ${expected:-N/A}"
 echo -e " URLs Found: ${found:-0}"
 echo -e " HTML Scraped: ${scraped:-0} ($(format_percent "${scraped:-0}" "$found"))"
 echo -e " HTML Failed: ${failed:-0}"
 echo -e " HTML Blocked: ${blocked:-0}"
 echo -e " Total Attempted: $attempted / ${found:-0}"
 echo ""echo -e " Builds: ${builds:-N/A}"
 echo -e " Mods: ${mods:-N/A}"
 
 if [[ -n "$notes" && "$notes" != "null" ]]; then
 echo ""echo -e " ${CYAN}Notes:${NC} $notes"
 fi
 
 if [[ "$current_status" == "blocked" || "$correct_status" == "blocked" ]]; then
 echo ""echo -e " ${YELLOW}Run stealth scraper:${NC}"
 echo -e " python scripts/tools/stealth_scraper.py --source $id"
 fi
 
 echo ""echo "---"
}

# Summary counts
show_summary() {
 local sources=$(cat "$SOURCES_FILE" | jq -c '.sources[]')
 
 local completed=0
 local blocked=0
 local in_progress=0
 local pending=0
 local mismatched=0
 local total_urls=0
 local total_scraped=0
 local total_blocked_urls=0
 
 while IFS= read -r source; do
 local current_status=$(echo "$source" | jq -r '.status')
 local found=$(echo "$source" | jq -r '.pipeline.urlsFound // 0')
 local scraped=$(echo "$source" | jq -r '.pipeline.htmlScraped // 0')
 local failed=$(echo "$source" | jq -r '.pipeline.htmlFailed // 0')
 local blocked_count=$(echo "$source" | jq -r '.pipeline.htmlBlocked // 0')
 local builds=$(echo "$source" | jq -r '.pipeline.builds')
 local mods=$(echo "$source" | jq -r '.pipeline.mods')
 
 [[ "$found" == "null" ]] && found=0
 [[ "$scraped" == "null" ]] && scraped=0
 [[ "$failed" == "null" ]] && failed=0
 [[ "$blocked_count" == "null" ]] && blocked_count=0
 
 local correct_status=$(calculate_status "$found" "$scraped" "$failed" "$blocked_count" "$builds" "$current_status" "$mods")
 
 case $correct_status in
 completed) ((completed++)) ;;
 blocked) ((blocked++)) ;;
 in_progress) ((in_progress++)) ;;
 pending) ((pending++)) ;;
 esac
 
 [[ "$current_status" != "$correct_status" ]] && ((mismatched++))
 
 total_urls=$((total_urls + found))
 total_scraped=$((total_scraped + scraped))
 total_blocked_urls=$((total_blocked_urls + blocked_count))
 done <<< "$sources"
 
 local total=$((completed + blocked + in_progress + pending))
 
 echo -e "${BOLD}Ralph Source Summary${NC}"
 echo "===================="
 echo ""echo -e " ${GREEN}${NC} Completed: $completed"
 echo -e " ${RED}${NC} Blocked: $blocked"
 echo -e " ${YELLOW}${NC} In Progress: $in_progress"
 echo -e " ${BLUE}${NC} Pending: $pending"
 echo " "
 echo -e " Total: $total"
 echo ""echo -e " Total URLs Found: $total_urls"
 echo -e " Total HTML Scraped: $total_scraped"
 echo -e " Total HTML Blocked: $total_blocked_urls"
 
 if [[ $total_urls -gt 0 ]]; then
 local overall_percent=$(echo "scale=1; $total_scraped * 100 / $total_urls" | bc)
 echo -e " Overall Progress: $(format_percent "$total_scraped" "$total_urls")"
 fi
 
 if [[ $mismatched -gt 0 ]]; then
 echo ""echo -e " ${RED} $mismatched sources have incorrect status!${NC}"
 echo -e " Run: ${YELLOW}./check_completion.sh --fix${NC}"
 fi
}

# Show blocked sources only
show_blocked() {
 local sources=$(cat "$SOURCES_FILE" | jq -c '.sources[] | select(.status == "blocked" or .pipeline.htmlBlocked > 0)')
 
 if [[ -z "$sources" ]]; then
 echo -e "${GREEN}No blocked sources!${NC}"
 return
 fi
 
 echo -e "${BOLD}Blocked Sources - Need Stealth Scraper${NC}"
 echo "======================================="
 echo ""while IFS= read -r source; do
 local id=$(echo "$source" | jq -r '.id')
 local name=$(echo "$source" | jq -r '.name')
 local found=$(echo "$source" | jq -r '.pipeline.urlsFound // 0')
 local scraped=$(echo "$source" | jq -r '.pipeline.htmlScraped // 0')
 local blocked=$(echo "$source" | jq -r '.pipeline.htmlBlocked // 0')
 
 [[ "$found" == "null" ]] && found=0
 [[ "$scraped" == "null" ]] && scraped=0
 [[ "$blocked" == "null" ]] && blocked=0
 
 echo -e "${RED}${NC} ${BOLD}$name${NC} ($id)"
 echo -e " Scraped: $scraped / $found ($(format_percent "$scraped" "$found"))"
 echo -e " Blocked: $blocked URLs remaining"
 echo -e " ${YELLOW}→ python scripts/tools/stealth_scraper.py --source $id${NC}"
 echo ""done <<< "$sources"
}

# Fix incorrect statuses
fix_statuses() {
 local sources=$(cat "$SOURCES_FILE" | jq -c '.sources[]')
 local fixed=0
 local tmpfile=$(mktemp)
 
 echo -e "${BOLD}Checking source statuses...${NC}"
 echo ""# Create updated sources array
 echo "[" > "$tmpfile"
 local first=true
 
 while IFS= read -r source; do
 local id=$(echo "$source" | jq -r '.id')
 local current_status=$(echo "$source" | jq -r '.status')
 local found=$(echo "$source" | jq -r '.pipeline.urlsFound // 0')
 local scraped=$(echo "$source" | jq -r '.pipeline.htmlScraped // 0')
 local failed=$(echo "$source" | jq -r '.pipeline.htmlFailed // 0')
 local blocked=$(echo "$source" | jq -r '.pipeline.htmlBlocked // 0')
 local builds=$(echo "$source" | jq -r '.pipeline.builds')
 local mods=$(echo "$source" | jq -r '.pipeline.mods')
 
 [[ "$found" == "null" ]] && found=0
 [[ "$scraped" == "null" ]] && scraped=0
 [[ "$failed" == "null" ]] && failed=0
 [[ "$blocked" == "null" ]] && blocked=0
 
 local correct_status=$(calculate_status "$found" "$scraped" "$failed" "$blocked" "$builds" "$current_status" "$mods")
 
 if [[ "$current_status" != "$correct_status" ]]; then
 echo -e " ${YELLOW}$id${NC}: $current_status → ${GREEN}$correct_status${NC}"
 source=$(echo "$source" | jq --arg status "$correct_status" '.status = $status')
 ((fixed++))
 fi
 
 if [[ "$first" == "true" ]]; then
 first=false
 else
 echo "," >> "$tmpfile"
 fi
 echo "$source" >> "$tmpfile"
 done <<< "$sources"
 
 echo "]" >> "$tmpfile"
 
 if [[ $fixed -gt 0 ]]; then
 # Reconstruct full JSON with updated sources
 jq --slurpfile new_sources "$tmpfile" '.sources = $new_sources[0]' "$SOURCES_FILE" > "${SOURCES_FILE}.tmp"
 mv "${SOURCES_FILE}.tmp" "$SOURCES_FILE"
 echo ""echo -e "${GREEN}Fixed $fixed source statuses.${NC}"
 else
 echo -e "${GREEN}All statuses are correct!${NC}"
 fi
 
 rm -f "$tmpfile"
}

# Main logic
main() {
 if [[ ! -f "$SOURCES_FILE" ]]; then
 echo -e "${RED}Error: sources.json not found at $SOURCES_FILE${NC}"
 exit 1
 fi
 
 if [[ "$FIX_MODE" == "true" ]]; then
 fix_statuses
 exit 0
 fi
 
 if [[ "$SUMMARY_ONLY" == "true" ]]; then
 show_summary
 exit 0
 fi
 
 if [[ "$BLOCKED_ONLY" == "true" ]]; then
 show_blocked
 exit 0
 fi
 
 if [[ -n "$SOURCE_ID" ]]; then
 # Show specific source
 local source=$(cat "$SOURCES_FILE" | jq -c ".sources[] | select(.id == \"$SOURCE_ID\")")
 if [[ -z "$source" ]]; then
 echo -e "${RED}Error: Source '$SOURCE_ID' not found${NC}"
 exit 1
 fi
 show_source "$source"
 else
 # Show all sources
 show_summary
 echo ""echo "---"
 echo ""local sources=$(cat "$SOURCES_FILE" | jq -c '.sources[]')
 while IFS= read -r source; do
 show_source "$source"
 done <<< "$sources"
 fi
}

main

