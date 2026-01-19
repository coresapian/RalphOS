#!/bin/bash
#
# Ralph Source Discovery - Autonomous source discovery loop
#
# Usage:
#   ./scripts/ralph/ralph-discovery.sh              # Standard discovery (5 new sources)
#   ./scripts/ralph/ralph-discovery.sh --quick      # Quick discovery (3 new sources)
#   ./scripts/ralph/ralph-discovery.sh --deep       # Deep discovery (15 new sources)
#   ./scripts/ralph/ralph-discovery.sh --continuous # Run continuously until stopped
#   ./scripts/ralph/ralph-discovery.sh --categories jdm trucks  # Target specific vehicle types
#
# Environment:
#   MAX_ITERATIONS - Override max iterations (default: from PRD)
#   TARGET_SOURCES - Override target new sources (default: from PRD)
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PRD_FILE="$SCRIPT_DIR/prd.json"
SOURCES_FILE="$SCRIPT_DIR/sources.json"
PROMPT_FILE="$SCRIPT_DIR/prompts/source_discovery.md"
PROGRESS_FILE="$SCRIPT_DIR/progress.txt"
LOG_FILE="$PROJECT_ROOT/logs/ralph_discovery.log"

# Defaults
MODE="standard"
CONTINUOUS=false
CATEGORIES=""
MAX_ITERATIONS=${MAX_ITERATIONS:-20}
TARGET_SOURCES=${TARGET_SOURCES:-5}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --quick|-q)
            MODE="quick"
            MAX_ITERATIONS=10
            TARGET_SOURCES=3
            shift
            ;;
        --deep|-d)
            MODE="deep"
            MAX_ITERATIONS=50
            TARGET_SOURCES=15
            shift
            ;;
        --continuous|-c)
            CONTINUOUS=true
            shift
            ;;
        --categories)
            shift
            CATEGORIES="$@"
            break
            ;;
        --help|-h)
            echo "Ralph Source Discovery - Find new vehicle build sources"
            echo ""
            echo "Usage:"
            echo "  $0                        # Standard discovery session"
            echo "  $0 --quick                # Quick discovery (fewer searches)"
            echo "  $0 --deep                 # Deep discovery (all categories)"
            echo "  $0 --continuous           # Run continuously"
            echo "  $0 --categories jdm trucks  # Target specific vehicle types"
            echo ""
            echo "Categories: build_showcase, forum_threads, tuner_shops,"
            echo "            wheel_fitment, auctions, publications,"
            echo "            jdm, trucks, muscle, european, exotic"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Banner
echo -e "${PURPLE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           RALPH SOURCE DISCOVERY                             ║"
echo "║   Autonomous Vehicle Build Source Finder                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Create logs directory
mkdir -p "$PROJECT_ROOT/logs"

# Function to count sources
count_sources() {
    local status=$1
    if [[ -n "$status" ]]; then
        jq "[.sources[] | select(.status == \"$status\")] | length" "$SOURCES_FILE" 2>/dev/null || echo 0
    else
        jq ".sources | length" "$SOURCES_FILE" 2>/dev/null || echo 0
    fi
}

# Function to display source stats
show_stats() {
    echo -e "${CYAN}Current Source Statistics:${NC}"
    echo "  Total sources:   $(count_sources)"
    echo "  Pending:         $(count_sources pending)"
    echo "  In progress:     $(count_sources in_progress)"
    echo "  Completed:       $(count_sources completed)"
    echo "  Blocked:         $(count_sources blocked)"
    echo ""
}

# Generate PRD if needed
generate_prd() {
    echo -e "${BLUE}Generating discovery PRD...${NC}"

    local prd_args=""
    case $MODE in
        quick)
            prd_args="--quick"
            ;;
        deep)
            prd_args="--deep"
            ;;
        *)
            if [[ -n "$CATEGORIES" ]]; then
                prd_args="--categories $CATEGORIES --target $TARGET_SOURCES"
            fi
            ;;
    esac

    python3 "$PROJECT_ROOT/scripts/tools/generate_discovery_prd.py" $prd_args

    echo -e "${GREEN}PRD generated: $PRD_FILE${NC}"
}

