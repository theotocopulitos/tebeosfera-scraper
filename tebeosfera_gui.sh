#!/bin/bash
# Launcher script for TebeoSfera GUI

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to script directory
cd "$SCRIPT_DIR"

# Run the GUI
python3 tebeosfera_gui.py "$@"
