param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$SessionRoot,
    [string]$ResultBranch = "diagnostics/runtime-errors"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Invoke-Git {
    param([Parameter(Mandatory = $true)][string[]]$GitArgs)
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & git @GitArgs
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }
    if ($exitCode -ne 0) {
        throw "git failed ($exitCode): git $($GitArgs -join ' ')"
    }
}

function Protect-DiagnosticText {
    param([string]$Text)
    $safe = [string]$Text
    $safe = [regex]::Replace(
        $safe,
        '(?im)\b(profile_id|profile_name|account_name|client_pid|old_pid|new_pid|pid)\s*[=:]\s*[^\s,;|}\]]+',
        '$1=<redacted>'
    )
    $safe = [regex]::Replace(
        $safe,
        '(?im)\b(authorization|password|passwd|cookie|token|secret)\s*[=:]\s*[^\s,;|}\]]+',
        '$1=<redacted>'
    )
    $safe = [regex]::Replace(
        $safe,
        '(?i)[A-Z]:\\Users\\[^\\\r\n]+',
        'C:\Users\<redacted>'
    )
    $safe = [regex]::Replace(
        $safe,
        '(?i)(profiles\.json|settings\.json|[^\s"''|]+\.kvtm)',
        '<blocked-sensitive-file>'
    )
    return $safe
}

$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
$session = (Resolve-Path -LiteralPath $SessionRoot).Path
$sourceLog = Join-Path $session "errors.log"
if (-not (Test-Path -LiteralPath $sourceLog -PathType Leaf)) {
    throw "Không có errors.log: $sourceLog"
}
$raw = [System.IO.File]::ReadAllText($sourceLog, [System.Text.Encoding]::UTF8)
if ([string]::IsNullOrWhiteSpace($raw)) {
    exit 0
}
$safe = Protect-DiagnosticText -Text $raw
if ($safe -match '(?i)(authorization|password|passwd|cookie|token|secret)\s*[=:]\s*(?!<redacted>)') {
    throw "Sanitizer còn phát hiện trường nhạy cảm; từ chối upload."
}

$mutex = New-Object System.Threading.Mutex($false, "Local\KVTM_Runtime_Error_Upload_v1")
$locked = $false
$tempRoot = Join-Path $env:TEMP "KVTM_RUNTIME_ERROR_UPLOAD_WORKTREE"
$worktreeAdded = $false
try {
    $locked = $mutex.WaitOne(30000)
    if (-not $locked) {
        throw "Một lượt upload log khác đang chạy."
    }
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
    Invoke-Git -GitArgs @("-C", $repo, "worktree", "prune")
    $remoteExists = $true
    try {
        Invoke-Git -GitArgs @("-C", $repo, "fetch", "origin", $ResultBranch)
        Invoke-Git -GitArgs @("-C", $repo, "rev-parse", "--verify", "refs/remotes/origin/$ResultBranch")
    }
    catch {
        $remoteExists = $false
    }
    $base = if ($remoteExists) { "origin/$ResultBranch" } else { "HEAD" }
    Invoke-Git -GitArgs @("-C", $repo, "worktree", "add", "--detach", $tempRoot, $base)
    $worktreeAdded = $true

    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $runRel = "diagnostics/runtime-errors/runs/$stamp"
    $runDir = Join-Path $tempRoot ($runRel -replace "/", "\")
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null
    [System.IO.File]::WriteAllText(
        (Join-Path $runDir "runtime-errors.log"),
        $safe,
        (New-Object System.Text.UTF8Encoding($false))
    )
    $sourceHead = (& git -C $repo rev-parse HEAD | Select-Object -First 1).Trim()
    @(
        "timestamp=$stamp"
        "source_head=$sourceHead"
        "sanitized=true"
        "images=false"
        "profiles_settings_secrets=false"
    ) | Set-Content -LiteralPath (Join-Path $runDir "metadata.txt") -Encoding UTF8

    $pointerDir = Join-Path $tempRoot "diagnostics\runtime-errors"
    New-Item -ItemType Directory -Path $pointerDir -Force | Out-Null
    $runRel | Set-Content -LiteralPath (Join-Path $pointerDir "LATEST.txt") -Encoding ASCII

    Invoke-Git -GitArgs @("-C", $tempRoot, "config", "user.name", "KVTM Runtime Diagnostics")
    Invoke-Git -GitArgs @("-C", $tempRoot, "config", "user.email", "kvtm-runtime-diagnostics@local")
    Invoke-Git -GitArgs @("-C", $tempRoot, "add", "-f", "--", $runRel, "diagnostics/runtime-errors/LATEST.txt")
    Invoke-Git -GitArgs @("-C", $tempRoot, "commit", "-m", "Add sanitized runtime diagnostics $stamp")
    Invoke-Git -GitArgs @("-C", $tempRoot, "push", "origin", "HEAD:refs/heads/$ResultBranch")
}
finally {
    if ($worktreeAdded) {
        try { Invoke-Git -GitArgs @("-C", $repo, "worktree", "remove", "--force", $tempRoot) } catch {}
    }
    try { Invoke-Git -GitArgs @("-C", $repo, "worktree", "prune") } catch {}
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
