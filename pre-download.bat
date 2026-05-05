@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "HF_HOME=%SCRIPT_DIR%cache\hf"

echo ==========================================
echo    Qwen3-TTS — Pre-download Models
echo ==========================================
echo.
echo Cache directory: %HF_HOME%
echo.

if exist "%SCRIPT_DIR%venv\Scripts\python.exe" (
    set "PYTHON=%SCRIPT_DIR%venv\Scripts\python.exe"
) else (
    echo ERROR: Virtual environment not found.
    echo Run setup first:  setup.bat
    pause
    exit /b 1
)

"%PYTHON%" "%SCRIPT_DIR%scripts\pre_download.py" %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Some downloads failed. Re-run this script to resume.
    pause
)

endlocal
