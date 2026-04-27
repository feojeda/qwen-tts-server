@echo off
echo ==========================================
echo    Qwen3-TTS API Server
echo ==========================================
echo.
echo IMPORTANT: This server downloads AI models on first run.
echo - CustomVoice (1.7B): ~3.4 GB download on first startup
echo - VoiceDesign (1.7B): ~3.4 GB download on first use
echo - Base/Clone (1.7B): ~3.4 GB download on first use
echo.
echo Models are cached in: %%USERPROFILE%%\.cache\huggingface\hub\
echo After first download, startup is instant.
echo.
echo Press any key to start the server...
pause >nul
echo.
echo Starting server...
.\venv\Scripts\python.exe main.py
pause
