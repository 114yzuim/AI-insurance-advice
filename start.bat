@echo off
echo Stopping existing servers...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM python3.13.exe /T 2>nul
taskkill /F /IM node.exe /T 2>nul
timeout /t 1 /nobreak >nul

echo Starting AI-insurance-advice servers...
start "Backend - FastAPI" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --reload"
start "Frontend - Next.js" cmd /k "cd /d %~dp0frontend && npm run dev"
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
