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
$script:CacheRoot = Join-Path $RuntimesDir 'cache'
$script:UvCacheDir = Join-Path $CacheRoot 'uv'
$script:PythonCacheDir = Join-Path $CacheRoot 'pycache'
$script:NpmCacheDir = Join-Path $CacheRoot 'npm'
$script:PytestCacheDir = Join-Path $CacheRoot 'pytest'
$script:PytestTempDir = Join-Path $CacheRoot 'pytest-tmp'
$script:RuffCacheDir = Join-Path $CacheRoot 'ruff'
$script:CoverageDir = Join-Path $CacheRoot 'coverage'
$script:CoverageFile = Join-Path $CoverageDir '.coverage'
$script:PlaywrightDir = Join-Path $CacheRoot 'playwright'
$script:PlaywrightBrowsersDir = Join-Path $PlaywrightDir 'browsers'
$script:ViteCacheDir = Join-Path $CacheRoot 'vite'
$script:VitestCacheDir = Join-Path $CacheRoot 'vitest'
$script:EslintCacheDir = Join-Path $CacheRoot 'eslint'
$script:MypyCacheDir = Join-Path $CacheRoot 'mypy'
$script:PipCacheDir = Join-Path $CacheRoot 'pip'
$script:FrontendBuildDir = Join-Path $CacheRoot 'frontend-dist'
$script:HuggingFaceCacheDir = Join-Path $CacheRoot 'huggingface'
$script:HuggingFaceHubCacheDir = Join-Path $HuggingFaceCacheDir 'hub'
$script:HuggingFaceAssetsCacheDir = Join-Path $HuggingFaceCacheDir 'assets'
$script:HuggingFaceXetCacheDir = Join-Path $HuggingFaceCacheDir 'xet'
$script:TorchCacheDir = Join-Path $CacheRoot 'torch'
$script:DotEnv = Join-Path $SettingsDir '.env'
$script:DotEnvExample = Join-Path $SettingsDir '.env.example'
$script:PythonVersion = '3.14.2'
$script:NodeVersion = '22.12.0'
$script:SkippedCacheCount = 0
$script:FirstSkippedCachePath = $null
$script:NextProgressId = 1
$script:ActiveProgressActivities = [Collections.Generic.Dictionary[int, string]]::new()
$script:BackendTerminalTitle = 'ParaGraph Backend Logs'
$script:LauncherProgressEnabled = -not [Console]::IsOutputRedirected
$script:LauncherInteractive = -not [Console]::IsInputRedirected -and -not [Console]::IsOutputRedirected

#region Console and menu helpers

