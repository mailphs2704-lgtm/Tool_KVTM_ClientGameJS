param(
    [string]$OutputName = "KVTM-ClientJS-Suite-Multi-DEV"
)

$ErrorActionPreference = "Stop"
$Builder = Join-Path $PSScriptRoot "BUILD_FULL_PACKAGE.ps1"
if (-not (Test-Path -LiteralPath $Builder -PathType Leaf)) {
    throw "Missing builder: $Builder"
}

function Resolve-KvtmGitExe {
    $cmd = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd -and $cmd.Source) { return [string]$cmd.Source }
    $candidates = @()
    if ($env:ProgramFiles) { $candidates += (Join-Path $env:ProgramFiles "Git\cmd\git.exe") }
    if (${env:ProgramFiles(x86)}) { $candidates += (Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe") }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return [string]$candidate }
    }
    return $null
}

[string]$KvtmGitExe = Resolve-KvtmGitExe
if ([string]::IsNullOrWhiteSpace($KvtmGitExe)) { throw "git.exe not found for package build." }

Write-Host "PS5.1 package compatibility wrapper" -ForegroundColor Cyan
Write-Host "Git: $KvtmGitExe"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
[object[]]$probeOutput = @(& $KvtmGitExe -C $RepoRoot rev-parse HEAD 2>$null)
$probeExit = $LASTEXITCODE
[string]$probeHead = ($probeOutput | Select-Object -First 1)
if ($probeExit -ne 0 -or [string]::IsNullOrWhiteSpace($probeHead)) {
    throw "Native Git HEAD preflight failed; exit=$probeExit repo=$RepoRoot"
}
Write-Host "Git HEAD preflight: $($probeHead.Trim())" -ForegroundColor Green

# BUILD_FULL_PACKAGE.ps1 was written for newer PowerShell semantics and checks
# LASTEXITCODE after piping native git output through Select-Object. On Windows
# PowerShell 5.1 that value can become stale/-1 even though git succeeded.
# Create a temporary sibling copy so PSScriptRoot stays identical and patch only
# compatibility-sensitive blocks. The authoritative builder file itself remains
# untouched.
$source = Get-Content -LiteralPath $Builder -Raw -Encoding UTF8
$oldBlock = @'
$head = (& git -C $RepoRoot rev-parse HEAD 2>$null | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($head)) {
    throw "Cannot determine repository HEAD for package stamp."
}
'@
$newBlock = @'
[object[]]$headOutput = @(& $env:KVTM_PS51_GIT_EXE -C $RepoRoot rev-parse HEAD 2>$null)
$headExit = $LASTEXITCODE
$head = [string]($headOutput | Select-Object -First 1)
if ($headExit -ne 0 -or [string]::IsNullOrWhiteSpace($head)) {
    throw "Cannot determine repository HEAD for package stamp. exit=$headExit"
}
'@
if (-not $source.Contains($oldBlock)) {
    throw "PS5.1 compatibility patch target not found in BUILD_FULL_PACKAGE.ps1."
}
$patched = $source.Replace($oldBlock, $newBlock)

# The clear-stall verifier predates the independent AUTO MULTI DEV image runtime
# and still contains one obsolete assertion that requires local_launcher. Keep
# every other clear-stall safety check active by routing only this build through
# a migration-aware adapter. The dedicated Bridge V3 verifier remains mandatory.
$ClearStallAdapter = Join-Path $RepoRoot "tools\verify_clear_stall_contract_build.py"
if (-not (Test-Path -LiteralPath $ClearStallAdapter -PathType Leaf)) {
    throw "Missing migration-aware clear-stall verifier: $ClearStallAdapter"
}
$oldClearStallVerifier = '$ClearStallVerifier = Join-Path $RepoRoot "tools\verify_clear_stall_contract.py"'
$newClearStallVerifier = '$ClearStallVerifier = Join-Path $RepoRoot "tools\verify_clear_stall_contract_build.py"'
if (-not $patched.Contains($oldClearStallVerifier)) {
    throw "Clear-stall verifier patch target not found in BUILD_FULL_PACKAGE.ps1."
}
$patched = $patched.Replace($oldClearStallVerifier, $newClearStallVerifier)

$RuntimeBuilder = Join-Path $PSScriptRoot "BUILD_FULL_PACKAGE_PS51.runtime.ps1"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($RuntimeBuilder, $patched, $utf8NoBom)

$previousGitExe = $env:KVTM_PS51_GIT_EXE
$env:KVTM_PS51_GIT_EXE = $KvtmGitExe
try {
    Write-Host "PS5.1 HEAD stamp patch: READY" -ForegroundColor Green
    Write-Host "AUTO MULTI DEV clear-stall migration gate: READY" -ForegroundColor Green
    & $RuntimeBuilder -OutputName $OutputName
}
finally {
    if ($null -eq $previousGitExe) {
        Remove-Item Env:\KVTM_PS51_GIT_EXE -ErrorAction SilentlyContinue
    }
    else {
        $env:KVTM_PS51_GIT_EXE = $previousGitExe
    }
    Remove-Item -LiteralPath $RuntimeBuilder -Force -ErrorAction SilentlyContinue
}