param(
    [ValidateSet("Update", "ActivatePending")]
    [string]$Mode = "Update",
    [string]$RuntimePath,
    [string]$StagingPath,
    [string]$Branch = "develop/multi-auto-dev",
    [int]$OwnerPid = 0,
    [switch]$Relaunched
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

function Get-RuntimeProcesses {
    param([string]$Root)
    try {
        $needle = [IO.Path]::GetFullPath($Root)
        return @(
            Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
                $name = [string]$_.Name
                $cmd = [string]$_.CommandLine
                $python = ($name -match '^python(?:w)?(?:3(?:\.11)?)?\.exe$')
                $python -and -not [string]::IsNullOrWhiteSpace($cmd) -and
                    $cmd.IndexOf($needle, [StringComparison]::OrdinalIgnoreCase) -ge 0
            }
        )
    }
    catch {
        return @()
    }
}

function Test-RuntimeBusy {
    param([string]$Root)
    try {
        [object[]]$rows = @(Get-RuntimeProcesses -Root $Root)
        return ($rows.Count -gt 0)
    }
    catch {
        return $true
    }
}

function Get-RuntimeHostPid {
    param([string]$Root)
    try {
        [object[]]$rows = @(Get-RuntimeProcesses -Root $Root | Where-Object {
            ([string]$_.CommandLine).IndexOf(
                "kvtm_multi_dev_host.py",
                [StringComparison]::OrdinalIgnoreCase
            ) -ge 0
        })
        if ($rows.Count -gt 0) { return [int]$rows[0].ProcessId }
    }
    catch { }
    return 0
}

