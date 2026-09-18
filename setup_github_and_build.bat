@echo off
echo ============================================================
echo   VWAP Backtest Android APK - GitHub Setup
echo ============================================================
echo.

cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git is not installed. Download from https://git-scm.com
    pause
    exit /b 1
)

echo [1/5] Initialising git repository...
if not exist ".git" (
    git init
    git checkout -b main
) else (
    echo       Already a git repo. Skipping init.
)

echo [2/5] Staging all files...
git add .

echo [3/5] Creating first commit...
git diff --staged --quiet
if errorlevel 1 (
    git commit -m "Initial: VWAP Backtest Android App"
) else (
    echo       Nothing new to commit.
)

echo.
echo [4/5] Enter your GitHub repository URL below.
echo       Example: https://github.com/YourUsername/vwap-backtest-app.git
echo.
set /p REPO_URL=GitHub repo URL: 

if "%REPO_URL%"=="" (
    echo [ERROR] No URL entered. Exiting.
    pause
    exit /b 1
)

git remote remove origin 2>nul
git remote add origin %REPO_URL%

echo [5/5] Pushing to GitHub...
git push -u origin main

if errorlevel 1 (
    echo.
    echo [ERROR] Push failed. Make sure the repo exists on GitHub and you are authenticated.
    echo         Try: git config --global credential.helper manager
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   SUCCESS! Code pushed to GitHub.
echo.
echo   NEXT STEPS:
echo   1. Open %REPO_URL% in your browser
echo   2. Click the "Actions" tab
echo   3. The APK build starts automatically (takes ~25-35 min)
echo   4. When "Build Android APK" shows a green tick:
echo      - Click on it
echo      - Scroll down to "Artifacts"
echo      - Download "VWAP-Backtest-APK"
echo   5. Unzip the downloaded file to get the .apk
echo   6. Send the .apk to your Android phone
echo   7. On Android: Settings > Install Unknown Apps > Allow
echo   8. Tap the .apk to install. Done!
echo.
echo   Trade logs are saved to: /sdcard/trading_logs/YYYY-MM-DD.json
echo ============================================================
echo.
pause