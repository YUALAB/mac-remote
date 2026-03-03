#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "========================================"
echo "  Mac Remote Control - Setup & Start"
echo "========================================"

# Install Python dependencies
echo ""
echo "[1/2] Installing dependencies..."
pip3 install -q flask flask-socketio simple-websocket

# Start server (pass all args through, e.g. --tunnel)
echo "[2/2] Starting server..."
echo ""
python3 server.py "$@"
