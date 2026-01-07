#!/bin/bash
#
# Sub-Ralph Pipeline Orchestrator
#
# Manages 4 specialized sub-ralphs in a cascading pipeline:
#   1. url-detective: Discovers all URLs
#   2. html-scraper: Downloads HTML content
#   3. build-extractor: Extracts vehicle data
#   4. mod-extractor: Extracts modifications
#
# Each sub-ralph triggers the next after 20 items are ready.
#
# Usage:
#   ./pipeline.sh <source_id>
#   ./pipeline.sh custom_wheel_offset
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SOURCES_FILE="$SCRIPT_DIR/sources.json"
PROMPTS_DIR="$SCRIPT_DIR/prompts"
TRIGGER_THRESHOLD=20
CHECK_INTERVAL=10  # seconds between trigger checks

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

# Track sub-ralph PIDs
URL_PID=""
HTML_PID=""
BUILD_PID=""
MOD_PID=""

# Cleanup function
cleanup() {
    echo ""
    echo -e "${RED}⚠️  Shutting down pipeline...${NC}"
    
    # Kill all sub-ralphs
    for pid in $URL_PID $HTML_PID $BUILD_PID $MOD_PID; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo -e "${DIM}Stopping PID $pid${NC}"
            kill "$pid" 2>/dev/null || true
        fi
    done
    
    # Kill any remaining background jobs
    jobs -p | xargs -r kill 2>/dev/null || true
    
    echo -e "${GREEN}✓ Pipeline stopped${NC}"
    exit 130
}

trap cleanup SIGINT SIGTERM SIGHUP

# Logging
log() {
    echo -e "${DIM}[$(date +%H:%M:%S)]${NC} $1"
}

log_stage() {
    echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} ${BLUE}[$1]${NC} $2"
}

log_success() {
    echo -e "${GREEN}[$(date +%H:%M:%S)] ✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date +%H:%M:%S)] ⚠${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +%H:%M:%S)] ✗${NC} $1"
}

# Get source info
get_source() {
    local source_id=$1
    jq -r ".sources[] | select(.id == \"$source_id\")" "$SOURCES_FILE"
}

