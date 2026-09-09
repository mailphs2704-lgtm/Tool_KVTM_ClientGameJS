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
    # Stop descendants/large PIDs first, then parents. Stop-Process -Force is
    # intentional here: [1] is a rebuild transaction and the old runtime must not
    # keep executable/script handles inside the directory being replaced.
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

# Stop only runtime processes that are proven to belong to the old packaged
# output. This fixes rebuilds where the hidden Multi host keeps dist\...\Multi
# locked even after the operator closes the visible window.
Stop-KvtmPackagedRuntimeProcesses -OutputRoot $OutputRoot

# Persistent DEV settings are a build contract. This protects Dọn quầy profile
# settings and the proven Multi speed baseline from being silently regressed by a
# later source update.
$PersistentSettingsVerifier = Join-Path $RepoRoot "tools\verify_multi_dev_persistent_settings_contract.py"
if (-not (Test-Path -LiteralPath $PersistentSettingsVerifier -PathType Leaf)) {
    throw "Missing persistent settings verifier: $PersistentSettingsVerifier"
}
& py.exe -3.11 $PersistentSettingsVerifier
if ($LASTEXITCODE -ne 0) {
    throw "AUTO MULTI DEV persistent settings contract failed; exit=$LASTEXITCODE"
}
Write-Host "AUTO MULTI DEV persistent settings contract: VERIFIED" -ForegroundColor Green

# Exact-main must work across account-specific farm backgrounds. Lock the runtime
# contract to fixed own-farm HUD + behavioral goDown boundary evidence and reject
# any future return to a quay_hang/world-image exact-main gate.
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

# Windows can release a directory handle a few hundred milliseconds after its
# owning process exits. Replace the one-shot output deletion in the runtime copy
# with a bounded retry so a transient handle/AV scan cannot waste the whole build.
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
    Write-Host "AUTO MULTI DEV old-runtime release: READY" -ForegroundColor Green
    Write-Host "AUTO MULTI DEV output cleanup retry: READY" -ForegroundColor Green
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