function Write-Step([string]$Message) { Clear-LauncherProgress; Write-Host "[STEP] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Clear-LauncherProgress; Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Info([string]$Message) { Clear-LauncherProgress; Write-Host "[INFO] $Message" -ForegroundColor DarkCyan }
function Write-Warn([string]$Message) { Clear-LauncherProgress; Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Fatal([string]$Message) { Clear-LauncherProgress; Write-Host "[FATAL] $Message" -ForegroundColor Red }

function Start-LauncherProgress {
    param([Parameter(Mandatory = $true)][string]$Activity, [Parameter(Mandatory = $true)][string]$Status)
    $id = $script:NextProgressId++
    $script:ActiveProgressActivities[$id] = $Activity
    if ($script:LauncherProgressEnabled) { Write-Progress -Id $id -Activity $Activity -Status $Status }
    return $id
}

function Update-LauncherProgress {
    param(
        [Parameter(Mandatory = $true)][int]$Id,
        [Parameter(Mandatory = $true)][string]$Activity,
        [Parameter(Mandatory = $true)][string]$Status,
        [Nullable[int]]$PercentComplete
    )
    if (-not $script:ActiveProgressActivities.ContainsKey($Id)) { return }
    $activity = $script:ActiveProgressActivities[$Id]
    $progress = @{ Id = $Id; Activity = $activity; Status = $Status }
    if ($null -ne $PercentComplete) { $progress.PercentComplete = $PercentComplete }
    if ($script:LauncherProgressEnabled) { Write-Progress @progress }
}

function Complete-LauncherProgress([int]$Id) {
    if ($script:ActiveProgressActivities.ContainsKey($Id)) {
        $activity = $script:ActiveProgressActivities[$Id]
        try {
            if ($script:LauncherProgressEnabled) {
                try { Write-Progress -Id $Id -Activity $activity -Completed } catch { }
            }
        }
        finally {
            [void]$script:ActiveProgressActivities.Remove($Id)
        }
    }
}

function Clear-LauncherProgress {
    foreach ($id in @($script:ActiveProgressActivities.Keys)) {
        Complete-LauncherProgress -Id $id
    }
}

function Invoke-TrackedLauncherAction {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )
    Write-Step "Starting $Name"
    try {
        & $Action
        Write-Ok "$Name completed"
    }
    catch {
        Write-Fatal "$Name failed: $($_.Exception.Message)"
        throw
    }
    finally {
        Clear-LauncherProgress
    }
}

function Write-MenuDivider {
    Write-Host ('-' * 70) -ForegroundColor DarkGray
}

function Get-LauncherMenuEntries {
    return @(
        [pscustomobject]@{ Section = 'APPLICATION'; Title = 'Launch application'; Description = 'Start the backend and frontend'; Key = 'Launch'; Destructive = $false }
        [pscustomobject]@{ Section = 'APPLICATION'; Title = 'Kill all app processes'; Description = 'Stop the backend, frontend, and terminal'; Key = 'KillProcesses'; Destructive = $true }
        [pscustomobject]@{ Section = 'SETUP & VALIDATION'; Title = 'Install or update dependencies'; Description = 'Sync runtimes, dependencies, browser, database, and UI build'; Key = 'Install'; Destructive = $false }
        [pscustomobject]@{ Section = 'SETUP & VALIDATION'; Title = 'Rebuild frontend'; Description = 'Build the frontend only'; Key = 'Rebuild'; Destructive = $false }
        [pscustomobject]@{ Section = 'SETUP & VALIDATION'; Title = 'Initialize or upgrade database'; Description = 'Apply SQLite/Alembic migrations'; Key = 'Database'; Destructive = $false }
        [pscustomobject]@{ Section = 'SETUP & VALIDATION'; Title = 'Run test suite'; Description = 'Execute project checks'; Key = 'Tests'; Destructive = $false }
        [pscustomobject]@{ Section = 'SOURCE CONTROL'; Title = 'Check for updates'; Description = 'Report origin/main status only'; Key = 'Check'; Destructive = $false }
        [pscustomobject]@{ Section = 'SOURCE CONTROL'; Title = 'Update from main'; Description = 'Pull latest code from origin/main'; Key = 'Update'; Destructive = $false }
        [pscustomobject]@{ Section = 'DATA & MAINTENANCE'; Title = 'Remove log files'; Description = 'Delete local application logs'; Key = 'Logs'; Destructive = $true }
        [pscustomobject]@{ Section = 'DATA & MAINTENANCE'; Title = 'Clear canonical cache hierarchy'; Description = 'Remove all disposable data under runtimes/cache'; Key = 'Cache'; Destructive = $true }
        [pscustomobject]@{ Section = 'DATA & MAINTENANCE'; Title = 'Remove all data'; Description = 'Delete user data and database'; Key = 'AllData'; Destructive = $true }
        [pscustomobject]@{ Section = 'DATA & MAINTENANCE'; Title = 'Uninstall application'; Description = 'Remove local runtimes and packages'; Key = 'Uninstall'; Destructive = $true }
        [pscustomobject]@{ Section = 'EXIT'; Title = 'Exit'; Description = 'Close this launcher'; Key = 'Exit'; Destructive = $false }
    )
}

function Write-MenuOption {
    param(
        [Parameter(Mandatory = $true)][pscustomobject]$Entry,
        [Parameter(Mandatory = $true)][int]$NumberWidth,
        [Parameter(Mandatory = $true)][int]$TitleWidth
    )
    $color = if ($Entry.Destructive) { 'Yellow' } elseif ($Entry.Key -eq 'Exit') { 'DarkGray' } else { 'White' }
    Write-Host ("  {0,$NumberWidth}. {1,-$TitleWidth}  {2}" -f $Entry.Number, $Entry.Title, $Entry.Description) -ForegroundColor $color
}

function Read-InstallationType {
    Clear-LauncherProgress
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
    Clear-LauncherProgress
    if ($script:LauncherInteractive) { try { Clear-Host } catch { } }
    $entries = @(Get-LauncherMenuEntries)
    for ($index = 0; $index -lt $entries.Count; $index++) {
        $entries[$index] = [pscustomobject]@{
            Number = $index + 1
            Section = $entries[$index].Section
            Title = $entries[$index].Title
            Description = $entries[$index].Description
            Key = $entries[$index].Key
            Destructive = $entries[$index].Destructive
        }
    }
    $numberWidth = ([string]$entries.Count).Length
    $titleWidth = ($entries | ForEach-Object { $_.Title.Length } | Measure-Object -Maximum).Maximum
    Write-Host
    Write-Host '  PARAGRAPH' -ForegroundColor Cyan
    Write-Host '  LLM Workflow' -ForegroundColor White
    Write-Host '  Local workspace control center' -ForegroundColor DarkGray
    Write-Host
    Write-MenuDivider
    $lastSection = $null
    foreach ($entry in $entries) {
        if ($entry.Section -ne $lastSection) {
            if ($null -ne $lastSection) { Write-Host }
            Write-Host ("  {0}" -f $entry.Section) -ForegroundColor DarkCyan
            Write-MenuDivider
            $lastSection = $entry.Section
        }
        Write-MenuOption -Entry $entry -NumberWidth $numberWidth -TitleWidth $titleWidth
    }
    Write-MenuDivider
    Write-Host '  Enter a number to continue. Remove All Data requires explicit confirmation.' -ForegroundColor DarkGray
    Write-Host
    return $entries
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
        $CacheRoot,
        $UvCacheDir,
        $PythonCacheDir,
        $NpmCacheDir,
        $PytestCacheDir,
        $PytestTempDir,
        $RuffCacheDir,
        $CoverageDir,
        $PlaywrightBrowsersDir,
        $ViteCacheDir,
        $VitestCacheDir,
        $EslintCacheDir,
        $MypyCacheDir,
        $PipCacheDir,
        $HuggingFaceHubCacheDir,
        $HuggingFaceAssetsCacheDir,
        $HuggingFaceXetCacheDir,
        $TorchCacheDir,
        $FrontendBuildDir
    ) -Force | Out-Null
    $env:UV_CACHE_DIR = $UvCacheDir
    $env:UV_PROJECT_ENVIRONMENT = $VenvDir
    $env:UV_LINK_MODE = 'copy'
    $env:PYTHONPYCACHEPREFIX = $PythonCacheDir
    $env:RUFF_CACHE_DIR = $RuffCacheDir
    $env:MYPY_CACHE_DIR = $MypyCacheDir
    $env:PIP_CACHE_DIR = $PipCacheDir
    $env:COVERAGE_FILE = $CoverageFile
    $env:npm_config_cache = $NpmCacheDir
    $env:PLAYWRIGHT_BROWSERS_PATH = $PlaywrightBrowsersDir
    $env:HF_HOME = $HuggingFaceCacheDir
    $env:HF_HUB_CACHE = $HuggingFaceHubCacheDir
    $env:HF_ASSETS_CACHE = $HuggingFaceAssetsCacheDir
    $env:HF_XET_CACHE = $HuggingFaceXetCacheDir
    $env:TORCH_HOME = $TorchCacheDir
    $env:PATH = "$NodeDir;$($env:PATH)"
    Clear-PythonEnvironment
}

function Invoke-DownloadAndExtract {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$ArchivePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )
    $activity = "ParaGraph: download and extract $([IO.Path]::GetFileName($ArchivePath))"
    $progressId = Start-LauncherProgress -Activity $activity -Status "Downloading $Uri"
    try {
        New-Item -ItemType Directory -Path (Split-Path -Parent $ArchivePath) -Force | Out-Null
        New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null
        Invoke-WebRequest -Uri $Uri -OutFile $ArchivePath
        Update-LauncherProgress -Id $progressId -Activity $activity -Status 'Extracting archive'
        Expand-Archive -LiteralPath $ArchivePath -DestinationPath $DestinationPath -Force
    }
    finally {
        Remove-Item -LiteralPath $ArchivePath -Force -ErrorAction SilentlyContinue
        Complete-LauncherProgress $progressId
    }
}

