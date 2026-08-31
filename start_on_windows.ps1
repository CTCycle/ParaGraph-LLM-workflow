[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$script:RepoRoot = $PSScriptRoot
$script:AppDir = Join-Path $RepoRoot 'app'
$script:ServerDir = Join-Path $AppDir 'server'
$script:ClientDir = Join-Path $AppDir 'client'
$script:TestsDir = Join-Path $AppDir 'tests'
$script:SettingsDir = Join-Path $RepoRoot 'settings'
$script:DefaultResourcesDir = Join-Path $AppDir 'resources'
$script:RuntimesDir = Join-Path $RepoRoot 'runtimes'
$script:PythonDir = Join-Path $RuntimesDir 'python'
$script:PythonExe = Join-Path $PythonDir 'python.exe'
$script:PythonPth = Join-Path $PythonDir 'python314._pth'
$script:UvDir = Join-Path $RuntimesDir 'uv'
$script:UvExe = Join-Path $UvDir 'uv.exe'
$script:NodeDir = Join-Path $RuntimesDir 'nodejs'
$script:NodeExe = Join-Path $NodeDir 'node.exe'
$script:NpmCmd = Join-Path $NodeDir 'npm.cmd'
$script:VenvDir = Join-Path $ServerDir '.venv'
$script:VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$script:RuntimeCacheDir = Join-Path $RuntimesDir 'cache'
$script:TestCacheDir = Join-Path $TestsDir 'cache'
$script:UvCacheDir = Join-Path $RuntimeCacheDir 'uv'
$script:PythonCacheDir = Join-Path $RuntimeCacheDir 'pycache'
$script:NpmCacheDir = Join-Path $RuntimeCacheDir 'npm'
$script:PytestCacheDir = Join-Path $TestCacheDir 'pytest'
$script:PytestTempDir = Join-Path $TestCacheDir 'pytest-tmp'
$script:RuffCacheDir = Join-Path $TestCacheDir 'ruff'
$script:CoverageDir = Join-Path $TestCacheDir 'coverage'
$script:CoverageFile = Join-Path $CoverageDir '.coverage'
$script:PlaywrightDir = Join-Path $TestCacheDir 'playwright'
$script:PlaywrightBrowsersDir = Join-Path $PlaywrightDir 'browsers'
$script:ViteCacheDir = Join-Path $TestCacheDir 'vite'
$script:VitestCacheDir = Join-Path $TestCacheDir 'vitest'
$script:FrontendBuildDir = Join-Path $TestCacheDir 'frontend-dist'
$script:DotEnv = Join-Path $SettingsDir '.env'
$script:DotEnvExample = Join-Path $SettingsDir '.env.example'
$script:PythonVersion = '3.14.2'
$script:NodeVersion = '22.12.0'
$script:SkippedCacheCount = 0
$script:FirstSkippedCachePath = $null

#region Console and menu helpers

function Write-Step([string]$Message) { Write-Host "[STEP] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Info([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor DarkCyan }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Fatal([string]$Message) { Write-Host "[FATAL] $Message" -ForegroundColor Red }

function Write-MenuDivider {
    Write-Host ('-' * 70) -ForegroundColor DarkGray
}

function Write-MenuOption {
    param(
        [Parameter(Mandatory = $true)][string]$Number,
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][string]$Description,
        [switch]$Destructive
    )
    $numberColor = if ($Destructive) { 'DarkYellow' } else { 'Cyan' }
    $titleColor = if ($Destructive) { 'Yellow' } else { 'White' }
    Write-Host (("  [{0}]" -f $Number).PadRight(7)) -ForegroundColor $numberColor -NoNewline
    Write-Host (" {0} " -f $Title.PadRight(34)) -ForegroundColor $titleColor -NoNewline
    Write-Host $Description -ForegroundColor DarkGray
}

function Read-InstallationType {
    Write-Host '  [1] Development - include Ruff, Pyright, and pytest'
    Write-Host '  [2] Standard    - install runtime dependencies only'
    $selection = (Read-Host '  Select installation profile [1-2]').Trim()
    switch ($selection) {
        '1' { return 'Development' }
        '2' { return 'Standard' }
        default { throw 'Invalid installation profile. Enter 1 for Development or 2 for Standard.' }
    }
}

function Show-Menu {
    Clear-Host
    Write-Host
    Write-Host '  PARAGRAPH' -ForegroundColor Cyan
    Write-Host '  LLM Workflow' -ForegroundColor White
    Write-Host '  Local workspace control center' -ForegroundColor DarkGray
    Write-Host
    Write-MenuDivider
    Write-Host '  APPLICATION' -ForegroundColor DarkCyan
    Write-MenuDivider
    Write-MenuOption -Number '1' -Title 'Launch Application' -Description 'Start the backend and frontend'
    Write-Host
    Write-Host '  SETUP AND DEVELOPMENT' -ForegroundColor DarkCyan
    Write-MenuDivider
    Write-MenuOption -Number '2' -Title 'Install or Update Dependencies' -Description 'Sync runtimes, database, and UI build'
    Write-MenuOption -Number '3' -Title 'Rebuild Frontend' -Description 'Build the frontend only'
    Write-MenuOption -Number '4' -Title 'Initialize or Upgrade Database' -Description 'Apply SQLite/Alembic migrations'
    Write-MenuOption -Number '5' -Title 'Run Test Suite' -Description 'Execute project checks'
    Write-Host
    Write-Host '  SOURCE CONTROL' -ForegroundColor DarkCyan
    Write-MenuDivider
    Write-MenuOption -Number '6' -Title 'Update from Main' -Description 'Pull latest code from origin/main'
    Write-MenuOption -Number '7' -Title 'Check for Updates' -Description 'Report origin/main status only'
    Write-Host
    Write-Host '  MAINTENANCE AND DATA' -ForegroundColor DarkCyan
    Write-MenuDivider
    Write-MenuOption -Number '8' -Title 'Remove Log Files' -Description 'Delete local application logs'
    Write-MenuOption -Number '9' -Title 'Clear Runtime Cache' -Description 'Remove runtime and test/tool caches'
    Write-MenuOption -Number '10' -Title 'Remove All Data' -Description 'Delete user data and database' -Destructive
    Write-Host
    Write-Host '  APPLICATION REMOVAL' -ForegroundColor DarkCyan
    Write-MenuDivider
    Write-MenuOption -Number '11' -Title 'Uninstall Application' -Description 'Remove local runtimes and packages' -Destructive
    Write-MenuOption -Number '12' -Title 'Exit' -Description 'Close this launcher'
    Write-MenuDivider
    Write-Host '  Enter a number to continue. Remove All Data requires explicit confirmation.' -ForegroundColor DarkGray
    Write-Host
}

#endregion

#region Environment and dependency setup

function Clear-PythonEnvironment {
    foreach ($name in 'PYTHONHOME', 'PYTHONPATH', 'PYTHONNOUSERSITE') {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
        Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
    }
}

function Set-LauncherEnvironment {
    New-Item -ItemType Directory -Path @(
        $RuntimeCacheDir,
        $UvCacheDir,
        $PythonCacheDir,
        $NpmCacheDir,
        $TestCacheDir,
        $PytestCacheDir,
        $PytestTempDir,
        $RuffCacheDir,
        $CoverageDir,
        $PlaywrightBrowsersDir,
        $ViteCacheDir,
        $VitestCacheDir,
        $FrontendBuildDir
    ) -Force | Out-Null
    $env:UV_CACHE_DIR = $UvCacheDir
    $env:UV_PROJECT_ENVIRONMENT = $VenvDir
    $env:UV_LINK_MODE = 'copy'
    $env:PYTHONPYCACHEPREFIX = $PythonCacheDir
    $env:RUFF_CACHE_DIR = $RuffCacheDir
    $env:COVERAGE_FILE = $CoverageFile
    $env:npm_config_cache = $NpmCacheDir
    $env:PLAYWRIGHT_BROWSERS_PATH = $PlaywrightBrowsersDir
    $env:PATH = "$NodeDir;$($env:PATH)"
    Clear-PythonEnvironment
}

function Invoke-DownloadAndExtract {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$ArchivePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )
    New-Item -ItemType Directory -Path (Split-Path -Parent $ArchivePath) -Force | Out-Null
    New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null
    Invoke-WebRequest -Uri $Uri -OutFile $ArchivePath
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $DestinationPath -Force
    Remove-Item -LiteralPath $ArchivePath -Force
}

