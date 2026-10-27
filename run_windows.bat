@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (echo Install Python 3.11+ first. & pause & exit /b 1)
py -3 -m pip install -r requirements-runtime.txt
py -3 src\modeshift.py