function Invoke-PatchPth {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (Test-Path -LiteralPath $Path) {
        $content = Get-Content -LiteralPath $Path
        if ($content -contains '#import site') {
            $content -replace '^#import site$', 'import site' |
                Set-Content -LiteralPath $Path
        }
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
    $activity = "ParaGraph: wait for health $Url"
    $progressId = Start-LauncherProgress -Activity $activity -Status "Waiting up to $Attempts attempts"
    try {
        for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
            Update-LauncherProgress -Id $progressId -Activity $activity -Status "Attempt $attempt of $Attempts"
            try {
                $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
                if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) { return $true }
            } catch { }
            if ($attempt -lt $Attempts) { Start-Sleep -Seconds $IntervalSeconds }
        }
        return $false
    }
    finally {
        Complete-LauncherProgress $progressId
    }
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
    foreach ($requiredKey in @('FASTAPI_HOST', 'FASTAPI_PORT', 'UI_HOST', 'UI_PORT', 'RELOAD')) {
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
            if (Test-Path -LiteralPath $VenvDir) { [void](Remove-LauncherPath -Path $VenvDir -Activity 'ParaGraph: recreate Python environment' -Strict) }
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

    Install-PlaywrightBrowser

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
    $fingerprintPath = Join-Path $FrontendBuildDir '.paragraph-build-fingerprint'
    if (Test-Path -LiteralPath $fingerprintPath) {
        Remove-Item -LiteralPath $fingerprintPath -Force -ErrorAction Stop
    }
    Push-Location $ClientDir
    try {
        & $NpmCmd run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with exit code $LASTEXITCODE" }
    } finally { Pop-Location }
    Write-FrontendBuildFingerprint
    Write-Ok 'Frontend build is ready.'
}

function Get-FrontendBuildInputFiles {
    $relativePaths = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($relativeRoot in @('src', 'public')) {
        $rootPath = Join-Path $ClientDir $relativeRoot
        if (-not (Test-Path -LiteralPath $rootPath -PathType Container)) { continue }
        foreach ($file in @(Get-ChildItem -LiteralPath $rootPath -File -Recurse -Force -ErrorAction Stop)) {
            $relativePath = [IO.Path]::GetRelativePath($ClientDir, $file.FullName).Replace('\', '/')
            [void]$relativePaths.Add($relativePath)
        }
    }
    foreach ($relativePath in @(
        'index.html',
        'package.json',
        'package-lock.json',
        'tsconfig.json',
        'tsconfig.node.json',
        'vite.config.ts'
    )) {
        [void]$relativePaths.Add($relativePath)
    }
    $sortedPaths = [string[]]@($relativePaths)
    [Array]::Sort($sortedPaths, [StringComparer]::OrdinalIgnoreCase)
    return $sortedPaths
}

function Get-FrontendBuildFingerprint {
    param([string]$ViteApiBaseUrl = $env:VITE_API_BASE_URL)

    $hasher = [Security.Cryptography.SHA256]::Create()
    try {
        $manifest = [Text.StringBuilder]::new()
        [void]$manifest.AppendLine('paragraph-frontend-build-fingerprint:v1')
        [void]$manifest.AppendLine('build-command:npm run build')

        $rawApiBase = if ($null -eq $ViteApiBaseUrl) { '' } else { ([string]$ViteApiBaseUrl).Trim() }
        if ([string]::IsNullOrWhiteSpace($rawApiBase)) {
            $effectiveApiBase = '<missing>'
        } elseif ($rawApiBase -match '^[a-zA-Z][a-zA-Z\d+\-.]*://') {
            $effectiveApiBase = $rawApiBase
        } else {
            $effectiveApiBase = if ($rawApiBase.StartsWith('/')) { $rawApiBase } else { "/$rawApiBase" }
            if ($effectiveApiBase.Length -gt 1 -and $effectiveApiBase.EndsWith('/')) {
                $effectiveApiBase = $effectiveApiBase.Substring(0, $effectiveApiBase.Length - 1)
            }
        }
        [void]$manifest.AppendLine("vite-env:VITE_API_BASE_URL=$effectiveApiBase")

        foreach ($relativePath in @(Get-FrontendBuildInputFiles)) {
            $fullPath = Join-Path $ClientDir ($relativePath.Replace('/', '\'))
            if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
                throw "Missing frontend build input: $relativePath"
            }
            $fileHash = [BitConverter]::ToString(
                $hasher.ComputeHash([IO.File]::ReadAllBytes($fullPath))
            ).Replace('-', '').ToLowerInvariant()
            [void]$manifest.AppendLine("file:$relativePath=$fileHash")
        }

        return [BitConverter]::ToString(
            $hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($manifest.ToString()))
        ).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $hasher.Dispose()
    }
}

function Get-FrontendBuildState {
    $indexPath = Join-Path $FrontendBuildDir 'index.html'
    $fingerprintPath = Join-Path $FrontendBuildDir '.paragraph-build-fingerprint'
    if (-not (Test-Path -LiteralPath $indexPath -PathType Leaf)) {
        return [pscustomobject]@{ Current = $false; Reason = 'build output missing' }
    }
    if (-not (Test-Path -LiteralPath $fingerprintPath -PathType Leaf)) {
        return [pscustomobject]@{ Current = $false; Reason = 'fingerprint missing' }
    }

    try {
        $storedFingerprint = (Get-Content -LiteralPath $fingerprintPath -Raw -ErrorAction Stop).Trim()
    }
    catch {
        return [pscustomobject]@{ Current = $false; Reason = 'fingerprint invalid' }
    }
    if ($storedFingerprint -notmatch '^[0-9a-fA-F]{64}$') {
        return [pscustomobject]@{ Current = $false; Reason = 'fingerprint invalid' }
    }

    try {
        $currentFingerprint = Get-FrontendBuildFingerprint
    }
    catch {
        return [pscustomobject]@{ Current = $false; Reason = "input fingerprint unavailable: $($_.Exception.Message)" }
    }
    if ($storedFingerprint -ine $currentFingerprint) {
        return [pscustomobject]@{ Current = $false; Reason = 'input fingerprint changed' }
    }
    return [pscustomobject]@{ Current = $true; Reason = 'current' }
}

function Write-FrontendBuildFingerprint {
    $indexPath = Join-Path $FrontendBuildDir 'index.html'
    if (-not (Test-Path -LiteralPath $indexPath -PathType Leaf)) {
        throw "Frontend build completed without $indexPath"
    }
    $fingerprintPath = Join-Path $FrontendBuildDir '.paragraph-build-fingerprint'
    $fingerprint = Get-FrontendBuildFingerprint
    Set-Content -LiteralPath $fingerprintPath -Value $fingerprint -NoNewline -Encoding ascii
}

function Install-PlaywrightBrowser {
    $playwrightCommand = Join-Path $ClientDir 'node_modules\.bin\playwright.cmd'
    if (-not (Test-Path -LiteralPath $playwrightCommand)) {
        throw "Playwright runner not found at $playwrightCommand"
    }

    Write-Step 'Installing Playwright Chromium browser'
    Push-Location $ClientDir
    try {
        & $playwrightCommand install chromium
        if ($LASTEXITCODE -ne 0) { throw "Playwright browser installation failed with exit code $LASTEXITCODE" }
    } finally { Pop-Location }
    Write-Ok "Playwright Chromium browser is ready under $PlaywrightBrowsersDir."
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
        [void](Remove-LauncherPath -Path $nestedNodeDir -Activity 'ParaGraph: flatten Node.js runtime' -Strict)
    }
    if (-not (Test-Path -LiteralPath $NodeExe)) { throw "node.exe not found at $NodeExe" }
    if (-not (Test-Path -LiteralPath $NpmCmd)) { throw "npm.cmd not found at $NpmCmd" }
    $nodeVersionFound = & $NodeExe --version
    if ($LASTEXITCODE -ne 0) { throw 'Node.js failed its version check.' }
    Write-Ok "Node.js ready: $nodeVersionFound"
}