# Check if discovery PRD exists
check_prd() {
    if [[ ! -f "$PRD_FILE" ]]; then
        return 1
    fi

    # Check if it's a discovery PRD
    local mode=$(jq -r '.mode // ""' "$PRD_FILE" 2>/dev/null)
    if [[ "$mode" != "discovery" ]]; then
        return 1
    fi

    # Check if complete
    local incomplete=$(jq '[.userStories[] | select(.passes == false)] | length' "$PRD_FILE" 2>/dev/null)
    if [[ "$incomplete" -eq 0 ]]; then
        return 1
    fi

    return 0
}

# Run a single discovery iteration
run_iteration() {
    local iteration=$1

    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Discovery Iteration $iteration${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Build the prompt for Claude
    local prompt="You are running in Source Discovery mode.

Read the prompt file at: scripts/ralph/prompts/source_discovery.md
Read the current PRD at: scripts/ralph/prd.json
Read existing sources at: scripts/ralph/sources.json

Execute the current incomplete story. Use webSearchPrime to search for new sources,
webReader to validate them, and add valid sources to sources.json.

IMPORTANT:
- DO NOT add sources that already exist in sources.json
- Validate each source before adding (check for individual build pages with mods listed)
- Update the PRD when a story is complete
- Append discovery progress to progress.txt

Stop when:
- All stories are complete (output RALPH_DONE)
- You've found ${TARGET_SOURCES} new valid sources
- No more valid candidates found after thorough search

Work autonomously. Do not ask questions."

    # Run Claude CLI
    local start_time=$(date +%s)

    echo "$prompt" | claude --dangerously-skip-permissions \
        --print "Read the prompt at scripts/ralph/prompts/source_discovery.md and execute the current discovery story from scripts/ralph/prd.json" \
        2>&1 | tee -a "$LOG_FILE"

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    echo -e "${CYAN}Iteration completed in ${duration}s${NC}"

    # Check for completion signal
    if grep -q "RALPH_DONE" "$LOG_FILE" 2>/dev/null; then
        return 0  # Done
    fi

    return 1  # Continue
}

# Main discovery loop
main() {
    cd "$PROJECT_ROOT"

    echo -e "${CYAN}Mode: $MODE${NC}"
    echo -e "${CYAN}Max iterations: $MAX_ITERATIONS${NC}"
    echo -e "${CYAN}Target new sources: $TARGET_SOURCES${NC}"
    echo ""

    show_stats

    # Generate or check PRD
    if ! check_prd; then
        generate_prd
    else
        echo -e "${BLUE}Using existing discovery PRD${NC}"
    fi

    echo ""

    local iteration=0
    local initial_count=$(count_sources)

    while true; do
        iteration=$((iteration + 1))

        if [[ $iteration -gt $MAX_ITERATIONS ]]; then
            echo -e "${YELLOW}Max iterations ($MAX_ITERATIONS) reached${NC}"
            break
        fi

        # Run iteration
        if run_iteration $iteration; then
            echo -e "${GREEN}Discovery complete!${NC}"
            break
        fi

        # Check if we hit target
        local current_count=$(count_sources)
        local new_sources=$((current_count - initial_count))

        if [[ $new_sources -ge $TARGET_SOURCES ]]; then
            echo -e "${GREEN}Target reached: $new_sources new sources found!${NC}"

            if [[ "$CONTINUOUS" == "true" ]]; then
                echo -e "${YELLOW}Continuous mode: starting new discovery session...${NC}"
                initial_count=$current_count
                generate_prd
            else
                break
            fi
        fi

        # Small delay between iterations
        sleep 2
    done

    # Final stats
    echo ""
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}DISCOVERY SESSION COMPLETE${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    local final_count=$(count_sources)
    local total_new=$((final_count - initial_count))

    echo ""
    show_stats
    echo -e "${CYAN}New sources discovered this session: $total_new${NC}"
    echo ""

    # List new sources
    if [[ $total_new -gt 0 ]]; then
        echo -e "${GREEN}New sources added:${NC}"
        jq -r '.sources[-'$total_new':] | .[] | "  - \(.id): \(.name) (\(.url))"' "$SOURCES_FILE"
    fi
}

# Run main
main
