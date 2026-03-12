@echo off
REM ═════════════════════════════════════════════════════════════════════════════
REM   QUANTUM-RESISTANT BLOCKCHAIN + DASHBOARD LAUNCHER (Windows)
REM ═════════════════════════════════════════════════════════════════════════════
REM 
REM   This script starts both the blockchain system and the web dashboard.
REM   Requires: Python 3.8+, Flask
REM 
REM   Usage:
REM       launch_dashboard.bat
REM 
REM ═════════════════════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion

echo.
echo ════════════════════════════════════════════════════════════
echo   QUANTUM-RESISTANT BLOCKCHAIN - WEB DASHBOARD
echo   CRYSTALS-Kyber1024 + CRYSTALS-Dilithium3
echo ════════════════════════════════════════════════════════════
echo.

REM Check if Flask is installed
python -c "import flask" 2>nul
if errorlevel 1 (
    echo ⚠️  Flask not found. Installing...
    python -m pip install Flask==2.3.2
)

REM Check if blockchain.db exists
if not exist "blockchain.db" (
    echo.
    echo ⓘ blockchain.db not found.
    echo   Creating new blockchain by running main_v2.py...
    echo.
    python main_v2.py
    if errorlevel 1 (
        echo ❌ Failed to run main_v2.py
        pause
        exit /b 1
    )
)

echo.
echo ✓ Starting dashboard server...
echo.

REM Start dashboard in the current window
cd dashboard_app
python app.py

REM If we reach here, Flask was stopped
cd ..
echo.
echo Dashboard server stopped.
pause
