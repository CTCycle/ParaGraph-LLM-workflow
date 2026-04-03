@echo off
setlocal EnableDelayedExpansion

REM ============================================================================
REM ParaGraph Test Runner
REM Full local test automation runner for Windows
REM ============================================================================

echo.
echo ============================================================
echo  ParaGraph All-Tests Runner
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI"
set "PARAGRAPH_DIR=%PROJECT_ROOT%\ParaGraph"
set "CLIENT_DIR=%PARAGRAPH_DIR%\client"
set "DOTENV=%PARAGRAPH_DIR%\settings\.env"
set "VENV_PYTHON=%PROJECT_ROOT%\runtimes\.venv\Scripts\python.exe"
set "EMBEDDED_NPM=%PROJECT_ROOT%\runtimes\nodejs\npm.cmd"
set "CLIENT_LOCKFILE=%CLIENT_DIR%\package-lock.json"
set "CLIENT_DIST=%CLIENT_DIR%\dist"
set "TESTS_E2E_DIR=%PROJECT_ROOT%\tests\e2e"

set "FASTAPI_HOST=127.0.0.1"
set "FASTAPI_PORT=8000"
set "UI_HOST=127.0.0.1"
set "UI_PORT=7861"

set "PARAGRAPH_SKIP_BACKEND=%PARAGRAPH_SKIP_BACKEND%"
set "PARAGRAPH_SKIP_FRONTEND=%PARAGRAPH_SKIP_FRONTEND%"
set "PARAGRAPH_SKIP_BOOTSTRAP=%PARAGRAPH_SKIP_BOOTSTRAP%"
set "PARAGRAPH_ENABLE_LIVE_E2E_SERVERS=%PARAGRAPH_ENABLE_LIVE_E2E_SERVERS%"
set "PARAGRAPH_FORCE_FRONTEND_BUILD=%PARAGRAPH_FORCE_FRONTEND_BUILD%"

if "%PARAGRAPH_SKIP_BACKEND%"=="" set "PARAGRAPH_SKIP_BACKEND=false"
if "%PARAGRAPH_SKIP_FRONTEND%"=="" set "PARAGRAPH_SKIP_FRONTEND=false"
if "%PARAGRAPH_SKIP_BOOTSTRAP%"=="" set "PARAGRAPH_SKIP_BOOTSTRAP=false"
if "%PARAGRAPH_ENABLE_LIVE_E2E_SERVERS%"=="" set "PARAGRAPH_ENABLE_LIVE_E2E_SERVERS=false"
if "%PARAGRAPH_FORCE_FRONTEND_BUILD%"=="" set "PARAGRAPH_FORCE_FRONTEND_BUILD=false"

set "BACKEND_PHASE=SKIPPED"
set "FRONTEND_BOOTSTRAP_PHASE=SKIPPED"
set "FRONTEND_UNIT_PHASE=SKIPPED"
set "FRONTEND_E2E_PHASE=SKIPPED"
set "LIVE_SERVER_PHASE=SKIPPED"
set "OVERALL_RESULT=0"

set "TEST_TARGET=%PROJECT_ROOT%\tests\unit"
if exist "%TESTS_E2E_DIR%" set "TEST_TARGET=%PROJECT_ROOT%\tests"
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

echo [INFO] Backend URL: %PARAGRAPH_TEST_BACKEND_URL%
echo [INFO] Frontend URL: %PARAGRAPH_TEST_FRONTEND_URL%
echo [INFO] Backend test target: %TEST_TARGET%
echo [INFO] Skip backend phase: %PARAGRAPH_SKIP_BACKEND%
echo [INFO] Skip frontend phase: %PARAGRAPH_SKIP_FRONTEND%
echo [INFO] Skip frontend bootstrap: %PARAGRAPH_SKIP_BOOTSTRAP%
echo [INFO] Enable live servers for tests/e2e: %PARAGRAPH_ENABLE_LIVE_E2E_SERVERS%
echo.

