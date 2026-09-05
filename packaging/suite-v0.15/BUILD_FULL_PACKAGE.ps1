param(
    [string]$OutputName = "KVTM-ClientJS-Suite-Multi-DEV"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$AutoSource = Join-Path $RepoRoot "source-archive\auto-pro-reference"
$MultiSource = Join-Path $RepoRoot "source-archive\multi-current\kvtm_multi_tool"
$PatchSource = Join-Path $RepoRoot "test-candidates\auto-pro-clientjs-temp"
$BridgeV3Source = Join-Path $RepoRoot "bridge-v3"
$ClientJsAutoSource = Join-Path $RepoRoot "components\clientjs-auto"
$CleanAutoSource = Join-Path $ClientJsAutoSource "kvtm_automation"
$DistRoot = Join-Path $RepoRoot "dist"
$OutputRoot = Join-Path $DistRoot $OutputName
$PreserveRoot = Join-Path $DistRoot (".kvtm-dev-data-" + [guid]::NewGuid().ToString("N"))
$PreservedFiles = @{}
$PreservedClearStall = $false
$PreservedClearStallProbe = $false
New-Item -ItemType Directory -Path $DistRoot -Force | Out-Null

$ClearStallVerifier = Join-Path $RepoRoot "tools\verify_clear_stall_contract.py"
if (-not (Test-Path -LiteralPath $ClearStallVerifier -PathType Leaf)) {
    throw "Missing clear-stall contract verifier: $ClearStallVerifier"
}
& py.exe -3.11 $ClearStallVerifier
if ($LASTEXITCODE -ne 0) {
    throw "Clear-stall static contract failed; exit=$LASTEXITCODE"
}
Write-Host "Clear-stall static contract: VERIFIED" -ForegroundColor Green

function Test-GitLfsPointer {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -gt 1024) {
        return $false
    }
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $length = [Math]::Min(200, [int]$stream.Length)
        if ($length -le 0) {
            return $false
        }
        $buffer = New-Object byte[] $length
        $read = $stream.Read($buffer, 0, $length)
        $text = [System.Text.Encoding]::ASCII.GetString($buffer, 0, $read)
        return $text.StartsWith("version https://git-lfs.github.com/spec/v1")
    }
    finally {
        $stream.Dispose()
    }
}

function Copy-PreservedDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$TimeoutSeconds = 600
    )
    Write-Host "[DATA] Bat dau bao toan $Label..." -ForegroundColor Cyan
    $arguments = @(
        ('"' + $Source + '"'),
        ('"' + $Destination + '"'),
        "/E", "/COPY:DAT", "/DCOPY:DAT",
        "/R:1", "/W:1", "/MT:8",
        "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
    )
    $copyProcess = Start-Process -FilePath "robocopy.exe" -ArgumentList $arguments -PassThru -NoNewWindow
    $startedAt = [DateTime]::UtcNow
    $nextHeartbeat = $startedAt.AddSeconds(15)
    while (-not $copyProcess.HasExited) {
        Start-Sleep -Milliseconds 500
        $now = [DateTime]::UtcNow
        if (($now - $startedAt).TotalSeconds -ge $TimeoutSeconds) {
            try { $copyProcess.Kill() } catch {}
            throw (
                "Bao toan $Label vuot timeout ${TimeoutSeconds}s. " +
                "Du lieu goc van duoc giu nguyen tai: $Source"
            )
        }
        if ($now -ge $nextHeartbeat) {
            $elapsed = [int](($now - $startedAt).TotalSeconds)
            Write-Host "[DATA] Dang bao toan $Label... ${elapsed}s" -ForegroundColor DarkCyan
            $nextHeartbeat = $now.AddSeconds(15)
        }
    }
    $copyProcess.WaitForExit()
    $exitCode = [int]$copyProcess.ExitCode
    if ($exitCode -ge 8) {
        throw (
            "Robocopy bao toan $Label that bai; exit=$exitCode. " +
            "Du lieu goc van duoc giu nguyen tai: $Source"
        )
    }
    $elapsed = [int](([DateTime]::UtcNow - $startedAt).TotalSeconds)
    Write-Host "[DATA] Bao toan $Label xong sau ${elapsed}s." -ForegroundColor Green
}


