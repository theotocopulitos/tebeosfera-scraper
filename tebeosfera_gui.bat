@echo off
REM Launcher script for TebeoSfera GUI (Windows)

REM Change to script directory
cd /d "%~dp0"

REM Run the GUI
python3 tebeosfera_gui.py %*
