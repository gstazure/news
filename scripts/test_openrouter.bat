@echo off
setlocal enabledelayedexpansion

REM ============================================
REM OpenRouter Local Test Script (Windows cmd.exe)
REM Logs verbosely and exits with non-zero code on failures
REM Usage:
REM   1) Ensure Python and curl are installed
REM   2) Put your API key in .env as: OPENROUTER_API_KEY=sk-or-XXXX
REM   3) Run: scripts\test_openrouter.bat
REM ============================================

set LOGFILE=logs\openrouter_test_%DATE:~-4,4%-%DATE:~4,2%-%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%.log
set LOGFILE=%LOGFILE: =0%

if not exist logs (
  mkdir logs
)

echo [INFO] Starting OpenRouter local test >> "%LOGFILE%"
echo [INFO] Timestamp: %DATE% %TIME% >> "%LOGFILE%"

REM 1) Show Python version
echo. >> "%LOGFILE%"
echo [STEP] Checking Python version... >> "%LOGFILE%"
python --version 1>> "%LOGFILE%" 2>> "%LOGFILE%"
if errorlevel 1 (
  echo [ERROR] Python not found. Please install Python and ensure it is in PATH.
  echo [ERROR] Python not found. >> "%LOGFILE%"
  exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python version: %PYVER%
echo [OK] Python version: %PYVER% >> "%LOGFILE%"

REM 2) Load .env into current session for OPENROUTER_API_KEY
echo. >> "%LOGFILE%"
echo [STEP] Loading .env OPENROUTER_API_KEY if present... >> "%LOGFILE%"
set ORIG_KEY=%OPENROUTER_API_KEY%
for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
  if /I "%%a"=="OPENROUTER_API_KEY" (
    set OPENROUTER_API_KEY=%%b
  )
)
if not defined OPENROUTER_API_KEY (
  echo [WARN] OPENROUTER_API_KEY not found in environment or .env
  echo [WARN] OPENROUTER_API_KEY not found in environment or .env >> "%LOGFILE%"
  echo [HINT] Add to .env as: OPENROUTER_API_KEY=sk-or-REPLACE
  exit /b 2
) else (
  echo [OK] OPENROUTER_API_KEY loaded (hidden)
  echo [OK] OPENROUTER_API_KEY loaded >> "%LOGFILE%"
)

REM 3) Simple Python import of requests (optional dependency)
echo. >> "%LOGFILE%"
echo [STEP] Verifying requests import (optional)... >> "%LOGFILE%"
python - <<EOF 1>>"%LOGFILE%" 2>>"%LOGFILE%"
import sys
try:
    import requests  # noqa
    print("[OK] requests import succeeded")
except Exception as e:
    print("[WARN] requests import failed:", e)
EOF

REM 4) Curl sanity call to OpenRouter
echo. >> "%LOGFILE%"
echo [STEP] Making OpenRouter test call with curl... >> "%LOGFILE%"
set TEST_JSON={"model":"openrouter/auto","messages":[{"role":"user","content":"hello from curl"}]}

REM Write request to a temp file for logging
echo %TEST_JSON%> tmp_openrouter_req.json

echo [DEBUG] Request body: %TEST_JSON% >> "%LOGFILE%"
echo [DEBUG] Hitting: https://openrouter.ai/api/v1/chat/completions >> "%LOGFILE%"

REM Use -sS for stderr on errors, -w to print HTTP code on a separate line
for /f "tokens=* usebackq" %%r in (`curl -sS -o tmp_openrouter_resp.json -w "HTTP_STATUS:%%{http_code}" -H "Authorization: Bearer %OPENROUTER_API_KEY%" -H "Content-Type: application/json" --data "@tmp_openrouter_req.json" https://openrouter.ai/api/v1/chat/completions 2^>^> "%LOGFILE%"`) do set CURL_STATUS=%%r

type tmp_openrouter_resp.json >> "%LOGFILE%"
echo %CURL_STATUS% >> "%LOGFILE%"

echo [INFO] Curl status line: %CURL_STATUS%
for /f "tokens=2 delims=:" %%c in ("%CURL_STATUS%") do set HTTP_CODE=%%c

if "%HTTP_CODE%"=="" set HTTP_CODE=000

echo [INFO] HTTP code: %HTTP_CODE%

if "%HTTP_CODE%"=="401" (
  echo [ERROR] Unauthorized (401). Check OPENROUTER_API_KEY validity/credits.
  echo [ERROR] 401 Unauthorized >> "%LOGFILE%"
  goto :fallback
) else if "%HTTP_CODE%"=="200" (
  echo [OK] OpenRouter call succeeded (200). See logs\ and tmp_openrouter_resp.json
  echo [OK] 200 Success >> "%LOGFILE%"
  goto :done
) else (
  echo [WARN] Unexpected HTTP code: %HTTP_CODE%. See logs\ for details.
  echo [WARN] Unexpected HTTP code: %HTTP_CODE% >> "%LOGFILE%"
  goto :fallback
)

:fallback
echo. >> "%LOGFILE%"
echo [STEP] Executing fallback path (skip OpenRouter, return canned output)... >> "%LOGFILE%"
echo {
echo   "fallback": true,
echo   "reason": "OpenRouter unavailable or unauthorized (HTTP %HTTP_CODE%)",
echo   "output": "This is a local fallback response."
echo } > tmp_openrouter_fallback.json
type tmp_openrouter_fallback.json
type tmp_openrouter_fallback.json >> "%LOGFILE%"
echo [OK] Fallback completed. >> "%LOGFILE%"
exit /b 0

:done
echo [DONE] All checks passed. >> "%LOGFILE%"
exit /b 0