function Get-GitLfsPointers {
    param([Parameter(Mandatory = $true)][string]$Root)

    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        return @()
    }
    return @(
        Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction Stop |
            Where-Object { Test-GitLfsPointer -Path $_.FullName }
    )
}

function Resolve-AutoProLfsRuntime {
    $pointers = @(Get-GitLfsPointers -Root $AutoSource)
    if ($pointers.Count -eq 0) {
        return
    }
    Write-Host ("Git LFS: found {0} runtime pointers; resolving real objects..." -f $pointers.Count) -ForegroundColor Yellow
    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if ($null -eq $gitCommand) {
        throw "AUTO PRO runtime still contains Git LFS pointers and git is unavailable."
    }
    Push-Location $RepoRoot
    try {
        & git lfs version | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Git LFS is not available."
        }
        & git lfs pull
        if ($LASTEXITCODE -ne 0) {
            throw "git lfs pull failed."
        }
    }
    finally {
        Pop-Location
    }
    $remaining = @(Get-GitLfsPointers -Root $AutoSource)
    if ($remaining.Count -gt 0) {
        $sample = ($remaining | Select-Object -First 12 | ForEach-Object { $_.FullName }) -join "`n  - "
        throw (
            "Cannot package: {0} Git LFS pointers remain in AUTO PRO runtime.`n  - {1}" -f
            $remaining.Count, $sample
        )
    }
    Write-Host "Git LFS runtime VERIFIED: all tracked files are real objects" -ForegroundColor Green
}

