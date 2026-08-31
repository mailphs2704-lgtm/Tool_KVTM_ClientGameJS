param(
    [string]$OutputName = "KVTM-ClientJS-Suite-Multi-DEV"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$AutoSource = Join-Path $RepoRoot "source-archive\auto-pro-reference"
$MultiSource = Join-Path $RepoRoot "source-archive\multi-current\kvtm_multi_tool"
$PatchSource = Join-Path $RepoRoot "test-candidates\auto-pro-clientjs-temp"
$ClientJsAutoSource = Join-Path $RepoRoot "components\clientjs-auto"
$DistRoot = Join-Path $RepoRoot "dist"
$OutputRoot = Join-Path $DistRoot $OutputName
$PreserveRoot = Join-Path $DistRoot (".kvtm-dev-data-" + [guid]::NewGuid().ToString("N"))
$PreservedFiles = @{}
New-Item -ItemType Directory -Path $DistRoot -Force | Out-Null

# Preserve isolated DEV data before replacing the fixed package. Prefer the
# current fixed folder, then the newest older DEV package, then APPDATA.
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

foreach ($required in @(
    (Join-Path $AutoSource "local_launcher.py"),
    (Join-Path $AutoSource "runtime\pyc\gui_base.pyc"),
    (Join-Path $AutoSource "runtime\pyc\gui.pyc"),
    (Join-Path $AutoSource "runtime\pyc\adb_controller.pyc"),
    (Join-Path $MultiSource "kvtm_multi.py"),
    (Join-Path $PatchSource "clientjs_auto_patch.py"),
    (Join-Path $ClientJsAutoSource "catalog\functions.json"),
    (Join-Path $ClientJsAutoSource "worker\runtime_probe.py"),
    (Join-Path $ClientJsAutoSource "worker\auto_worker.py")
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Thieu file bat buoc trong repo: $required"
    }
}

if (Test-Path -LiteralPath $OutputRoot) {
    Remove-Item -LiteralPath $OutputRoot -Recurse -Force
}

$AutoOut = Join-Path $OutputRoot "AUTO_PRO"
$MultiOut = Join-Path $OutputRoot "Multi"
New-Item -ItemType Directory -Path $AutoOut, $MultiOut -Force | Out-Null

# Copy the complete recovered runtime. Do not exclude *.pyc: these files are
# the actual AUTO PRO source modules, not disposable cache files.
Copy-Item -Path (Join-Path $AutoSource "*") -Destination $AutoOut -Recurse -Force
Copy-Item -Path (Join-Path $MultiSource "*") -Destination $MultiOut -Recurse -Force

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
        throw "Thieu file adapter ClientJS: $source"
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
foreach ($name in @("01_BUILD_BRIDGE.bat", "02_START_MULTI.bat", "02_START_MULTI_DEV.bat", "03_START_AUTO.bat", "04_BUILD_MULTI_EXE.bat", "05_IMPORT_PROFILES_TO_DEV.ps1")) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination $OutputRoot
}

$checks = @(
    (Join-Path $AutoOut "runtime\pyc\gui_base.pyc"),
    (Join-Path $AutoOut "runtime\pyc\gui.pyc"),
    (Join-Path $AutoOut "runtime\pyc\adb_controller.pyc"),
    (Join-Path $AutoOut "_internal\cv2\cv2.pyd"),
    (Join-Path $AutoOut "clientjs_auto_patch.py"),
    (Join-Path $MultiOut "kvtm_multi.py"),
    (Join-Path $ClientJsAutoOut "catalog\functions.json"),
    (Join-Path $ClientJsAutoOut "worker\runtime_probe.py"),
    (Join-Path $ClientJsAutoOut "worker\auto_worker.py")
)
foreach ($file in $checks) {
    if (-not (Test-Path -LiteralPath $file)) {
        throw "Dong goi khong day du: $file"
    }
}

$ZipPath = "$OutputRoot.zip"
if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -LiteralPath $OutputRoot -DestinationPath $ZipPath -CompressionLevel Optimal

# Restore local account data only after ZIP creation so login/profile data is
# never embedded in the distributable archive.
$DevDataOut = Join-Path $OutputRoot "data-dev"
New-Item -ItemType Directory -Path $DevDataOut -Force | Out-Null
foreach ($name in @("profiles.json", "settings.json")) {
    $preserved = Join-Path $PreserveRoot $name
    if (Test-Path -LiteralPath $preserved -PathType Leaf) {
        Copy-Item -LiteralPath $preserved -Destination (Join-Path $DevDataOut $name) -Force
    }
}
Remove-Item -LiteralPath $PreserveRoot -Recurse -Force

Write-Host "PACKAGE OK" -ForegroundColor Green
Write-Host "Folder: $OutputRoot"
Write-Host "ZIP:    $ZipPath"
Write-Host "runtime/pyc VERIFIED: gui_base.pyc, gui.pyc, adb_controller.pyc"
if ($PreservedFiles.Count -gt 0) {
    foreach ($name in $PreservedFiles.Keys) {
        Write-Host ("DATA KEPT: {0} <- {1}" -f $name, $PreservedFiles[$name]) -ForegroundColor Cyan
    }
} else {
    Write-Host "DATA: no existing profile/settings found; data-dev created empty" -ForegroundColor Yellow
}
Write-Host "FIXED DEV: use this same folder for every build" -ForegroundColor Cyan
