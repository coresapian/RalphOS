#!/bin/bash
# ==========================================
# FACTORY RALPH - Robust Autonomous Loop
# ==========================================
# Enhanced version of ralph.sh with:
# - Git snapshots every iteration
# - Structured logging (JSONL)
# - Circuit breakers for failures
# - Tool usage monitoring
# - Visual validation integration
# - MCP asset management
# ==========================================

set -euo pipefail

# ==========================================
# CONFIGURATION
# ==========================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SESSION_ID="factory-ralph-$(date +%s)"
PROMPT_FILE="${SCRIPT_DIR}/prompt.md"
PRD_FILE="${SCRIPT_DIR}/prd.json"
SOURCES_FILE="${SCRIPT_DIR}/sources.json"
CONFIG_FILE="${SCRIPT_DIR}/config.json"
PROGRESS_FILE="${SCRIPT_DIR}/progress.txt"

# Logging
LOG_DIR="${PROJECT_ROOT}/logs/factory"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/exec_$(date +%Y%m%d_%H%M%S).log"
JSONL_LOG="${LOG_DIR}/exec_$(date +%Y%m%d_%H%M%S).jsonl"

# Git
GIT_BRANCH="factory-ralph-$(date +%Y%m%d)"

# Iteration Control
MAX_ITERATIONS="${1:-25}"
AUTO_LEVEL="${2:-medium}"  # low, medium, high

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ==========================================
# LOGGING FUNCTIONS
# ==========================================
log_json() {
    local level="$1"
    local message="$2"
    local data="${3:-{}}"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    echo "{\"timestamp\":\"$timestamp\",\"level\":\"$level\",\"message\":\"$message\",\"data\":$data,\"session\":\"$SESSION_ID\"}" >> "$JSONL_LOG"
}

log_info() {
    echo -e "${CYAN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
    log_json "INFO" "$1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
    log_json "SUCCESS" "$1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
    log_json "WARNING" "$1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    log_json "ERROR" "$1"
}

log_iteration() {
    local iter="$1"
    echo "" | tee -a "$LOG_FILE"
    echo -e "${BOLD}${PURPLE}════════════════════════════════════════${NC}" | tee -a "$LOG_FILE"
    echo -e "${BOLD}${PURPLE}  ITERATION $iter / $MAX_ITERATIONS${NC}" | tee -a "$LOG_FILE"
    echo -e "${BOLD}${PURPLE}════════════════════════════════════════${NC}" | tee -a "$LOG_FILE"
    log_json "ITERATION" "Starting iteration $iter" "{\"iteration\":$iter,\"max\":$MAX_ITERATIONS}"
}

# ==========================================
# GIT FUNCTIONS
# ==========================================
setup_git_branch() {
    log_info "Setting up Git branch: $GIT_BRANCH"

    # Check if branch exists
    if git show-ref --verify --quiet "refs/heads/$GIT_BRANCH" 2>/dev/null; then
        git checkout "$GIT_BRANCH" 2>/dev/null || true
        log_info "Switched to existing branch: $GIT_BRANCH"
    else
        # Stay on current branch but create a tag for this session
        local current_branch=$(git branch --show-current 2>/dev/null || echo "main")
        log_info "Staying on branch: $current_branch (session: $SESSION_ID)"
    fi
}

commit_iteration() {
    local iteration="$1"
    local status="${2:-in_progress}"

    # Check if there are actual changes
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        log_info "Changes detected. Committing to Git..."

        # Stage all changes
        git add -A

        # Create commit message
        local commit_msg="[Factory Ralph Iter $iteration] $status"

        # Commit without running hooks (to avoid blocking)
        git commit -m "$commit_msg" --no-verify 2>/dev/null || true

        log_success "Committed: $commit_msg"
        log_json "GIT_COMMIT" "Iteration commit" "{\"iteration\":$iteration,\"status\":\"$status\"}"
    else
        log_info "No changes detected in this iteration."
    fi
}

# ==========================================
# TOOL MANAGEMENT
# ==========================================
manage_tool_usage() {
    local iteration="$1"

    # Check if Ralph used the toolkit
    if grep -q "./tools/" "$LOG_FILE" 2>/dev/null; then
        log_info "[MONITOR] Ralph is using the Toolkit."

        # Count tool invocations
        local tool_count=$(grep -c "./tools/" "$LOG_FILE" 2>/dev/null || echo "0")
        log_info "[MONITOR] Total Tool Invocations: $tool_count"
        log_json "TOOL_USAGE" "Tool invocations detected" "{\"count\":$tool_count,\"iteration\":$iteration}"
    else
        log_warning "[MONITOR] Ralph might be running raw commands. Check logs."
    fi
}

