$ErrorActionPreference = 'Stop'

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$launcherPath = Join-Path $repoRoot 'start_on_windows.ps1'
. $launcherPath

$script:OriginalConfirmPortConflictTermination = (Get-Item Function:\Confirm-PortConflictTermination).ScriptBlock
$script:HarnessState = [ordered]@{}
$script:TestFailures = [Collections.Generic.List[string]]::new()

function Reset-HarnessState {
    $script:HarnessState = [ordered]@{
        ProcessChecks = [Collections.Generic.Queue[bool]]::new()
        ProcessExistsDefault = $true
        TerminationExitCode = 0
        TerminationCalls = 0
        OnTermination = $null
        ListenerReadCount = 0
    }
}

function Test-LauncherProcessExists {
    param([int]$ProcessId)

    if ($script:HarnessState.ProcessChecks.Count -gt 0) {
        return $script:HarnessState.ProcessChecks.Dequeue()
    }
    return [bool]$script:HarnessState.ProcessExistsDefault
}

function Invoke-LauncherProcessTreeTermination {
    param([int]$ProcessId)

    $script:HarnessState.TerminationCalls++
    if ($null -ne $script:HarnessState.OnTermination) {
        & $script:HarnessState.OnTermination
    }
    return [int]$script:HarnessState.TerminationExitCode
}

function Get-PortListenerRecords {
    param([int[]]$Ports)

    $script:HarnessState.ListenerReadCount++
    if ($script:HarnessState.ListenerReadCount -eq 1) {
        return @([pscustomobject]@{ Port = 5002; ProcessId = 31001 })
    }
    return @([pscustomobject]@{ Port = 5002; ProcessId = 31002 })
}

function Get-PortConflictProcesses {
    param([object[]]$ListenerRecords)

    return @($ListenerRecords | Group-Object -Property ProcessId | ForEach-Object {
        [pscustomobject]@{
            ProcessId = [int]$_.Name
            ProcessName = 'disposable-test-listener'
            Ports = @($_.Group | ForEach-Object { [int]$_.Port } | Sort-Object -Unique)
        }
    })
}

function Confirm-PortConflictTermination {
    param([object[]]$Conflicts)
    return $true
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Invoke-TestCase {
    param([string]$Name, [scriptblock]$Test)

    try {
        Reset-HarnessState
        & $Test
        Write-Host "[PASS] $Name" -ForegroundColor Green
    }
    catch {
        $script:TestFailures.Add("$Name`: $($_.Exception.Message)")
        Write-Host "[FAIL] $Name`: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Invoke-TestCase -Name 'launcher PID conflict is refused before termination' -Test {
    $conflict = [pscustomobject]@{
        ProcessId = $PID
        ProcessName = 'test-launcher'
        Ports = @(5002)
    }
    $failure = $null
    try { & $script:OriginalConfirmPortConflictTermination -Conflicts @($conflict) }
    catch { $failure = $_.Exception.Message }

    Assert-True ($failure -match 'Refusing to terminate the launcher') 'Expected launcher-PID refusal.'
    Assert-True ($script:HarnessState.TerminationCalls -eq 0) 'No process termination may be requested.'
}

Invoke-TestCase -Name 'process exit during termination counts as successful cleanup' -Test {
    $script:HarnessState.ProcessChecks.Enqueue($true)
    $script:HarnessState.TerminationExitCode = 128
    $script:HarnessState.OnTermination = {
        $script:HarnessState.ProcessChecks.Enqueue($false)
    }

    $result = Stop-ProcessTree -ProcessId 31001
    Assert-True ([bool]$result) 'A process that exited during taskkill should count as stopped.'
    Assert-True ($script:HarnessState.TerminationCalls -eq 1) 'Expected one termination attempt.'
}

Invoke-TestCase -Name 'surviving process after failed termination reports the OS failure' -Test {
    $script:HarnessState.TerminationExitCode = 5
    $failure = $null
    try { Stop-ProcessTree -ProcessId 31001 }
    catch { $failure = $_.Exception.Message }

    Assert-True ($failure -match 'taskkill failed with exit code 5') 'Expected taskkill failure details.'
    Assert-True ($script:HarnessState.TerminationCalls -eq 1) 'Expected one termination attempt.'
}

Invoke-TestCase -Name 'surviving process after successful termination command is still reported' -Test {
    $failure = $null
    try { Stop-ProcessTree -ProcessId 31001 }
    catch { $failure = $_.Exception.Message }

    Assert-True ($failure -match 'is still alive after taskkill completed') 'Expected surviving-process failure.'
    Assert-True ($script:HarnessState.TerminationCalls -eq 1) 'Expected one termination attempt.'
}

Invoke-TestCase -Name 'replacement listener is detected and never terminated' -Test {
    $script:HarnessState.ProcessChecks.Enqueue($true)
    $script:HarnessState.ProcessChecks.Enqueue($false)
    $settings = @{ FASTAPI_PORT = 5002; UI_PORT = 8002 }
    $failure = $null
    try { [void](Resolve-LaunchPortConflicts -Settings $settings) }
    catch { $failure = $_.Exception.Message }

    Assert-True ($failure -match 'Remaining listeners: PID 31002') 'Expected the replacement listener to be reported.'
    Assert-True ($script:HarnessState.TerminationCalls -eq 1) 'Only the original listener may be targeted.'
    Assert-True ($script:HarnessState.ListenerReadCount -eq 2) 'Expected a fresh listener scan after termination.'
}

if ($script:TestFailures.Count -gt 0) {
    throw ("{0} safety-race test(s) failed: {1}" -f $script:TestFailures.Count, ($script:TestFailures -join '; '))
}

Write-Host 'All launcher safety-race checks passed.' -ForegroundColor Green
