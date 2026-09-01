param(
    [ValidateSet("Update", "ActivatePending")]
    [string]$Mode = "Update",
    [string]$RuntimePath,
    [string]$StagingPath,
    [string]$Branch = "develop/multi-auto-dev"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Builder = Join-Path $RepoRoot "packaging\suite-v0.15\BUILD_FULL_PACKAGE_PS51.ps1"
$DefaultRuntime = Join-Path $RepoRoot "dist\KVTM-ClientJS-Suite-Multi-DEV"
if ([string]::IsNullOrWhiteSpace($RuntimePath)) { $RuntimePath = $DefaultRuntime }
$RuntimePath = [IO.Path]::GetFullPath($RuntimePath)

function Resolve-KvtmGit {
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

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    $parent = Split-Path -Parent $Path
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, $Text, $utf8)
}

function Get-StatusPath {
    param([string]$Root)
    return (Join-Path $Root "data-dev\runtime-update-status.json")
}

function Write-UpdateStatus {
    param(
        [string]$State,
        [string]$Message,
        [string]$Head = "",
        [string]$Stage = ""
    )
    $payload = [ordered]@{
        state = $State
        message = $Message
        head = $Head
        updated_at = [DateTimeOffset]::Now.ToString("yyyy-MM-dd HH:mm:ss zzz")
    }
    if (-not [string]::IsNullOrWhiteSpace($Stage)) { $payload["staging_path"] = $Stage }
    $json = $payload | ConvertTo-Json -Depth 4
    Write-Utf8NoBom -Path (Get-StatusPath $RuntimePath) -Text ($json + "`r`n")
}

function Get-BlockingDirtyLines {
    param([object[]]$DirtyLines)
    return @(
        $DirtyLines | Where-Object {
            $line = [string]$_
            $line -notmatch 'source-archive/auto-pro-reference/runtime/pyc/'
        }
    )
}

function Get-GitFirstLine {
    param([string]$Git, [string[]]$Arguments)
    [object[]]$output = @(& $Git @Arguments 2>$null)
    $rc = $LASTEXITCODE
    [string]$first = ($output | Select-Object -First 1)
    if ($rc -ne 0 -or [string]::IsNullOrWhiteSpace($first)) {
        throw "git command failed rc=$rc args=$($Arguments -join ' ')"
    }
    return $first.Trim()
}

function Test-RuntimeBusy {
    param([string]$Root)
    try {
        $needle = [IO.Path]::GetFullPath($Root)
        [object[]]$rows = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
            $name = [string]$_.Name
            $cmd = [string]$_.CommandLine
            $python = ($name -match '^python(?:w)?(?:3(?:\.11)?)?\.exe$')
            $python -and -not [string]::IsNullOrWhiteSpace($cmd) -and
                $cmd.IndexOf($needle, [StringComparison]::OrdinalIgnoreCase) -ge 0
        })
        return ($rows.Count -gt 0)
    }
    catch {
        # Fail safe: if process inspection is unavailable, do not hot-swap files.
        return $true
    }
}

function Sync-CurrentDataToStage {
    param([string]$Current, [string]$Stage)
    $source = Join-Path $Current "data-dev"
    $dest = Join-Path $Stage "data-dev"
    if (Test-Path -LiteralPath $dest) {
        Remove-Item -LiteralPath $dest -Recurse -Force
    }
    if (Test-Path -LiteralPath $source -PathType Container) {
        Copy-Item -LiteralPath $source -Destination $dest -Recurse -Force
    }
    else {
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
    }
}