function Invoke-PatchPth {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (Test-Path -LiteralPath $Path) {
        (Get-Content -LiteralPath $Path) -replace '^#import site$', 'import site' |
            Set-Content -LiteralPath $Path
    }
}

function Invoke-CheckPyVer {
    param([Parameter(Mandatory = $true)][string]$PythonExe)
    & $PythonExe -c 'import platform; print(platform.python_version())'
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Find-UvExecutable {
    param([Parameter(Mandatory = $true)][string]$SearchPath)
    $uv = Get-ChildItem -LiteralPath $SearchPath -Recurse -Filter 'uv.exe' -File |
        Select-Object -First 1
    if ($null -eq $uv) { throw "uv.exe was not found under $SearchPath" }
    return $uv.FullName
}

function Invoke-HealthCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$Attempts = 60,
        [int]$IntervalSeconds = 1
    )
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) { return $true }
        } catch { }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds $IntervalSeconds }
    }
    return $false
}

function Ensure-PortableRuntimes {
    New-Item -ItemType Directory -Path $RuntimesDir, $PythonDir, $UvDir, $NodeDir -Force | Out-Null

    Write-Step 'Setting up Python (embeddable) locally'
    if (-not (Test-Path -LiteralPath $PythonExe)) {
        $pythonZipName = "python-$PythonVersion-embed-amd64.zip"
        $pythonZip = Join-Path $PythonDir $pythonZipName
        $pythonUrl = "https://www.python.org/ftp/python/$PythonVersion/$pythonZipName"
        Write-Info "Downloading $pythonUrl"
        Invoke-DownloadAndExtract -Uri $pythonUrl -ArchivePath $pythonZip -DestinationPath $PythonDir
    }
    Invoke-PatchPth -Path $PythonPth
    $foundVersion = Invoke-CheckPyVer -PythonExe $PythonExe
    Write-Ok "Python ready: $foundVersion"

    Write-Step 'Installing uv (portable)'
    if (-not (Test-Path -LiteralPath $UvExe)) {
        $uvArchive = Join-Path $UvDir 'uv.zip'
        $uvTarget = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
            'uv-aarch64-pc-windows-msvc.zip'
        } else {
            'uv-x86_64-pc-windows-msvc.zip'
        }
        $uvUrl = "https://github.com/astral-sh/uv/releases/latest/download/$uvTarget"
        Write-Info "Downloading $uvUrl"
        Invoke-DownloadAndExtract -Uri $uvUrl -ArchivePath $uvArchive -DestinationPath $UvDir
        $foundUv = Find-UvExecutable -SearchPath $UvDir
        if ([IO.Path]::GetFullPath($foundUv) -ne [IO.Path]::GetFullPath($UvExe)) {
            Copy-Item -LiteralPath $foundUv -Destination $UvExe -Force
        }
    }
    $uvVersion = & $UvExe --version
    if ($LASTEXITCODE -ne 0) { throw 'uv failed its version check.' }
    Write-Ok $uvVersion

    Ensure-NodeRuntime
    Write-Ok 'Portable runtimes ready.'
}

