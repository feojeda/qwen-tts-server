@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "HF_HOME=%SCRIPT_DIR%cache\hf"
set "HF_HUB_ENABLE_HF_TRANSFER=1"

echo ==========================================
echo    Qwen3-TTS API Server
echo ==========================================
echo.
echo Models cached in: %HF_HOME%
echo.

if exist "%SCRIPT_DIR%venv\Scripts\python.exe" (
    set "PYTHON=%SCRIPT_DIR%venv\Scripts\python.exe"
) else (
    echo ERROR: Virtual environment not found.
    echo Run setup first:  setup.bat
    pause
    exit /b 1
)

for /f "tokens=3" %%a in ('dir "%SCRIPT_DIR%" /-c 2^>nul ^| findstr /c:"bytes free"') do set FREE_BYTES=%%a
if defined FREE_BYTES (
    set /a FREE_GB=%FREE_BYTES:~0,-9%
    if %FREE_GB% LSS 10 (
        echo ERROR: Insufficient disk space for AI models.
        echo   Available: ~%FREE_GB% GB
        echo   Required:  ~10 GB
        echo.
        echo Models are cached in: %HF_HOME%
        echo Free up space or move HF_HOME to another drive.
        pause
        exit /b 1
    )
    echo Disk space: ~%FREE_GB% GB available
)

echo.
echo Checking models...
"%PYTHON%" "%SCRIPT_DIR%scripts/pre_download.py"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Model download failed. Check your connection and retry.
    pause
    exit /b 1
)

echo Starting server...
"%PYTHON%" "%SCRIPT_DIR%main.py"

pause
endlocal