# Check if a sub-ralph is still running
is_running() {
    local pid=$1
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

# Count items for trigger checks
count_urls() {
    local source_id=$1
    local urls_file="$PROJECT_ROOT/data/$source_id/urls.json"
    if [ -f "$urls_file" ]; then
        jq -r '.urls | length' "$urls_file" 2>/dev/null || echo 0
    else
        echo 0
    fi
}

count_html() {
    local source_id=$1
    local html_dir="$PROJECT_ROOT/data/$source_id/html"
    if [ -d "$html_dir" ]; then
        find "$html_dir" -name "*.html" 2>/dev/null | wc -l | tr -d ' '
    else
        echo 0
    fi
}

count_builds() {
    local source_id=$1
    local builds_file="$PROJECT_ROOT/data/$source_id/builds.json"
    if [ -f "$builds_file" ]; then
        jq -r '.builds | length' "$builds_file" 2>/dev/null || echo 0
    else
        echo 0
    fi
}

count_mods() {
    local source_id=$1
    local mods_file="$PROJECT_ROOT/data/$source_id/mods.json"
    if [ -f "$mods_file" ]; then
        jq -r '.mods | length' "$mods_file" 2>/dev/null || echo 0
    else
        echo 0
    fi
}

# Start a sub-ralph
start_sub_ralph() {
    local stage=$1
    local source_id=$2
    local prompt_file=$3
    local output_dir=$4
    
    log_stage "$stage" "Starting sub-ralph..."
    
    # Create output directory
    mkdir -p "$output_dir"
    
    # Build the context for Claude
    local context="Source ID: $source_id
Output Directory: data/$source_id
Source Info:
$(get_source "$source_id")"
    
    # Run Claude CLI with the sub-ralph prompt
    claude --print \
        --dangerously-skip-permissions \
        --system-prompt "$(cat "$prompt_file")" \
        "$context" \
        > "$output_dir/${stage}.log" 2>&1 &
    
    echo $!
}

# Main pipeline function
run_pipeline() {
    local source_id=$1
    
    # Validate source exists
    local source=$(get_source "$source_id")
    if [ -z "$source" ] || [ "$source" == "null" ]; then
        log_error "Source '$source_id' not found in sources.json"
        exit 1
    fi
    
    local output_dir=$(echo "$source" | jq -r '.outputDir')
    local source_url=$(echo "$source" | jq -r '.url')
    
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}           ${BLUE}Sub-Ralph Pipeline Orchestrator${NC}              ${CYAN}║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║${NC} Source: ${YELLOW}$source_id${NC}"
    echo -e "${CYAN}║${NC} URL:    ${DIM}$source_url${NC}"
    echo -e "${CYAN}║${NC} Output: ${DIM}$output_dir${NC}"
    echo -e "${CYAN}║${NC} Threshold: ${GREEN}$TRIGGER_THRESHOLD${NC} items to trigger next stage"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Create output directory
    mkdir -p "$PROJECT_ROOT/$output_dir"
    mkdir -p "$PROJECT_ROOT/$output_dir/html"
    
    # Stage flags
    local url_started=false
    local html_started=false
    local build_started=false
    local mod_started=false
    
    local url_done=false
    local html_done=false
    local build_done=false
    local mod_done=false
    
    # Start URL detective immediately
    log_stage "url-detective" "Starting URL discovery..."
    URL_PID=$(start_sub_ralph "url-detective" "$source_id" "$PROMPTS_DIR/url_detective.md" "$PROJECT_ROOT/$output_dir")
    url_started=true
    log "URL detective started (PID: $URL_PID)"
    
    # Main monitoring loop
    while true; do
        # Get current counts
        local urls=$(count_urls "$source_id")
        local htmls=$(count_html "$source_id")
        local builds=$(count_builds "$source_id")
        local mods=$(count_mods "$source_id")
        
        # Status display
        echo -ne "\r${DIM}[$(date +%H:%M:%S)]${NC} URLs: ${GREEN}$urls${NC} | HTML: ${GREEN}$htmls${NC} | Builds: ${GREEN}$builds${NC} | Mods: ${GREEN}$mods${NC}    "
        
        # Check URL detective status
        if $url_started && ! is_running "$URL_PID"; then
            if ! $url_done; then
                echo ""
                log_success "URL detective completed"
                url_done=true
            fi
        fi
        
        # Trigger HTML scraper at 20 URLs
        if ! $html_started && [ "$urls" -ge "$TRIGGER_THRESHOLD" ]; then
            echo ""
            log_stage "html-scraper" "Threshold reached ($urls URLs) - Starting HTML scraper..."
            HTML_PID=$(start_sub_ralph "html-scraper" "$source_id" "$PROMPTS_DIR/html_scraper.md" "$PROJECT_ROOT/$output_dir")
            html_started=true
            log "HTML scraper started (PID: $HTML_PID)"
        fi
        
        # Check HTML scraper status
        if $html_started && ! is_running "$HTML_PID"; then
            if ! $html_done; then
                echo ""
                log_success "HTML scraper completed"
                html_done=true
            fi
        fi
        
        # Trigger build extractor at 20 HTMLs
        if ! $build_started && [ "$htmls" -ge "$TRIGGER_THRESHOLD" ]; then
            echo ""
            log_stage "build-extractor" "Threshold reached ($htmls HTMLs) - Starting build extractor..."
            BUILD_PID=$(start_sub_ralph "build-extractor" "$source_id" "$PROMPTS_DIR/build_extractor.md" "$PROJECT_ROOT/$output_dir")
            build_started=true
            log "Build extractor started (PID: $BUILD_PID)"
        fi
        
        # Check build extractor status
        if $build_started && ! is_running "$BUILD_PID"; then
            if ! $build_done; then
                echo ""
                log_success "Build extractor completed"
                build_done=true
            fi
        fi
        
        # Trigger mod extractor at 20 builds
        if ! $mod_started && [ "$builds" -ge "$TRIGGER_THRESHOLD" ]; then
            echo ""
            log_stage "mod-extractor" "Threshold reached ($builds builds) - Starting mod extractor..."
            MOD_PID=$(start_sub_ralph "mod-extractor" "$source_id" "$PROMPTS_DIR/mod_extractor.md" "$PROJECT_ROOT/$output_dir")
            mod_started=true
            log "Mod extractor started (PID: $MOD_PID)"
        fi
        
        # Check mod extractor status
        if $mod_started && ! is_running "$MOD_PID"; then
            if ! $mod_done; then
                echo ""
                log_success "Mod extractor completed"
                mod_done=true
            fi
        fi
        
        # Check if all stages are done
        if $url_done && $html_done && $build_done && $mod_done; then
            echo ""
            echo ""
            log_success "All sub-ralphs completed!"
            break
        fi
        
        # Also check if all started stages have finished (for sources with fewer items)
        local all_started_done=true
        if $url_started && ! $url_done && is_running "$URL_PID"; then all_started_done=false; fi
        if $html_started && ! $html_done && is_running "$HTML_PID"; then all_started_done=false; fi
        if $build_started && ! $build_done && is_running "$BUILD_PID"; then all_started_done=false; fi
        if $mod_started && ! $mod_done && is_running "$MOD_PID"; then all_started_done=false; fi
        
        # If URL is done and we haven't hit thresholds, we need to start remaining stages
        if $url_done && ! $html_started && [ "$urls" -gt 0 ]; then
            echo ""
            log_stage "html-scraper" "URL done with $urls URLs - Starting HTML scraper..."
            HTML_PID=$(start_sub_ralph "html-scraper" "$source_id" "$PROMPTS_DIR/html_scraper.md" "$PROJECT_ROOT/$output_dir")
            html_started=true
        fi
        
        if $html_done && ! $build_started && [ "$htmls" -gt 0 ]; then
            echo ""
            log_stage "build-extractor" "HTML done with $htmls files - Starting build extractor..."
            BUILD_PID=$(start_sub_ralph "build-extractor" "$source_id" "$PROMPTS_DIR/build_extractor.md" "$PROJECT_ROOT/$output_dir")
            build_started=true
        fi
        
        if $build_done && ! $mod_started && [ "$builds" -gt 0 ]; then
            echo ""
            log_stage "mod-extractor" "Builds done with $builds records - Starting mod extractor..."
            MOD_PID=$(start_sub_ralph "mod-extractor" "$source_id" "$PROMPTS_DIR/mod_extractor.md" "$PROJECT_ROOT/$output_dir")
            mod_started=true
        fi
        
        sleep $CHECK_INTERVAL
    done
    
    # Run quality control
    run_qc "$source_id"
}