function Test-ProcessAlive {
    param([int]$ProcessId)
    if ($ProcessId -le 0) { return $false }
    try {
        $null = Get-Process -Id $ProcessId -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

function Quote-ProcessArgument {
    param([string]$Value)
    if ($null -eq $Value) { return '""' }
    return '"' + ($Value -replace '"', '\"') + '"'
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

function Get-RelativeRuntimePath {
    param([string]$Root, [string]$Path)
    $prefix = [IO.Path]::GetFullPath($Root).TrimEnd('\\') + '\\'
    $full = [IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside runtime root: $full"
    }
    return $full.Substring($prefix.Length)
}

function Test-FilesIdentical {
    param([string]$Left, [string]$Right)
    if (-not (Test-Path -LiteralPath $Left -PathType Leaf)) { return $false }
    if (-not (Test-Path -LiteralPath $Right -PathType Leaf)) { return $false }
    $leftInfo = Get-Item -LiteralPath $Left
    $rightInfo = Get-Item -LiteralPath $Right
    if ($leftInfo.Length -ne $rightInfo.Length) { return $false }
    return (
        (Get-FileHash -LiteralPath $Left -Algorithm SHA256).Hash -eq
        (Get-FileHash -LiteralPath $Right -Algorithm SHA256).Hash
    )
}

function Activate-RuntimeOverlay {
    param([string]$Current, [string]$Stage, [string]$Backup)

    if (Test-Path -LiteralPath $Backup) {
        Remove-Item -LiteralPath $Backup -Recurse -Force
    }
    Copy-Item -LiteralPath $Current -Destination $Backup -Recurse -Force

    $stageRoot = [IO.Path]::GetFullPath($Stage)
    foreach ($source in Get-ChildItem -LiteralPath $Stage -File -Recurse) {
        $relative = Get-RelativeRuntimePath -Root $stageRoot -Path $source.FullName
        if ($relative -eq "data-dev" -or $relative.StartsWith(
            "data-dev\\", [StringComparison]::OrdinalIgnoreCase
        )) {
            continue
        }
        $destination = Join-Path $Current $relative
        if (Test-FilesIdentical -Left $source.FullName -Right $destination) {
            continue
        }
        $parent = Split-Path -Parent $destination
        if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        Copy-Item -LiteralPath $source.FullName -Destination $destination -Force
    }

    foreach ($source in Get-ChildItem -LiteralPath $Stage -File -Recurse) {
        $relative = Get-RelativeRuntimePath -Root $stageRoot -Path $source.FullName
        if ($relative -eq "data-dev" -or $relative.StartsWith(
            "data-dev\\", [StringComparison]::OrdinalIgnoreCase
        )) {
            continue
        }
        $destination = Join-Path $Current $relative
        if (-not (Test-FilesIdentical -Left $source.FullName -Right $destination)) {
            throw "Overlay verification failed: $relative"
        }
    }

    Remove-Item -LiteralPath $Stage -Recurse -Force
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
        $renameError = $_
        if ($movedCurrent -and -not (Test-Path -LiteralPath $Current) -and (Test-Path -LiteralPath $backup)) {
            Move-Item -LiteralPath $backup -Destination $Current -ErrorAction SilentlyContinue
        }
        if ($movedCurrent -or -not (Test-Path -LiteralPath $Current -PathType Container)) {
            throw $renameError
        }

        # GameClientJS intentionally remains alive when Multi closes and can
        # keep an unchanged bridge DLL loaded. In that case Windows refuses to
        # rename the whole runtime directory. Back up the current runtime, then
        # overlay only changed staging files. Identical locked files are skipped
        # after SHA-256 comparison; changed locked files still fail safely.
        Activate-RuntimeOverlay -Current $Current -Stage $Stage -Backup $backup
        Write-UpdateStatus -State "activated" -Message "Đã kích hoạt runtime DEV mới bằng overlay an toàn." -Head $Head
        return
    }

    Write-UpdateStatus -State "activated" -Message "Đã kích hoạt runtime DEV mới." -Head $Head
}

function Start-ActivationWatcher {
    param([string]$Current, [string]$Stage, [int]$OwnerProcessId)
    $rawArgs = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
        "-File", $PSCommandPath,
        "-Mode", "ActivatePending",
        "-RuntimePath", $Current,
        "-StagingPath", $Stage,
        "-Branch", $Branch,
        "-OwnerPid", ([string]$OwnerProcessId)
    )
    $argumentLine = ($rawArgs | ForEach-Object { Quote-ProcessArgument ([string]$_) }) -join ' '
    Start-Process -FilePath "powershell.exe" -ArgumentList $argumentLine -WindowStyle Hidden | Out-Null
}

function Invoke-ActivatePending {
    if ([string]::IsNullOrWhiteSpace($StagingPath)) { throw "ActivatePending requires -StagingPath." }
    $headFile = Join-Path $StagingPath ".source-head.txt"
    $head = ""
    if (Test-Path -LiteralPath $headFile -PathType Leaf) {
        $head = (Get-Content -LiteralPath $headFile -Raw -Encoding ASCII).Trim()
    }
    if ([string]::IsNullOrWhiteSpace($head)) {
        $git = Resolve-KvtmGit
        if ($git) { $head = Get-GitFirstLine -Git $git -Arguments @("-C", $RepoRoot, "rev-parse", "HEAD") }
    }

    if ($OwnerPid -gt 0) {
        while (Test-ProcessAlive -ProcessId $OwnerPid) {
            Start-Sleep -Milliseconds 100
        }
    }
    else {
        while (Test-RuntimeBusy $RuntimePath) {
            Start-Sleep -Milliseconds 250
        }
    }

    $lastError = $null
    for ($attempt = 1; $attempt -le 240; $attempt++) {
        try {
            if (Test-RuntimeBusy $RuntimePath) {
                Start-Sleep -Milliseconds 250
                continue
            }
            Activate-Runtime -Current $RuntimePath -Stage $StagingPath -Head $head
            return
        }
        catch {
            $lastError = $_
            Start-Sleep -Milliseconds 250
        }
    }
    if ($lastError) { throw $lastError }
    throw "Pending runtime activation timed out."
}

function Restart-WithFreshUpdater {
    param([int]$CurrentOwnerPid)
    $rawArgs = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", $PSCommandPath,
        "-Mode", "Update",
        "-RuntimePath", $RuntimePath,
        "-Branch", $Branch,
        "-OwnerPid", ([string]$CurrentOwnerPid),
        "-Relaunched"
    )
    $argumentLine = ($rawArgs | ForEach-Object { Quote-ProcessArgument ([string]$_) }) -join ' '
    $proc = Start-Process -FilePath "powershell.exe" -ArgumentList $argumentLine -WindowStyle Hidden -PassThru
    if (-not $proc) { throw "Không chạy lại được updater DEV mới sau khi pull." }
}

