[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$script:RepoRoot = $PSScriptRoot
$script:AppDir = Join-Path $RepoRoot 'app'
$script:ServerDir = Join-Path $AppDir 'server'
$script:ClientDir = Join-Path $AppDir 'client'
$script:SettingsDir = Join-Path $RepoRoot 'settings'
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
$script:UvCacheDir = Join-Path $RuntimesDir '.uv-cache'
$script:DotEnv = Join-Path $SettingsDir '.env'
$script:DotEnvExample = Join-Path $SettingsDir '.env.example'
$script:PythonVersion = '3.14.2'
$script:NodeVersion = '22.12.0'

function Write-Step([string]$Message) { Write-Host "[STEP] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Info([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor DarkCyan }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Fatal([string]$Message) { Write-Host "[FATAL] $Message" -ForegroundColor Red }

function Clear-PythonEnvironment {
    foreach ($name in 'PYTHONHOME', 'PYTHONPATH', 'PYTHONNOUSERSITE') {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
        Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
    }
}

function Set-LauncherEnvironment {
    $env:UV_CACHE_DIR = $UvCacheDir
    $env:UV_PROJECT_ENVIRONMENT = $VenvDir
    $env:UV_LINK_MODE = 'copy'
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

function Import-DotEnv {
    $values = [ordered]@{
        FASTAPI_HOST = '127.0.0.1'
        FASTAPI_PORT = '8000'
        UI_HOST = '127.0.0.1'
        UI_PORT = '8001'
        RELOAD = 'false'
        OPTIONAL_DEPENDENCIES = 'false'
        BACKEND_LOGS_VISIBLE = 'true'
        always_rebuild = 'true'
    }
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
    return $values
}

function Sync-Dependencies([System.Collections.IDictionary]$Settings, [switch]$PruneCache) {
    if (-not (Test-Path -LiteralPath (Join-Path $ServerDir 'pyproject.toml'))) {
        throw "Missing pyproject.toml in $ServerDir"
    }
    Write-Step 'Installing Python dependencies with uv'
    $uvArgs = @('sync', '--python', $PythonExe)
    if ([string]$Settings.OPTIONAL_DEPENDENCIES -ieq 'true') { $uvArgs += '--all-extras' }
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
        if ([string]$Settings.always_rebuild -ieq 'true') {
            Write-Step 'Building frontend'
            & $NpmCmd run build
            if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with exit code $LASTEXITCODE" }
        } else {
            Write-Info 'Skipping frontend build because always_rebuild=false.'
        }
    } finally { Pop-Location }

    if ($PruneCache -and (Test-Path -LiteralPath $UvCacheDir)) {
        Write-Step 'Pruning uv cache'
        Remove-Item -LiteralPath $UvCacheDir -Recurse -Force
    }
    Write-Ok 'Dependencies and frontend build are ready.'
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

function Invoke-Launch {
    Ensure-PortableRuntimes
    $settings = Import-DotEnv
    Sync-Dependencies -Settings $settings
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
    $arguments = @('run', '--project', (Join-Path $AppDir 'server'), '--python', $PythonExe, 'python', (Join-Path $AppDir 'scripts\initialize_database.py'), '--drop-existing', '--seed-catalogs', '--force-reseed-catalogs')
    & $UvExe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Database initialization failed with exit code $LASTEXITCODE" }
    Write-Ok 'Database initialization completed.'
}

function Invoke-TestSuite {
    $testScript = Join-Path $AppDir 'tests\run_tests.bat'
    if (-not (Test-Path -LiteralPath $testScript)) { throw "Missing test script: $testScript" }
    & cmd.exe /c $testScript
    if ($LASTEXITCODE -ne 0) { throw "Test suite failed with exit code $LASTEXITCODE" }
    Write-Ok 'Test suite completed.'
}

function Remove-LogFiles {
    $logDir = Join-Path $AppDir 'resources\logs'
    if (-not (Test-Path -LiteralPath $logDir)) { Write-Info "Log directory not found: $logDir"; return }
    Get-ChildItem -LiteralPath $logDir -Filter '*.log' -File -ErrorAction SilentlyContinue | Remove-Item -Force
    Write-Ok 'Log files removed.'
}

function Remove-PythonCaches {
    Get-ChildItem -LiteralPath $RepoRoot -Directory -Filter '__pycache__' -Recurse -Force -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

function Clear-ApplicationCache {
    Remove-PythonCaches
    if (Test-Path -LiteralPath $UvCacheDir) { Remove-Item -LiteralPath $UvCacheDir -Recurse -Force }
    Write-Ok 'Python and uv caches removed.'
}

function Remove-RepoItem([string]$RelativePath) {
    $target = [IO.Path]::GetFullPath((Join-Path $RepoRoot $RelativePath))
    $rootWithSeparator = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\') + '\'
    if (-not $target.StartsWith($rootWithSeparator, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside the repository: $target"
    }
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
}

function Uninstall-Application {
    foreach ($relativePath in @(
        'runtimes', 'app\server\.venv', '.venv', 'app\client\node_modules',
        'app\client\.angular', 'app\client\dist', 'app\client\package-lock.json',
        'app\server\uv.lock', 'uv.lock'
    )) { Remove-RepoItem -RelativePath $relativePath }
    Remove-PythonCaches
    Write-Ok 'Application runtimes, dependencies, caches, and lockfiles removed. Settings and user data were preserved.'
}

function Wait-ForMenu {
    Write-Host
    Write-Host 'Press any key to return to menu...'
    try { $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { $null = Read-Host }
}

while ($true) {
    Clear-Host
    Write-Host '========================================='
    Write-Host '    ParaGraph -- LLM Workflow'
    Write-Host '========================================='
    Write-Host '1.  Launch application'
    Write-Host '2.  Install / update dependencies'
    Write-Host '3.  Initialize database'
    Write-Host '4.  Run test suite'
    Write-Host '5.  Remove logs'
    Write-Host '6.  Clear cache'
    Write-Host '7.  Uninstall application'
    Write-Host '8.  Exit'
    Write-Host '========================================='
    $selection = Read-Host 'Select an option (1-8)'
    if ($selection -notmatch '^[1-8]$') {
        Write-Warn 'Select a number from 1 through 8.'
        Wait-ForMenu
        continue
    }
    if ($selection -eq '8') { break }
    try {
        switch ($selection) {
            '1' { Invoke-Launch; exit 0 }
            '2' { Ensure-PortableRuntimes; $settings = Import-DotEnv; Sync-Dependencies -Settings $settings -PruneCache }
            '3' { Invoke-DatabaseInitialization }
            '4' { Invoke-TestSuite }
            '5' { Remove-LogFiles }
            '6' { Clear-ApplicationCache }
            '7' { Uninstall-Application }
        }
    } catch {
        Write-Fatal $_.Exception.Message
    }
    Wait-ForMenu
}
