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

function Stop-KvtmDevRuntimeProcesses {
    param(
        [Parameter(Mandatory = $true)][string]$OutputRoot,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [int]$TimeoutSeconds = 15
    )

    # DEV runtime data moved to %APPDATA% so the package can be rebuilt without
    # deleting profiles/settings. The previous cleanup only recognized processes
    # by the dist tree, which can miss an injected ClientJS process whose EXE is
    # outside dist. Read the authoritative persistent running-client map as well.
    $outputNeedle = [System.IO.Path]::GetFullPath($OutputRoot).TrimEnd('\').ToLowerInvariant()
    $repoNeedle = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\').ToLowerInvariant()
    $persistentData = Join-Path $env:APPDATA "KVTM Multi DEV"
    $runningMap = Join-Path $persistentData "running_clients.json"

    $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    if ($all.Count -eq 0) {
        Write-Host "[WARN] Khong doc duoc Win32_Process; bo qua process scan." -ForegroundColor Yellow
        return
    }

    $byPid = @{}
    $byParent = @{}
    foreach ($process in $all) {
        $pidValue = [int]$process.ProcessId
        if ($pidValue -gt 0) {
            $byPid[$pidValue] = $process
        }
        $parentId = [int]$process.ParentProcessId
        if (-not $byParent.ContainsKey($parentId)) {
            $byParent[$parentId] = New-Object System.Collections.ArrayList
        }
        [void]$byParent[$parentId].Add($process)
    }

    # Use non-generic ArrayList here. Windows PowerShell 5.1 can throw
    # "Argument types do not match" when @() expands generic HashSet/List values.
    $owned = New-Object System.Collections.ArrayList
    $runtimeMarkers = @(
        "kvtm_multi_owned_host.py",
        "kvtm_multi_dev_host.py",
        "auto_multi_dev_worker.py",
        "clear_stall_step1_probe.py",
        "bridge_v3_gesture_probe.py"
    )

    foreach ($process in $all) {
        $pidValue = [int]$process.ProcessId
        if ($pidValue -le 0 -or $pidValue -eq $PID) { continue }
        $commandLine = ([string]$process.CommandLine).ToLowerInvariant()
        $executablePath = ([string]$process.ExecutablePath).ToLowerInvariant()

        $matchesOutput = (
            (-not [string]::IsNullOrWhiteSpace($commandLine) -and $commandLine.Contains($outputNeedle)) -or
            (-not [string]::IsNullOrWhiteSpace($executablePath) -and $executablePath.StartsWith($outputNeedle))
        )
        $matchesKnownRuntime = $false
        if (
            (-not [string]::IsNullOrWhiteSpace($commandLine)) -and
            ($commandLine.Contains($repoNeedle) -or $commandLine.Contains($outputNeedle))
        ) {
            foreach ($marker in $runtimeMarkers) {
                if ($commandLine.Contains($marker)) {
                    $matchesKnownRuntime = $true
                    break
                }
            }
        }
        if (($matchesOutput -or $matchesKnownRuntime) -and -not $owned.Contains($pidValue)) {
            [void]$owned.Add($pidValue)
        }
    }

    if (Test-Path -LiteralPath $runningMap -PathType Leaf) {
        try {
            $mapData = Get-Content -LiteralPath $runningMap -Raw -Encoding UTF8 | ConvertFrom-Json
            foreach ($clientEntry in @($mapData.clients)) {
                $mappedPid = 0
                if (-not [int]::TryParse([string]$clientEntry.pid, [ref]$mappedPid)) { continue }
                if ($mappedPid -le 0 -or $mappedPid -eq $PID) { continue }
                if (-not $byPid.ContainsKey($mappedPid)) { continue }

                # Guard against stale PID reuse. A mapped PID is stopped only if
                # the live process still looks like a ClientJS process.
                $mapped = $byPid[$mappedPid]
                $mappedName = ([string]$mapped.Name).ToLowerInvariant()
                $mappedCommand = ([string]$mapped.CommandLine).ToLowerInvariant()
                $mappedExe = ([string]$mapped.ExecutablePath).ToLowerInvariant()
                $looksClient = (
                    $mappedName.Contains("clientjs") -or
                    $mappedCommand.Contains("clientjs") -or
                    $mappedExe.Contains("clientjs")
                )
                if ($looksClient) {
                    if (-not $owned.Contains($mappedPid)) {
                        [void]$owned.Add($mappedPid)
                    }
                    Write-Host (
                        "[DEV] Persistent runtime map: ClientJS PID {0} se duoc release truoc build." -f $mappedPid
                    ) -ForegroundColor DarkCyan
                }
            }
        }
        catch {
            Write-Host (
                "[WARN] Khong doc duoc persistent running_clients.json: {0}" -f $_.Exception.Message
            ) -ForegroundColor Yellow
        }
    }

    # Include descendants of proven DEV owners. This catches worker/ClientJS
    # children even when their command line is short or their EXE lives elsewhere.
    $queue = New-Object System.Collections.Queue
    foreach ($ownedPid in $owned) { $queue.Enqueue([int]$ownedPid) }
    while ($queue.Count -gt 0) {
        $parent = [int]$queue.Dequeue()
        if (-not $byParent.ContainsKey($parent)) { continue }
        foreach ($child in $byParent[$parent]) {
            $childPid = [int]$child.ProcessId
            if ($childPid -le 0 -or $childPid -eq $PID) { continue }
            if (-not $owned.Contains($childPid)) {
                [void]$owned.Add($childPid)
                $queue.Enqueue($childPid)
            }
        }
    }

    if ($owned.Count -gt 0) {
        Write-Host (
            "[DEV] Giai phong {0} process Multi/ClientJS DEV truoc build..." -f $owned.Count
        ) -ForegroundColor Yellow
        foreach ($ownedPid in @($owned | Sort-Object -Descending)) {
            $candidate = Get-Process -Id $ownedPid -ErrorAction SilentlyContinue
            if ($null -eq $candidate) { continue }
            try {
                Write-Host (
                    "[DEV] Stop DEV runtime PID {0} ({1})" -f $ownedPid, $candidate.ProcessName
                ) -ForegroundColor DarkYellow
                Stop-Process -Id $ownedPid -Force -ErrorAction Stop
            }
            catch {
                Write-Host (
                    "[WARN] Chua stop duoc PID {0}: {1}" -f $ownedPid, $_.Exception.Message
                ) -ForegroundColor Yellow
            }
        }

        $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(1, $TimeoutSeconds))
        do {
            $remaining = @(
                $owned | Where-Object { $null -ne (Get-Process -Id $_ -ErrorAction SilentlyContinue) }
            )
            if ($remaining.Count -eq 0) { break }
            Start-Sleep -Milliseconds 250
        } while ([DateTime]::UtcNow -lt $deadline)

        $stillAlive = @(
            $owned | Where-Object { $null -ne (Get-Process -Id $_ -ErrorAction SilentlyContinue) }
        )
        if ($stillAlive.Count -gt 0) {
            throw (
                "Khong giai phong duoc DEV runtime sau ${TimeoutSeconds}s; PID con song: " +
                ($stillAlive -join ", ")
            )
        }
    }
    else {
        Write-Host "[DEV] Khong co process Multi/ClientJS DEV dang chay." -ForegroundColor DarkCyan
    }

    # Verify the exact legacy DLL that previously blocked the package rebuild.
    # This is only a lock probe; the build still owns the actual replace/copy.
    $bridgeInUse = Join-Path $OutputRoot "AUTO_PRO\bin\kvtm_bridge.dll"
    if (Test-Path -LiteralPath $bridgeInUse -PathType Leaf) {
        $released = $false
        for ($attempt = 1; $attempt -le 20; $attempt++) {
            try {
                $stream = [System.IO.File]::Open(
                    $bridgeInUse,
                    [System.IO.FileMode]::Open,
                    [System.IO.FileAccess]::ReadWrite,
                    [System.IO.FileShare]::None
                )
                $stream.Dispose()
                $released = $true
                break
            }
            catch {
                Start-Sleep -Milliseconds 250
            }
        }
        if (-not $released) {
            throw (
                "kvtm_bridge.dll van bi khoa sau DEV cleanup; " +
                "khong build de tranh xoa/copy runtime dang duoc su dung"
            )
        }
    }

    Write-Host "[DEV] Multi/ClientJS runtime handles: RELEASED" -ForegroundColor Green
}

