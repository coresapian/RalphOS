#!/bin/bash
# Ralph Dashboard Launcher

cd "$(dirname "${BASH_SOURCE[0]}")"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

clear
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  🤖 RALPH Dashboard Launcher${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Progress function
progress() {
    echo -e "  ${CYAN}▸${NC} $1"
}

done_msg() {
    echo -e "  ${GREEN}✓${NC} $1"
}

error_msg() {
    echo -e "  ${RED}✗${NC} $1"
}

# Step 1: Python
progress "Checking Python 3..."
sleep 0.2
if ! command -v python3 &> /dev/null; then
    error_msg "Python 3 not found"
    read -p "Press Enter to close..."
    exit 1
fi
done_msg "Python 3 ready"

# Step 2: Server file
progress "Locating server..."
sleep 0.2
DASHBOARD_SERVER="scripts/dashboard/dashboard_server.py"
if [ ! -f "$DASHBOARD_SERVER" ]; then
    error_msg "Server not found: $DASHBOARD_SERVER"
    read -p "Press Enter to close..."
    exit 1
fi
done_msg "Server found"

# Step 3: Virtual environment
progress "Checking environment..."
sleep 0.2
if [ -f ".venv/bin/activate" ]; then
    source ".venv/bin/activate"
    done_msg "Virtual environment activated"
elif [ -f "venv/bin/activate" ]; then
    source "venv/bin/activate"
    done_msg "Virtual environment activated"
else
    done_msg "Using system Python"
fi

# Step 4: Port check
progress "Checking port 8765..."
sleep 0.2
if lsof -Pi :8765 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo ""
    echo -e "  ${YELLOW}⚠ Port 8765 already in use${NC}"
    echo ""
    echo "    1) Kill existing & restart"
    echo "    2) Just open browser"
    echo "    3) Cancel"
    echo ""
    read -p "  Choice [1-3]: " choice
    echo ""
    
    case $choice in
        1)
            progress "Stopping existing server..."
            kill $(lsof -Pi :8765 -sTCP:LISTEN -t) 2>/dev/null
            sleep 1
            done_msg "Server stopped"
            ;;
        2)
            progress "Opening browser..."
            open "http://localhost:8765/" 2>/dev/null
            done_msg "Browser opened"
            echo ""
            exit 0
            ;;
        *)
            echo "Cancelled."
            exit 0
            ;;
    esac
else
    done_msg "Port 8765 available"
fi

# Step 5: Create logs dir
mkdir -p logs 2>/dev/null

# Step 6: Start server
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
progress "Starting server..."
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Start server
python3 "$DASHBOARD_SERVER"

# Handle exit
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ] && [ $EXIT_CODE -ne 130 ]; then
    echo ""
    error_msg "Server exited with error ($EXIT_CODE)"
    read -p "Press Enter to close..."
fi