function Import-DotEnv {
    $values = [ordered]@{}
    if (-not (Test-Path -LiteralPath $DotEnv)) {
        if (-not (Test-Path -LiteralPath $DotEnvExample)) {
            throw "Missing environment template: $DotEnvExample"
        }
        Copy-Item -LiteralPath $DotEnvExample -Destination $DotEnv
        Write-Info "Created $DotEnv from .env.example."
    }
    foreach ($rawLine in Get-Content -LiteralPath $DotEnv) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith('#') -or $line.StartsWith(';')) { continue }
        $separator = $line.IndexOf('=')
        if ($separator -lt 1) { continue }
        $key = $line.Substring(0, $separator).Trim()
        $value = $line.Substring($separator + 1).Trim().Trim('"').Trim("'")
        $values[$key] = $value
        [Environment]::SetEnvironmentVariable($key, $value, 'Process')
    }
    foreach ($requiredKey in @(
        'FASTAPI_HOST', 'FASTAPI_PORT', 'UI_HOST', 'UI_PORT', 'RELOAD', 'BACKEND_LOGS_VISIBLE'
    )) {
        if (-not $values.Contains($requiredKey) -or [string]::IsNullOrWhiteSpace([string]$values[$requiredKey])) {
            throw "Environment file is missing required setting: $requiredKey"
        }
    }
    return $values
}