# Quality Control
run_qc() {
    local source_id=$1
    
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Quality Control${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    local urls=$(count_urls "$source_id")
    local htmls=$(count_html "$source_id")
    local builds=$(count_builds "$source_id")
    local mods=$(count_mods "$source_id")
    
    echo ""
    echo "Final counts:"
    echo "  URLs discovered: $urls"
    echo "  HTML files:      $htmls"
    echo "  Builds extracted: $builds"
    echo "  Mods extracted:  $mods"
    echo ""
    
    # Check for issues
    local issues=0
    
    if [ "$htmls" -lt "$urls" ]; then
        log_warning "HTML count ($htmls) < URL count ($urls) - some pages may have failed"
        ((issues++))
    fi
    
    if [ "$builds" -lt "$htmls" ]; then
        log_warning "Build count ($builds) < HTML count ($htmls) - some extractions may have failed"
        ((issues++))
    fi
    
    # Update sources.json
    log "Updating sources.json with final counts..."
    
    # Use jq to update the source
    local tmp_file=$(mktemp)
    jq --arg id "$source_id" \
       --argjson urls "$urls" \
       --argjson htmls "$htmls" \
       --argjson builds "$builds" \
       --argjson mods "$mods" \
       '(.sources[] | select(.id == $id).pipeline) |= . + {
         "urlsFound": $urls,
         "htmlScraped": $htmls,
         "builds": $builds,
         "mods": $mods
       }' "$SOURCES_FILE" > "$tmp_file" && mv "$tmp_file" "$SOURCES_FILE"
    
    # Determine final status
    if [ "$issues" -eq 0 ] && [ "$mods" -gt 0 ]; then
        # Set status to completed
        jq --arg id "$source_id" \
           '(.sources[] | select(.id == $id).status) = "completed"' \
           "$SOURCES_FILE" > "$tmp_file" && mv "$tmp_file" "$SOURCES_FILE"
        log_success "Source marked as completed!"
    else
        log_warning "Source has issues - keeping status as in_progress"
    fi
    
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}              ${GREEN}Pipeline Complete!${NC}                         ${GREEN}║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Main
if [ $# -lt 1 ]; then
    echo "Usage: $0 <source_id>"
    echo ""
    echo "Example:"
    echo "  $0 custom_wheel_offset"
    echo "  $0 bringatrailer"
    exit 1
fi

SOURCE_ID=$1

# Check dependencies
if ! command -v claude &> /dev/null; then
    log_error "Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    log_error "jq not found. Install with: brew install jq"
    exit 1
fi

run_pipeline "$SOURCE_ID"

