$ErrorActionPreference = 'Stop'

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$launcherPath = Join-Path $repoRoot 'start_on_windows.ps1'
$tempParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$fixtureRoot = Join-Path $tempParent ("paragraph-cleanup-tests-" + [guid]::NewGuid().ToString('N'))
$script:TestFailures = [Collections.Generic.List[string]]::new()
$script:TestConfirm = $true
$script:SimulatedProcesses = @()

Push-Location $tempParent
try { . $launcherPath } finally { Pop-Location }
if ([IO.Path]::GetFullPath($script:RepoRoot) -ne $repoRoot) { throw 'Launcher paths must resolve from PSScriptRoot when invoked outside the repository.' }

function Get-ActiveParaGraphProcessIds { return @($script:SimulatedProcesses) }
function Confirm-DestructiveAction([string]$Description) { return [bool]$script:TestConfirm }

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function New-TestDirectory([string]$Path) {
    [void][IO.Directory]::CreateDirectory($Path)
}

function New-TestFile([string]$Path, [string]$Content = 'fixture') {
    $parent = [IO.Path]::GetDirectoryName($Path)
    if ($parent) { New-TestDirectory $parent }
    [IO.File]::WriteAllText($Path, $Content)
}

function Reset-TestFixture {
    if (Test-Path -LiteralPath $fixtureRoot) {
        $fullPath = [IO.Path]::GetFullPath($fixtureRoot)
        $tempPrefix = $tempParent.TrimEnd('\') + '\'
        if (-not $fullPath.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe test cleanup target: $fullPath" }
        Remove-Item -LiteralPath $fullPath -Recurse -Force -ErrorAction Stop
    }
    New-TestDirectory $fixtureRoot
    $script:RepoRoot = Join-Path $fixtureRoot 'repo'
    $script:AppDir = Join-Path $script:RepoRoot 'app'
    $script:ServerDir = Join-Path $script:AppDir 'server'
    $script:ClientDir = Join-Path $script:AppDir 'client'
    $script:TestsDir = Join-Path $script:AppDir 'tests'
    $script:SettingsDir = Join-Path $script:RepoRoot 'settings'
    $script:DefaultResourcesDir = Join-Path $script:RepoRoot 'data'
    $script:RuntimesDir = Join-Path $script:RepoRoot 'runtimes'
    $script:CacheRoot = Join-Path $script:RuntimesDir 'cache'
    $script:VenvDir = Join-Path $script:ServerDir '.venv'
    $script:DotEnv = Join-Path $script:SettingsDir '.env'
    $script:DryRun = $false
    $script:LauncherInteractive = $true
    $env:PARAGRAPH_RESOURCES_DIR = Join-Path $fixtureRoot 'resources'
    New-TestDirectory $script:RepoRoot
    New-TestDirectory $script:SettingsDir
    New-TestDirectory $script:ServerDir
    New-TestDirectory $script:ClientDir
    New-TestDirectory $script:TestsDir
    New-TestDirectory $script:DefaultResourcesDir
}

function Invoke-TestCase([string]$Name, [scriptblock]$Test) {
    try {
        Reset-TestFixture
        & $Test
        Write-Host "[PASS] $Name" -ForegroundColor Green
    } catch {
        $script:TestFailures.Add("$Name`: $($_.Exception.Message)")
        Write-Host "[FAIL] $Name`: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Invoke-TestCase -Name 'cache discovery previews nested, hidden, frontend, backend, and generated test paths' -Test {
    $resourcesRoot = $env:PARAGRAPH_RESOURCES_DIR
    New-TestDirectory (Join-Path $script:CacheRoot 'pytest')
    New-TestFile (Join-Path $script:CacheRoot '.gitkeep')
    New-TestFile (Join-Path $script:CacheRoot 'pytest\case.tmp')
    New-TestFile (Join-Path $script:RepoRoot '.pytest_cache\v\cache\nodeids')
    New-TestFile (Join-Path $script:RepoRoot '.ruff_cache\content\a')
    New-TestFile (Join-Path $script:RepoRoot '.coverage.123')
    New-TestFile (Join-Path $script:RepoRoot 'coverage.xml')
    New-TestFile (Join-Path $script:ServerDir 'api\__pycache__\route.pyc')
    New-TestFile (Join-Path $script:ServerDir 'api\nested.pyc')
    New-TestFile (Join-Path $script:TestsDir 'unit\.pytest_cache\v\cache\lastfailed')
    New-TestFile (Join-Path $script:AppDir 'scripts\__pycache__\initialize.pyc')
    New-TestFile (Join-Path $script:VenvDir 'Lib\__pycache__\package.pyc')
    New-TestFile (Join-Path $script:ClientDir 'src\.vite\deps\chunk.js')
    New-TestFile (Join-Path $script:ClientDir 'node_modules\.cache\eslint\cache')
    New-TestFile (Join-Path $script:ClientDir 'node_modules\package.json')
    New-TestFile (Join-Path $script:RepoRoot 'assets\cache\pytest-tmp-cleanup\db.sqlite')
    New-TestFile (Join-Path $resourcesRoot 'database_config.json') ('{"backend":"sqlite","database_path":"db.sqlite"}')

    $script:DryRun = $true
    $discovery = Get-RecognizedCacheTargets -IncludeCanonical
    $paths = @($discovery.Targets | ForEach-Object { [IO.Path]::GetFullPath($_.Path) })
    foreach ($expected in @(
        $script:CacheRoot, (Join-Path $script:RepoRoot '.pytest_cache'), (Join-Path $script:RepoRoot '.ruff_cache'),
        (Join-Path $script:RepoRoot '.coverage.123'), (Join-Path $script:RepoRoot 'coverage.xml'),
        (Join-Path $script:ServerDir 'api\__pycache__'), (Join-Path $script:ServerDir 'api\nested.pyc'),
        (Join-Path $script:TestsDir 'unit\.pytest_cache'), (Join-Path $script:AppDir 'scripts\__pycache__'), (Join-Path $script:VenvDir 'Lib\__pycache__'),
        (Join-Path $script:ClientDir 'src\.vite'), (Join-Path $script:ClientDir 'node_modules\.cache'),
        (Join-Path $script:RepoRoot 'assets\cache\pytest-tmp-cleanup')
    )) { Assert-True ($paths -contains [IO.Path]::GetFullPath($expected)) "Cache target was not discovered: $expected" }

    Clear-ApplicationCache
    Assert-True (Test-Path -LiteralPath (Join-Path $script:ServerDir 'api\__pycache__\route.pyc')) 'Dry run removed a backend cache.'
    Assert-True (Test-Path -LiteralPath (Join-Path $script:ClientDir 'node_modules\package.json')) 'Dry run changed frontend dependencies.'
    Assert-True (Test-Path -LiteralPath (Join-Path $resourcesRoot 'database_config.json')) 'Dry run changed persistent configuration.'
}

Invoke-TestCase -Name 'cache cleanup is repeatable and preserves dependencies, sentinel, and user data' -Test {
    $resourcesRoot = $env:PARAGRAPH_RESOURCES_DIR
    New-TestFile (Join-Path $script:CacheRoot '.gitkeep')
    New-TestFile (Join-Path $script:CacheRoot 'vite\cache.bin')
    New-TestFile (Join-Path $script:RepoRoot '.pytest_cache\cache')
    New-TestFile (Join-Path $script:RepoRoot '.ruff_cache\cache')
    New-TestFile (Join-Path $script:ClientDir 'node_modules\.cache\cache')
    New-TestFile (Join-Path $script:ClientDir 'node_modules\package.json')
    New-TestFile (Join-Path $script:ServerDir 'api\__pycache__\route.pyc')
    New-TestFile (Join-Path $resourcesRoot 'database_config.json') ('{"backend":"sqlite","database_path":"db.sqlite"}')
    New-TestFile (Join-Path $resourcesRoot 'artifacts\upload.csv')
    $script:DryRun = $false

    Clear-ApplicationCache
    Clear-ApplicationCache
    Assert-True (Test-Path -LiteralPath (Join-Path $script:CacheRoot '.gitkeep')) 'Cache sentinel was removed.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $script:CacheRoot 'vite\cache.bin'))) 'Canonical runtime cache remained.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $script:RepoRoot '.pytest_cache'))) 'Root pytest cache remained.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $script:ClientDir 'node_modules\.cache'))) 'Client dependency cache remained.'
    Assert-True (Test-Path -LiteralPath (Join-Path $script:ClientDir 'node_modules\package.json')) 'Cache cleanup removed frontend dependencies.'
    Assert-True (Test-Path -LiteralPath (Join-Path $resourcesRoot 'artifacts\upload.csv')) 'Cache cleanup removed user artifacts.'
}