function Invoke-FrontendRebuild {
    Ensure-NodeRuntime
    Import-DotEnv | Out-Null
    Set-LauncherEnvironment
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

    $installStateWriteTime = (Get-Item -LiteralPath $frontendInstallState).LastWriteTimeUtc
    foreach ($manifestPath in @($frontendPackage, $frontendLock)) {
        if ((Get-Item -LiteralPath $manifestPath).LastWriteTimeUtc -gt $installStateWriteTime) {
            return $false
        }
    }

    & $VenvPython -c 'import fastapi, uvicorn' *> $null
    if ($LASTEXITCODE -ne 0) { return $false }

    return $true
}

function Get-ListenerPids([int]$Port) {
    return @(netstat -ano | ForEach-Object {
        if ($_ -match "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$") { [int]$Matches[1] }
    } | Sort-Object -Unique)
}

function Get-PortListenerRecords {
    param([Parameter(Mandatory = $true)][int[]]$Ports)

    $configuredPorts = [Collections.Generic.HashSet[int]]::new()
    foreach ($port in $Ports) {
        if ($port -lt 1 -or $port -gt 65535) { throw "Invalid configured port: $port" }
        [void]$configuredPorts.Add($port)
    }

    $records = [Collections.Generic.List[object]]::new()
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $netstatOutput = @(netstat.exe -ano)
    if ($LASTEXITCODE -ne 0) { throw "netstat failed with exit code $LASTEXITCODE" }
    foreach ($line in $netstatOutput) {
        if ($line -match '^\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$') {
            $port = [int]$Matches[1]
            $processId = [int]$Matches[2]
            $recordKey = "$port/$processId"
            if ($configuredPorts.Contains($port) -and $seen.Add($recordKey)) {
                [void]$records.Add([pscustomobject]@{
                    Port      = $port
                    ProcessId = $processId
                })
            }
        }
    }
    return @($records)
}

function Get-PortConflictProcesses {
    param([Parameter(Mandatory = $true)][object[]]$ListenerRecords)

    $conflicts = foreach ($group in @($ListenerRecords | Group-Object -Property ProcessId)) {
        $processId = [int]$group.Name
        $processName = 'unavailable'
        try {
            $process = Get-Process -Id $processId -ErrorAction Stop
            if (-not [string]::IsNullOrWhiteSpace([string]$process.ProcessName)) {
                $processName = [string]$process.ProcessName
            }
        }
        catch { }
        [pscustomobject]@{
            ProcessId   = $processId
            ProcessName = $processName
            Ports       = @($group.Group | ForEach-Object { [int]$_.Port } | Sort-Object -Unique)
        }
    }
    return @($conflicts | Sort-Object -Property ProcessId)
}

function Confirm-PortConflictTermination {
    param([Parameter(Mandatory = $true)][object[]]$Conflicts)

    Write-Warn 'Configured launch ports are already in use:'
    foreach ($conflict in $Conflicts) {
        $ports = (@($conflict.Ports | Sort-Object -Unique) -join ', ')
        Write-Host ("  PID {0} ({1}) owns port(s): {2}" -f $conflict.ProcessId, $conflict.ProcessName, $ports) -ForegroundColor Yellow
    }

    $launcherConflict = @($Conflicts | Where-Object { [int]$_.ProcessId -eq $PID })
    if ($launcherConflict.Count -gt 0) {
        $ports = (@($launcherConflict | ForEach-Object { $_.Ports } | Sort-Object -Unique) -join ', ')
        throw "The launcher process PID $PID owns configured port(s) $ports. Refusing to terminate the launcher; free the port(s) and retry."
    }
    if (-not $script:LauncherInteractive) {
        throw 'Configured launch ports are occupied, but termination requires an interactive confirmation.'
    }

    $confirmation = ([string](Read-Host 'Terminate all listed port-conflict process trees? [y/N]')).Trim()
    if ($confirmation -notmatch '^(?i:y|yes)$') {
        Write-Info 'Launch cancelled. No port-conflict processes were terminated.'
        return $false
    }
    return $true
}

function Stop-ProcessTree([int]$ProcessId) {
    if ($ProcessId -le 0) { throw "Invalid process ID: $ProcessId" }
    if ($ProcessId -eq $PID) { throw "Refusing to terminate the launcher process PID $PID." }

    $targetExists = $true
    try {
        $target = [Diagnostics.Process]::GetProcessById($ProcessId)
        $target.Dispose()
    }
    catch [System.ArgumentException] {
        $targetExists = $false
    }
    catch { $targetExists = $true }
    if (-not $targetExists) { return $true }

    & taskkill.exe /PID $ProcessId /T /F | Out-Null
    $taskKillExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
    for ($attempt = 1; $attempt -le 10; $attempt++) {
        $targetExists = $true
        try {
            $target = [Diagnostics.Process]::GetProcessById($ProcessId)
            $target.Dispose()
        }
        catch [System.ArgumentException] {
            $targetExists = $false
        }
        catch { $targetExists = $true }
        if (-not $targetExists) { return $true }
        if ($attempt -lt 10) { Start-Sleep -Milliseconds 100 }
    }
    if ($taskKillExitCode -ne 0) {
        throw "taskkill failed with exit code $taskKillExitCode and process PID $ProcessId is still alive."
    }
    throw "Process PID $ProcessId is still alive after taskkill completed."
}