[string]$KvtmGitExe = Resolve-KvtmGitExe
if ([string]::IsNullOrWhiteSpace($KvtmGitExe)) { throw "git.exe not found for package build." }

Write-Host "PS5.1 package compatibility wrapper" -ForegroundColor Cyan
Write-Host "Git: $KvtmGitExe"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$OutputRoot = Join-Path (Join-Path $RepoRoot "dist") $OutputName
[object[]]$probeOutput = @(& $KvtmGitExe -C $RepoRoot rev-parse HEAD 2>$null)
$probeExit = $LASTEXITCODE
[string]$probeHead = ($probeOutput | Select-Object -First 1)
if ($probeExit -ne 0 -or [string]::IsNullOrWhiteSpace($probeHead)) {
    throw "Native Git HEAD preflight failed; exit=$probeExit repo=$RepoRoot"
}
Write-Host "Git HEAD preflight: $($probeHead.Trim())" -ForegroundColor Green

# The old standalone recorder BAT is intentionally gone. The GUI recorder is a
# required package source and uses the resident cv2 runtime already shipped by
# AUTO_PRO. Block the build if the integrated recorder contract disappears.
# Keep every verifier token ASCII-only because Windows PowerShell 5.1 parses
# UTF-8-without-BOM script literals through the active ANSI code page.
$VideoRecorderSource = Join-Path $RepoRoot "source-archive\multi-current\kvtm_multi_tool\client_video_recorder.py"
if (-not (Test-Path -LiteralPath $VideoRecorderSource -PathType Leaf)) {
    throw "Missing integrated ClientJS MP4 recorder: $VideoRecorderSource"
}
$VideoRecorderText = Get-Content -LiteralPath $VideoRecorderSource -Raw -Encoding UTF8
foreach ($token in @(
    'VIDEO_WIDTH = 1920',
    'VIDEO_HEIGHT = 1080',
    'VIDEO_FPS = 60.0',
    'VIDEO_CODEC = "mp4v"',
    'VIDEO_EXTENSION = ".mp4"',
    'capture_bgra',
    'def wrapped_build_ui(self) -> None:',
    'screenshot_button = _find_widget_by_text(self',
    '_client_video_button = core.ttk.Button(',
    'command=lambda: _toggle_client_video(self)',
    'Quay MP4'
)) {
    if (-not $VideoRecorderText.Contains($token)) {
        throw "Integrated ClientJS MP4 recorder missing contract token '$token'"
    }
}
if (Test-Path -LiteralPath (Join-Path $RepoRoot "KVTM_QUAY_VIDEO_60FPS.bat") -PathType Leaf) {
    throw "Legacy KVTM_QUAY_VIDEO_60FPS.bat must stay deleted; GUI MP4 recorder owns recording"
}
Write-Host "VIDEO GUI contract: MP4 1920x1080@60 + GUI hook + legacy BAT removed" -ForegroundColor Green