Invoke-TestCase -Name 'maintenance menu actions and ordering remain stable' -Test {
    $keys = @(Get-LauncherMenuEntries | ForEach-Object { $_.Key })
    $expected = @('Launch', 'KillProcesses', 'Install', 'Rebuild', 'Database', 'Tests', 'Check', 'Update', 'Logs', 'Cache', 'AllData', 'Uninstall', 'Exit')
    Assert-True (($keys -join ',') -eq ($expected -join ',')) 'Existing menu actions or numbering changed.'
}

Invoke-TestCase -Name 'path safeguards reject traversal and preserve junction targets' -Test {
    $outside = Join-Path $fixtureRoot 'outside'
    New-TestFile (Join-Path $outside 'keep.txt')
    $failure = $null
    try { [void](Get-LauncherPathPlan -Path (Join-Path $script:RepoRoot '..\outside') -AllowedRoots @($script:RepoRoot)) } catch { $failure = $_.Exception.Message }
    Assert-True ($failure -match 'traversal|outside registered') 'Traversal path was not rejected.'
    $failure = $null
    try { [void](Get-LauncherPathPlan -Path (Join-Path $outside 'keep.txt') -AllowedRoots @($script:RepoRoot)) } catch { $failure = $_.Exception.Message }
    Assert-True ($failure -match 'outside registered') 'A path outside registered roots was not rejected.'
    $failure = $null
    try { [void](Get-LauncherPathPlan -Path $script:RepoRoot -AllowedRoots @($script:RepoRoot)) } catch { $failure = $_.Exception.Message }
    Assert-True ($failure -match 'root') 'Repository root deletion was not rejected.'

    $link = Join-Path $script:CacheRoot 'outside-link'
    New-TestDirectory $script:CacheRoot
    try { New-Item -ItemType Junction -Path $link -Target $outside -ErrorAction Stop | Out-Null }
    catch {
        Write-Warn "Junction assertion could not run in this environment: $($_.Exception.Message)"
        return
    }
    New-TestFile (Join-Path $script:CacheRoot 'ordinary.cache')
    $result = Remove-LauncherPath -Path $script:CacheRoot -AllowedRoots @($script:RepoRoot) -KeepRoot
    Assert-True (@($result.SkippedPaths) -contains $link) 'Junction was not reported as skipped.'
    Assert-True (Test-Path -LiteralPath (Join-Path $outside 'keep.txt')) 'Junction cleanup modified its external target.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $script:CacheRoot 'ordinary.cache'))) 'Cleanup failed to remove a normal sibling.'
}