function Stop-PortListeners([int]$Port) {
    $pids = @(Get-ListenerPids -Port $Port)
    foreach ($processId in $pids) {
        Write-Info "Releasing port $Port from PID $processId."
        [void](Stop-ProcessTree -ProcessId $processId)
    }
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        $stillListening = netstat -ano | Select-String -Pattern "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+\d+\s*$"
        if (-not $stillListening) { return }
        Start-Sleep -Seconds 1
    }
    throw "Port $Port is still occupied after 20 seconds."
}

function Get-BackendTerminalProcessIds {
    $processIds = [Collections.Generic.HashSet[int]]::new()
    foreach ($process in @(Get-Process -Name 'cmd' -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -eq $script:BackendTerminalTitle })) {
        [void]$processIds.Add([int]$process.Id)
    }
    try {
        foreach ($process in @(Get-CimInstance Win32_Process -Filter "Name = 'cmd.exe'" -ErrorAction Stop |
            Where-Object { [string]$_.CommandLine -match 'server\.app:app' })) {
            [void]$processIds.Add([int]$process.ProcessId)
        }
    }
    catch { }
    return @($processIds)
}

function Stop-ApplicationProcesses {
    param(
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$Settings
    )

    $ports = @([int]$Settings.FASTAPI_PORT, [int]$Settings.UI_PORT) | Sort-Object -Unique
    $processIds = [Collections.Generic.HashSet[int]]::new()
    foreach ($port in $ports) {
        foreach ($processId in @(Get-ListenerPids -Port $port)) {
            [void]$processIds.Add([int]$processId)
        }
    }
    foreach ($processId in @(Get-BackendTerminalProcessIds)) {
        [void]$processIds.Add([int]$processId)
    }

    if ($processIds.Count -eq 0) {
        Write-Info 'No running ParaGraph application processes were found.'
        return
    }

    foreach ($processId in $processIds) {
        Write-Info "Stopping application process tree rooted at PID $processId."
        [void](Stop-ProcessTree -ProcessId $processId)
    }
    foreach ($port in $ports) {
        Stop-PortListeners -Port $port
    }
    Write-Ok "Stopped $($processIds.Count) ParaGraph application process tree(s)."
}

function Get-ListenerPid([int]$Port) {
    foreach ($line in netstat -ano) {
        if ($line -match "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$") {
            return [int]$Matches[1]
        }
    }
    return $null
}

function Resolve-LaunchPortConflicts {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Settings)

    $ports = @([int]$Settings.FASTAPI_PORT, [int]$Settings.UI_PORT) | Sort-Object -Unique
    $listenerRecords = @(Get-PortListenerRecords -Ports $ports)
    if ($listenerRecords.Count -eq 0) { return $true }

    $conflicts = @(Get-PortConflictProcesses -ListenerRecords $listenerRecords)
    if (-not (Confirm-PortConflictTermination -Conflicts $conflicts)) { return $false }

    $terminationErrors = [Collections.Generic.List[string]]::new()
    foreach ($conflict in $conflicts) {
        try {
            [void](Stop-ProcessTree -ProcessId ([int]$conflict.ProcessId))
        }
        catch {
            [void]$terminationErrors.Add(("PID {0} ({1}): {2}" -f $conflict.ProcessId, $conflict.ProcessName, $_.Exception.Message))
        }
    }

    $remainingRecords = @(Get-PortListenerRecords -Ports $ports)
    if ($remainingRecords.Count -gt 0) {
        $remainingConflicts = @(Get-PortConflictProcesses -ListenerRecords $remainingRecords)
        $remainingDetails = @($remainingConflicts | ForEach-Object {
            "PID $($_.ProcessId) ($($_.ProcessName)) on port(s) $(@($_.Ports | Sort-Object -Unique) -join ', ')"
        }) -join '; '
        $failureDetails = if ($terminationErrors.Count -gt 0) {
            " Termination errors: $($terminationErrors -join '; ')."
        } else { '' }
        throw "Approved port-conflict termination did not free all configured ports. Remaining listeners: $remainingDetails.$failureDetails"
    }
    if ($terminationErrors.Count -gt 0) {
        throw "Approved port-conflict termination reported failures: $($terminationErrors -join '; ')."
    }
    Write-Ok 'Configured launch ports are free.'
    return $true
}

#endregion

#region Application lifecycle and verification

function Start-BackendTerminalProcess {
    param([Parameter(Mandatory = $true)][string]$BackendCommand)

    $existingCmdIds = [Collections.Generic.HashSet[int]]::new()
    foreach ($processId in @(Get-Process -Name 'cmd' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)) {
        [void]$existingCmdIds.Add([int]$processId)
    }

    $windowTitleArgument = '"' + $script:BackendTerminalTitle + '"'
    $launcherProcess = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d', '/c', 'start', $windowTitleArgument, 'cmd.exe', '/k', $BackendCommand) -WorkingDirectory $AppDir -PassThru
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        $candidateIds = @(Get-Process -Name 'cmd' -ErrorAction SilentlyContinue |
            Where-Object { -not $existingCmdIds.Contains([int]$_.Id) } |
            Select-Object -ExpandProperty Id)
        $commandLineCandidates = @()
        try {
            $commandLineCandidates = @(Get-CimInstance Win32_Process -Filter "Name = 'cmd.exe'" -ErrorAction Stop |
                Where-Object {
                    -not $existingCmdIds.Contains([int]$_.ProcessId) -and
                    [string]$_.CommandLine -match 'server\.app:app'
                } |
                Select-Object -ExpandProperty ProcessId)
        }
        catch { }

        $terminalId = @($commandLineCandidates | Select-Object -First 1)
        if ($terminalId.Count -eq 0) {
            $terminalId = @(Get-Process -Name 'cmd' -ErrorAction SilentlyContinue |
                Where-Object {
                    -not $existingCmdIds.Contains([int]$_.Id) -and
                    $_.MainWindowTitle -eq $script:BackendTerminalTitle
                } |
                Select-Object -ExpandProperty Id -First 1)
        }
        if ($terminalId.Count -eq 0 -and $candidateIds.Count -eq 1) {
            $terminalId = @($candidateIds[0])
        }
        if ($terminalId.Count -gt 0) {
            $terminal = Get-Process -Id ([int]$terminalId[0]) -ErrorAction SilentlyContinue
            if ($null -ne $terminal -and -not $terminal.HasExited) { return $terminal }
        }
        if ($attempt -lt 20) { Start-Sleep -Milliseconds 100 }
    }

    try { [void](Stop-ProcessTree -ProcessId ([int]$launcherProcess.Id)) } catch { }
    throw "Unable to identify the visible '$script:BackendTerminalTitle' process created for the backend launch."
}

