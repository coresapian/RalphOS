#!/bin/bash
# Fylo-Core-MCP Setup Script

set -e

echo "Setting up Fylo-Core-MCP..."

cd "$(dirname "$0")"

# Install dependencies
echo "Installing dependencies..."
npm install

# Build TypeScript
echo "Building TypeScript..."
npm run build

# Create data directory
echo "Creating data directory..."
mkdir -p ../data/fylo-graph

echo ""
echo "Setup complete!"
echo ""
echo "To add to Claude Code, run:"
echo "  claude mcp add --scope project fylo-core-mcp -- node fylo-core-mcp/build/index.js"
echo ""
echo "Or restart Claude Code to pick up the .mcp.json configuration."
