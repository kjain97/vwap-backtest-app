[app]
title = VWAP Backtest Engine
package.name = vwapbacktest
package.domain = org.tradingbot
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0.0
requirements = python3,kivy==2.3.0
orientation = portrait
fullscreen = 0
android.presplash_color = #1a1a2e
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,FOREGROUND_SERVICE,WAKE_LOCK
android.api = 34
android.minapi = 24
android.ndk = 25b
android.sdk = 34
android.accept_sdk_license = True
android.logcat_filters = *:S python:D
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1