function Sync-Dependencies {
    param(
        [switch]$PruneCache,
        [ValidateSet('Standard', 'Development')]
        [string]$InstallationType = 'Standard'
    )
    if (-not (Test-Path -LiteralPath (Join-Path $ServerDir 'pyproject.toml'))) {
        throw "Missing pyproject.toml in $ServerDir"
    }
    Write-Step 'Installing Python dependencies with uv'
    $uvArgs = @('sync', '--python', $PythonExe)
    if ($InstallationType -eq 'Development') { $uvArgs += '--all-extras' }
    Push-Location $ServerDir
    try {
        & $UvExe @uvArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Warn 'uv sync failed; recreating the project virtual environment once.'
            if (Test-Path -LiteralPath $VenvDir) { Remove-Item -LiteralPath $VenvDir -Recurse -Force }
            & $UvExe @uvArgs
            if ($LASTEXITCODE -ne 0) { throw "uv sync failed with exit code $LASTEXITCODE" }
        }
    } finally { Pop-Location }

    Write-Step 'Installing frontend dependencies'
    Push-Location $ClientDir
    try {
        if (Test-Path -LiteralPath (Join-Path $ClientDir 'package-lock.json')) {
            & $NpmCmd ci
        } else {
            & $NpmCmd install
        }
        if ($LASTEXITCODE -ne 0) { throw "npm dependency installation failed with exit code $LASTEXITCODE" }
    } finally { Pop-Location }

    if ($PruneCache) {
        Write-Step 'Pruning uv cache'
        if (-not (Clear-CacheDirectory -Path $UvCacheDir)) {
            Write-Warn "Some uv cache entries could not be removed: $UvCacheDir"
        }
    }
    Write-Ok 'Dependencies are ready.'
}

function Build-Frontend {
    Write-Step 'Building frontend'
    Push-Location $ClientDir
    try {
        & $NpmCmd run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with exit code $LASTEXITCODE" }
    } finally { Pop-Location }
    Write-Ok 'Frontend build is ready.'
}

function Ensure-NodeRuntime {
    New-Item -ItemType Directory -Path $NodeDir -Force | Out-Null

    Write-Step 'Installing Node.js (portable)'
    if (-not (Test-Path -LiteralPath $NodeExe)) {
        $nodeZipName = "node-v$NodeVersion-win-x64.zip"
        $nodeZip = Join-Path $NodeDir $nodeZipName
        $nodeUrl = "https://nodejs.org/dist/v$NodeVersion/$nodeZipName"
        Write-Info "Downloading $nodeUrl"
        Invoke-DownloadAndExtract -Uri $nodeUrl -ArchivePath $nodeZip -DestinationPath $NodeDir
    }
    $nestedNodeDir = Join-Path $NodeDir "node-v$NodeVersion-win-x64"
    if (Test-Path -LiteralPath (Join-Path $nestedNodeDir 'node.exe')) {
        Get-ChildItem -LiteralPath $nestedNodeDir -Force | Move-Item -Destination $NodeDir -Force
        Remove-Item -LiteralPath $nestedNodeDir -Recurse -Force
    }
    if (-not (Test-Path -LiteralPath $NodeExe)) { throw "node.exe not found at $NodeExe" }
    if (-not (Test-Path -LiteralPath $NpmCmd)) { throw "npm.cmd not found at $NpmCmd" }
    $nodeVersionFound = & $NodeExe --version
    if ($LASTEXITCODE -ne 0) { throw 'Node.js failed its version check.' }
    Write-Ok "Node.js ready: $nodeVersionFound"
    Set-LauncherEnvironment
}

function Invoke-FrontendRebuild {
    Ensure-NodeRuntime
    Import-DotEnv | Out-Null
    Build-Frontend
}