function Invoke-Update {
    $git = Resolve-KvtmGit
    if ([string]::IsNullOrWhiteSpace($git)) { throw "git.exe not found." }
    if (-not (Test-Path -LiteralPath $Builder -PathType Leaf)) { throw "Builder missing: $Builder" }
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot ".git"))) { throw "Not a Git repo: $RepoRoot" }

    Write-UpdateStatus -State "checking" -Message "Đang kiểm tra cập nhật GitHub/local DEV..."

    [object[]]$branchOutput = @(& $git -C $RepoRoot branch --show-current 2>$null)
    $branchExit = $LASTEXITCODE
    [string]$currentBranch = ($branchOutput | Select-Object -First 1)
    if ($branchExit -ne 0 -or [string]::IsNullOrWhiteSpace($currentBranch) -or $currentBranch.Trim() -ne $Branch) {
        throw "Repo phải ở branch $Branch trước khi update runtime. detected='$($currentBranch.Trim())' git_exit=$branchExit"
    }

    [object[]]$dirty = @(& $git -C $RepoRoot status --porcelain)
    [object[]]$blockingDirty = @(Get-BlockingDirtyLines $dirty)
    if ($blockingDirty.Count -gt 0) {
        throw "Repo có thay đổi DEV chưa commit; updater không ghi đè working tree."
    }

    $effectiveOwnerPid = $OwnerPid
    if ($effectiveOwnerPid -le 0) {
        $effectiveOwnerPid = Get-RuntimeHostPid -Root $RuntimePath
    }

    $beforeFetchHead = Get-GitFirstLine -Git $git -Arguments @("-C", $RepoRoot, "rev-parse", "HEAD")

    & $git -C $RepoRoot fetch origin $Branch
    if ($LASTEXITCODE -ne 0) { throw "git fetch origin $Branch failed." }

    $localHead = Get-GitFirstLine -Git $git -Arguments @("-C", $RepoRoot, "rev-parse", "HEAD")
    $remoteHead = Get-GitFirstLine -Git $git -Arguments @("-C", $RepoRoot, "rev-parse", "origin/$Branch")
    $pulledNewSource = $false

    if ($localHead -ne $remoteHead) {
        & $git -C $RepoRoot merge-base --is-ancestor $localHead $remoteHead *> $null
        $localBehind = ($LASTEXITCODE -eq 0)
        & $git -C $RepoRoot merge-base --is-ancestor $remoteHead $localHead *> $null
        $localAhead = ($LASTEXITCODE -eq 0)

        if ($localBehind) {
            Write-UpdateStatus -State "pulling" -Message "Có bản GitHub mới; đang pull fast-forward..." -Head $remoteHead
            & $git -C $RepoRoot pull --ff-only origin $Branch
            if ($LASTEXITCODE -ne 0) { throw "git pull --ff-only failed." }
            $pulledNewSource = $true
        }
        elseif (-not $localAhead) {
            throw "Local và origin/$Branch đã diverge; cần xử lý Git trước khi update runtime."
        }
    }

    $afterPullHead = Get-GitFirstLine -Git $git -Arguments @("-C", $RepoRoot, "rev-parse", "HEAD")
    if ($pulledNewSource -and -not $Relaunched -and $afterPullHead -ne $beforeFetchHead) {
        Write-UpdateStatus -State "pulling" -Message "Đã tải updater mới; đang chuyển sang updater mới..." -Head $afterPullHead
        Restart-WithFreshUpdater -CurrentOwnerPid $effectiveOwnerPid
        return
    }

    & $git -C $RepoRoot lfs install *> $null
    if ($LASTEXITCODE -ne 0) { throw "git lfs install failed." }
    & $git -C $RepoRoot lfs pull
    if ($LASTEXITCODE -ne 0) { throw "git lfs pull failed." }

    $targetHead = Get-GitFirstLine -Git $git -Arguments @("-C", $RepoRoot, "rev-parse", "HEAD")
    $stampPath = Join-Path $RuntimePath ".source-head.txt"
    $currentStamp = ""
    if (Test-Path -LiteralPath $stampPath -PathType Leaf) {
        $currentStamp = (Get-Content -LiteralPath $stampPath -Raw -Encoding ASCII).Trim()
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
        (Join-Path $stagePath ".source-head.txt"),
        (Join-Path $stagePath "Multi\kvtm_multi_dev_host.py"),
        (Join-Path $stagePath "Multi\runtime_update_ui.py"),
        (Join-Path $stagePath "AUTO_PRO\local_launcher.py")
    )) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "Staging runtime incomplete: $required"
        }
    }

    if (Test-RuntimeBusy $RuntimePath) {
        if ($effectiveOwnerPid -le 0) {
            $effectiveOwnerPid = Get-RuntimeHostPid -Root $RuntimePath
        }
        Write-UpdateStatus -State "pending_restart" -Message "Bản mới đã tải/build xong. Tool hiện tại tiếp tục chạy; sẽ tự kích hoạt khi Multi đóng." -Head $targetHead -Stage $stagePath
        Start-ActivationWatcher -Current $RuntimePath -Stage $stagePath -OwnerProcessId $effectiveOwnerPid
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
