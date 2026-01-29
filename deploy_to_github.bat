@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Stock Agent - GitHub Deployment Script
echo ========================================
echo.

REM Check if git is installed
git --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git is not installed
    echo Download from: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo [OK] Git found
echo.

REM Navigate to project directory
cd /d "d:\Stock\New Stock project"
if errorlevel 1 (
    echo ERROR: Cannot find project directory
    pause
    exit /b 1
)

echo ========================================
echo Checking Git Status
echo ========================================
git status
echo.

echo ========================================
echo Adding all changes
echo ========================================
git add .
echo [OK] All files staged

echo.
echo ========================================
echo Committing changes
echo ========================================
set /p commit_msg="Enter commit message (or press Enter for default): "
if "!commit_msg!"=="" (
    set commit_msg=Update stock agent with improved batch download and robustness
)

git commit -m "!commit_msg!"
if errorlevel 1 (
    echo [!] Nothing to commit (working tree clean)
) else (
    echo [OK] Changes committed
)

echo.
echo ========================================
echo Pushing to GitHub
echo ========================================
git push origin main
if errorlevel 1 (
    echo.
    echo [!] Push might have failed. Try:
    echo    1. Check your GitHub credentials
    echo    2. Verify your branch name (main/master)
    echo    3. Run: git push -u origin main
    pause
    exit /b 1
)

echo [OK] Successfully pushed to GitHub!
echo.
echo Visit: https://github.com/Honey-Rajput/Stocks
echo.
pause