# Stop only processes proven to belong to this DEV runtime, including ClientJS
# PIDs from the persistent %APPDATA% runtime map used by the current launcher.
Stop-KvtmDevRuntimeProcesses -OutputRoot $OutputRoot -RepoRoot $RepoRoot

$PersistentSettingsVerifier = Join-Path $RepoRoot "tools\verify_multi_dev_persistent_settings_contract.py"
if (-not (Test-Path -LiteralPath $PersistentSettingsVerifier -PathType Leaf)) {
    throw "Missing persistent settings verifier: $PersistentSettingsVerifier"
}
& py.exe -3.11 $PersistentSettingsVerifier
if ($LASTEXITCODE -ne 0) {
    throw "AUTO MULTI DEV persistent settings contract failed; exit=$LASTEXITCODE"
}
Write-Host "AUTO MULTI DEV persistent settings contract: VERIFIED" -ForegroundColor Green

$MainBoundaryVerifier = Join-Path $RepoRoot "tools\verify_multi_dev_main_boundary_contract.py"
if (-not (Test-Path -LiteralPath $MainBoundaryVerifier -PathType Leaf)) {
    throw "Missing main-boundary verifier: $MainBoundaryVerifier"
}
& py.exe -3.11 $MainBoundaryVerifier
if ($LASTEXITCODE -ne 0) {
    throw "AUTO MULTI DEV main-boundary contract failed; exit=$LASTEXITCODE"
}
Write-Host "AUTO MULTI DEV main-boundary contract: VERIFIED" -ForegroundColor Green

$VpAdvertisingVerifier = Join-Path $RepoRoot "tools\verify_auto_vp_advertising_contract.py"
if (-not (Test-Path -LiteralPath $VpAdvertisingVerifier -PathType Leaf)) {
    throw "Missing VP advertising verifier: $VpAdvertisingVerifier"
}
& py.exe -3.11 $VpAdvertisingVerifier
if ($LASTEXITCODE -ne 0) {
    throw "AUTO MULTI DEV VP advertising contract failed; exit=$LASTEXITCODE"
}
Write-Host "AUTO MULTI DEV VP advertising contract: VERIFIED" -ForegroundColor Green

# BUILD_FULL_PACKAGE.ps1 is kept source-compatible. Patch its runtime copy for
# Windows PowerShell 5.1 plus the integrated GUI recorder migration.
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