function Test-DependenciesReady {
    $frontendPackage = Join-Path $ClientDir 'package.json'
    $frontendLock = Join-Path $ClientDir 'package-lock.json'
    $frontendModules = Join-Path $ClientDir 'node_modules'
    $frontendInstallState = Join-Path $frontendModules '.package-lock.json'
    $frontendRunner = Join-Path $frontendModules '.bin\vite.cmd'
    $backendEntrypoint = Join-Path $ServerDir 'app.py'

    if (-not (Test-Path -LiteralPath $PythonExe) -or
        -not (Test-Path -LiteralPath $UvExe) -or
        -not (Test-Path -LiteralPath $NodeExe) -or
        -not (Test-Path -LiteralPath $NpmCmd) -or
        -not (Test-Path -LiteralPath $VenvPython) -or
        -not (Test-Path -LiteralPath $backendEntrypoint) -or
        -not (Test-Path -LiteralPath $frontendPackage) -or
        -not (Test-Path -LiteralPath $frontendLock) -or
        -not (Test-Path -LiteralPath $frontendInstallState) -or
        -not (Test-Path -LiteralPath $frontendRunner)) {
        return $false
    }

    & $PythonExe --version *> $null
    if ($LASTEXITCODE -ne 0) { return $false }
    & $UvExe --version *> $null
    if ($LASTEXITCODE -ne 0) { return $false }
    & $NodeExe --version *> $null
    if ($LASTEXITCODE -ne 0) { return $false }
    & $VenvPython -c 'import fastapi, uvicorn' *> $null
    if ($LASTEXITCODE -ne 0) { return $false }

    return $true
}

function Test-FrontendBuildReady {
    return Test-Path -LiteralPath (Join-Path $FrontendBuildDir 'index.html')
}

function Stop-PortListeners([int]$Port) {
    $pids = netstat -ano | ForEach-Object {
        if ($_ -match "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$") { [int]$Matches[1] }
    } | Sort-Object -Unique
    foreach ($processId in $pids) {
        Write-Info "Releasing port $Port from PID $processId."
        & taskkill.exe /PID $processId /F | Out-Null
    }
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        $stillListening = netstat -ano | Select-String -Pattern "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+\d+\s*$"
        if (-not $stillListening) { return }
        Start-Sleep -Seconds 1
    }
    throw "Port $Port is still occupied after 20 seconds."
}

function Get-ListenerPid([int]$Port) {
    foreach ($line in netstat -ano) {
        if ($line -match "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$") {
            return [int]$Matches[1]
        }
    }
    return $null
}

#endregion

#region Application lifecycle and verification

function Invoke-Launch {
    Ensure-PortableRuntimes
    $settings = Import-DotEnv
    Set-LauncherEnvironment
    $dependenciesReady = Test-DependenciesReady
    $frontendBuildReady = Test-FrontendBuildReady
    if (-not $dependenciesReady -or -not $frontendBuildReady) {
        if (-not $dependenciesReady) {
            Write-Step 'Required application environments are missing or unusable; installing dependencies.'
            Sync-Dependencies -InstallationType 'Standard'
        }
        if (-not $frontendBuildReady) {
            Write-Step 'Frontend build is missing; rebuilding frontend.'
        }
        Build-Frontend
    }
    else {
        Write-Ok 'Application environments are ready; skipped dependency installation.'
    }
    if (-not (Test-Path -LiteralPath $VenvPython)) { throw "Virtual environment Python not found at $VenvPython" }

    $backendPort = [int]$settings.FASTAPI_PORT
    $uiPort = [int]$settings.UI_PORT
    Stop-PortListeners -Port $backendPort
    Stop-PortListeners -Port $uiPort
    Clear-PythonEnvironment

    $backendArgs = @('-m', 'uvicorn', 'server.app:app', '--host', [string]$settings.FASTAPI_HOST, '--port', [string]$backendPort, '--log-level', 'info')
    if ([string]$settings.RELOAD -ieq 'true') { $backendArgs += '--reload' }
    Write-Step "Launching backend on $($settings.FASTAPI_HOST):$backendPort"
    if ([string]$settings.BACKEND_LOGS_VISIBLE -ieq 'true') {
        $quotedPython = '"' + $VenvPython + '"'
        $backendCommand = "$quotedPython $($backendArgs -join ' ')"
        Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d', '/c', 'start', '"ParaGraph Backend Logs"', 'cmd.exe', '/k', $backendCommand) -WorkingDirectory $AppDir | Out-Null
    } else {
        $stdout = Join-Path $env:TEMP 'paragraph-backend.stdout.log'
        $stderr = Join-Path $env:TEMP 'paragraph-backend.stderr.log'
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
        Start-Process -FilePath $VenvPython -ArgumentList $backendArgs -WorkingDirectory $AppDir -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr | Out-Null
    }

    $healthUrl = "http://$($settings.FASTAPI_HOST):$backendPort/docs"
    Write-Info "Waiting for $healthUrl"
    if (-not (Invoke-HealthCheck -Url $healthUrl -Attempts 60 -IntervalSeconds 1)) {
        Stop-PortListeners -Port $backendPort
        throw "Backend did not become healthy at $healthUrl within 60 seconds."
    }

    Write-Step "Launching frontend preview on $($settings.UI_HOST):$uiPort"
    $frontend = Start-Process -FilePath $NpmCmd -ArgumentList @('run', 'preview', '--', '--host', [string]$settings.UI_HOST, '--port', [string]$uiPort, '--strictPort') -WorkingDirectory $ClientDir -WindowStyle Hidden -PassThru
    $uiUrl = "http://$($settings.UI_HOST):$uiPort"
    Start-Process $uiUrl
    Start-Sleep -Milliseconds 500
    $backendPid = Get-ListenerPid -Port $backendPort
    Write-Ok 'ParaGraph started successfully.'
    Write-Host "  Backend: $healthUrl (PID $backendPid)"
    Write-Host "  Frontend: $uiUrl (PID $($frontend.Id))"
}

