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
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    $candidates = @()
    if ($env:ProgramFiles) { $candidates += (Join-Path $env:ProgramFiles "Git\cmd\git.exe") }
    if (${env:ProgramFiles(x86)}) { $candidates += (Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe") }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}

$script:KvtmGitExe = Resolve-KvtmGitExe
if (-not $script:KvtmGitExe) { throw "git.exe not found for package build." }

# Windows PowerShell 5.1 can leave LASTEXITCODE in an unreliable state when a
# native command is piped through Select-Object. BUILD_FULL_PACKAGE.ps1 has a
# `git rev-parse HEAD | Select-Object -First 1` stamp check. Route `git` through
# a PowerShell function so the real native exit code is captured explicitly.
function global:git {
    & $script:KvtmGitExe @args
    $nativeExit = $LASTEXITCODE
    $global:LASTEXITCODE = $nativeExit
}

try {
    Write-Host "PS5.1 package compatibility wrapper" -ForegroundColor Cyan
    Write-Host "Git: $script:KvtmGitExe"
    & $Builder -OutputName $OutputName
    $builderExit = $LASTEXITCODE
    if ($builderExit -ne 0) { exit $builderExit }
}
finally {
    Remove-Item Function:\global:git -ErrorAction SilentlyContinue
}
