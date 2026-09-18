# VWAP Backtest Engine - Android App

A standalone Android application for backtesting the VWAP Strangle strategy.

## Features
- Dark-mode trading dashboard
- Live candle-by-candle backtest replay
- Trade log saved to `/sdcard/trading_logs/YYYY-MM-DD.json`
- Multiple built-in sample datasets (17-Sep SENSEX, 15-Sep NIFTY)
- Runs as foreground service (stays alive in background)

## How to Build the APK

### Prerequisites
- GitHub account (free)
- Android phone with "Install Unknown Apps" enabled

### Step 1: Create a GitHub Repo
1. Go to https://github.com/new
2. Name it `vwap-backtest-app`
3. Set to **Private** (recommended for trading code)
4. Do NOT initialise with README
5. Click **Create repository**

### Step 2: Run the Setup Script
On your Windows PC, double-click:
```
setup_github_and_build.bat
```
Paste your repo URL when prompted (e.g. `https://github.com/YourName/vwap-backtest-app.git`)

### Step 3: Download the APK
1. Go to your repo on GitHub
2. Click the **Actions** tab
3. Wait for "Build Android APK" to show a green tick (~25-35 minutes)
4. Click on the workflow run
5. Scroll to **Artifacts** section
6. Download **VWAP-Backtest-APK**

### Step 4: Install on Android
1. Unzip the downloaded file to get `*.apk`
2. Send the APK to your phone (WhatsApp, email, or USB)
3. On Android: **Settings > Apps > Special Access > Install Unknown Apps**
4. Tap the APK file and install

## Trade Logs
Logs are saved at: `/sdcard/trading_logs/YYYY-MM-DD.json`

Access them using:
- Files app on Android
- Or connect via USB and browse the `trading_logs` folder

Each log contains the full event stream and trade summary for AI review.

## App Usage
| Button | Action |
|--------|--------|
| ▶ RUN | Start the backtest for the selected dataset |
| ⏹ STOP | Stop the running backtest |
| ⇄ DATASET | Switch between available sample sessions |
| 📋 LOGS | View saved trade log files |