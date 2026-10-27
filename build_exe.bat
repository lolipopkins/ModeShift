@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
 echo Python is required. Install Python 3.11+ from python.org and enable the launcher.
 pause
 exit /b 1
)
py -3 -m venv .buildvenv
if errorlevel 1 goto :failed
call .buildvenv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
if errorlevel 1 goto :failed
python -m unittest discover -s tests -v
if errorlevel 1 goto :failed
python -m PyInstaller --noconfirm --clean --onefile --windowed --name ModeShift --icon assets\modeshift.ico --add-data "assets\modeshift.ico;assets" --collect-all psutil src\modeshift.py
if errorlevel 1 goto :failed
echo.
echo SUCCESS: %cd%\dist\ModeShift.exe
echo Open the dist folder to launch the standalone EXE.
start "" "%cd%\dist"
pause
exit /b 0
:failed
echo Build failed. Read the errors above.
pause
exit /b 1
