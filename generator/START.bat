@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python fehlt. Installieren von: https://www.python.org/downloads/
  echo WICHTIG: Beim Installieren den Haken "Add python.exe to PATH" setzen.
  echo.
  pause
  exit /b
)
python -m pip install --quiet --user pillow
python make_slides.py %1
start "" "%~dp0..\fertige_posts"
pause