Invoke-TestCase -Name 'locked entries are reported and a second pass completes safely' -Test {
    $lockedRoot = Join-Path $script:RepoRoot 'locked-fixture'
    $lockedFile = Join-Path $lockedRoot 'locked.bin'
    $ordinaryFile = Join-Path $lockedRoot 'ordinary.bin'
    New-TestFile $lockedFile
    New-TestFile $ordinaryFile
    $stream = [IO.File]::Open($lockedFile, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    try {
        $result = Remove-LauncherPath -Path $lockedRoot -AllowedRoots @($script:RepoRoot) -KeepRoot
        Assert-True ($result.FailedPaths.Count -gt 0) 'Locked file failure was not reported.'
        Assert-True (-not (Test-Path -LiteralPath $ordinaryFile)) 'An unlocked sibling was not removed.'
        Assert-True (Test-Path -LiteralPath $lockedFile) 'Locked file was unexpectedly removed.'
    } finally { $stream.Dispose() }
    $second = Remove-LauncherPath -Path $lockedRoot -AllowedRoots @($script:RepoRoot) -KeepRoot
    Assert-True ($second.FailedPaths.Count -eq 0) 'Second cleanup pass did not complete.'
}

Invoke-TestCase -Name 'permission-denied child is reported while accessible siblings are cleaned' -Test {
    $permissionRoot = Join-Path $script:RepoRoot 'permission-fixture'
    $deniedDirectory = Join-Path $permissionRoot 'denied'
    $deniedFile = Join-Path $deniedDirectory 'keep.bin'
    $ordinaryFile = Join-Path $permissionRoot 'ordinary.bin'
    New-TestFile $deniedFile
    New-TestFile $ordinaryFile

    $originalAcl = Get-Acl -LiteralPath $deniedDirectory
    $restrictedAcl = Get-Acl -LiteralPath $deniedDirectory
    $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $denyList = [Security.AccessControl.FileSystemAccessRule]::new(
        $currentSid,
        [Security.AccessControl.FileSystemRights]::ListDirectory,
        [Security.AccessControl.AccessControlType]::Deny
    )
    [void]$restrictedAcl.AddAccessRule($denyList)
    Set-Acl -LiteralPath $deniedDirectory -AclObject $restrictedAcl
    try {
        $result = Remove-LauncherPath -Path $permissionRoot -AllowedRoots @($script:RepoRoot) -KeepRoot
        Assert-True ($result.FailedPaths.Count -gt 0) 'Access-denied enumeration was not reported.'
        Assert-True (-not (Test-Path -LiteralPath $ordinaryFile)) 'An accessible sibling was not removed.'
        Assert-True (Test-Path -LiteralPath $deniedFile) 'The denied directory contents were changed.'
    } finally {
        Set-Acl -LiteralPath $deniedDirectory -AclObject $originalAcl
    }
}

Invoke-TestCase -Name 'cleanup refuses to run while a ParaGraph process is active' -Test {
    $script:SimulatedProcesses = @(43210)
    $failure = $null
    try { Assert-ApplicationStopped } catch { $failure = $_.Exception.Message }
    $script:SimulatedProcesses = @()
    Assert-True ($failure -match '43210') 'Active application process was not reported.'
}

Invoke-TestCase -Name 'uninstall preserves user data while full removal targets configured external database' -Test {
    $resourcesRoot = $env:PARAGRAPH_RESOURCES_DIR
    $databaseParent = Join-Path $fixtureRoot 'external-database'
    $databasePath = Join-Path $databaseParent 'paragraph.sqlite'
    New-TestFile (Join-Path $script:CacheRoot '.gitkeep')
    New-TestFile (Join-Path $script:RuntimesDir 'python\python.exe')
    New-TestFile (Join-Path $script:VenvDir 'Scripts\python.exe')
    New-TestFile (Join-Path $script:RepoRoot '.venv\Scripts\python.exe')
    New-TestFile (Join-Path $script:ClientDir 'node_modules\package.json')
    New-TestFile $script:DotEnv ("FASTAPI_HOST=127.0.0.1`nFASTAPI_PORT=5002`nUI_HOST=127.0.0.1`nUI_PORT=8002`nRELOAD=false`nPARAGRAPH_RESOURCES_DIR=$resourcesRoot")
    New-TestFile (Join-Path $resourcesRoot 'database_config.json') (ConvertTo-Json @{ backend = 'sqlite'; database_path = $databasePath })
    New-TestFile $databasePath
    New-TestFile "$databasePath-wal"
    New-TestFile (Join-Path $resourcesRoot 'artifacts\upload.csv')
    New-TestFile (Join-Path $resourcesRoot 'logs\ParaGraph_test.log')
    New-TestFile (Join-Path $resourcesRoot 'logs\other.log')
    New-TestFile (Join-Path $resourcesRoot 'models\model.bin')
    New-TestFile (Join-Path $resourcesRoot 'nodes\custom_nodes\custom.json')
    New-TestFile (Join-Path $resourcesRoot 'workflow_templates\template.json')
    New-TestFile (Join-Path $resourcesRoot '.database-test-stale')

    Uninstall-Application
    Assert-True (Test-Path -LiteralPath $databasePath) 'Standard uninstall removed the application database.'
    Assert-True (Test-Path -LiteralPath (Join-Path $resourcesRoot 'artifacts\upload.csv')) 'Standard uninstall removed user artifacts.'
    Assert-True (Test-Path -LiteralPath (Join-Path $resourcesRoot 'models\model.bin')) 'Standard uninstall removed user model files.'
    Assert-True (Test-Path -LiteralPath (Join-Path $resourcesRoot 'nodes\custom_nodes\custom.json')) 'Standard uninstall removed custom nodes.'
    Assert-True (Test-Path -LiteralPath (Join-Path $resourcesRoot 'workflow_templates\template.json')) 'Standard uninstall removed templates.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $resourcesRoot 'logs\ParaGraph_test.log'))) 'Standard uninstall left ParaGraph logs.'
    Assert-True (Test-Path -LiteralPath (Join-Path $resourcesRoot 'logs\other.log')) 'Standard uninstall removed an unrelated log.'
    Assert-True (Test-Path -LiteralPath (Join-Path $script:RepoRoot '.venv\Scripts\python.exe')) 'Uninstall removed the unowned repository-root venv.'

    $script:TestConfirm = $false
    Remove-AllData
    Assert-True (Test-Path -LiteralPath $databasePath) 'Cancelled data removal changed the external database.'
    $script:TestConfirm = $true
    Remove-AllData
    Assert-True (-not (Test-Path -LiteralPath $databasePath)) 'Full data removal missed the configured external database.'
    Assert-True (-not (Test-Path -LiteralPath "$databasePath-wal")) 'Full data removal missed the SQLite WAL sidecar.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $resourcesRoot 'artifacts\upload.csv'))) 'Full data removal left uploaded artifacts.'
    Assert-True (Test-Path -LiteralPath (Join-Path $resourcesRoot 'database_config.json')) 'Full data removal removed application settings.'
    Assert-True (Test-Path -LiteralPath $script:DotEnv) 'Full data removal removed the launcher settings file.'
    Assert-True (Test-Path -LiteralPath (Join-Path $resourcesRoot 'workflow_templates\template.json')) 'Full data removal removed built-in templates.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $resourcesRoot 'nodes\custom_nodes\custom.json'))) 'Full data removal left custom nodes.'
}

Invoke-TestCase -Name 'invalid database configuration aborts full data removal before mutation' -Test {
    $resourcesRoot = $env:PARAGRAPH_RESOURCES_DIR
    New-TestFile (Join-Path $resourcesRoot 'database_config.json') '{invalid json'
    New-TestFile (Join-Path $resourcesRoot 'artifacts\keep.csv')
    $failure = $null
    try { Remove-AllData } catch { $failure = $_.Exception.Message }
    Assert-True ($failure -match 'stopped before any changes') 'Invalid database configuration did not stop removal.'
    Assert-True (Test-Path -LiteralPath (Join-Path $resourcesRoot 'artifacts\keep.csv')) 'Invalid database configuration caused partial deletion.'
}

if (Test-Path -LiteralPath $fixtureRoot) {
    $fullPath = [IO.Path]::GetFullPath($fixtureRoot)
    $tempPrefix = $tempParent.TrimEnd('\') + '\'
    if (-not $fullPath.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe test cleanup target: $fullPath" }
    Remove-Item -LiteralPath $fullPath -Recurse -Force -ErrorAction SilentlyContinue
}
Remove-Item Env:PARAGRAPH_RESOURCES_DIR -ErrorAction SilentlyContinue

if ($script:TestFailures.Count -gt 0) {
    throw ("{0} cleanup test(s) failed: {1}" -f $script:TestFailures.Count, ($script:TestFailures -join '; '))
}
Write-Host 'All launcher cleanup checks passed.' -ForegroundColor Green