if exist "%VENV_PYTHON%" (
    set "PYTHON_CMD=%VENV_PYTHON%"
) else (
    echo [ERROR] Runtime .venv not found at "%VENV_PYTHON%".
    echo [ERROR] Run ParaGraph\start_on_windows.bat to create the environment.
    exit /b 1
)

if exist "%EMBEDDED_NPM%" (
    set "NPM_CMD=%EMBEDDED_NPM%"
) else (
    where npm >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] npm was not found.
        echo [ERROR] Install Node.js or ensure runtimes\nodejs is available.
        exit /b 1
    )
    set "NPM_CMD=npm"
)

"%PYTHON_CMD%" -c "import pytest" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] pytest is not installed in runtimes\.venv.
    echo [ERROR] Sync test dependencies first: uv sync --extra test
    exit /b 1
)

echo [INFO] Prerequisites verified.
echo.

set "STARTED_BACKEND=0"
set "STARTED_FRONTEND=0"

if /i "%PARAGRAPH_ENABLE_LIVE_E2E_SERVERS%"=="true" if exist "%TESTS_E2E_DIR%" (
    set "LIVE_SERVER_PHASE=PASS"
    echo [INFO] Checking live server availability for tests/e2e...

    set "BACKEND_RUNNING=0"
    set "FRONTEND_RUNNING=0"
    curl -s --max-time 2 %PARAGRAPH_TEST_BACKEND_URL%/docs >nul 2>&1
    if %ERRORLEVEL% equ 0 set "BACKEND_RUNNING=1"
    curl -s --max-time 2 %PARAGRAPH_TEST_FRONTEND_URL% >nul 2>&1
    if %ERRORLEVEL% equ 0 set "FRONTEND_RUNNING=1"

    if "!BACKEND_RUNNING!"=="0" (
        echo [INFO] Starting backend server...
        start "" /B /D "%PROJECT_ROOT%" "%PYTHON_CMD%" -m uvicorn ParaGraph.server.app:app --host %FASTAPI_HOST% --port %FASTAPI_PORT%
        set "STARTED_BACKEND=1"
    )

    if "!FRONTEND_RUNNING!"=="0" (
        if /i "%PARAGRAPH_SKIP_BOOTSTRAP%"=="false" (
            if not exist "%CLIENT_DIR%\node_modules" (
                echo [INFO] Installing frontend dependencies before preview startup...
                pushd "%CLIENT_DIR%" >nul
                if exist "%CLIENT_LOCKFILE%" (
                    call "%NPM_CMD%" ci
                ) else (
                    call "%NPM_CMD%" install
                )
                set "INSTALL_RC=!ERRORLEVEL!"
                popd >nul
                if not "!INSTALL_RC!"=="0" (
                    set "LIVE_SERVER_PHASE=FAIL"
                    set "OVERALL_RESULT=1"
                    echo [ERROR] Frontend dependency install failed with code !INSTALL_RC!.
                    goto cleanup
                )
            )
            if not exist "%CLIENT_DIST%" (
                echo [INFO] Building frontend before preview startup...
                pushd "%CLIENT_DIR%" >nul
                call "%NPM_CMD%" run build
                set "BUILD_RC=!ERRORLEVEL!"
                popd >nul
                if not "!BUILD_RC!"=="0" (
                    set "LIVE_SERVER_PHASE=FAIL"
                    set "OVERALL_RESULT=1"
                    echo [ERROR] Frontend build failed with code !BUILD_RC!.
                    goto cleanup
                )
            )
        )

        echo [INFO] Starting frontend preview server...
        start "" /B /D "%CLIENT_DIR%" cmd /c ""%NPM_CMD%" run preview -- --host %UI_HOST% --port %UI_PORT%"
        set "STARTED_FRONTEND=1"
    )

    echo [INFO] Waiting for live servers to be ready...
    set "ATTEMPTS=0"
    :wait_for_live_servers
    if !ATTEMPTS! geq 30 (
        set "LIVE_SERVER_PHASE=FAIL"
        set "OVERALL_RESULT=1"
        echo [ERROR] Live servers failed to start within 30 seconds.
        goto cleanup
    )

    curl -s --max-time 2 %PARAGRAPH_TEST_BACKEND_URL%/docs >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        set /a ATTEMPTS+=1
        timeout /t 1 /nobreak >nul
        goto wait_for_live_servers
    )
    curl -s --max-time 2 %PARAGRAPH_TEST_FRONTEND_URL% >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        set /a ATTEMPTS+=1
        timeout /t 1 /nobreak >nul
        goto wait_for_live_servers
    )

    echo [INFO] Live servers are ready.
    echo.
) else (
    if /i "%PARAGRAPH_ENABLE_LIVE_E2E_SERVERS%"=="true" (
        echo [INFO] Live server phase skipped: tests/e2e does not exist.
    ) else (
        echo [INFO] Live server phase skipped.
    )
)

