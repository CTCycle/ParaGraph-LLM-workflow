@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM == Generic APP local launcher (Windows)
REM ============================================================================

set "project_folder=%~dp0"
set "root_folder=%project_folder%..\\"
set "settings_dir=%project_folder%settings"
set "frontend_dir=%project_folder%client"
set "dotenv=%settings_dir%\.env"
set "uvicorn_module=APP.server.app:app"

set "FASTAPI_HOST=127.0.0.1"
set "FASTAPI_PORT=8000"
set "UI_HOST=127.0.0.1"
set "UI_PORT=7861"
set "RELOAD=false"
set "OPTIONAL_DEPENDENCIES=false"

if exist "%dotenv%" (
  for /f "usebackq tokens=* delims=" %%L in ("%dotenv%") do (
    set "line=%%L"
    if not "!line!"=="" if "!line:~0,1!" NEQ "#" if "!line:~0,1!" NEQ ";" (
      for /f "tokens=1,* delims==" %%A in ("!line!") do (
        set "k=%%A"
        set "v=%%B"
        if defined v (
          for /f "tokens=* delims= " %%Q in ("!v!") do set "v=%%Q"
          set "v=!v:"=!"
          if "!v:~0,1!"=="'" if "!v:~-1!"=="'" set "v=!v:~1,-1!"
        )
        set "!k!=!v!"
      )
    )
  )
)

echo [STEP 1/4] Syncing backend dependencies with uv
pushd "%root_folder%" >nul
set "uv_extras="
if /i "%OPTIONAL_DEPENDENCIES%"=="true" set "uv_extras=--all-extras"
uv sync %uv_extras%
if not "%ERRORLEVEL%"=="0" (
  echo [FATAL] uv sync failed.
  popd >nul
  goto error
)
popd >nul

echo [STEP 2/4] Installing frontend dependencies
pushd "%frontend_dir%" >nul
if exist "package-lock.json" (
  call npm ci
) else (
  call npm install
)
if not "%ERRORLEVEL%"=="0" (
  popd >nul
  echo [FATAL] Frontend dependency installation failed.
  goto error
)

echo [STEP 3/4] Building frontend
call npm run build
if not "%ERRORLEVEL%"=="0" (
  popd >nul
  echo [FATAL] Frontend build failed.
  goto error
)
popd >nul

echo [STEP 4/4] Launching backend and frontend
set "RELOAD_FLAG="
if /i "%RELOAD%"=="true" set "RELOAD_FLAG=--reload"

call :kill_port %FASTAPI_PORT%
start "" /b uv run python -m uvicorn %uvicorn_module% --host %FASTAPI_HOST% --port %FASTAPI_PORT% %RELOAD_FLAG% --log-level info

call :kill_port %UI_PORT%
pushd "%frontend_dir%" >nul
start "" /b npm run preview -- --host %UI_HOST% --port %UI_PORT% --strictPort
popd >nul

start "" "http://%UI_HOST%:%UI_PORT%"
echo [SUCCESS] Backend and frontend started
goto end

:kill_port
set "target_port=%~1"
if not defined target_port goto :eof
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R ":%target_port%" ^| findstr LISTENING') do (
  taskkill /PID %%P /F >nul 2>&1
)
goto :eof

:error
echo.
echo !!! Launcher failed !!!
exit /b 1

:end
endlocal
