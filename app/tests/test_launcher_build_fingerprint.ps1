$ErrorActionPreference = 'Stop'

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$launcherPath = Join-Path $repoRoot 'start_on_windows.ps1'
. $launcherPath

$script:TestFailures = [Collections.Generic.List[string]]::new()
$script:FixturePrefix = 'paragraph-launcher-build-fingerprint-'
$script:FixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ($script:FixturePrefix + [guid]::NewGuid().ToString('N'))
$script:ClientDir = Join-Path $script:FixtureRoot 'client'
$script:FrontendBuildDir = Join-Path $script:FixtureRoot 'frontend-dist'
$script:NpmCmd = Join-Path $script:FixtureRoot 'npm.cmd'
$script:EnvironmentKeys = @('VITE_API_BASE_URL', 'FASTAPI_HOST', 'FASTAPI_PORT', 'UI_HOST', 'UI_PORT')
$script:OriginalEnvironment = @{}
foreach ($key in $script:EnvironmentKeys) {
    $script:OriginalEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Invoke-TestCase {
    param([string]$Name, [scriptblock]$Test)

    try {
        & $Test
        Write-Host ("[PASS] {0}" -f $Name) -ForegroundColor Green
    }
    catch {
        $script:TestFailures.Add(('{0}: {1}' -f $Name, $_.Exception.Message))
        Write-Host ("[FAIL] {0}: {1}" -f $Name, $_.Exception.Message) -ForegroundColor Red
    }
}

function Write-FixtureFile {
    param([string]$RelativePath, [string]$Contents)

    $path = Join-Path $script:ClientDir ($RelativePath.Replace('/', '\'))
    $parent = Split-Path -Parent $path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    [IO.File]::WriteAllText($path, $Contents, [Text.Encoding]::UTF8)
}

function Write-FakeNpmCommand {
    param([string]$Path, [string]$RecordPath, [int]$ExitCode)

    $lines = @(
        '@echo off',
        ('echo %* > "' + $RecordPath + '"'),
        ('exit /b ' + $ExitCode)
    )
    [IO.File]::WriteAllLines($Path, $lines, [Text.Encoding]::ASCII)
}

function Set-ProcessEnvironmentValue {
    param([string]$Name, [string]$Value)
    [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
}

function Restore-ProcessEnvironment {
    foreach ($key in $script:EnvironmentKeys) {
        $value = $script:OriginalEnvironment[$key]
        if ($null -eq $value) {
            Remove-Item -LiteralPath "Env:$key" -ErrorAction SilentlyContinue
        } else {
            Set-Item -LiteralPath "Env:$key" -Value $value
        }
    }
}

try {
    New-Item -ItemType Directory -Path $script:ClientDir -Force | Out-Null
    New-Item -ItemType Directory -Path $script:FrontendBuildDir -Force | Out-Null

    $fixtureFiles = [ordered]@{
        'src/main.ts' = 'export const main = 1;'
        'src/nested/helper.ts' = 'export const helper = 1;'
        'public/logo.svg' = '<svg></svg>'
        'index.html' = '<html><body>fixture</body></html>'
        'package.json' = '{ "scripts": { "build": "tsc && vite build" } }'
        'package-lock.json' = '{ "lockfileVersion": 3 }'
        'tsconfig.json' = '{ "compilerOptions": {} }'
        'tsconfig.node.json' = '{ "compilerOptions": {} }'
        'vite.config.ts' = 'export default {};'
    }
    foreach ($relativePath in $fixtureFiles.Keys) {
        Write-FixtureFile -RelativePath $relativePath -Contents $fixtureFiles[$relativePath]
    }
    Set-ProcessEnvironmentValue -Name 'VITE_API_BASE_URL' -Value '/api'
    Set-ProcessEnvironmentValue -Name 'FASTAPI_HOST' -Value '127.0.0.1'
    Set-ProcessEnvironmentValue -Name 'FASTAPI_PORT' -Value '5002'
    Set-ProcessEnvironmentValue -Name 'UI_HOST' -Value '127.0.0.1'
    Set-ProcessEnvironmentValue -Name 'UI_PORT' -Value '8002'

    Invoke-TestCase -Name 'every frontend build input changes the fingerprint' -Test {
        $expectedPaths = @($fixtureFiles.Keys | Sort-Object)
        $actualPaths = @(Get-FrontendBuildInputFiles)
        $missingPaths = @($expectedPaths | Where-Object { $actualPaths -notcontains $_ })
        $unexpectedPaths = @($actualPaths | Where-Object { $expectedPaths -notcontains $_ })
        Assert-True ($missingPaths.Count -eq 0) ("Build inputs missing from fingerprint: " + ($missingPaths -join ', '))
        Assert-True ($unexpectedPaths.Count -eq 0) ("Unexpected fixture inputs: " + ($unexpectedPaths -join ', '))

        $baseFingerprint = Get-FrontendBuildFingerprint
        foreach ($relativePath in $actualPaths) {
            $path = Join-Path $script:ClientDir ($relativePath.Replace('/', '\'))
            $originalBytes = [IO.File]::ReadAllBytes($path)
            try {
                $changedBytes = [byte[]]::new($originalBytes.Length + 1)
                [Array]::Copy($originalBytes, $changedBytes, $originalBytes.Length)
                $changedBytes[$changedBytes.Length - 1] = 33
                [IO.File]::WriteAllBytes($path, $changedBytes)
                $changedFingerprint = Get-FrontendBuildFingerprint
                Assert-True ($changedFingerprint -ne $baseFingerprint) "Changing $relativePath did not change the fingerprint."
            }
            finally {
                [IO.File]::WriteAllBytes($path, $originalBytes)
            }
            Assert-True ((Get-FrontendBuildFingerprint) -eq $baseFingerprint) "Restoring $relativePath did not restore the fingerprint."
        }
    }

    Invoke-TestCase -Name 'VITE_API_BASE_URL invalidates while runtime host and port settings do not' -Test {
        $baseFingerprint = Get-FrontendBuildFingerprint
        Set-ProcessEnvironmentValue -Name 'VITE_API_BASE_URL' -Value '/api/v2'
        $changedApiFingerprint = Get-FrontendBuildFingerprint
        Assert-True ($changedApiFingerprint -ne $baseFingerprint) 'Changing VITE_API_BASE_URL did not change the fingerprint.'

        Set-ProcessEnvironmentValue -Name 'VITE_API_BASE_URL' -Value '/api'
        $baseFingerprint = Get-FrontendBuildFingerprint
        Set-ProcessEnvironmentValue -Name 'FASTAPI_HOST' -Value '192.0.2.10'
        Set-ProcessEnvironmentValue -Name 'FASTAPI_PORT' -Value '6500'
        Set-ProcessEnvironmentValue -Name 'UI_HOST' -Value '192.0.2.11'
        Set-ProcessEnvironmentValue -Name 'UI_PORT' -Value '8500'
        Assert-True ((Get-FrontendBuildFingerprint) -eq $baseFingerprint) 'Runtime host or port settings changed the fingerprint.'
    }

    Invoke-TestCase -Name 'missing, invalid, changed, and current build states are classified' -Test {
        $indexPath = Join-Path $script:FrontendBuildDir 'index.html'
        $fingerprintPath = Join-Path $script:FrontendBuildDir '.paragraph-build-fingerprint'
        Remove-Item -LiteralPath $indexPath, $fingerprintPath -Force -ErrorAction SilentlyContinue
        $state = Get-FrontendBuildState
        Assert-True (-not $state.Current -and $state.Reason -eq 'build output missing') 'Missing build output was not reported as stale.'

        [IO.File]::WriteAllText($indexPath, 'fixture output', [Text.Encoding]::UTF8)
        $state = Get-FrontendBuildState
        Assert-True (-not $state.Current -and $state.Reason -eq 'fingerprint missing') 'Missing fingerprint was not reported as stale.'

        [IO.File]::WriteAllText($fingerprintPath, 'invalid', [Text.Encoding]::ASCII)
        $state = Get-FrontendBuildState
        Assert-True (-not $state.Current -and $state.Reason -eq 'fingerprint invalid') 'Invalid fingerprint was not reported as stale.'

        $currentFingerprint = Get-FrontendBuildFingerprint
        $differentFingerprint = if ($currentFingerprint.EndsWith('0')) {
            $currentFingerprint.Substring(0, 63) + '1'
        } else {
            $currentFingerprint.Substring(0, 63) + '0'
        }
        [IO.File]::WriteAllText($fingerprintPath, $differentFingerprint, [Text.Encoding]::ASCII)
        $state = Get-FrontendBuildState
        Assert-True (-not $state.Current -and $state.Reason -eq 'input fingerprint changed') 'Changed input fingerprint was not reported as stale.'

        $missingInputPath = Join-Path $script:ClientDir 'vite.config.ts'
        $savedInput = [IO.File]::ReadAllBytes($missingInputPath)
        try {
            Remove-Item -LiteralPath $missingInputPath -Force
            [IO.File]::WriteAllText($fingerprintPath, $currentFingerprint, [Text.Encoding]::ASCII)
            $state = Get-FrontendBuildState
            Assert-True (-not $state.Current -and $state.Reason -like 'input fingerprint unavailable:*') 'Missing build input was not reported as stale.'
        }
        finally {
            [IO.File]::WriteAllBytes($missingInputPath, $savedInput)
        }

        [IO.File]::WriteAllText($fingerprintPath, $currentFingerprint, [Text.Encoding]::ASCII)
        $state = Get-FrontendBuildState
        Assert-True ($state.Current -and $state.Reason -eq 'current') 'Matching build output and fingerprint were not classified current.'
    }

    Invoke-TestCase -Name 'Build-Frontend runs npm build, writes a current fingerprint, and removes it after failure' -Test {
        $indexPath = Join-Path $script:FrontendBuildDir 'index.html'
        $fingerprintPath = Join-Path $script:FrontendBuildDir '.paragraph-build-fingerprint'
        $argumentsPath = Join-Path $script:FixtureRoot 'npm-arguments.txt'
        [IO.File]::WriteAllText($indexPath, 'fixture output', [Text.Encoding]::UTF8)

        Write-FakeNpmCommand -Path $script:NpmCmd -RecordPath $argumentsPath -ExitCode 0
        Build-Frontend
        Assert-True ((Get-Content -LiteralPath $argumentsPath -Raw).Trim() -eq 'run build') 'Launcher did not invoke npm run build.'
        Assert-True ((Get-FrontendBuildState).Current) 'Successful build did not write a current fingerprint.'

        Write-FakeNpmCommand -Path $script:NpmCmd -RecordPath $argumentsPath -ExitCode 7
        $failureMessage = $null
        try { Build-Frontend }
        catch { $failureMessage = $_.Exception.Message }
        Assert-True ($failureMessage -match 'Frontend build failed with exit code 7') 'Failed npm build did not surface its exit code.'
        Assert-True (-not (Test-Path -LiteralPath $fingerprintPath)) 'Failed build left a fingerprint that could mark stale output current.'
        Assert-True ((Get-Content -LiteralPath $argumentsPath -Raw).Trim() -eq 'run build') 'Launcher did not invoke npm run build for the failure case.'
    }
}
finally {
    Restore-ProcessEnvironment
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $fixtureRoot = [IO.Path]::GetFullPath($script:FixtureRoot)
    $fixtureName = [IO.Path]::GetFileName($fixtureRoot)
    if (
        $fixtureRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and
        $fixtureName.StartsWith($script:FixturePrefix, [StringComparison]::OrdinalIgnoreCase)
    ) {
        Remove-Item -LiteralPath $fixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        throw "Refusing to remove unexpected test fixture path: $fixtureRoot"
    }
}

if ($script:TestFailures.Count -gt 0) {
    throw ("{0} launcher build fingerprint test(s) failed: {1}" -f $script:TestFailures.Count, ($script:TestFailures -join '; '))
}

Write-Host 'All launcher build fingerprint checks passed.' -ForegroundColor Green