function Sync-PackagedPythonRuntime {
    param(
        [Parameter(Mandatory = $true)][string]$AutoRoot
    )

    $pyc = Join-Path $AutoRoot "runtime\pyc"
    $internal = Join-Path $AutoRoot "_internal"
    if (-not (Test-Path -LiteralPath $pyc -PathType Container) -or
        -not (Test-Path -LiteralPath $internal -PathType Container)) {
        throw "Missing packaged Python runtime: $pyc / $internal"
    }

    $copied = 0
    foreach ($source in @(Get-ChildItem -LiteralPath $internal -Recurse -File -ErrorAction Stop)) {
        $relative = $source.FullName.Substring($internal.Length).TrimStart("\")
        $parts = $relative.Split("\")
        if ($parts.Count -lt 2) { continue }
        $packageRoot = Join-Path $pyc $parts[0]
        if (-not (Test-Path -LiteralPath $packageRoot)) { continue }

        $destination = Join-Path $pyc $relative
        $copy = -not (Test-Path -LiteralPath $destination -PathType Leaf)
        if (-not $copy) {
            $copy = ((Get-Item -LiteralPath $destination).Length -ne $source.Length)
        }
        if ($copy) {
            $parent = Split-Path -Parent $destination
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
            Copy-Item -LiteralPath $source.FullName -Destination $destination -Force
            $copied++
        }
    }
    Write-Host ("Python image runtime PRE-SYNC VERIFIED; files copied during build: {0}" -f $copied) -ForegroundColor Green
}

function Assert-CleanClearStallWorker {
    param([Parameter(Mandatory = $true)][string]$Path)

    $source = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    foreach ($token in @(
        "from auto_worker import",
        "import auto_worker",
        "FarmAutomation",
        "ADBController",
        "install_headless_clientjs_runtime",
        "automation.pyc",
        "adb_controller.pyc",
        "runtime/pyc"
    )) {
        if ($source.Contains($token)) {
            throw "Clean Dọn quầy worker contains forbidden legacy runtime token '$token': $Path"
        }
    }
}

function Test-X86PortableExecutable {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    try {
        [byte[]]$bytes = [System.IO.File]::ReadAllBytes($Path)
        if ($bytes.Length -lt 4096 -or $bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A) {
            return $false
        }
        $peOffset = [BitConverter]::ToInt32($bytes, 0x3C)
        if ($peOffset -lt 0 -or ($peOffset + 6) -gt $bytes.Length) { return $false }
        if (
            $bytes[$peOffset] -ne 0x50 -or
            $bytes[$peOffset + 1] -ne 0x45 -or
            $bytes[$peOffset + 2] -ne 0x00 -or
            $bytes[$peOffset + 3] -ne 0x00
        ) {
            return $false
        }
        return ([BitConverter]::ToUInt16($bytes, $peOffset + 4) -eq 0x014C)
    }
    catch {
        return $false
    }
}

function Restore-CurrentRuntimeBridge {
    param(
        [Parameter(Mandatory = $true)][string[]]$Names,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $runtimeHeadFile = Join-Path $OutputRoot ".source-head.txt"
    $runtimeBin = Join-Path $OutputRoot "AUTO_PRO\bin"
    if (-not (Test-Path -LiteralPath $runtimeHeadFile -PathType Leaf)) {
        return $false
    }

    try {
        $runtimeHead = (Get-Content -LiteralPath $runtimeHeadFile -Raw -Encoding ASCII).Trim()
    }
    catch {
        return $false
    }
    if ($runtimeHead -notmatch "^[0-9a-fA-F]{40}$") { return $false }

    $gitCommand = if ($env:KVTM_PS51_GIT_EXE) {
        $env:KVTM_PS51_GIT_EXE
    }
    else {
        $resolved = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue
        if ($resolved) { [string]$resolved.Source } else { $null }
    }
    if ([string]::IsNullOrWhiteSpace([string]$gitCommand)) { return $false }

    $bridgeInputs = @(
        "test-candidates/auto-pro-clientjs-temp/native/kvtm_bridge.cpp",
        "test-candidates/auto-pro-clientjs-temp/native/kvtm_loader.cpp",
        "test-candidates/auto-pro-clientjs-temp/BUILD_X86.bat",
        "bridge-v3/native/kvtm_bridge_v3.cpp",
        "bridge-v3/native/kvtm_loader_v3.cpp",
        "bridge-v3/KVTM_BRIDGE_V3_CONTROL.bat"
    )
    [object[]]$commitProbe = @(& $gitCommand -C $RepoRoot cat-file -e ($runtimeHead + "^{commit}") 2>$null)
    $commitProbeExit = $LASTEXITCODE
    if ($commitProbeExit -ne 0) { return $false }

    $diffArgs = @("-C", $RepoRoot, "diff", "--name-only", $runtimeHead, "HEAD", "--") + $bridgeInputs
    [object[]]$changedOutput = @(& $gitCommand @diffArgs 2>$null)
    $changedExit = $LASTEXITCODE
    $changedInputs = @($changedOutput | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($changedExit -ne 0 -or $changedInputs.Count -gt 0) {
        Write-Host (
            "[BLOCK] Source bridge da doi tu runtime $runtimeHead; khong dung binary cu."
        ) -ForegroundColor Red
        return $false
    }

    foreach ($name in $Names) {
        $sourceFile = Join-Path $runtimeBin $name
        if (-not (Test-X86PortableExecutable -Path $sourceFile)) {
            Write-Host "[BLOCK] Binary runtime cu khong hop le/x86: $sourceFile" -ForegroundColor Red
            return $false
        }
    }

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    foreach ($name in $Names) {
        Copy-Item -LiteralPath (Join-Path $runtimeBin $name) -Destination (Join-Path $Destination $name) -Force
    }
    Write-Host (
        "[DEV] ${Label}: dung binary x86 tu runtime $runtimeHead; source bridge khong doi."
    ) -ForegroundColor Yellow
    return $true
}

function Build-ClientJsCaptureBridge {
    $buildScript = Join-Path $PatchSource "BUILD_X86.bat"
    $source = Join-Path $PatchSource "native\kvtm_bridge.cpp"
    $loader = Join-Path $PatchSource "bin\kvtm_loader.exe"
    $bridge = Join-Path $PatchSource "bin\kvtm_bridge.dll"
    if (-not (Test-Path -LiteralPath $buildScript -PathType Leaf)) {
        throw "Missing capture bridge builder: $buildScript"
    }
    $sourceText = Get-Content -LiteralPath $source -Raw -Encoding UTF8
    foreach ($token in @("CAPTURE", "OK FRAME", "KCAP")) {
        if (-not $sourceText.Contains($token)) {
            throw "Capture bridge source missing protocol token '$token': $source"
        }
    }
    Write-Host "Building ClientJS OpenGL capture bridge (x86)..." -ForegroundColor Cyan
    & cmd.exe /d /c ('"' + $buildScript + '"')
    $buildExit = $LASTEXITCODE
    if ($buildExit -ne 0) {
        $restored = $false
        if ($buildExit -eq 20) {
            $restored = Restore-CurrentRuntimeBridge -Names @(
                "kvtm_loader.exe", "kvtm_bridge.dll"
            ) -Destination (Join-Path $PatchSource "bin") -Label "Capture bridge"
        }
        if (-not $restored) {
            throw "ClientJS capture bridge build failed; exit=$buildExit. Install Visual Studio C++ x86/x64 Build Tools."
        }
    }
    foreach ($file in @($loader, $bridge)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "Capture bridge build did not create: $file"
        }
        if ((Get-Item -LiteralPath $file).Length -lt 4096) {
            throw "Capture bridge binary is unexpectedly small: $file"
        }
    }
    Write-Host "ClientJS OpenGL capture bridge BUILD VERIFIED" -ForegroundColor Green
}

function Build-KvtmBridgeV3 {
    $control = Join-Path $BridgeV3Source "KVTM_BRIDGE_V3_CONTROL.bat"
    $source = Join-Path $BridgeV3Source "native\kvtm_bridge_v3.cpp"
    $loader = Join-Path $BridgeV3Source "bin\kvtm_loader_v3.exe"
    $bridge = Join-Path $BridgeV3Source "bin\kvtm_bridge_v3.dll"
    foreach ($file in @($control, $source)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "Missing Bridge V3 build input: $file"
        }
    }
    $sourceText = Get-Content -LiteralPath $source -Raw -Encoding UTF8
    foreach ($token in @("KVTM_BRIDGE_V3", "CAPTURE3", "NO_LAYOUT", "KvtmBridgeProtocol")) {
        if (-not $sourceText.Contains($token)) {
            throw "Bridge V3 source missing contract token '$token': $source"
        }
    }
    Write-Host "Building isolated Bridge V3 capture/input binary (x86)..." -ForegroundColor Cyan
    & cmd.exe /d /c ('"' + $control + '" build')
    $buildExit = $LASTEXITCODE
    if ($buildExit -ne 0) {
        $restored = $false
        if ($buildExit -eq 20) {
            $restored = Restore-CurrentRuntimeBridge -Names @(
                "kvtm_loader_v3.exe", "kvtm_bridge_v3.dll"
            ) -Destination (Join-Path $BridgeV3Source "bin") -Label "Bridge V3"
        }
        if (-not $restored) {
            throw "Bridge V3 build failed; exit=$buildExit."
        }
    }
    foreach ($file in @($loader, $bridge)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or
            (Get-Item -LiteralPath $file).Length -lt 4096) {
            throw "Bridge V3 build output invalid: $file"
        }
    }
    Write-Host "BRIDGE V3 BUILD VERIFIED" -ForegroundColor Green
}

Resolve-AutoProLfsRuntime
Build-ClientJsCaptureBridge
Build-KvtmBridgeV3

$DataCandidates = @()
$CurrentData = Join-Path $OutputRoot "data-dev"
if (Test-Path -LiteralPath $CurrentData -PathType Container) {
    $DataCandidates += $CurrentData
}
if (Test-Path -LiteralPath $DistRoot -PathType Container) {
    $DataCandidates += @(
        Get-ChildItem -LiteralPath $DistRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object {
                $_.FullName -ne $OutputRoot -and
                $_.Name -like "KVTM-ClientJS-Suite-Multi-*" -and
                (Test-Path -LiteralPath (Join-Path $_.FullName "data-dev") -PathType Container)
            } |
            Sort-Object LastWriteTime -Descending |
            ForEach-Object { Join-Path $_.FullName "data-dev" }
    )
}
$MainProfileDir = Join-Path $env:APPDATA "KVTM Multi"
if (Test-Path -LiteralPath $MainProfileDir -PathType Container) {
    $DataCandidates += $MainProfileDir
}

New-Item -ItemType Directory -Path $PreserveRoot -Force | Out-Null
foreach ($name in @("profiles.json", "settings.json")) {
    foreach ($candidate in $DataCandidates) {
        $source = Join-Path $candidate $name
        if (Test-Path -LiteralPath $source -PathType Leaf) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $PreserveRoot $name) -Force
            $PreservedFiles[$name] = $source
            break
        }
    }
}

