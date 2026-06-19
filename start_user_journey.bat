@echo off
chcp 65001 >nul
cd /d "%~dp0"
pwsh -ExecutionPolicy Bypass -File "start_user_journey.ps1"
pause