function Invoke-DatabaseInitialization {
    Ensure-PortableRuntimes
    Set-LauncherEnvironment
    $arguments = @('run', '--project', (Join-Path $AppDir 'server'), '--python', $PythonExe, 'python', '-m', 'scripts.initialize_database')
    Push-Location $AppDir
    try {
        & $UvExe @arguments
        if ($LASTEXITCODE -ne 0) { throw "Database initialization failed with exit code $LASTEXITCODE" }
    } finally { Pop-Location }
    Write-Ok 'SQLite database migration check completed.'
}

function Invoke-TestSuite {
    $testScript = Join-Path $AppDir 'tests\run_tests.bat'
    if (-not (Test-Path -LiteralPath $testScript)) { throw "Missing test script: $testScript" }
    & cmd.exe /c $testScript
    if ($LASTEXITCODE -ne 0) { throw "Test suite failed with exit code $LASTEXITCODE" }
    Write-Ok 'Test suite completed.'
}

#endregion

#region Maintenance and data management

function Remove-LogFiles {
    $logDir = Join-Path $AppDir 'resources\logs'
    if (-not (Test-Path -LiteralPath $logDir)) { Write-Info "Log directory not found: $logDir"; return }
    Get-ChildItem -LiteralPath $logDir -Filter '*.log' -File -ErrorAction SilentlyContinue | Remove-Item -Force
    Write-Ok 'Log files removed.'
}

function Resolve-ResourcesRoot {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Settings)

    $configuredRoot = [string]$Settings['PARAGRAPH_RESOURCES_DIR']
    if ([string]::IsNullOrWhiteSpace($configuredRoot)) {
        return [IO.Path]::GetFullPath($DefaultResourcesDir)
    }

    $expandedRoot = [Environment]::ExpandEnvironmentVariables($configuredRoot.Trim())
    if (-not [IO.Path]::IsPathRooted($expandedRoot)) {
        $expandedRoot = Join-Path $RepoRoot $expandedRoot
    }
    return [IO.Path]::GetFullPath($expandedRoot)
}

function Confirm-DataRemoval {
    $confirmation = (Read-Host '  Type REMOVE to delete all user data').Trim()
    return $confirmation -ieq 'REMOVE'
}

function Remove-AllData {
    $settings = Import-DotEnv
    $resourceRoot = Resolve-ResourcesRoot -Settings $settings
    Write-Warn "This removes user data under $resourceRoot and the application database."
    Write-Info 'Built-in node definitions, workflow templates, settings, and application source files will be preserved.'
    if (-not (Confirm-DataRemoval)) {
        Write-Info 'Remove All Data cancelled.'
        return
    }

    $script:SkippedCacheCount = 0
    $script:FirstSkippedCachePath = $null
    $allRemoved = $true

    foreach ($relativePath in @(
        'artifacts', 'logs', 'models'
    )) {
        $dataPath = Join-Path $resourceRoot $relativePath
        if (-not (Clear-CacheDirectory -Path $dataPath -PreserveNames @('.gitkeep'))) {
            $allRemoved = $false
        }
    }

    $customNodesPath = Join-Path $resourceRoot 'nodes\custom_nodes'
    if (-not (Clear-CacheDirectory -Path $customNodesPath -PreserveNames @('.gitkeep', 'README.md'))) {
        $allRemoved = $false
    }

    if (Test-Path -LiteralPath $resourceRoot -PathType Container -ErrorAction SilentlyContinue) {
        $databaseFiles = @(Get-ChildItem -LiteralPath $resourceRoot -File -Force -Filter 'database.db*' -ErrorAction SilentlyContinue)
        foreach ($databaseFile in $databaseFiles) {
            if (-not (Remove-PathBestEffort -Path $databaseFile.FullName)) { $allRemoved = $false }
        }
    }

    if ($allRemoved) {
        Write-Ok 'All user data and database files were removed. Application files and settings were preserved.'
    } else {
        Write-Warn ("User data was removed where permitted; {0} locked or protected entries were skipped. First skipped path: {1}" -f $script:SkippedCacheCount, $script:FirstSkippedCachePath)
    }
}