echo ============================================================
echo  Running Test Phases
echo ============================================================
echo.

if /i "%PARAGRAPH_SKIP_BACKEND%"=="true" (
    echo [INFO] Backend phase skipped by PARAGRAPH_SKIP_BACKEND=true.
    set "BACKEND_PHASE=SKIPPED"
) else (
    echo [INFO] Running backend tests with pytest...
    cd /d "%PROJECT_ROOT%"
    "%PYTHON_CMD%" -m pytest "%TEST_TARGET%" -v --tb=short %*
    set "BACKEND_RC=!ERRORLEVEL!"
    if "!BACKEND_RC!"=="0" (
        set "BACKEND_PHASE=PASS"
    ) else (
        set "BACKEND_PHASE=FAIL"
        set "OVERALL_RESULT=1"
    )
    echo.
)

if /i "%PARAGRAPH_SKIP_FRONTEND%"=="true" (
    echo [INFO] Frontend phases skipped by PARAGRAPH_SKIP_FRONTEND=true.
    set "FRONTEND_BOOTSTRAP_PHASE=SKIPPED"
    set "FRONTEND_UNIT_PHASE=SKIPPED"
    set "FRONTEND_E2E_PHASE=SKIPPED"
    goto summary
)

if not exist "%CLIENT_DIR%\package.json" (
    echo [INFO] Frontend phase skipped: missing %CLIENT_DIR%\package.json.
    set "FRONTEND_BOOTSTRAP_PHASE=SKIPPED"
    set "FRONTEND_UNIT_PHASE=SKIPPED"
    set "FRONTEND_E2E_PHASE=SKIPPED"
    goto summary
)

set "FRONTEND_HAS_UNIT_TESTS=0"
set "FRONTEND_HAS_E2E_TESTS=0"
findstr /R /C:"\"test:unit\"[ ]*:" "%CLIENT_DIR%\package.json" >nul 2>&1
if %ERRORLEVEL% equ 0 set "FRONTEND_HAS_UNIT_TESTS=1"
findstr /R /C:"\"test:e2e\"[ ]*:" "%CLIENT_DIR%\package.json" >nul 2>&1
if %ERRORLEVEL% equ 0 set "FRONTEND_HAS_E2E_TESTS=1"