$oldOutputCleanup = @'
if (Test-Path -LiteralPath $OutputRoot) {
    Remove-Item -LiteralPath $OutputRoot -Recurse -Force
}
'@
$newOutputCleanup = @'
if (Test-Path -LiteralPath $OutputRoot) {
    $OutputRemoved = $false
    $LastOutputCleanupError = $null
    for ($OutputCleanupAttempt = 1; $OutputCleanupAttempt -le 20; $OutputCleanupAttempt++) {
        try {
            Remove-Item -LiteralPath $OutputRoot -Recurse -Force -ErrorAction Stop
            $OutputRemoved = -not (Test-Path -LiteralPath $OutputRoot)
            if ($OutputRemoved) {
                Write-Host ("[DEV] Old package output removed after attempt {0}/20." -f $OutputCleanupAttempt) -ForegroundColor Green
                break
            }
        }
        catch {
            $LastOutputCleanupError = $_
        }
        Start-Sleep -Milliseconds 350
    }
    if (-not $OutputRemoved) {
        $detail = if ($null -ne $LastOutputCleanupError) {
            $LastOutputCleanupError.Exception.Message
        } else {
            "unknown filesystem lock"
        }
        throw (
            "Khong xoa duoc package output sau 20 lan retry: $OutputRoot. " +
            "Hay kiem tra process ngoai KVTM/Explorer/antivirus dang giu file. LastError=$detail"
        )
    }
}
'@
if (-not $patched.Contains($oldOutputCleanup)) {
    throw "Output cleanup compatibility patch target not found in BUILD_FULL_PACKAGE.ps1."
}
$patched = $patched.Replace($oldOutputCleanup, $newOutputCleanup)

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

# Remove the obsolete standalone recorder packaging block from the runtime build.
$oldRecorderBlock = @'
$RecorderBat = Join-Path $RepoRoot "KVTM_QUAY_VIDEO_60FPS.bat"
$RecorderScript = Join-Path $RepoRoot "tools\KVTM_SCREEN_RECORDER.ps1"
if (-not (Test-Path -LiteralPath $RecorderBat -PathType Leaf) -or
    -not (Test-Path -LiteralPath $RecorderScript -PathType Leaf)) {
    throw "Missing standalone MP4 recorder files"
}
$RecorderToolsOut = Join-Path $OutputRoot "tools"
New-Item -ItemType Directory -Path $RecorderToolsOut -Force | Out-Null
Copy-Item -LiteralPath $RecorderBat -Destination $OutputRoot -Force
Copy-Item -LiteralPath $RecorderScript -Destination $RecorderToolsOut -Force
'@
$newRecorderBlock = @'
# ClientJS recording is integrated into Multi/client_video_recorder.py.
# No standalone recorder BAT/PowerShell files are shipped in the DEV package.
Write-Host "Integrated GUI MP4 recorder: PACKAGED" -ForegroundColor Green
'@
if (-not $patched.Contains($oldRecorderBlock)) {
    throw "Legacy recorder packaging block not found in BUILD_FULL_PACKAGE.ps1."
}
$patched = $patched.Replace($oldRecorderBlock, $newRecorderBlock)

# Make the integrated recorder an explicit source and output contract in addition
# to the existing wildcard copy of kvtm_multi_tool.
$oldRequiredHost = '(Join-Path $MultiSource "kvtm_multi_dev_host.py"),'
$newRequiredHost = @'
(Join-Path $MultiSource "kvtm_multi_dev_host.py"),
    (Join-Path $MultiSource "client_video_recorder.py"),
'@.TrimEnd()
if (-not $patched.Contains($oldRequiredHost)) {
    throw "Multi source required-file patch target not found"
}
$patched = $patched.Replace($oldRequiredHost, $newRequiredHost)

$oldPackagedHost = '(Join-Path $MultiOut "kvtm_multi_dev_host.py"),'
$newPackagedHost = @'
(Join-Path $MultiOut "kvtm_multi_dev_host.py"),
    (Join-Path $MultiOut "client_video_recorder.py"),
'@.TrimEnd()
if (-not $patched.Contains($oldPackagedHost)) {
    throw "Multi output required-file patch target not found"
}
$patched = $patched.Replace($oldPackagedHost, $newPackagedHost)

$RuntimeBuilder = Join-Path $PSScriptRoot "BUILD_FULL_PACKAGE_PS51.runtime.ps1"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($RuntimeBuilder, $patched, $utf8NoBom)

$previousGitExe = $env:KVTM_PS51_GIT_EXE
$env:KVTM_PS51_GIT_EXE = $KvtmGitExe
try {
    Write-Host "PS5.1 HEAD stamp patch: READY" -ForegroundColor Green
    Write-Host "AUTO MULTI DEV persistent runtime release: READY" -ForegroundColor Green
    Write-Host "AUTO MULTI DEV output cleanup retry: READY" -ForegroundColor Green
    Write-Host "AUTO MULTI DEV clear-stall migration gate: READY" -ForegroundColor Green
    Write-Host "AUTO MULTI DEV integrated MP4 recorder packaging: READY" -ForegroundColor Green
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