function Register-SkippedCachePath([string]$Path) {
    $script:SkippedCacheCount++
    if ([string]::IsNullOrEmpty($script:FirstSkippedCachePath)) {
        $script:FirstSkippedCachePath = $Path
    }
}

function Remove-PathBestEffort {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -ErrorAction SilentlyContinue)) { return $true }
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($null -eq $item) {
        Register-SkippedCachePath -Path $Path
        return $false
    }

    $allRemoved = $true
    if ($item.PSIsContainer) {
        try {
            $children = @(Get-ChildItem -LiteralPath $Path -Force -ErrorAction Stop)
        } catch {
            Register-SkippedCachePath -Path $Path
            return $false
        }
        foreach ($child in $children) {
            if (-not (Remove-PathBestEffort -Path $child.FullName)) { $allRemoved = $false }
        }
    }

    try {
        Remove-Item -LiteralPath $Path -Recurse -Force -Confirm:$false -ErrorAction Stop
    } catch {
        Register-SkippedCachePath -Path $Path
        return $false
    }
    return $allRemoved
}

function Clear-CacheDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [string[]]$PreserveNames = @('.gitkeep')
    )

    if (-not (Test-Path -LiteralPath $Path -ErrorAction SilentlyContinue)) { return $true }
    try {
        $children = @(Get-ChildItem -LiteralPath $Path -Force -ErrorAction Stop)
    } catch {
        Register-SkippedCachePath -Path $Path
        return $false
    }

    $allRemoved = $true
    foreach ($child in $children) {
        if ($child.Name -in $PreserveNames) { continue }
        if (-not (Remove-PathBestEffort -Path $child.FullName)) { $allRemoved = $false }
    }
    return $allRemoved
}

function Remove-PythonCaches {
    $allRemoved = $true
    foreach ($root in @($ServerDir, $TestsDir)) {
        if (-not (Test-Path -LiteralPath $root -ErrorAction SilentlyContinue)) { continue }
        $cacheDirectories = @(Get-ChildItem -LiteralPath $root -Directory -Filter '__pycache__' -Recurse -Force -ErrorAction SilentlyContinue)
        foreach ($cacheDirectory in $cacheDirectories) {
            if (-not (Remove-PathBestEffort -Path $cacheDirectory.FullName)) { $allRemoved = $false }
        }
    }
    return $allRemoved
}

function Clear-DeveloperCache {
    $allRemoved = $true
    foreach ($cacheRoot in @($RuntimeCacheDir, $TestCacheDir)) {
        if (-not (Clear-CacheDirectory -Path $cacheRoot)) { $allRemoved = $false }
    }
    return $allRemoved
}

function Clear-ApplicationCache {
    $script:SkippedCacheCount = 0
    $script:FirstSkippedCachePath = $null
    $allRemoved = Remove-PythonCaches
    if (-not (Clear-DeveloperCache)) { $allRemoved = $false }
    if ($allRemoved) {
        Write-Ok 'Runtime and test/tool caches were removed.'
    } else {
        Write-Warn ("Runtime and test/tool caches were cleared where permitted; {0} locked or protected entries were skipped. First skipped path: {1}" -f $script:SkippedCacheCount, $script:FirstSkippedCachePath)
    }
}

