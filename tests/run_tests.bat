@echo off
setlocal EnableDelayedExpansion

REM ============================================================================
REM ParaGraph Test Runner
REM Automated backend test execution for Windows
REM ============================================================================

echo.
echo ============================================================
echo  ParaGraph Test Runner
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI"
set "PARAGRAPH_DIR=%PROJECT_ROOT%\ParaGraph"
set "DOTENV=%PARAGRAPH_DIR%\settings\.env"
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "FASTAPI_HOST=127.0.0.1"
set "FASTAPI_PORT=8000"
set "UI_HOST=127.0.0.1"
set "UI_PORT=7861"
set "OPTIONAL_DEPENDENCIES=false"
set "TEST_TARGET=%PROJECT_ROOT%\tests\unit"
set "TEST_RESULT=1"

if defined PARAGRAPH_TEST_TARGET set "TEST_TARGET=%PARAGRAPH_TEST_TARGET%"

REM Load runtime settings from .env if present
if exist "%DOTENV%" (
    for /f "usebackq tokens=* delims=" %%A in ("%DOTENV%") do (
        set "line=%%A"
        if not "!line!"=="" if "!line:~0,1!" NEQ "#" if "!line:~0,1!" NEQ ";" (
            for /f "tokens=1* delims==" %%K in ("!line!") do (
                set "k=%%K"
                set "v=%%L"
                if defined v (
                    if "!v:~0,1!"=="\"" set "v=!v:~1,-1!"
                    if "!v:~0,1!"=="'" set "v=!v:~1,-1!"
                )

                if /i "!k!"=="OPTIONAL_DEPENDENCIES" set "OPTIONAL_DEPENDENCIES=!v!"
                if /i "!k!"=="FASTAPI_HOST" set "FASTAPI_HOST=!v!"
                if /i "!k!"=="FASTAPI_PORT" set "FASTAPI_PORT=!v!"
                if /i "!k!"=="UI_HOST" set "UI_HOST=!v!"
                if /i "!k!"=="UI_PORT" set "UI_PORT=!v!"
            )
        )
    )
)

set "BACKEND_CLIENT_HOST=%FASTAPI_HOST%"
if /i "%BACKEND_CLIENT_HOST%"=="0.0.0.0" set "BACKEND_CLIENT_HOST=127.0.0.1"
if /i "%BACKEND_CLIENT_HOST%"=="::" set "BACKEND_CLIENT_HOST=127.0.0.1"
if /i "%BACKEND_CLIENT_HOST%"=="[::]" set "BACKEND_CLIENT_HOST=127.0.0.1"
if "%BACKEND_CLIENT_HOST%"=="" set "BACKEND_CLIENT_HOST=127.0.0.1"

set "FRONTEND_CLIENT_HOST=%UI_HOST%"
if /i "%FRONTEND_CLIENT_HOST%"=="0.0.0.0" set "FRONTEND_CLIENT_HOST=127.0.0.1"
if /i "%FRONTEND_CLIENT_HOST%"=="::" set "FRONTEND_CLIENT_HOST=127.0.0.1"
if /i "%FRONTEND_CLIENT_HOST%"=="[::]" set "FRONTEND_CLIENT_HOST=127.0.0.1"
if "%FRONTEND_CLIENT_HOST%"=="" set "FRONTEND_CLIENT_HOST=127.0.0.1"

set "PARAGRAPH_TEST_BACKEND_URL=http://%BACKEND_CLIENT_HOST%:%FASTAPI_PORT%"
set "PARAGRAPH_TEST_FRONTEND_URL=http://%FRONTEND_CLIENT_HOST%:%UI_PORT%"

echo [INFO] Default backend URL: %PARAGRAPH_TEST_BACKEND_URL%
echo [INFO] Default frontend URL: %PARAGRAPH_TEST_FRONTEND_URL%
echo [INFO] Test target: %TEST_TARGET%

if exist "%VENV_PYTHON%" (
    set "PYTHON_CMD=%VENV_PYTHON%"
) else (
    echo [ERROR] .venv not found at "%VENV_PYTHON%".
    echo [ERROR] Run ParaGraph\start_on_windows.bat to create the environment.
    exit /b 1
)

"%PYTHON_CMD%" -c "import pytest" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] pytest is not installed in .venv.
    echo [ERROR] Sync the test extra first: uv sync --extra test
    echo [ERROR] Or set OPTIONAL_DEPENDENCIES=true and run ParaGraph\start_on_windows.bat.
    exit /b 1
)

if /i "%OPTIONAL_DEPENDENCIES%"=="true" (
    "%PYTHON_CMD%" -c "import psutil" >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] psutil is not installed in .venv.
        echo [ERROR] Sync the test extra first: uv sync --extra test
        exit /b 1
    )
)

echo.
echo [INFO] Prerequisites verified.
echo.

echo ============================================================
echo  Running Tests
echo ============================================================
echo.

cd /d "%PROJECT_ROOT%"
"%PYTHON_CMD%" -m pytest "%TEST_TARGET%" -v --tb=short %*
set "TEST_RESULT=%ERRORLEVEL%"

echo.
echo ============================================================
if %TEST_RESULT% equ 0 (
    echo  All tests PASSED
) else (
    echo  Some tests FAILED
)
echo ============================================================
echo.

exit /b %TEST_RESULT%