if /i "%PARAGRAPH_SKIP_BOOTSTRAP%"=="true" (
    echo [INFO] Frontend bootstrap skipped by PARAGRAPH_SKIP_BOOTSTRAP=true.
    set "FRONTEND_BOOTSTRAP_PHASE=SKIPPED"
) else (
    echo [INFO] Ensuring frontend dependencies and build prerequisites...
    pushd "%CLIENT_DIR%" >nul

    if not exist "%CLIENT_DIR%\node_modules" (
        echo [INFO] Installing frontend dependencies...
        if exist "%CLIENT_LOCKFILE%" (
            call "%NPM_CMD%" ci
        ) else (
            call "%NPM_CMD%" install
        )
        set "FRONTEND_INSTALL_RC=!ERRORLEVEL!"
        if not "!FRONTEND_INSTALL_RC!"=="0" (
            popd >nul
            set "FRONTEND_BOOTSTRAP_PHASE=FAIL"
            set "OVERALL_RESULT=1"
            echo [ERROR] Frontend dependency install failed with code !FRONTEND_INSTALL_RC!.
            goto summary
        )
    )

    set "NEED_BUILD=0"
    if "!FRONTEND_HAS_E2E_TESTS!"=="1" if not exist "%CLIENT_DIST%" set "NEED_BUILD=1"
    if /i "%PARAGRAPH_FORCE_FRONTEND_BUILD%"=="true" set "NEED_BUILD=1"
    if "!NEED_BUILD!"=="1" (
        echo [INFO] Building frontend...
        call "%NPM_CMD%" run build
        set "FRONTEND_BUILD_RC=!ERRORLEVEL!"
        if not "!FRONTEND_BUILD_RC!"=="0" (
            popd >nul
            set "FRONTEND_BOOTSTRAP_PHASE=FAIL"
            set "OVERALL_RESULT=1"
            echo [ERROR] Frontend build failed with code !FRONTEND_BUILD_RC!.
            goto summary
        )
    ) else (
        echo [INFO] Frontend build not required for this run.
    )

    popd >nul
    set "FRONTEND_BOOTSTRAP_PHASE=PASS"
)

if "!FRONTEND_HAS_UNIT_TESTS!"=="1" (
    echo [INFO] Running frontend unit tests...
    pushd "%CLIENT_DIR%" >nul
    call "%NPM_CMD%" run test:unit --if-present
    set "FRONTEND_UNIT_RC=!ERRORLEVEL!"
    popd >nul
    if "!FRONTEND_UNIT_RC!"=="0" (
        set "FRONTEND_UNIT_PHASE=PASS"
    ) else (
        set "FRONTEND_UNIT_PHASE=FAIL"
        set "OVERALL_RESULT=1"
    )
) else (
    echo [INFO] Frontend unit tests skipped: script "test:unit" not present.
    set "FRONTEND_UNIT_PHASE=SKIPPED"
)

if "!FRONTEND_HAS_E2E_TESTS!"=="1" (
    echo [INFO] Running frontend E2E tests...
    pushd "%CLIENT_DIR%" >nul
    call "%NPM_CMD%" run test:e2e --if-present
    set "FRONTEND_E2E_RC=!ERRORLEVEL!"
    popd >nul
    if "!FRONTEND_E2E_RC!"=="0" (
        set "FRONTEND_E2E_PHASE=PASS"
    ) else (
        set "FRONTEND_E2E_PHASE=FAIL"
        set "OVERALL_RESULT=1"
    )
) else (
    echo [INFO] Frontend E2E tests skipped: script "test:e2e" not present.
    set "FRONTEND_E2E_PHASE=SKIPPED"
)

:summary
echo.
echo ============================================================
echo  Phase Summary
echo ============================================================
echo  Live server phase   : %LIVE_SERVER_PHASE%
echo  Backend tests       : %BACKEND_PHASE%
echo  Frontend bootstrap  : %FRONTEND_BOOTSTRAP_PHASE%
echo  Frontend unit tests : %FRONTEND_UNIT_PHASE%
echo  Frontend E2E tests  : %FRONTEND_E2E_PHASE%
echo ============================================================
echo.

:cleanup
if "%STARTED_BACKEND%"=="1" (
    echo [INFO] Stopping backend server started by this runner...
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%FASTAPI_PORT% ^| findstr LISTENING') do (
        taskkill /F /PID %%a >nul 2>&1
    )
)

if "%STARTED_FRONTEND%"=="1" (
    echo [INFO] Stopping frontend server started by this runner...
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%UI_PORT% ^| findstr LISTENING') do (
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo.
if "%OVERALL_RESULT%"=="0" (
    echo [INFO] All enabled test phases completed successfully.
) else (
    echo [ERROR] One or more test phases failed.
)
echo.

exit /b %OVERALL_RESULT%
