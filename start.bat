@echo off
echo ==========================================
echo    Qwen3-TTS API Server - VRAM Pool
echo ==========================================
echo.
echo Modelos:
echo   - CustomVoice  (1.7B) HOT  en GPU  -> /v1/audio/speech
echo   - VoiceDesign  (1.7B) LAZY en GPU  -> /v1/audio/voice-design
echo   - Base/Clone   (1.7B) LAZY en GPU  -> /v1/audio/voice-clone
echo.
echo Los modelos lazy comparten VRAM: NUNCA estan ambos cargados a la vez.
echo Si se pide uno mientras el otro esta cargado, se descarga primero.
echo Se liberan tras 5 min de inactividad.
echo.
echo Press Ctrl+C to stop the server.
echo.
.\venv\Scripts\python.exe main.py
pause