function Activate-Runtime {
    param([string]$Current, [string]$Stage, [string]$Head)
    if (-not (Test-Path -LiteralPath $Stage -PathType Container)) {
        throw "Staging runtime missing: $Stage"
    }
    if (Test-RuntimeBusy $Current) {
        throw "Runtime is still busy; activation deferred."
    }

    Sync-CurrentDataToStage -Current $Current -Stage $Stage
    Write-Utf8NoBom -Path (Join-Path $Stage "data-dev\runtime-source-head.txt") -Text ($Head + "`r`n")

    $backup = $Current + ".previous"
    if (Test-Path -LiteralPath $backup) {
        Remove-Item -LiteralPath $backup -Recurse -Force
    }

    $movedCurrent = $false
    try {
        if (Test-Path -LiteralPath $Current -PathType Container) {
            Move-Item -LiteralPath $Current -Destination $backup
            $movedCurrent = $true
        }
        Move-Item -LiteralPath $Stage -Destination $Current
    }
    catch {
        if ($movedCurrent -and -not (Test-Path -LiteralPath $Current) -and (Test-Path -LiteralPath $backup)) {
            Move-Item -LiteralPath $backup -Destination $Current -ErrorAction SilentlyContinue
        }
        throw
    }

    Write-UpdateStatus -State "activated" -Message "Đã kích hoạt runtime DEV mới." -Head $Head
}

function Start-ActivationWatcher {
    param([string]$Current, [string]$Stage, [string]$Head)
    $args = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
        "-File", $PSCommandPath,
        "-Mode", "ActivatePending",
        "-RuntimePath", $Current,
        "-StagingPath", $Stage,
        "-Branch", $Branch
    )
    Start-Process -FilePath "powershell.exe" -ArgumentList $args -WindowStyle Hidden | Out-Null
}

function Invoke-ActivatePending {
    if ([string]::IsNullOrWhiteSpace($StagingPath)) { throw "ActivatePending requires -StagingPath." }
    $headFile = Join-Path $StagingPath "data-dev\runtime-source-head.txt"
    $head = ""
    if (Test-Path -LiteralPath $headFile -PathType Leaf) {
        $head = (Get-Content -LiteralPath $headFile -Raw -Encoding UTF8).Trim()
    }
    if ([string]::IsNullOrWhiteSpace($head)) {
        $git = Resolve-KvtmGit
        if ($git) { $head = Get-GitFirstLine -Git $git -Arguments @("-C", $RepoRoot, "rev-parse", "HEAD") }
    }

    while (Test-RuntimeBusy $RuntimePath) {
        Start-Sleep -Seconds 1
    }
    Start-Sleep -Milliseconds 1200
    Activate-Runtime -Current $RuntimePath -Stage $StagingPath -Head $head
}

