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

# The compatibility function is GLOBAL, therefore do not reference a script-scope
# variable from inside it. Windows PowerShell 5.1 can resolve $script: differently
# once a function is installed in global scope, which makes the call operator see
# $null/non-command and throw BadExpression. Keep one explicit temporary global
# string containing the native git.exe path instead.
$global:KvtmGitExeCompat = [string]$KvtmGitExe
function global:git {
    [string]$gitExe = $global:KvtmGitExeCompat
    if ([string]::IsNullOrWhiteSpace($gitExe)) {
        throw "KVTM Git compatibility path is empty."
    }
    & $gitExe @args
    $nativeExit = $LASTEXITCODE
    $global:LASTEXITCODE = $nativeExit
}

try {
    Write-Host "PS5.1 package compatibility wrapper" -ForegroundColor Cyan
    Write-Host "Git: $KvtmGitExe"

    # Exact preflight for the package-stamp call pattern. This catches wrapper
    # scope/call-operator regressions before the expensive package copy starts.
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
    $headProbe = (& git -C $RepoRoot rev-parse HEAD 2>$null | Select-Object -First 1)
    $headProbeExit = $LASTEXITCODE
    if ($headProbeExit -ne 0 -or [string]::IsNullOrWhiteSpace([string]$headProbe)) {
        throw "PS5.1 Git wrapper preflight failed; exit=$headProbeExit repo=$RepoRoot"
    }
    Write-Host "Git HEAD preflight: $(([string]$headProbe).Trim())" -ForegroundColor Green

    & $Builder -OutputName $OutputName
    $builderExit = $LASTEXITCODE
    if ($builderExit -ne 0) { exit $builderExit }
}
finally {
    Remove-Item Function:\global:git -ErrorAction SilentlyContinue
    Remove-Variable -Name KvtmGitExeCompat -Scope Global -ErrorAction SilentlyContinue
}