# Preserve profile-owned workflow state/diagnostics only from the fixed DEV
# folder. Restoration happens after ZIP creation, so no private runtime data is
# shipped in the distributable archive.
$CurrentClearStall = Join-Path $CurrentData "clear-stall"
if (Test-Path -LiteralPath $CurrentClearStall -PathType Container) {
    $PreservedClearStallPath = Join-Path $PreserveRoot "clear-stall"
    Copy-PreservedDirectory -Source $CurrentClearStall -Destination $PreservedClearStallPath -Label "clear-stall"
    # Keep diagnostic runs only. Dọn quầy deliberately has no cross-cycle
    # carryover, so stale state/carryover files must not survive a rebuild.
    Get-ChildItem -LiteralPath $PreservedClearStallPath -Directory -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "state" } |
        Remove-Item -Recurse -Force -ErrorAction Stop
    Get-ChildItem -LiteralPath $PreservedClearStallPath -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "carryover.json" } |
        Remove-Item -Force -ErrorAction Stop
    $PreservedClearStall = $true
}
$CurrentClearStallProbe = Join-Path $CurrentData "clear-stall-probe"
if (Test-Path -LiteralPath $CurrentClearStallProbe -PathType Container) {
    $PreservedClearStallProbePath = Join-Path $PreserveRoot "clear-stall-probe"
    Copy-PreservedDirectory -Source $CurrentClearStallProbe -Destination $PreservedClearStallProbePath -Label "clear-stall-probe"
    $PreservedClearStallProbe = $true
}

