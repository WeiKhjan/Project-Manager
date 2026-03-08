@echo off
echo ============================================================
echo   PROJECT MANAGER DASHBOARD
echo ============================================================
echo.
echo   Starting dashboard server on port 8100...
echo   URL: http://localhost:8100
echo.
echo   Press Ctrl+C to stop the server.
echo ============================================================
echo.

:: Try python first, then python3
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    start "" "http://localhost:8100"
    python "%~dp0server.py"
) else (
    where python3 >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        start "" "http://localhost:8100"
        python3 "%~dp0server.py"
    ) else (
        echo [ERROR] Python not found in PATH.
        echo         Please install Python 3.8+ and ensure it is on your PATH.
        echo.
        pause
    )
)
