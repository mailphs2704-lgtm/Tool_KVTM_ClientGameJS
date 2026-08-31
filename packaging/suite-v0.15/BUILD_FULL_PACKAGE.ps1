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

    Write-Host ("Git LFS: phát hiện {0} runtime pointer, đang lấy object thật..." -f $pointers.Count) -ForegroundColor Yellow

    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if ($null -eq $gitCommand) {
        throw "Runtime AUTO PRO còn Git LFS pointer nhưng máy không có git để tự phục hồi."
    }

    Push-Location $RepoRoot
    try {
        & git lfs version | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Git LFS chưa sẵn sàng."
        }
        & git lfs pull
        if ($LASTEXITCODE -ne 0) {
            throw "git lfs pull thất bại."
        }
    }
    finally {
        Pop-Location
    }

    $remaining = @(Get-GitLfsPointers -Root $AutoSource)
    if ($remaining.Count -gt 0) {
        $sample = ($remaining | Select-Object -First 12 | ForEach-Object { $_.FullName }) -join "`n  - "
        throw (
            "Không thể đóng gói: còn {0} Git LFS pointer trong AUTO PRO runtime.`n  - {1}" -f
            $remaining.Count, $sample
        )
    }

    Write-Host "Git LFS runtime VERIFIED: toàn bộ pointer đã được thay bằng object thật" -ForegroundColor Green
}

# The recovered AUTO PRO runtime is intentionally tracked with Git LFS. Never
# allow a 128-byte pointer text file to be copied into a distributable package.
Resolve-AutoProLfsRuntime

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
    (Join-Path $AutoSource "runtime\pyc\uiautomator2\__init__.pyc"),
    (Join-Path $AutoSource "_internal\cv2\cv2.pyd"),
    (Join-Path $MultiSource "kvtm_multi.py"),
    (Join-Path $MultiSource "kvtm_multi_entry.py"),
    (Join-Path $PatchSource "clientjs_auto_patch.py"),
    (Join-Path $ClientJsAutoSource "catalog\functions.json"),
    (Join-Path $ClientJsAutoSource "worker\runtime_probe.py"),
    (Join-Path $ClientJsAutoSource "worker\auto_worker.py"),
    (Join-Path $ClientJsAutoSource "worker\clear_stall_worker.py"),
    (Join-Path $ClientJsAutoSource "workflows\clear_stall\manifest.py"),
    (Join-Path $ClientJsAutoSource "workflows\clear_stall\workflow.py")
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Thieu file bat buoc trong repo: $required"
    }
    if (Test-GitLfsPointer -Path $required) {
        throw "File bắt buộc vẫn là Git LFS pointer, không phải runtime thật: $required"
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

$packagedPointers = @(Get-GitLfsPointers -Root $AutoOut)
if ($packagedPointers.Count -gt 0) {
    $sample = ($packagedPointers | Select-Object -First 12 | ForEach-Object { $_.FullName }) -join "`n  - "
    throw (
        "Đóng gói bị chặn: AUTO_PRO output còn {0} Git LFS pointer.`n  - {1}" -f
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
    (Join-Path $AutoOut "runtime\pyc\uiautomator2\__init__.pyc"),
    (Join-Path $AutoOut "_internal\cv2\cv2.pyd"),
    (Join-Path $AutoOut "clientjs_auto_patch.py"),
    (Join-Path $MultiOut "kvtm_multi.py"),
    (Join-Path $MultiOut "kvtm_multi_entry.py"),
    (Join-Path $ClientJsAutoOut "catalog\functions.json"),
    (Join-Path $ClientJsAutoOut "worker\runtime_probe.py"),
    (Join-Path $ClientJsAutoOut "worker\auto_worker.py"),
    (Join-Path $ClientJsAutoOut "worker\clear_stall_worker.py"),
    (Join-Path $ClientJsAutoOut "workflows\clear_stall\manifest.py"),
    (Join-Path $ClientJsAutoOut "workflows\clear_stall\workflow.py")
)
foreach ($file in $checks) {
    if (-not (Test-Path -LiteralPath $file)) {
        throw "Dong goi khong day du: $file"
    }
    if (Test-GitLfsPointer -Path $file) {
        throw "Dong goi chứa Git LFS pointer thay vì dữ liệu thật: $file"
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
Write-Host "runtime/pyc VERIFIED: real LFS objects, not pointer text" -ForegroundColor Green
Write-Host "clear_stall VERIFIED: entrypoint, worker, manifest, workflow" -ForegroundColor Green
if ($PreservedFiles.Count -gt 0) {
    foreach ($name in $PreservedFiles.Keys) {
        Write-Host ("DATA KEPT: {0} <- {1}" -f $name, $PreservedFiles[$name]) -ForegroundColor Cyan
    }
} else {
    Write-Host "DATA: no existing profile/settings found; data-dev created empty" -ForegroundColor Yellow
}
Write-Host "FIXED DEV: use this same folder for every build" -ForegroundColor Cyan
