@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ========================================================
echo        正在启动 Scrapy 版 Web 控制台（端口 5001）...
echo        旧项目界面在 5000 端口，请勿混淆
echo ========================================================
echo.
python web/server.py
pause
