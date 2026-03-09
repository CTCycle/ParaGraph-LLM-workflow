@echo off
setlocal enabledelayedexpansion

set "project_folder=%~dp0"
set "root_folder=%project_folder%..\\"
set "log_path=%project_folder%resources\logs"
set "script_path=%project_folder%scripts\initialize_database.py"

:menu
cls
echo ==========================================================================
echo                        Setup and Maintenance
echo ==========================================================================
echo 1. Remove logs
echo 2. Uninstall local artifacts
echo 3. Initialize database
echo 4. Exit
echo.
set /p choice="Select an option (1-4): "

if "%choice%"=="1" goto :logs
if "%choice%"=="2" goto :uninstall
if "%choice%"=="3" goto :initdb
if "%choice%"=="4" goto :exit
echo Invalid option.
pause
goto :menu

:logs
if not exist "%log_path%" (
  echo [INFO] Log directory not found.
  pause
  goto :menu
)
del /q "%log_path%\*.log" >nul 2>&1
echo [INFO] Log cleanup completed.
pause
goto :menu

:uninstall
echo This removes local runtime/build artifacts for a clean re-bootstrap.
set /p confirm="Type YES to continue: "
if /i not "%confirm%"=="YES" goto :menu

if exist "%root_folder%.venv" rd /s /q "%root_folder%.venv"
if exist "%project_folder%client\node_modules" rd /s /q "%project_folder%client\node_modules"
if exist "%project_folder%client\dist" rd /s /q "%project_folder%client\dist"
if exist "%project_folder%resources\runtimes" rd /s /q "%project_folder%resources\runtimes"
if exist "%project_folder%resources\database\database.db" del /q "%project_folder%resources\database\database.db"

echo [SUCCESS] Uninstall completed.
pause
goto :menu

:initdb
if not exist "%script_path%" (
  echo [ERROR] Missing script: %script_path%
  pause
  goto :menu
)
pushd "%root_folder%" >nul
uv run python "%script_path%"
set "ec=%ERRORLEVEL%"
popd >nul
if "%ec%"=="0" (
  echo [SUCCESS] Database initialized.
) else (
  echo [ERROR] Database initialization failed with code %ec%.
)
pause
goto :menu

:exit
endlocal