$ClearStallWorker = Join-Path $ClientJsAutoSource "worker\clear_stall_worker.py"
$ClearStallProbe = Join-Path $ClientJsAutoSource "worker\clear_stall_live_probe.py"
$Step1Probe = Join-Path $ClientJsAutoSource "worker\clear_stall_step1_probe.py"
$CleanWorkflow = Join-Path $CleanAutoSource "workflows\clear_stall"

foreach ($required in @(
    (Join-Path $AutoSource "local_launcher.py"),
    (Join-Path $AutoSource "runtime\pyc\gui_base.pyc"),
    (Join-Path $AutoSource "runtime\pyc\gui.pyc"),
    (Join-Path $AutoSource "runtime\pyc\adb_controller.pyc"),
    (Join-Path $AutoSource "runtime\pyc\uiautomator2\__init__.pyc"),
    (Join-Path $AutoSource "_internal\cv2\cv2.pyd"),
    (Join-Path $MultiSource "kvtm_multi.py"),
    (Join-Path $MultiSource "kvtm_multi_entry.py"),
    (Join-Path $MultiSource "kvtm_multi_dev_entry.py"),
    (Join-Path $MultiSource "kvtm_multi_dev_host.py"),
    (Join-Path $MultiSource "clear_stall_designer.py"),
    (Join-Path $MultiSource "clear_stall_probe_console.py"),
    (Join-Path $PatchSource "clientjs_auto_patch.py"),
    (Join-Path $PatchSource "pc_driver.py"),
    (Join-Path $PatchSource "engine_driver.py"),
    (Join-Path $ClientJsAutoSource "catalog\functions.json"),
    (Join-Path $ClientJsAutoSource "worker\runtime_probe.py"),
    (Join-Path $ClientJsAutoSource "worker\bridge_v3_gesture_probe.py"),
    (Join-Path $ClientJsAutoSource "worker\speed_binding_probe.py"),
    (Join-Path $ClientJsAutoSource "worker\auto_worker.py"),
    (Join-Path $ClientJsAutoSource "worker\clean_worker_support.py"),
    $ClearStallWorker,
    $ClearStallProbe,
    $Step1Probe,
    (Join-Path $CleanAutoSource "automation.py"),
    (Join-Path $CleanAutoSource "context.py"),
    (Join-Path $CleanAutoSource "models.py"),
    (Join-Path $CleanAutoSource "runtime\bootstrap.py"),
    (Join-Path $CleanAutoSource "runtime\driver.py"),
    (Join-Path $CleanAutoSource "runtime\vision.py"),
    (Join-Path $CleanAutoSource "actions\popup.py"),
    (Join-Path $CleanAutoSource "actions\navigation.py"),
    (Join-Path $CleanAutoSource "actions\stall.py"),
    (Join-Path $CleanAutoSource "actions\buying.py"),
    (Join-Path $CleanAutoSource "actions\inventory.py"),
    (Join-Path $CleanAutoSource "actions\selling.py"),
    (Join-Path $CleanWorkflow "config.py"),
    (Join-Path $CleanWorkflow "designer_policy.py"),
    (Join-Path $CleanWorkflow "manifest.py"),
    (Join-Path $CleanWorkflow "state.py"),
    (Join-Path $CleanWorkflow "result.py"),
    (Join-Path $CleanWorkflow "workflow.py")
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Missing required repository file: $required"
    }
    if (Test-GitLfsPointer -Path $required) {
        throw "Required file is still a Git LFS pointer: $required"
    }
}
Assert-CleanClearStallWorker -Path $ClearStallWorker
Assert-CleanClearStallWorker -Path $ClearStallProbe