function Invoke-Launch {
    $backendProcess = $null
    $frontendProcess = $null
    try {
        Ensure-PortableRuntimes
        $settings = Import-DotEnv
        Set-LauncherEnvironment

        if (-not (Test-DependenciesReady)) {
            Write-Step 'Required application environments are missing or unusable; installing dependencies.'
            Sync-Dependencies -InstallationType 'Standard'
        } else {
            Write-Ok 'Application environments are ready; skipped dependency installation.'
        }

        $frontendBuildState = Get-FrontendBuildState
        if (-not $frontendBuildState.Current) {
            Write-Step "Frontend build is $($frontendBuildState.Reason); rebuilding frontend."
            Build-Frontend
        } else {
            Write-Ok 'Frontend build fingerprint is current; skipped rebuild.'
        }

        if (-not (Test-Path -LiteralPath $VenvPython)) { throw "Virtual environment Python not found at $VenvPython" }

        $backendPort = [int]$settings.FASTAPI_PORT
        $uiPort = [int]$settings.UI_PORT
        if (-not (Resolve-LaunchPortConflicts -Settings $settings)) { return $false }
        Clear-PythonEnvironment

        $backendArgs = @('-m', 'uvicorn', 'server.app:app', '--host', [string]$settings.FASTAPI_HOST, '--port', [string]$backendPort, '--log-level', 'info')
        if ([string]$settings.RELOAD -ieq 'true') { $backendArgs += '--reload' }
        Write-Step "Launching backend on $($settings.FASTAPI_HOST):$backendPort"
        $quotedPython = '"' + $VenvPython + '"'
        $backendCommand = "$quotedPython $($backendArgs -join ' ')"
        $backendProcess = Start-BackendTerminalProcess -BackendCommand $backendCommand

        $healthUrl = "http://$($settings.FASTAPI_HOST):$backendPort/docs"
        Write-Info "Waiting for $healthUrl"
        if (-not (Invoke-HealthCheck -Url $healthUrl -Attempts 60 -IntervalSeconds 1)) {
            throw "Backend did not become healthy at $healthUrl within 60 seconds."
        }

        Write-Step "Launching frontend preview on $($settings.UI_HOST):$uiPort"
        $frontendProcess = Start-Process -FilePath $NpmCmd -ArgumentList @('run', 'preview', '--', '--host', [string]$settings.UI_HOST, '--port', [string]$uiPort, '--strictPort') -WorkingDirectory $ClientDir -WindowStyle Hidden -PassThru
        $uiUrl = "http://$($settings.UI_HOST):$uiPort"
        if (-not (Invoke-HealthCheck -Url $uiUrl -Attempts 30 -IntervalSeconds 1)) {
            throw "Frontend preview did not become healthy at $uiUrl within 30 seconds."
        }
        Start-Process $uiUrl
        $backendPid = Get-ListenerPid -Port $backendPort
        Write-Ok 'ParaGraph started successfully.'
        Write-Host "  Backend: $healthUrl (PID $backendPid)"
        Write-Host "  Frontend: $uiUrl (PID $($frontendProcess.Id))"
        return $true
    }
    catch {
        foreach ($process in @($frontendProcess, $backendProcess)) {
            if ($null -eq $process) { continue }
            try {
                [void](Stop-ProcessTree -ProcessId ([int]$process.Id))
            }
            catch {
                Write-Warn "Unable to clean up launch-owned PID $($process.Id): $($_.Exception.Message)"
            }
        }
        throw
    }
}

