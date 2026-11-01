@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ===================================================
echo   teams-ai-workflow (OneDrive Queue + LM Studio)
echo ===================================================

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

python -m app.main %*
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] アプリケーションが異常終了しました (Code: %ERRORLEVEL%)
    pause
)

