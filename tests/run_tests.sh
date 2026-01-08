#!/bin/bash
# Test runner script for RalphOS

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$TEST_DIR/.." && pwd)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  RalphOS Test Suite${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Run all tests
run_test() {
    local test_file=$1
    local test_name=$(basename "$test_file" .py)
    
    echo -e "${YELLOW}Running: ${test_name}${NC}"
    
    if python3 "$test_file" -v; then
        echo -e "${GREEN}✓ ${test_name} passed${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ ${test_name} failed${NC}"
        echo ""
        return 1
    fi
}

FAILED=0

# Unit tests
echo -e "${BLUE}Unit Tests${NC}"
echo -e "${BLUE}-----------${NC}"
echo ""

run_test "$TEST_DIR/test_checkpoint_manager.py" || FAILED=$((FAILED + 1))
run_test "$TEST_DIR/test_source_discovery.py" || FAILED=$((FAILED + 1))
run_test "$TEST_DIR/test_parallel_processor.py" || FAILED=$((FAILED + 1))

# Integration tests
echo -e "${BLUE}Integration Tests${NC}"
echo -e "${BLUE}-----------------${NC}"
echo ""

run_test "$TEST_DIR/test_integration.py" || FAILED=$((FAILED + 1))

# Summary
echo -e "${BLUE}========================================${NC}"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✓${NC}"
    echo -e "${BLUE}========================================${NC}"
    exit 0
else
    echo -e "${RED}$FAILED test(s) failed ✗${NC}"
    echo -e "${BLUE}========================================${NC}"
    exit 1
fi