function Invoke-DatabaseInitialization {
    param([switch]$SetupAlreadyReady)
    if (-not $SetupAlreadyReady) {
        Ensure-PortableRuntimes
        Set-LauncherEnvironment
    }
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

function Confirm-DestructiveAction([string]$Description) {
    if (-not $script:LauncherInteractive) {
        throw "The destructive action '$Description' requires an interactive console; no files were changed."
    }
    Clear-LauncherProgress
    $confirmation = ([string](Read-Host "Continue to $($Description)? [y/N]")).Trim()
    if ($confirmation -notmatch '^(?i:y|yes)$') {
        Write-Info 'Operation cancelled. No changes were made.'
        return $false
    }
    return $true
}

function Remove-LogFiles {
    if (-not (Confirm-DestructiveAction 'remove application log files')) { return }
    $logDir = Join-Path $AppDir 'resources\logs'
    if (-not (Test-Path -LiteralPath $logDir)) { Write-Info "Log directory not found: $logDir"; return }
    $logs = @(Get-ChildItem -LiteralPath $logDir -Filter '*.log' -File -ErrorAction SilentlyContinue |
        Sort-Object @{ Expression = { $_.FullName.ToUpperInvariant() }; Descending = $false })
    $skippedBefore = $script:SkippedCacheCount
    foreach ($log in $logs) {
        [void](Remove-PathBestEffort -Path $log.FullName)
    }
    $skipped = $script:SkippedCacheCount - $skippedBefore
    if ($skipped -gt 0) {
        Write-Warn "Removed $($logs.Count - $skipped) log file(s); skipped $skipped locked or protected file(s)."
    } else {
        Write-Ok 'Log files removed.'
    }
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

function Remove-AllData {
    $settings = Import-DotEnv
    $resourceRoot = Resolve-ResourcesRoot -Settings $settings
    Write-Warn "This removes user data under $resourceRoot and the application database."
    Write-Info 'Built-in node definitions, workflow templates, settings, and application source files will be preserved.'
    if (-not (Confirm-DestructiveAction 'remove all user data')) {
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

function Remove-LauncherPath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [switch]$KeepRoot,
        [string[]]$PreserveNames = @('.gitkeep'),
        [switch]$Strict,
        [switch]$WhatIf,
        [string]$Activity = 'ParaGraph: remove files'
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw 'Refusing to remove an empty path.'
    }
    $fullPath = [IO.Path]::GetFullPath($Path)
    $normalizedPath = $fullPath.TrimEnd('\')
    $filesystemRoot = [IO.Path]::GetPathRoot($fullPath).TrimEnd('\')
    $repositoryRoot = if ($script:RepoRoot) { [IO.Path]::GetFullPath([string]$script:RepoRoot).TrimEnd('\') } else { $null }
    if ($normalizedPath -eq $filesystemRoot -or
        ($repositoryRoot -and
        ($normalizedPath -eq $repositoryRoot -or
        $repositoryRoot.StartsWith("$normalizedPath\", [StringComparison]::OrdinalIgnoreCase)))) {
        throw "Refusing to remove a filesystem or repository root: $fullPath"
    }

    $plannedPaths = [Collections.Generic.List[string]]::new()
    $preservedPaths = [Collections.Generic.List[string]]::new()
    $removedPaths = [Collections.Generic.List[string]]::new()
    $skippedPaths = [Collections.Generic.List[string]]::new()
    $enumerationErrorPaths = [Collections.Generic.List[string]]::new()
    $warningMessages = [Collections.Generic.List[string]]::new()
    $result = [ordered]@{
        Target = $fullPath
        Path = $fullPath
        Planned = 0
        PlannedCount = 0
        PlannedPaths = @()
        Preserved = 0
        PreservedCount = 0
        PreservedEntries = @()
        PreservedPaths = @()
        Removed = 0
        RemovedCount = 0
        RemovedPaths = @()
        Skipped = 0
        SkippedCount = 0
        SkippedPaths = @()
        EnumerationErrors = @()
        EnumerationErrorCount = 0
        EnumerationErrorPaths = @()
        WhatIf = [bool]$WhatIf
    }

    try {
        $item = Get-Item -LiteralPath $fullPath -Force -ErrorAction Stop
    }
    catch {
        if ($_.CategoryInfo.Category -eq [System.Management.Automation.ErrorCategory]::ObjectNotFound) {
            Clear-LauncherProgress
            return [pscustomobject]$result
        }
        $message = [string]$_.Exception.Message
        [void]$skippedPaths.Add($fullPath)
        $result.Skipped = $skippedPaths.Count
        $result.SkippedCount = $skippedPaths.Count
        $result.SkippedPaths = @($skippedPaths.ToArray())
        Clear-LauncherProgress
        Write-Warn "Skipped inaccessible path: $fullPath ($message)"
        if ($Strict) { throw }
        return [pscustomobject]$result
    }

    $enumerationErrors = @()
    $entries = if ($item.PSIsContainer) {
        @(Get-ChildItem -LiteralPath $item.FullName -Force -Recurse -ErrorAction SilentlyContinue -ErrorVariable enumerationErrors)
    } else {
        @($item)
    }
    foreach ($enumerationError in @($enumerationErrors)) {
        $errorPath = [string]$enumerationError.TargetObject
        if ([string]::IsNullOrWhiteSpace($errorPath)) { $errorPath = $fullPath }
        [void]$enumerationErrorPaths.Add($errorPath)
        [void]$warningMessages.Add(("Skipped inaccessible path below {0}: {1}" -f $fullPath, $enumerationError.Exception.Message))
    }

    $protectedDirectories = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in @($entries)) {
        if ($entry.Name -in $PreserveNames) {
            [void]$preservedPaths.Add($entry.FullName)
            [void]$protectedDirectories.Add($item.FullName)
            $ancestor = [IO.Path]::GetDirectoryName($entry.FullName)
            while ($ancestor -and $ancestor.StartsWith($item.FullName.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
                [void]$protectedDirectories.Add($ancestor)
                $ancestor = [IO.Path]::GetDirectoryName($ancestor)
            }
        }
    }

    $candidates = @($entries |
        Where-Object { -not $preservedPaths.Contains($_.FullName) -and -not $protectedDirectories.Contains($_.FullName) } |
        Sort-Object @{ Expression = { $_.FullName.Length }; Descending = $true }, @{ Expression = { $_.FullName.ToUpperInvariant() }; Descending = $false })
    if ($item.PSIsContainer -and -not $KeepRoot -and $preservedPaths.Count -eq 0) {
        $candidates += $item
    }
    foreach ($candidate in @($candidates)) { [void]$plannedPaths.Add($candidate.FullName) }
    $result.Planned = $plannedPaths.Count
    $result.PlannedCount = $plannedPaths.Count
    $result.PlannedPaths = @($plannedPaths.ToArray())
    $result.Preserved = $preservedPaths.Count
    $result.PreservedCount = $preservedPaths.Count
    $result.PreservedEntries = @($preservedPaths.ToArray())
    $result.PreservedPaths = @($preservedPaths.ToArray() | Sort-Object { $_.ToUpperInvariant() })
    $result.EnumerationErrors = @($enumerationErrors | ForEach-Object { [string]$_ })
    $result.EnumerationErrorCount = $enumerationErrorPaths.Count
    $result.EnumerationErrorPaths = @($enumerationErrorPaths.ToArray() | Sort-Object { $_.ToUpperInvariant() })

    $progressId = $null
    try {
        if ($plannedPaths.Count -gt 0) {
            $progressId = Start-LauncherProgress -Activity $Activity -Status "0 of $($plannedPaths.Count) items"
        }
        for ($index = 0; $index -lt $plannedPaths.Count; $index++) {
            $candidatePath = $plannedPaths[$index]
            if ($null -ne $progressId) {
                Update-LauncherProgress -Id $progressId -Activity $Activity -Status "$($index + 1) of $($plannedPaths.Count): $([IO.Path]::GetFileName($candidatePath))" -PercentComplete ([int](($index + 1) * 100 / [Math]::Max(1, $plannedPaths.Count)))
            }
            if ($WhatIf) { continue }
            try {
                Remove-Item -LiteralPath $candidatePath -Force -Confirm:$false -ErrorAction Stop
                [void]$removedPaths.Add($candidatePath)
            }
            catch {
                [void]$skippedPaths.Add($candidatePath)
                [void]$warningMessages.Add("Skipped locked or protected path: $candidatePath ($($_.Exception.Message))")
            }
        }
    }
    finally {
        if ($null -ne $progressId) { Complete-LauncherProgress -Id $progressId }
    }

    $result.Removed = $removedPaths.Count
    $result.RemovedCount = $removedPaths.Count
    $result.RemovedPaths = @($removedPaths.ToArray())
    $result.Skipped = $skippedPaths.Count
    $result.SkippedCount = $skippedPaths.Count
    $result.SkippedPaths = @($skippedPaths.ToArray())
    foreach ($message in $warningMessages.ToArray()) { Write-Warn $message }
    Clear-LauncherProgress
    if ($Strict -and ($result.SkippedCount -gt 0 -or $result.EnumerationErrorCount -gt 0)) {
        throw "Removal of '$fullPath' was incomplete. Skipped $($result.SkippedCount) item(s) and encountered $($result.EnumerationErrorCount) enumeration error(s)."
    }
    return [pscustomobject]$result
}

function Remove-PathBestEffort {
    param([Parameter(Mandatory = $true)][string]$Path)
    $result = Remove-LauncherPath -Path $Path -Activity "ParaGraph: remove $([IO.Path]::GetFileName($Path))"
    foreach ($skippedPath in @($result.SkippedPaths)) { Register-SkippedCachePath -Path ([string]$skippedPath) }
    foreach ($errorPath in @($result.EnumerationErrorPaths)) { Register-SkippedCachePath -Path ([string]$errorPath) }
    return $result.SkippedCount -eq 0 -and $result.EnumerationErrorCount -eq 0
}

function Clear-CacheDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [string[]]$PreserveNames = @('.gitkeep')
    )

    if (-not (Test-Path -LiteralPath $Path -ErrorAction SilentlyContinue)) {
        Clear-LauncherProgress
        return $true
    }
    $result = Remove-LauncherPath -Path $Path -KeepRoot -PreserveNames $PreserveNames -Activity "ParaGraph: clear $Path"
    foreach ($skippedPath in @($result.SkippedPaths)) { Register-SkippedCachePath -Path ([string]$skippedPath) }
    foreach ($errorPath in @($result.EnumerationErrorPaths)) { Register-SkippedCachePath -Path ([string]$errorPath) }
    return $result.SkippedCount -eq 0 -and $result.EnumerationErrorCount -eq 0
}

function Remove-PythonCaches {
    $allRemoved = $true
    $venvRoot = ([IO.Path]::GetFullPath($VenvDir)).TrimEnd('\') + '\'
    foreach ($root in @($ServerDir, $TestsDir)) {
        if (-not (Test-Path -LiteralPath $root -ErrorAction SilentlyContinue)) { continue }
        $cacheDirectories = @(Get-ChildItem -LiteralPath $root -Directory -Filter '__pycache__' -Recurse -Force -ErrorAction SilentlyContinue |
            Where-Object { -not ([IO.Path]::GetFullPath($_.FullName)).StartsWith($venvRoot, [StringComparison]::OrdinalIgnoreCase) } |
            Sort-Object @{ Expression = { $_.FullName.Length }; Descending = $true }, @{ Expression = { $_.FullName.ToUpperInvariant() }; Descending = $false })
        foreach ($cacheDirectory in $cacheDirectories) {
            if (-not (Remove-PathBestEffort -Path $cacheDirectory.FullName)) { $allRemoved = $false }
        }
    }
    return $allRemoved
}

function Clear-DeveloperCache {
    return Clear-CacheDirectory -Path $CacheRoot
}

function Clear-ApplicationCache {
    if (-not (Confirm-DestructiveAction 'clear the canonical runtime, test/tool, browser, frontend, and library cache hierarchy under runtimes/cache')) { return }
    $script:SkippedCacheCount = 0
    $script:FirstSkippedCachePath = $null
    $allRemoved = Remove-PythonCaches
    if (-not (Clear-DeveloperCache)) { $allRemoved = $false }
    if ($allRemoved) {
        Write-Ok 'The canonical cache hierarchy under runtimes/cache was removed.'
    } else {
        Write-Warn ("The canonical cache hierarchy under runtimes/cache was cleared where permitted; {0} locked or protected entries were skipped. First skipped path: {1}" -f $script:SkippedCacheCount, $script:FirstSkippedCachePath)
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
    if (-not (Confirm-DestructiveAction 'remove local runtimes, dependencies, caches, and build outputs')) { return }
    $script:SkippedCacheCount = 0
    $script:FirstSkippedCachePath = $null
    $allRemoved = $true
    foreach ($relativePath in @(
        'runtimes', 'app\server\.venv', '.venv', 'app\client\node_modules'
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
    $branch = (& git -C $script:RepoRoot branch --show-current 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Unable to determine the current Git branch.' }
    return $branch
}

function Get-CurrentGitRevision {
    $revision = (& git -C $script:RepoRoot rev-parse HEAD 2>$null | Out-String).Trim()
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

    $status = (& git -C $script:RepoRoot status --porcelain 2>$null | Out-String).Trim()
    if (-not [string]::IsNullOrWhiteSpace($status)) {
        throw 'Update requires a clean Git working tree. Commit or safely preserve local changes before retrying.'
    }

    Write-Step 'Updating application from origin/main with git pull (fast-forward only)'
    & git -C $script:RepoRoot pull --ff-only origin main
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
    if ($exitCode -ne 0) { throw "Git pull failed with exit code $exitCode" }
    Write-Ok 'Application update completed.'
}

function Check-ForUpdates {
    $localRevision = Get-CurrentGitRevision
    $remoteLine = (& git -C $script:RepoRoot ls-remote origin refs/heads/main 2>$null | Select-Object -First 1)
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
    Clear-LauncherProgress
    Write-Host
    Write-Host 'Press any key to return to the menu...' -ForegroundColor DarkGray
    if (-not $script:LauncherInteractive) { return }
    try { $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { $null = Read-Host }
}

while ($true) {
    $entries = @(Show-Menu)
    $maxOption = $entries.Count
    if (-not $script:LauncherInteractive) { break }
    Clear-LauncherProgress
    $selection = Read-Host "  Select an option (1-$maxOption)"
    if ($selection -notmatch '^[1-9][0-9]*$' -or [int]$selection -lt 1 -or [int]$selection -gt $maxOption) {
        Write-Warn "Select a number from 1 through $maxOption."
        Wait-ForMenu
        continue
    }
    $entry = $entries[[int]$selection - 1]
    if ($entry.Key -eq 'Exit') { break }
    try {
        Invoke-TrackedLauncherAction -Name $entry.Title -Action {
            switch ($entry.Key) {
                'Launch' { if (Invoke-Launch) { exit 0 } }
                'KillProcesses' { Stop-ApplicationProcesses -Settings (Import-DotEnv) }
                'Install' {
                    Ensure-PortableRuntimes
                    $installationType = Read-InstallationType
                    Import-DotEnv | Out-Null
                    Set-LauncherEnvironment
                    Sync-Dependencies -PruneCache -InstallationType $installationType
                    Invoke-DatabaseInitialization -SetupAlreadyReady
                    Build-Frontend
                }
                'Rebuild' { Invoke-FrontendRebuild }
                'Database' { Invoke-DatabaseInitialization }
                'Tests' { Invoke-TestSuite }
                'Check' { Check-ForUpdates }
                'Update' { Update-Application }
                'Logs' { Remove-LogFiles }
                'Cache' { Clear-ApplicationCache }
                'AllData' { Remove-AllData }
                'Uninstall' { Uninstall-Application }
            }
        }
    } catch {
        Write-Fatal $_.Exception.Message
    }
    Wait-ForMenu
}
Clear-LauncherProgress
