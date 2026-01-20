#!/bin/bash
# ==========================================
# Factory Ralph Setup Verification Script
# ==========================================
# Verifies that all Factory Ralph components are properly installed
# and configured for autonomous operation.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RALPH_DIR="$PROJECT_ROOT/scripts/ralph"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}${NC}"
echo -e "${CYAN} Factory Ralph Setup Verification${NC}"
echo -e "${CYAN}${NC}"
echo ""ERRORS=0
WARNINGS=0

# ==========================================
# Helper Functions
# ==========================================

check_pass() {
 echo -e "${GREEN}${NC} $1"
}

check_fail() {
 echo -e "${RED}${NC} $1"
 ((ERRORS++))
}

check_warn() {
 echo -e "${YELLOW}${NC} $1"
 ((WARNINGS++))
}

# ==========================================
# 1. Core Files Check
# ==========================================

echo -e "${CYAN}[1/7] Checking Core Files...${NC}"

# Factory Ralph script
if [ -f "$RALPH_DIR/run_factory_ralph.sh" ]; then
 if [ -x "$RALPH_DIR/run_factory_ralph.sh" ]; then
 check_pass "run_factory_ralph.sh exists and is executable"
 else
 check_warn "run_factory_ralph.sh exists but not executable"
 chmod +x "$RALPH_DIR/run_factory_ralph.sh"
 check_pass "Fixed: Made executable"
 fi
else
 check_fail "run_factory_ralph.sh not found"
fi

# Ralph utils
if [ -f "$RALPH_DIR/ralph_utils.py" ]; then
 check_pass "ralph_utils.py exists"
else
 check_fail "ralph_utils.py not found"
fi

# Ralph DuckDB
if [ -f "$RALPH_DIR/ralph_duckdb.py" ]; then
 check_pass "ralph_duckdb.py exists"
else
 check_fail "ralph_duckdb.py not found"
fi

# Ralph VLM
if [ -f "$RALPH_DIR/ralph_vlm.py" ]; then
 check_pass "ralph_vlm.py exists"
else
 check_fail "ralph_vlm.py not found"
fi

# Ralph Validator
if [ -f "$RALPH_DIR/ralph_validator.py" ]; then
 check_pass "ralph_validator.py exists"
else
 check_fail "ralph_validator.py not found"
fi

# Ralph MCP
if [ -f "$RALPH_DIR/ralph_mcp.py" ]; then
 check_pass "ralph_mcp.py exists"
else
 check_fail "ralph_mcp.py not found"
fi

# Browser Helper
if [ -f "$PROJECT_ROOT/scripts/tools/browser_helper.js" ]; then
 check_pass "browser_helper.js exists"
else
 check_fail "browser_helper.js not found"
fi

# TOOLS.md
if [ -f "$RALPH_DIR/TOOLS.md" ]; then
 check_pass "TOOLS.md exists"
else
 check_warn "TOOLS.md not found (documentation)"
fi

echo ""# ==========================================
# 2. Python Dependencies Check
# ==========================================

echo -e "${CYAN}[2/7] Checking Python Dependencies...${NC}"

# Python 3
if command -v python3 &> /dev/null; then
 PYTHON_VERSION=$(python3 --version 2>&1)
 check_pass "Python 3 installed: $PYTHON_VERSION"
else
 check_fail "Python 3 not found"
fi

# Check core Python packages
python3 << 'EOF'
import sys
errors = []

# Required packages
packages = [
 ('requests', 'HTTP client'),
 ('json', 'JSON handling (stdlib)'),
 ('pathlib', 'Path handling (stdlib)'),
]

# Optional but recommended
optional = [
 ('duckdb', 'DuckDB database'),
 ('pandas', 'Data manipulation'),
 ('PIL', 'Image handling (Pillow)'),
 ('transformers', 'Hugging Face Transformers'),
 ('torch', 'PyTorch'),
 ('bs4', 'BeautifulSoup'),
]

print("Required packages:")
for pkg, desc in packages:
 try:
 __import__(pkg)
 print(f" {pkg}: {desc}")
 except ImportError:
 print(f" {pkg}: {desc} - MISSING")
 errors.append(pkg)

print("\nOptional packages:")
for pkg, desc in optional:
 try:
 __import__(pkg.split('.')[0])
 print(f" {pkg}: {desc}")
 except ImportError:
 print(f" {pkg}: {desc} - not installed")

sys.exit(len(errors))
EOF

