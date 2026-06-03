[CmdletBinding()]
param(
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
$clientDir = Join-Path $repoRoot "app\client"
$tauriDir = Join-Path $clientDir "src-tauri"
$projectDir = Join-Path $repoRoot "app"
$runtimesDir = Join-Path $repoRoot "runtimes"
$releaseDir = Join-Path $clientDir "src-tauri\target\release"
$bundleDir = Join-Path $releaseDir "bundle"
$bundleSourceDir = Join-Path $tauriDir "r"

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
  $outputDir = Join-Path $repoRoot "release\windows"
} else {
  $outputDir = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputPath))
}

$installersDir = Join-Path $outputDir "installers"
$portableDir = Join-Path $outputDir "portable"

if (-not (Test-Path $bundleDir)) {
  throw "Bundle directory not found. Run 'npm run tauri:build' first. Missing: $bundleDir"
}

if (Test-Path $outputDir) {
  Remove-Item -Recurse -Force $outputDir
}

New-Item -ItemType Directory -Path $installersDir -Force | Out-Null
New-Item -ItemType Directory -Path $portableDir -Force | Out-Null

$installerArtifacts = @()

$nsisDir = Join-Path $bundleDir "nsis"
if (Test-Path $nsisDir) {
  $nsisFiles = Get-ChildItem -Path $nsisDir -Filter "*.exe" -File
  foreach ($file in $nsisFiles) {
    Copy-Item -Path $file.FullName -Destination $installersDir -Force
    $installerArtifacts += Join-Path $installersDir $file.Name
  }
}

$msiDir = Join-Path $bundleDir "msi"
if (Test-Path $msiDir) {
  $msiFiles = Get-ChildItem -Path $msiDir -Filter "*.msi" -File
  foreach ($file in $msiFiles) {
    Copy-Item -Path $file.FullName -Destination $installersDir -Force
    $installerArtifacts += Join-Path $installersDir $file.Name
  }
}

$portableExeCandidates = Get-ChildItem -Path $releaseDir -Filter "*.exe" -File |
  Where-Object { $_.Name -notmatch "(?i)(setup|installer|uninstall|updater)" }

if ($portableExeCandidates.Count -eq 0) {
  throw "No portable desktop executable found in release directory: $releaseDir"
}

foreach ($file in $portableExeCandidates) {
  Copy-Item -Path $file.FullName -Destination $portableDir -Force
}

$portableResourceMap = @(
  @{ Name = "runtime"; SourceCandidates = @((Join-Path $releaseDir "runtime"), (Join-Path $bundleSourceDir "runtime")) },
  @{ Name = "_up_"; SourceCandidates = @((Join-Path $releaseDir "_up_"), (Join-Path $bundleSourceDir "_up_")) }
)

foreach ($entry in $portableResourceMap) {
  $sourcePath = $null
  foreach ($candidate in $entry.SourceCandidates) {
    if (Test-Path $candidate) {
      $sourcePath = $candidate
      break
    }
  }

  if ($null -ne $sourcePath) {
    $destinationPath = Join-Path $portableDir $entry.Name
    Copy-Item -Path $sourcePath -Destination $destinationPath -Recurse -Force
  }
}

$requiredPortablePaths = @(
  (Join-Path $portableDir "runtime\app"),
  (Join-Path $portableDir "runtime\runtimes\uv\uv.exe"),
  (Join-Path $portableDir "runtime\runtimes\python\python.exe"),
  (Join-Path $portableDir "runtime\runtimes\uv.lock"),
  (Join-Path $portableDir "runtime\pyproject.toml"),
  (Join-Path $portableDir "runtime\uv.lock")
)

foreach ($requiredPath in $requiredPortablePaths) {
  if (-not (Test-Path $requiredPath)) {
    throw "Portable export is incomplete. Missing required payload path: $requiredPath"
  }
}

$instructions = @"
app desktop build output

1) Preferred for users:
   Open installers\ and run the setup executable (.exe) or .msi.

2) Portable executable:
   portable\ contains the app .exe and a sibling runtime\ folder.
   Keep the exported contents together in the same directory.

Generated from:
$bundleDir
"@
Set-Content -Path (Join-Path $outputDir "README.txt") -Value $instructions -Encoding ascii

Write-Host "[OK] Exported Windows artifacts to: $outputDir"
Write-Host "[INFO] Installers:"
if ($installerArtifacts.Count -eq 0) {
  Write-Host " - none found"
} else {
  $installerArtifacts | ForEach-Object { Write-Host " - $_" }
}
Write-Host "[INFO] Portable executables:"
$portableFiles = Get-ChildItem -Path $portableDir -Filter "*.exe" -File
if ($portableFiles.Count -eq 0) {
  Write-Host " - none found"
} else {
  $portableFiles | ForEach-Object { Write-Host " - $($_.FullName)" }
}

