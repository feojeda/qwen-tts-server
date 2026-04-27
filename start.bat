@echo off
setlocal

REM Set HuggingFace cache to project folder (E: drive) instead of C:
set "SCRIPT_DIR=%~dp0"
set "HF_HOME=%SCRIPT_DIR%cache\hf"

REM Also set TRANSFORMERS_CACHE for older libraries
set "TRANSFORMERS_CACHE=%HF_HOME%"

echo ==========================================
echo    Qwen3-TTS API Server
echo ==========================================
echo.
echo IMPORTANT: This server downloads AI models on first run.
echo - CustomVoice (1.7B): ~3.4 GB download on first startup
echo - VoiceDesign (1.7B): ~3.4 GB download on first use
echo - Base/Clone  (1.7B): ~3.4 GB download on first use
echo.
echo Models are cached in: %HF_HOME%
echo After first download, startup is instant.
echo.
echo Press any key to start the server...
pause >nul
echo.
echo Starting server...

.\venv\Scripts\python.exe main.py

pause
endlocal
