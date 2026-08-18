@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
  echo Python نصب نیست. صفحه نصب باز می‌شود.
  start https://www.python.org/downloads/
  pause
  exit /b 1
)
python -m pip install -q -r requirements.txt
start "" http://127.0.0.1:5000
python app.py
pause
