param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,
    [string]$DistRelative = "dist\\KVTM-ClientJS-Suite-Multi-DEV",
    [string]$ResultBranch = "diagnostics/clear-stall"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Invoke-Git {
    param([Parameter(Mandatory = $true)][string[]]$GitArgs)
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git failed ($LASTEXITCODE): git $($GitArgs -join ' ')"
    }
}

$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
$gateRoot = Join-Path $repo (Join-Path $DistRelative "data-dev\\clear-stall-probe")
if (-not (Test-Path -LiteralPath $gateRoot -PathType Container)) {
    throw "Chưa có thư mục log Gate: $gateRoot"
}

$activity = Get-ChildItem -LiteralPath $gateRoot -Recurse -Filter "activity.log" -File |
    Where-Object { $_.Length -gt 0 } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
$report = Get-ChildItem -LiteralPath $gateRoot -Recurse -Filter "report.json" -File |
    Where-Object { $_.Length -gt 0 } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if ($null -eq $activity -and $null -eq $report) {
    throw "Không có activity.log hoặc report.json có nội dung. Hãy bấm Gate trước."
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runRelGit = "diagnostics/clear-stall/gate-runs/$stamp"
$tempRoot = Join-Path $env:TEMP "KVTM_DEV_GATE_DIAGNOSTICS_WORKTREE"
$worktreeAdded = $false

try {
    Set-Location -LiteralPath $repo
    # The temp path may be a plain leftover directory rather than a
    # registered Git worktree. Remove the exact temp directory first, then let
    # prune clear any stale registration; do not call worktree remove blindly.
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
    Invoke-Git -GitArgs @("worktree", "prune")

    & git fetch origin $ResultBranch 2>$null
    & git rev-parse --verify "refs/remotes/origin/$ResultBranch" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Invoke-Git -GitArgs @("worktree", "add", "--detach", $tempRoot, "origin/$ResultBranch")
    } else {
        Invoke-Git -GitArgs @("worktree", "add", "--detach", $tempRoot, "HEAD")
    }
    $worktreeAdded = $true

    $runDir = Join-Path $tempRoot ($runRelGit -replace "/", "\\")
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null

    if ($null -ne $activity) {
        Copy-Item -LiteralPath $activity.FullName -Destination (Join-Path $runDir "activity.log") -Force
    }
    if ($null -ne $report) {
        Copy-Item -LiteralPath $report.FullName -Destination (Join-Path $runDir "report.json") -Force
        Get-ChildItem -LiteralPath $report.Directory.FullName -Filter "*.png" -File -ErrorAction SilentlyContinue |
            Copy-Item -Destination $runDir -Force
        $templateSource = Join-Path $report.Directory.FullName "templates"
        if (Test-Path -LiteralPath $templateSource -PathType Container) {
            $templateTarget = Join-Path $runDir "templates"
            New-Item -ItemType Directory -Path $templateTarget -Force | Out-Null
            Get-ChildItem -LiteralPath $templateSource -Filter "*.png" -File -ErrorAction SilentlyContinue |
                Copy-Item -Destination $templateTarget -Force
        }
    }

    $evidence = Get-ChildItem -LiteralPath $runDir -File -ErrorAction SilentlyContinue |
        Where-Object { ($_.Name -eq "activity.log" -or $_.Name -eq "report.json") -and $_.Length -gt 0 }
    if (@($evidence).Count -eq 0) {
        throw "Không sao chép được activity.log/report.json có nội dung."
    }

    $allowedNames = @("activity.log", "report.json")
    $allFiles = Get-ChildItem -LiteralPath $runDir -Recurse -File
    foreach ($file in $allFiles) {
        $isAllowed = ($allowedNames -contains $file.Name) -or
            ($file.Extension -ieq ".png")
        if (-not $isAllowed) {
            throw "File ngoài whitelist: $($file.Name)"
        }
    }

    $textFiles = $allFiles | Where-Object { $_.Extension -in @(".log", ".json") }
    $bad = $textFiles | Select-String -Pattern "(?i)(authorization|password|cookie|token|profiles\.json|\.kvtm)" -ErrorAction SilentlyContinue
    if ($bad) {
        throw "Log Gate chứa chuỗi nhạy cảm; không upload."
    }

    $sourceHead = (& git -C $repo rev-parse HEAD).Trim()
    @(
        "gate=READ_ONLY_SCAN"
        "timestamp=$stamp"
        "source_head=$sourceHead"
        "activity_present=$([bool](Test-Path -LiteralPath (Join-Path $runDir 'activity.log')))"
        "report_present=$([bool](Test-Path -LiteralPath (Join-Path $runDir 'report.json')))"
        "note=Allowlisted Gate diagnostics only. No profiles/settings/secrets."
    ) | Set-Content -LiteralPath (Join-Path $runDir "metadata.txt") -Encoding UTF8

    $pointerDir = Join-Path $tempRoot "diagnostics\\clear-stall"
    New-Item -ItemType Directory -Path $pointerDir -Force | Out-Null
    $runRelGit | Set-Content -LiteralPath (Join-Path $pointerDir "LATEST_GATE.txt") -Encoding ASCII

    Invoke-Git -GitArgs @("-C", $tempRoot, "config", "user.name", "KVTM DEV Diagnostics")
    Invoke-Git -GitArgs @("-C", $tempRoot, "config", "user.email", "kvtm-dev-diagnostics@local")
    Invoke-Git -GitArgs @("-C", $tempRoot, "add", "-f", "--", $runRelGit, "diagnostics/clear-stall/LATEST_GATE.txt")

    $staged = @(& git -C $tempRoot diff --cached --name-only -- $runRelGit)
    if ($LASTEXITCODE -ne 0) {
        throw "Không đọc được staged files."
    }
    $hasEvidence = $false
    foreach ($name in $staged) {
        if ($name -eq "$runRelGit/activity.log" -or $name -eq "$runRelGit/report.json") {
            $hasEvidence = $true
        }
    }
    if (-not $hasEvidence) {
        throw "Git chưa stage activity.log/report.json; không tạo commit metadata rỗng."
    }

    Write-Host "[GIT] Allowlisted files da stage:"
    $staged | ForEach-Object { Write-Host $_ }

    Invoke-Git -GitArgs @("-C", $tempRoot, "commit", "-m", "Add clear stall Gate diagnostics $stamp")
    Invoke-Git -GitArgs @("-C", $tempRoot, "push", "origin", "HEAD:refs/heads/$ResultBranch")

    Write-Host ""
    Write-Host "[PASS] Da gui log Gate an toan."
    Write-Host "[GIT] branch=$ResultBranch"
    Write-Host "[GIT] latest=$runRelGit"
}
finally {
    Set-Location -LiteralPath $repo
    if ($worktreeAdded) {
        try {
            Invoke-Git -GitArgs @("worktree", "remove", "--force", $tempRoot)
        } catch {
            Write-Warning "Không dọn được worktree tạm: $($_.Exception.Message)"
        }
    }
    try {
        Invoke-Git -GitArgs @("worktree", "prune")
    } catch {
        Write-Warning "Không prune được worktree tạm: $($_.Exception.Message)"
    }
}
