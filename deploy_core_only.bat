@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Stock Agent - Selective GitHub Deploy
echo ========================================
echo.
echo Deploying only core files:
echo   - src/
echo   - requirements.txt
echo   - .gitignore
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
echo Current Git Status
echo ========================================
git status
echo.

echo ========================================
echo Staging ONLY core files
echo ========================================
git add src/
echo [OK] Added: src/

git add requirements.txt
echo [OK] Added: requirements.txt

git add .gitignore
echo [OK] Added: .gitignore

echo.
echo ========================================
echo Files staged for commit
echo ========================================
git diff --cached --name-only
echo.

echo ========================================
echo Committing changes
echo ========================================
set /p commit_msg="Enter commit message: "
if "!commit_msg!"=="" (
    set commit_msg=Update stock agent with improved batch download robustness
)

git commit -m "!commit_msg!"
if errorlevel 1 (
    echo [!] Nothing new to commit
    pause
    exit /b 1
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
    echo [!] Push failed. Trying master branch...
    git push origin master
    if errorlevel 1 (
        echo [ERROR] Push failed on both main and master
        echo Try running manually: git push -u origin main
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo SUCCESS! Deployed to GitHub
echo ========================================
echo Repository: https://github.com/Honey-Rajput/Stocks
echo.
pause
