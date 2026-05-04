@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%venv"

echo ==========================================
echo    Qwen3-TTS API Server - Setup
echo ==========================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] python not found. Install Python 3.10+ and try again.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VERSION=%%v
echo [OK]    Python %PY_VERSION% detected

where sox >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [WARN]  sox not found. Required by librosa for audio processing.
    echo [INFO]  Installing sox via winget...
    winget install --id GnuWin32.SoX --accept-source-agreements --accept-package-agreements >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo [WARN]  Could not install sox automatically.
        echo         Download from https://sourceforge.net/projects/sox/ or install manually.
    ) else (
        echo [OK]    sox installed.
    )
)

for /f "tokens=3" %%a in ('dir "%SCRIPT_DIR%" /-c 2^>nul ^| findstr /c:"bytes free"') do set FREE_BYTES=%%a
if defined FREE_BYTES (
    set /a FREE_GB=%FREE_BYTES:~0,-9%
    if %FREE_GB% LSS 5 (
        echo [ERROR] Insufficient disk space for venv + dependencies.
        echo   Available: ~%FREE_GB% GB
        echo   Required:  ~5 GB
        pause
        exit /b 1
    )
    echo [OK]    ~%FREE_GB% GB available for venv + dependencies
)

if exist "%VENV_DIR%\Scripts\python.exe" (
    echo [INFO]  Virtual environment 'venv' already exists -- reusing it.
) else (
    echo [INFO]  Creating virtual environment 'venv'...
    python -m venv "%VENV_DIR%"
    echo [OK]    Virtual environment created.
)

echo [INFO]  Upgrading pip...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip --quiet

echo [INFO]  Installing dependencies from requirements.txt...
"%VENV_DIR%\Scripts\pip.exe" install -r "%SCRIPT_DIR%requirements.txt"

echo.
echo [OK]    All dependencies installed.
echo.
echo ==========================================
echo    Setup complete!
echo ==========================================
echo.
echo   Run the server with:
echo     start.bat
echo.

pause
endlocal