function Invoke-Update {
    $git = Resolve-KvtmGit
    if ([string]::IsNullOrWhiteSpace($git)) { throw "git.exe not found." }
    if (-not (Test-Path -LiteralPath $Builder -PathType Leaf)) { throw "Builder missing: $Builder" }
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot ".git") -PathType Container)) { throw "Not a Git repo: $RepoRoot" }

    Write-UpdateStatus -State "checking" -Message "Đang kiểm tra cập nhật GitHub/local DEV..."

    [object[]]$dirty = @(& $git -C $RepoRoot status --porcelain)
    [object[]]$blockingDirty = @(Get-BlockingDirtyLines $dirty)
    if ($blockingDirty.Count -gt 0) {
        throw "Repo có thay đổi DEV chưa commit; updater không ghi đè working tree."
    }

    & $git -C $RepoRoot fetch origin $Branch
    if ($LASTEXITCODE -ne 0) { throw "git fetch origin $Branch failed." }

    $localHead = Get-GitFirstLine -Git $git -Arguments @("-C", $RepoRoot, "rev-parse", "HEAD")
    $remoteHead = Get-GitFirstLine -Git $git -Arguments @("-C", $RepoRoot, "rev-parse", "origin/$Branch")

    if ($localHead -ne $remoteHead) {
        & $git -C $RepoRoot merge-base --is-ancestor $localHead $remoteHead *> $null
        $localBehind = ($LASTEXITCODE -eq 0)
        & $git -C $RepoRoot merge-base --is-ancestor $remoteHead $localHead *> $null
        $localAhead = ($LASTEXITCODE -eq 0)

        if ($localBehind) {
            Write-UpdateStatus -State "pulling" -Message "Có bản GitHub mới; đang pull fast-forward..." -Head $remoteHead
            & $git -C $RepoRoot pull --ff-only origin $Branch
            if ($LASTEXITCODE -ne 0) { throw "git pull --ff-only failed." }
            $localHead = Get-GitFirstLine -Git $git -Arguments @("-C", $RepoRoot, "rev-parse", "HEAD")
        }
        elseif (-not $localAhead) {
            throw "Local và origin/$Branch đã diverge; cần xử lý Git trước khi update runtime."
        }
        # localAhead is intentionally supported on the main DEV machine: build
        # its committed local source even before that commit is pushed.
    }

    & $git -C $RepoRoot lfs install *> $null
    if ($LASTEXITCODE -ne 0) { throw "git lfs install failed." }
    & $git -C $RepoRoot lfs pull
    if ($LASTEXITCODE -ne 0) { throw "git lfs pull failed." }

    $targetHead = Get-GitFirstLine -Git $git -Arguments @("-C", $RepoRoot, "rev-parse", "HEAD")
    $stampPath = Join-Path $RuntimePath "data-dev\runtime-source-head.txt"
    $currentStamp = ""
    if (Test-Path -LiteralPath $stampPath -PathType Leaf) {
        $currentStamp = (Get-Content -LiteralPath $stampPath -Raw -Encoding UTF8).Trim()
    }

    if ($currentStamp -eq $targetHead) {
        Write-UpdateStatus -State "no_update" -Message "Runtime đã là bản mới nhất." -Head $targetHead
        return
    }

    $short = $targetHead.Substring(0, [Math]::Min(12, $targetHead.Length))
    $stageName = "KVTM-ClientJS-Suite-Multi-DEV-UPDATE-$short"
    $stagePath = Join-Path (Split-Path -Parent $RuntimePath) $stageName
    if (Test-Path -LiteralPath $stagePath) {
        Remove-Item -LiteralPath $stagePath -Recurse -Force
    }

    Write-UpdateStatus -State "building" -Message "Đang build runtime mới ở staging; Multi hiện tại vẫn chạy." -Head $targetHead -Stage $stagePath
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Builder -OutputName $stageName
    if ($LASTEXITCODE -ne 0) { throw "Runtime staging build failed." }

    foreach ($required in @(
        (Join-Path $stagePath "Multi\kvtm_multi_dev_host.py"),
        (Join-Path $stagePath "Multi\runtime_update_ui.py"),
        (Join-Path $stagePath "AUTO_PRO\local_launcher.py")
    )) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "Staging runtime incomplete: $required"
        }
    }
    Write-Utf8NoBom -Path (Join-Path $stagePath "data-dev\runtime-source-head.txt") -Text ($targetHead + "`r`n")

    if (Test-RuntimeBusy $RuntimePath) {
        Write-UpdateStatus -State "pending_restart" -Message "Bản mới đã tải/build xong. Tool hiện tại tiếp tục chạy; sẽ tự kích hoạt khi Multi đóng." -Head $targetHead -Stage $stagePath
        Start-ActivationWatcher -Current $RuntimePath -Stage $stagePath -Head $targetHead
        return
    }

    Write-UpdateStatus -State "activating" -Message "Đang kích hoạt runtime mới..." -Head $targetHead -Stage $stagePath
    Activate-Runtime -Current $RuntimePath -Stage $stagePath -Head $targetHead
}

try {
    switch ($Mode) {
        "Update" { Invoke-Update }
        "ActivatePending" { Invoke-ActivatePending }
    }
}
catch {
    try { Write-UpdateStatus -State "error" -Message ([string]$_.Exception.Message) } catch { }
    Write-Error $_
    exit 1
}