# ==========================================
# VISUAL ASSETS (MCP/VLM)
# ==========================================
manage_visual_assets() {
    local iteration="$1"

    # Check for browser interactions
    if grep -q "browser_click\|browser_navigate\|chrome_" "$LOG_FILE" 2>/dev/null; then
        log_info "[VISUAL] Browser interaction detected. Archiving screenshots..."

        # Check for new screenshots
        local screenshot_dir="${PROJECT_ROOT}/tools/logs"
        mkdir -p "$screenshot_dir"

        if find "$screenshot_dir" -name '*.png' -newermt '1 minute ago' 2>/dev/null | grep -q .; then
            git add "$screenshot_dir"/*.png 2>/dev/null || true
            log_info "[VISUAL] Screenshots staged for commit."
        fi
    fi

    # Check for MCP-generated assets
    local mcp_output="${PROJECT_ROOT}/tools/mcp_output"
    if [ -d "$mcp_output" ] && find "$mcp_output" -type f -newermt '1 minute ago' 2>/dev/null | grep -q .; then
        log_info "[MCP] New MCP-generated assets detected."

        # Create metadata
        cat > "${mcp_output}/.mcp_metadata.json" << EOF
{
    "iteration": $iteration,
    "timestamp": "$(date -Iseconds)",
    "session": "$SESSION_ID"
}
EOF
        git add "$mcp_output" 2>/dev/null || true
    fi

    # Check for DuckDB assets
    if find "$PROJECT_ROOT" -name "*.duckdb" -newermt '1 minute ago' 2>/dev/null | grep -q .; then
        log_info "[DUCKDB] Database files detected."
        git add "$PROJECT_ROOT"/*.duckdb 2>/dev/null || true
    fi
}

# ==========================================
# SUCCESS/FAILURE DETECTION
# ==========================================
check_success_flag() {
    # Check for success file
    if [ -f "${PROJECT_ROOT}/.ralph_success" ]; then
        log_success "SUCCESS FLAG DETECTED (.ralph_success file exists)"
        return 0
    fi

    # Check for success marker in log
    if grep -q "✅ Done!\|RALPH_DONE\|<promise>COMPLETE</promise>" "$LOG_FILE" 2>/dev/null; then
        log_success "SUCCESS MARKER DETECTED in logs"
        return 0
    fi

    return 1
}

check_critical_failure() {
    # Check for critical errors
    if grep -q "CRITICAL_FAILURE\|Segmentation fault\|FATAL ERROR" "$LOG_FILE" 2>/dev/null; then
        log_error "CRITICAL ERROR DETECTED. PAUSING LOOP."
        return 0
    fi

    # Check for repeated failures (circuit breaker)
    local error_count=$(grep -c "ERROR\|FAIL\|Exception" "$LOG_FILE" 2>/dev/null || echo "0")
    if [ "$error_count" -gt 10 ]; then
        log_error "Too many errors ($error_count). Circuit breaker triggered."
        return 0
    fi

    return 1
}

# ==========================================
# PRD MANAGEMENT
# ==========================================
get_pending_stories() {
    if [ -f "$PRD_FILE" ]; then
        jq -r '.userStories[] | select(.passes == false) | .id' "$PRD_FILE" 2>/dev/null | head -5
    fi
}

get_project_info() {
    if [ -f "$PRD_FILE" ]; then
        local name=$(jq -r '.projectName // "Unknown"' "$PRD_FILE" 2>/dev/null)
        local stage=$(jq -r '.pipelineStage // 1' "$PRD_FILE" 2>/dev/null)
        local total=$(jq -r '.userStories | length' "$PRD_FILE" 2>/dev/null)
        local done=$(jq -r '[.userStories[] | select(.passes == true)] | length' "$PRD_FILE" 2>/dev/null)
        echo "$name (Stage $stage) - $done/$total stories complete"
    else
        echo "No PRD loaded"
    fi
}

# ==========================================
# MAIN EXECUTION
# ==========================================
run_claude_iteration() {
    local iteration="$1"

    # Build the Claude command
    local pending=$(get_pending_stories | head -1)

    if [ -z "$pending" ]; then
        log_info "No pending stories found."
        return 1
    fi

    log_info "Working on story: $pending"

    # Execute Claude CLI
    # Note: We use tee to capture output while also showing it live
    local claude_output
    claude_output=$(claude --print --verbose --dangerously-skip-permissions \
        "Read the PRD at $PRD_FILE. Execute the next pending user story (passes: false).
         Follow instructions in $PROMPT_FILE.
         Session: $SESSION_ID, Iteration: $iteration" 2>&1 | tee -a "$LOG_FILE") || true

    return 0
}

# ==========================================
# CLEANUP
# ==========================================
cleanup() {
    log_info "Factory Ralph shutting down..."

    # Final commit
    commit_iteration "$iteration" "shutdown"

    # Create session summary
    cat > "${LOG_DIR}/session_${SESSION_ID}_summary.json" << EOF
{
    "session_id": "$SESSION_ID",
    "started": "$(head -1 "$JSONL_LOG" | jq -r '.timestamp' 2>/dev/null || echo 'unknown')",
    "ended": "$(date -Iseconds)",
    "iterations_completed": $iteration,
    "max_iterations": $MAX_ITERATIONS,
    "log_file": "$LOG_FILE",
    "jsonl_log": "$JSONL_LOG"
}
EOF

    log_info "Session summary saved to ${LOG_DIR}/session_${SESSION_ID}_summary.json"
}

trap cleanup EXIT INT TERM

# ==========================================
# BANNER
# ==========================================
print_banner() {
    echo -e "${BOLD}${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║   ███████╗ █████╗  ██████╗████████╗ ██████╗ ██████╗ ██╗   ██╗║"
    echo "║   ██╔════╝██╔══██╗██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗╚██╗ ██╔╝║"
    echo "║   █████╗  ███████║██║        ██║   ██║   ██║██████╔╝ ╚████╔╝ ║"
    echo "║   ██╔══╝  ██╔══██║██║        ██║   ██║   ██║██╔══██╗  ╚██╔╝  ║"
    echo "║   ██║     ██║  ██║╚██████╗   ██║   ╚██████╔╝██║  ██║   ██║   ║"
    echo "║   ╚═╝     ╚═╝  ╚═╝ ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ║"
    echo "║                                                              ║"
    echo "║   ██████╗  █████╗ ██╗     ██████╗ ██╗  ██╗                   ║"
    echo "║   ██╔══██╗██╔══██╗██║     ██╔══██╗██║  ██║                   ║"
    echo "║   ██████╔╝███████║██║     ██████╔╝███████║                   ║"
    echo "║   ██╔══██╗██╔══██║██║     ██╔═══╝ ██╔══██║                   ║"
    echo "║   ██║  ██║██║  ██║███████╗██║     ██║  ██║                   ║"
    echo "║   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝                   ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo -e "${BOLD}Session:${NC} $SESSION_ID"
    echo -e "${BOLD}Max Iterations:${NC} $MAX_ITERATIONS"
    echo -e "${BOLD}Auto Level:${NC} $AUTO_LEVEL"
    echo -e "${BOLD}Log File:${NC} $LOG_FILE"
    echo -e "${BOLD}Project:${NC} $(get_project_info)"
    echo ""
}

# ==========================================
# MAIN LOOP
# ==========================================
main() {
    print_banner

    log_json "SESSION_START" "Factory Ralph initiated" "{\"max_iterations\":$MAX_ITERATIONS,\"auto_level\":\"$AUTO_LEVEL\"}"

    # Setup Git tracking
    setup_git_branch

    # Main iteration loop
    iteration=0

    while [ $iteration -lt $MAX_ITERATIONS ]; do
        ((iteration++))

        log_iteration $iteration

        # Check for pending work
        local pending=$(get_pending_stories)
        if [ -z "$pending" ]; then
            log_success "No pending stories. All work complete!"
            break
        fi

        # Run Claude iteration
        run_claude_iteration $iteration
        local exit_code=$?

        # Post-execution analysis

        # 1. Check for success flags
        if check_success_flag; then
            log_success "Task completed successfully!"
            commit_iteration $iteration "SUCCESS"
            break
        fi

        # 2. Check for critical failures (circuit breaker)
        if check_critical_failure; then
            log_error "Critical failure detected. Stopping loop."
            commit_iteration $iteration "CRITICAL_FAILURE"
            break
        fi

        # 3. Commit current state
        commit_iteration $iteration "in_progress"

        # 4. Monitor tool usage
        manage_tool_usage $iteration

        # 5. Manage visual/MCP assets
        manage_visual_assets $iteration

        # 6. Safety delay to prevent API rate limiting
        sleep 2

    done

    log_json "SESSION_END" "Factory Ralph completed" "{\"iterations\":$iteration,\"status\":\"complete\"}"

    echo ""
    echo -e "${BOLD}${GREEN}════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}  FACTORY RALPH COMPLETE${NC}"
    echo -e "${BOLD}${GREEN}  Iterations: $iteration / $MAX_ITERATIONS${NC}"
    echo -e "${BOLD}${GREEN}════════════════════════════════════════${NC}"
}

# Run main
main "$@"