# Release only ClientJS processes proven to belong to this DEV runtime.
$BridgeInUse = Join-Path $OutputRoot "AUTO_PRO\bin\kvtm_bridge.dll"
$DevPids = New-Object "System.Collections.Generic.HashSet[int]"
$RunningMap = Join-Path $CurrentData "running_clients.json"
if (Test-Path -LiteralPath $RunningMap -PathType Leaf) {
    try {
        $MapData = Get-Content -LiteralPath $RunningMap -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($ClientEntry in @($MapData.clients)) {
            $MappedPid = 0
            if ([int]::TryParse([string]$ClientEntry.pid, [ref]$MappedPid)) {
                if ($MappedPid -gt 0) {
                    [void]$DevPids.Add($MappedPid)
                }
            }
        }
    } catch {
        Write-Host "[WARN] Khong doc duoc running_clients.json." -ForegroundColor Yellow
    }
}
foreach ($GameProcess in @(Get-Process -Name "GameClientJS" -ErrorAction SilentlyContinue)) {
    try {
        foreach ($LoadedModule in @($GameProcess.Modules)) {
            if ([string]::Equals(
                [string]$LoadedModule.FileName,
                [string]$BridgeInUse,
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
                [void]$DevPids.Add([int]$GameProcess.Id)
                break
            }
        }
    } catch {
        Write-Host "[WARN] Khong doc duoc module PID $($GameProcess.Id); khong tu dong dong." -ForegroundColor Yellow
    }
}
foreach ($DevProcessId in @($DevPids)) {
    $Candidate = Get-Process -Id $DevProcessId -ErrorAction SilentlyContinue
    if ($null -ne $Candidate) {
        if ($Candidate.ProcessName -eq "GameClientJS") {
            Write-Host "[DEV] Dong ClientJS DEV PID $DevProcessId de giai phong bridge..." -ForegroundColor Yellow
            Stop-Process -Id $DevProcessId -Force -ErrorAction Stop
        }
    }
}
if (Test-Path -LiteralPath $BridgeInUse -PathType Leaf) {
    $Released = $false
    for ($Attempt = 1; $Attempt -le 20; $Attempt++) {
        try {
            $Stream = [System.IO.File]::Open(
                $BridgeInUse,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None
            )
            $Stream.Dispose()
            $Released = $true
            break
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if (-not $Released) {
        throw "kvtm_bridge.dll van bi khoa; hay dong worker Multi DEV con an"
    }
}

if (Test-Path -LiteralPath $OutputRoot) {
    Remove-Item -LiteralPath $OutputRoot -Recurse -Force
}

$AutoOut = Join-Path $OutputRoot "AUTO_PRO"
$MultiOut = Join-Path $OutputRoot "Multi"
New-Item -ItemType Directory -Path $AutoOut, $MultiOut -Force | Out-Null
Copy-Item -Path (Join-Path $AutoSource "*") -Destination $AutoOut -Recurse -Force
Copy-Item -Path (Join-Path $MultiSource "*") -Destination $MultiOut -Recurse -Force
Sync-PackagedPythonRuntime -AutoRoot $AutoOut

# AUTO reference contains the legacy frame-lock bridge. Always overlay the
# freshly built CAPTURE1/KCAP bridge so Workspace and AUTO share frames by PID.
$BridgeOut = Join-Path $AutoOut "bin"
New-Item -ItemType Directory -Path $BridgeOut -Force | Out-Null
foreach ($name in @("kvtm_loader.exe", "kvtm_bridge.dll")) {
    Copy-Item -LiteralPath (Join-Path $PatchSource ("bin\" + $name)) -Destination (Join-Path $BridgeOut $name) -Force
}
foreach ($name in @("kvtm_loader_v3.exe", "kvtm_bridge_v3.dll")) {
    Copy-Item -LiteralPath (Join-Path $BridgeV3Source ("bin\" + $name)) -Destination (Join-Path $BridgeOut $name) -Force
}

$packagedPointers = @(Get-GitLfsPointers -Root $AutoOut)
if ($packagedPointers.Count -gt 0) {
    $sample = ($packagedPointers | Select-Object -First 12 | ForEach-Object { $_.FullName }) -join "`n  - "
    throw (
        "Package blocked: AUTO_PRO output still contains {0} Git LFS pointers.`n  - {1}" -f
        $packagedPointers.Count, $sample
    )
}

$PatchFiles = @(
    "adaptive_cv.py",
    "BUILD_X86.bat",
    "clientjs_auto_patch.py",
    "engine_driver.py",
    "pc_auto_engine_launcher.py",
    "pc_auto_launcher.py",
    "pc_driver.py",
    "RUN_ENGINE_AUTO.bat"
)
foreach ($name in $PatchFiles) {
    $source = Join-Path $PatchSource $name
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Missing ClientJS adapter file: $source"
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $AutoOut $name) -Force
}

$ComponentsOut = Join-Path $OutputRoot "components"
$ClientJsAutoOut = Join-Path $ComponentsOut "clientjs-auto"
New-Item -ItemType Directory -Path $ClientJsAutoOut -Force | Out-Null
Copy-Item -Path (Join-Path $ClientJsAutoSource "*") -Destination $ClientJsAutoOut -Recurse -Force

$NativeOut = Join-Path $AutoOut "native"
New-Item -ItemType Directory -Path $NativeOut -Force | Out-Null
Copy-Item -Path (Join-Path $PatchSource "native\*") -Destination $NativeOut -Force

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "README.txt") -Destination $OutputRoot
foreach ($name in @("01_BUILD_BRIDGE.bat", "02_START_MULTI.bat", "02_START_MULTI_DEV.bat", "START_MULTI_DEV_SILENT.ps1", "03_START_AUTO.bat", "04_BUILD_MULTI_EXE.bat", "05_IMPORT_PROFILES_TO_DEV.ps1")) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination $OutputRoot
}
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

$PackagedClean = Join-Path $ClientJsAutoOut "kvtm_automation"
$checks = @(
    (Join-Path $AutoOut "runtime\pyc\gui_base.pyc"),
    (Join-Path $AutoOut "runtime\pyc\gui.pyc"),
    (Join-Path $AutoOut "runtime\pyc\adb_controller.pyc"),
    (Join-Path $AutoOut "runtime\pyc\uiautomator2\__init__.pyc"),
    (Join-Path $AutoOut "_internal\cv2\cv2.pyd"),
    (Join-Path $AutoOut "clientjs_auto_patch.py"),
    (Join-Path $AutoOut "pc_driver.py"),
    (Join-Path $AutoOut "engine_driver.py"),
    (Join-Path $AutoOut "bin\kvtm_loader.exe"),
    (Join-Path $AutoOut "bin\kvtm_bridge.dll"),
    (Join-Path $AutoOut "bin\kvtm_loader_v3.exe"),
    (Join-Path $AutoOut "bin\kvtm_bridge_v3.dll"),
    (Join-Path $MultiOut "kvtm_multi.py"),
    (Join-Path $MultiOut "kvtm_multi_entry.py"),
    (Join-Path $MultiOut "kvtm_multi_dev_entry.py"),
    (Join-Path $MultiOut "kvtm_multi_dev_host.py"),
    (Join-Path $MultiOut "clear_stall_probe_console.py"),
    (Join-Path $ClientJsAutoOut "catalog\functions.json"),
    (Join-Path $ClientJsAutoOut "worker\runtime_probe.py"),
    (Join-Path $ClientJsAutoOut "worker\bridge_v3_gesture_probe.py"),
    (Join-Path $ClientJsAutoOut "worker\speed_binding_probe.py"),
    (Join-Path $ClientJsAutoOut "worker\auto_worker.py"),
    (Join-Path $ClientJsAutoOut "worker\clean_worker_support.py"),
    (Join-Path $ClientJsAutoOut "worker\clear_stall_worker.py"),
    (Join-Path $ClientJsAutoOut "worker\clear_stall_live_probe.py"),
    (Join-Path $ClientJsAutoOut "worker\clear_stall_step1_probe.py"),
    (Join-Path $PackagedClean "automation.py"),
    (Join-Path $PackagedClean "runtime\bootstrap.py"),
    (Join-Path $PackagedClean "actions\navigation.py"),
    (Join-Path $PackagedClean "actions\stall.py"),
    (Join-Path $PackagedClean "workflows\clear_stall\manifest.py"),
    (Join-Path $PackagedClean "workflows\clear_stall\state.py"),
    (Join-Path $PackagedClean "workflows\clear_stall\workflow.py")
)
foreach ($file in $checks) {
    if (-not (Test-Path -LiteralPath $file)) {
        throw "Incomplete package: $file"
    }
    if (Test-GitLfsPointer -Path $file) {
        throw "Package contains Git LFS pointer instead of real data: $file"
    }
}
Assert-CleanClearStallWorker -Path (Join-Path $ClientJsAutoOut "worker\clear_stall_worker.py")
Assert-CleanClearStallWorker -Path (Join-Path $ClientJsAutoOut "worker\clear_stall_live_probe.py")

$head = (& git -C $RepoRoot rev-parse HEAD 2>$null | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($head)) {
    throw "Cannot determine repository HEAD for package stamp."
}
[System.IO.File]::WriteAllText(
    (Join-Path $OutputRoot ".source-head.txt"),
    ($head.Trim() + "`n"),
    [System.Text.Encoding]::ASCII
)

$ZipPath = "$OutputRoot.zip"
if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -LiteralPath $OutputRoot -DestinationPath $ZipPath -CompressionLevel Optimal

$DevDataOut = Join-Path $OutputRoot "data-dev"
New-Item -ItemType Directory -Path $DevDataOut -Force | Out-Null
foreach ($name in @("profiles.json", "settings.json")) {
    $preserved = Join-Path $PreserveRoot $name
    if (Test-Path -LiteralPath $preserved -PathType Leaf) {
        Copy-Item -LiteralPath $preserved -Destination (Join-Path $DevDataOut $name) -Force
    }
}
if ($PreservedClearStall) {
    Copy-Item -LiteralPath (Join-Path $PreserveRoot "clear-stall") -Destination (Join-Path $DevDataOut "clear-stall") -Recurse -Force
}
if ($PreservedClearStallProbe) {
    Copy-Item -LiteralPath (Join-Path $PreserveRoot "clear-stall-probe") -Destination (Join-Path $DevDataOut "clear-stall-probe") -Recurse -Force
}
Remove-Item -LiteralPath $PreserveRoot -Recurse -Force

Write-Host "PACKAGE OK" -ForegroundColor Green
Write-Host "Folder: $OutputRoot"
Write-Host "ZIP:    $ZipPath"
Write-Host "SOURCE HEAD: $($head.Trim())" -ForegroundColor Cyan
Write-Host "Legacy AUTO PRO runtime kept only for other suite features/reference." -ForegroundColor DarkGray
Write-Host "Dọn quầy CLEAN VERIFIED: no legacy pyc execution dependency" -ForegroundColor Green
Write-Host "Dọn quầy CLEAN VERIFIED: dynamic capacity + x10 remaining counter + serialized queue" -ForegroundColor Green
if ($PreservedFiles.Count -gt 0) {
    foreach ($name in $PreservedFiles.Keys) {
        Write-Host ("DATA KEPT: {0} <- {1}" -f $name, $PreservedFiles[$name]) -ForegroundColor Cyan
    }
} else {
    Write-Host "DATA: no existing profile/settings found; data-dev created empty" -ForegroundColor Yellow
}
if ($PreservedClearStall) {
    Write-Host "DATA KEPT: clear-stall diagnostic runs only; carryover purged" -ForegroundColor Cyan
}
if ($PreservedClearStallProbe) {
    Write-Host "DATA KEPT: clear-stall-probe screenshots/reports" -ForegroundColor Cyan
}
Write-Host "FIXED DEV: use this same folder for every build" -ForegroundColor Cyan