function Remove-RepoItem([string]$RelativePath) {
    $target = [IO.Path]::GetFullPath((Join-Path $RepoRoot $RelativePath))
    $rootWithSeparator = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\') + '\'
    if (-not $target.StartsWith($rootWithSeparator, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside the repository: $target"
    }
    if (Test-Path -LiteralPath $target -ErrorAction SilentlyContinue) {
        return Remove-PathBestEffort -Path $target
    }
    return $true
}

function Uninstall-Application {
    $script:SkippedCacheCount = 0
    $script:FirstSkippedCachePath = $null
    $allRemoved = $true
    foreach ($relativePath in @(
        'runtimes', 'app\server\.venv', '.venv', 'app\client\node_modules',
        'app\client\.angular', 'app\client\dist'
    )) {
        if (-not (Remove-RepoItem -RelativePath $relativePath)) { $allRemoved = $false }
    }
    if (-not (Remove-PythonCaches)) { $allRemoved = $false }
    if (-not (Clear-DeveloperCache)) { $allRemoved = $false }
    if ($allRemoved) {
        Write-Ok 'Application runtimes, dependencies, caches, and build outputs removed. Dependency lockfiles and user data were preserved.'
    } else {
        Write-Warn ("Application runtimes, dependencies, caches, and build outputs were removed where permitted; {0} locked or protected entries were skipped. Dependency lockfiles and user data were preserved. First skipped path: {1}" -f $script:SkippedCacheCount, $script:FirstSkippedCachePath)
    }
}

#endregion

#region Source control

function Get-CurrentGitBranch {
    $branch = (& git branch --show-current 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Unable to determine the current Git branch.' }
    return $branch
}

function Get-CurrentGitRevision {
    $revision = (& git rev-parse HEAD 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($revision)) {
        throw 'Unable to determine the current Git revision.'
    }
    return $revision
}

function Update-Application {
    $branch = Get-CurrentGitBranch
    if ($branch -ne 'main') {
        throw "Update from main requires the main branch to be checked out. Current branch: $branch"
    }

    $status = (& git status --porcelain 2>$null | Out-String).Trim()
    if (-not [string]::IsNullOrWhiteSpace($status)) {
        throw 'Update requires a clean Git working tree. Commit or safely preserve local changes before retrying.'
    }

    Write-Step 'Updating application from origin/main with git pull'
    & git pull origin main
    if ($LASTEXITCODE -ne 0) { throw "Git pull failed with exit code $LASTEXITCODE" }
    Write-Ok 'Application update completed.'
}

function Check-ForUpdates {
    $localRevision = Get-CurrentGitRevision
    $remoteLine = (& git ls-remote origin refs/heads/main 2>$null | Select-Object -First 1)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$remoteLine)) {
        throw 'Unable to check origin/main for updates.'
    }

    $remoteRevision = ([string]$remoteLine -split '\s+')[0]
    if ($localRevision -eq $remoteRevision) {
        Write-Ok "Application is up to date with origin/main ($($localRevision.Substring(0, 7)))."
        return
    }

    $branch = Get-CurrentGitBranch
    Write-Warn "A different origin/main revision is available (local $($localRevision.Substring(0, 7)), remote $($remoteRevision.Substring(0, 7)))."
    Write-Info "Current branch: $branch. No files were downloaded or changed."
}

#endregion

#region Menu loop

function Wait-ForMenu {
    Write-Host
    Write-Host 'Press any key to return to menu...'
    try { $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { $null = Read-Host }
}

while ($true) {
    Show-Menu
    $selection = Read-Host '  Select an option (1-12)'
    if ($selection -notmatch '^(?:[1-9]|1[0-2])$') {
        Write-Warn 'Select a number from 1 through 12.'
        Wait-ForMenu
        continue
    }
    if ($selection -eq '12') { break }
    try {
        switch ($selection) {
            '1' { Invoke-Launch; exit 0 }
            '2' {
                Ensure-PortableRuntimes
                $installationType = Read-InstallationType
                Import-DotEnv | Out-Null
                Sync-Dependencies -PruneCache -InstallationType $installationType
                Invoke-DatabaseInitialization
                Build-Frontend
            }
            '3' { Invoke-FrontendRebuild }
            '4' { Invoke-DatabaseInitialization }
            '5' { Invoke-TestSuite }
            '6' { Update-Application }
            '7' { Check-ForUpdates }
            '8' { Remove-LogFiles }
            '9' { Clear-ApplicationCache }
            '10' { Remove-AllData }
            '11' { Uninstall-Application }
        }
    } catch {
        Write-Fatal $_.Exception.Message
    }
    Wait-ForMenu
}
