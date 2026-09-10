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

function Stop-KvtmPackagedRuntimeProcesses {
    param(
        [Parameter(Mandatory = $true)][string]$OutputRoot,
        [int]$TimeoutSeconds = 12
    )

    # A hidden Multi DEV host is python/pythonw with its script/cwd under the
    # packaged output. It can keep dist\...\Multi locked even after the visible
    # window is gone. Detect only processes proven to belong to this exact output
    # tree, then include their descendants. Never kill unrelated Python/ClientJS.
    if (-not (Test-Path -LiteralPath $OutputRoot -PathType Container)) {
        Write-Host "[DEV] Runtime cu khong ton tai; khong can giai phong process." -ForegroundColor DarkCyan
        return
    }

    $normalizedRoot = [System.IO.Path]::GetFullPath($OutputRoot).TrimEnd('\')
    $rootNeedle = $normalizedRoot.ToLowerInvariant()
    $all = @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue
    )
    if ($all.Count -eq 0) {
        Write-Host "[WARN] Khong doc duoc Win32_Process; se dung cleanup retry o buoc xoa output." -ForegroundColor Yellow
        return
    }

    $byParent = @{}
    foreach ($process in $all) {
        $parentId = [int]$process.ParentProcessId
        if (-not $byParent.ContainsKey($parentId)) {
            $byParent[$parentId] = New-Object System.Collections.Generic.List[object]
        }
        $byParent[$parentId].Add($process)
    }

    $owned = New-Object "System.Collections.Generic.HashSet[int]"
    foreach ($process in $all) {
        $pidValue = [int]$process.ProcessId
        if ($pidValue -le 0 -or $pidValue -eq $PID) { continue }
        $commandLine = [string]$process.CommandLine
        $executablePath = [string]$process.ExecutablePath
        $matchesOutput = (
            (-not [string]::IsNullOrWhiteSpace($commandLine) -and $commandLine.ToLowerInvariant().Contains($rootNeedle)) -or
            (-not [string]::IsNullOrWhiteSpace($executablePath) -and $executablePath.ToLowerInvariant().StartsWith($rootNeedle))
        )
        if ($matchesOutput) {
            [void]$owned.Add($pidValue)
        }
    }

    # Include children even when their command line is short/opaque. This catches
    # ClientJS/worker descendants created by the packaged Multi host without
    # widening the kill scope to processes from another project folder.
    $queue = New-Object System.Collections.Generic.Queue[int]
    foreach ($ownedPid in @($owned)) { $queue.Enqueue([int]$ownedPid) }
    while ($queue.Count -gt 0) {
        $parent = $queue.Dequeue()
        if (-not $byParent.ContainsKey($parent)) { continue }
        foreach ($child in @($byParent[$parent])) {
            $childPid = [int]$child.ProcessId
            if ($childPid -le 0 -or $childPid -eq $PID) { continue }
            if ($owned.Add($childPid)) {
                $queue.Enqueue($childPid)
            }
        }
    }

    if ($owned.Count -eq 0) {
        Write-Host "[DEV] Khong co process runtime cu nao dang giu package output." -ForegroundColor DarkCyan
        return
    }

    Write-Host ("[DEV] Giai phong {0} process runtime cu truoc build..." -f $owned.Count) -ForegroundColor Yellow
    foreach ($ownedPid in @($owned | Sort-Object -Descending)) {
        $candidate = Get-Process -Id $ownedPid -ErrorAction SilentlyContinue
        if ($null -eq $candidate) { continue }
        try {
            Write-Host ("[DEV] Stop packaged runtime PID {0} ({1})" -f $ownedPid, $candidate.ProcessName) -ForegroundColor DarkYellow
            Stop-Process -Id $ownedPid -Force -ErrorAction Stop
        }
        catch {
            Write-Host ("[WARN] Chua stop duoc PID {0}: {1}" -f $ownedPid, $_.Exception.Message) -ForegroundColor Yellow
        }
    }

    $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(1, $TimeoutSeconds))
    do {
        $remaining = @(
            $owned | Where-Object { $null -ne (Get-Process -Id $_ -ErrorAction SilentlyContinue) }
        )
        if ($remaining.Count -eq 0) {
            Write-Host "[DEV] Packaged runtime handles: RELEASED" -ForegroundColor Green
            return
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)

    $stillAlive = @(
        $owned | Where-Object { $null -ne (Get-Process -Id $_ -ErrorAction SilentlyContinue) }
    )
    throw (
        "Khong giai phong duoc packaged runtime sau ${TimeoutSeconds}s; PID con song: " +
        ($stillAlive -join ", ")
    )
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
    'Chụp ảnh',
    'Quay MP4'
)) {
    if (-not $VideoRecorderText.Contains($token)) {
        throw "Integrated ClientJS MP4 recorder missing contract token '$token'"
    }
}
if (Test-Path -LiteralPath (Join-Path $RepoRoot "KVTM_QUAY_VIDEO_60FPS.bat") -PathType Leaf) {
    throw "Legacy KVTM_QUAY_VIDEO_60FPS.bat must stay deleted; GUI MP4 recorder owns recording"
}
Write-Host "VIDEO GUI contract: MP4 1920x1080@60 + legacy BAT removed" -ForegroundColor Green

# Stop only runtime processes that are proven to belong to the old packaged output.
Stop-KvtmPackagedRuntimeProcesses -OutputRoot $OutputRoot

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
    Write-Host "AUTO MULTI DEV old-runtime release: READY" -ForegroundColor Green
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
