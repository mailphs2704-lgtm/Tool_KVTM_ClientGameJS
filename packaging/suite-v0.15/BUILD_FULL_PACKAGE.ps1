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
    if ($LASTEXITCODE -ne 0) {
        throw "ClientJS capture bridge build failed; exit=$LASTEXITCODE. Install Visual Studio C++ x86/x64 Build Tools."
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
    if ($LASTEXITCODE -ne 0) {
        throw "Bridge V3 build failed; exit=$LASTEXITCODE."
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
    Copy-Item -LiteralPath $CurrentClearStall -Destination $PreservedClearStallPath -Recurse -Force
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
    Copy-Item -LiteralPath $CurrentClearStallProbe -Destination $PreservedClearStallProbePath -Recurse -Force
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

if (Test-Path -LiteralPath $OutputRoot) {
    Remove-Item -LiteralPath $OutputRoot -Recurse -Force
}

$AutoOut = Join-Path $OutputRoot "AUTO_PRO"
$MultiOut = Join-Path $OutputRoot "Multi"
New-Item -ItemType Directory -Path $AutoOut, $MultiOut -Force | Out-Null
Copy-Item -Path (Join-Path $AutoSource "*") -Destination $AutoOut -Recurse -Force
Copy-Item -Path (Join-Path $MultiSource "*") -Destination $MultiOut -Recurse -Force

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