if [ $? -eq 0 ]; then
 check_pass "All required Python packages installed"
else
 check_fail "Missing required Python packages"
fi

echo ""# ==========================================
# 3. Ollama Check (for VLM)
# ==========================================

echo -e "${CYAN}[3/7] Checking Ollama (VLM Backend)...${NC}"

if command -v ollama &> /dev/null; then
 check_pass "Ollama installed"

 # Check if service is running
 if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
 check_pass "Ollama service is running"

 # Check for moondream model
 if curl -s http://localhost:11434/api/tags | grep -q "moondream"; then
 check_pass "Moondream model available"
 else
 check_warn "Moondream model not found. Run: ollama pull moondream"
 fi
 else
 check_warn "Ollama installed but service not running. Start with: ollama serve"
 fi
else
 check_warn "Ollama not installed. VLM will use Hugging Face fallback."
 echo " Install from: https://ollama.com"
fi

echo ""# ==========================================
# 4. DuckDB Check
# ==========================================

echo -e "${CYAN}[4/7] Checking DuckDB...${NC}"

python3 << 'EOF'
try:
 import duckdb
 print(f" DuckDB installed: v{duckdb.__version__}")

 # Quick functionality test
 con = duckdb.connect(":memory:")
 con.execute("CREATE TABLE test AS SELECT * FROM range(10)")
 result = con.execute("SELECT COUNT(*) FROM test").fetchone()
 if result[0] == 10:
 print(" DuckDB functionality OK")
 con.close()
except ImportError:
 print(" DuckDB not installed. Run: pip install duckdb")
 exit(1)
except Exception as e:
 print(f" DuckDB error: {e}")
 exit(1)
EOF

if [ $? -eq 0 ]; then
 check_pass "DuckDB operational"
else
 check_warn "DuckDB not available"
fi

echo ""# ==========================================
# 5. Browser Tools Check
# ==========================================

echo -e "${CYAN}[5/7] Checking Browser Tools...${NC}"

# Node.js
if command -v node &> /dev/null; then
 NODE_VERSION=$(node --version 2>&1)
 check_pass "Node.js installed: $NODE_VERSION"
else
 check_warn "Node.js not installed (required for browser tools)"
fi

# Chrome DevTools scripts
BROWSER_DIR="$PROJECT_ROOT/scripts/tools/browser"
if [ -d "$BROWSER_DIR" ]; then
 check_pass "Browser tools directory exists"

 for script in start.js nav.js eval.js screenshot.js; do
 if [ -f "$BROWSER_DIR/$script" ]; then
 check_pass " $script exists"
 else
 check_warn " $script not found"
 fi
 done
else
 check_warn "Browser tools directory not found"
fi

echo ""# ==========================================
# 6. Git Check
# ==========================================

echo -e "${CYAN}[6/7] Checking Git Configuration...${NC}"

if command -v git &> /dev/null; then
 check_pass "Git installed"

 # Check if in a repo
 if git rev-parse --git-dir > /dev/null 2>&1; then
 check_pass "Inside a Git repository"

 # Check for uncommitted changes
 if git diff-index --quiet HEAD -- 2>/dev/null; then
 check_pass "Working tree is clean"
 else
 check_warn "Uncommitted changes detected"
 fi
 else
 check_warn "Not inside a Git repository"
 fi
else
 check_fail "Git not installed"
fi

echo ""# ==========================================
# 7. Claude CLI Check
# ==========================================

echo -e "${CYAN}[7/7] Checking Claude CLI...${NC}"

if command -v claude &> /dev/null; then
 check_pass "Claude CLI installed"
else
 check_fail "Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
fi

echo ""# ==========================================
# Summary
# ==========================================

echo -e "${CYAN}${NC}"
echo -e "${CYAN} Verification Summary${NC}"
echo -e "${CYAN}${NC}"
echo ""if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
 echo -e "${GREEN} All checks passed! Factory Ralph is ready.${NC}"
 echo ""echo "To start Factory Ralph:"
 echo " ./scripts/ralph/run_factory_ralph.sh 25"
 exit 0
elif [ $ERRORS -eq 0 ]; then
 echo -e "${YELLOW} $WARNINGS warning(s) found, but no critical errors.${NC}"
 echo "Factory Ralph can run but some features may be limited."
 exit 0
else
 echo -e "${RED} $ERRORS error(s) and $WARNINGS warning(s) found.${NC}"
 echo "Please fix the errors before running Factory Ralph."
 exit 1
fi
