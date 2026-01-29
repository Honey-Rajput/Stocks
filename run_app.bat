@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Stock Agent - Streamlit App Launcher
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Python found
echo.

REM Navigate to project directory
cd /d "d:\Stock\New Stock project"
if errorlevel 1 (
    echo ERROR: Cannot find project directory
    pause
    exit /b 1
)

echo [OK] Changed to project directory
echo.

REM Check if requirements are installed
echo Checking dependencies...
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo [!] Streamlit not found, installing...
    pip install -r requirements.txt
)

echo.
echo ========================================
echo Starting Streamlit App...
echo ========================================
echo Opening browser to: http://localhost:8501
echo.

REM Run the app
python -m streamlit run src/app.py

pause
