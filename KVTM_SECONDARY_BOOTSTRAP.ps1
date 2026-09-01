param(
    [string]$TargetDirectory = (Join-Path ([Environment]::GetFolderPath("Desktop")) "Tool_KVTM_Multi_DEV"),
    [switch]$BuildRuntime,
    [switch]$OpenZingPlayPage
)

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/mailphs2704-lgtm/Tool_KVTM_ClientGameJS.git"
$Branch = "develop/multi-auto-dev"

function Resolve-Winget {
    $cmd = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    $path = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\winget.exe"
    if (Test-Path -LiteralPath $path -PathType Leaf) { return $path }
    return $null
}

function Resolve-Git {
    $cmd = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    $path = Join-Path $env:ProgramFiles "Git\cmd\git.exe"
    if (Test-Path -LiteralPath $path -PathType Leaf) { return $path }
    return $null
}

function Refresh-ProcessPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (($machine, $user) -join ";")
}

if ($env:OS -ne "Windows_NT" -or -not [Environment]::Is64BitOperatingSystem) {
    throw "Can Windows x64."
}

$winget = Resolve-Winget
if (-not $winget) {
    throw "Khong tim thay WinGet. Hay cai Microsoft App Installer tu Microsoft Store, sau do chay lai file nay."
}

Write-Host "=== KVTM SECONDARY MACHINE BOOTSTRAP ===" -ForegroundColor Cyan
$git = Resolve-Git
if (-not $git) {
    Write-Host "[1/5] Cai Git for Windows..."
    & $winget install --id Git.Git --exact --source winget --architecture x64 --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) { throw "WinGet cai Git fail, exit=$LASTEXITCODE" }
    Refresh-ProcessPath
    $git = Resolve-Git
}
if (-not $git) { throw "Da cai Git nhung chua tim thay git.exe. Mo PowerShell moi va chay lai." }

Write-Host "[2/5] Chuan bi repository dung branch..."
$previousSkipSmudge = $env:GIT_LFS_SKIP_SMUDGE
$env:GIT_LFS_SKIP_SMUDGE = "1"
try {
    if (Test-Path -LiteralPath (Join-Path $TargetDirectory ".git")) {
        $dirty = @(& $git -C $TargetDirectory status --porcelain)
        if ($dirty.Count -gt 0) { throw "Repo may phu co thay doi chua commit. Khong pull de tranh ghi de: $TargetDirectory" }
        & $git -C $TargetDirectory fetch origin $Branch
        if ($LASTEXITCODE -ne 0) { throw "git fetch fail" }
        $current = (& $git -C $TargetDirectory branch --show-current | Select-Object -First 1)
        if ($current -ne $Branch) {
            & $git -C $TargetDirectory checkout $Branch
            if ($LASTEXITCODE -ne 0) { throw "git checkout $Branch fail" }
        }
        & $git -C $TargetDirectory pull --ff-only origin $Branch
        if ($LASTEXITCODE -ne 0) { throw "git pull --ff-only fail" }
    }
    else {
        if (Test-Path -LiteralPath $TargetDirectory) {
            $items = @(Get-ChildItem -LiteralPath $TargetDirectory -Force -ErrorAction SilentlyContinue)
            if ($items.Count -gt 0) { throw "Thu muc dich da ton tai va khong rong: $TargetDirectory" }
        }
        else { New-Item -ItemType Directory -Path (Split-Path -Parent $TargetDirectory) -Force | Out-Null }
        & $git clone --branch $Branch --single-branch $RepoUrl $TargetDirectory
        if ($LASTEXITCODE -ne 0) { throw "git clone fail. Repo private co the yeu cau dang nhap GitHub qua cua so trinh duyet." }
    }
}
finally {
    $env:GIT_LFS_SKIP_SMUDGE = $previousSkipSmudge
}

Write-Host "[3/5] Cai/kiem tra dependency bang diagnostic chinh..."
$setup = Join-Path $TargetDirectory "tools\KVTM_MACHINE_SETUP.ps1"
if (-not (Test-Path -LiteralPath $setup -PathType Leaf)) { throw "Thieu $setup" }
$setupArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $setup, "-InstallMissing")
if ($OpenZingPlayPage) { $setupArgs += "-OpenZingPlayPage" }
& powershell.exe @setupArgs
Refresh-ProcessPath

Write-Host "[4/5] Git LFS materialize..."
$git = Resolve-Git
if (-not $git) { throw "Khong tim thay git.exe sau setup." }
& $git lfs install
if ($LASTEXITCODE -ne 0) { throw "git lfs install fail" }
& $git -C $TargetDirectory lfs pull
if ($LASTEXITCODE -ne 0) { throw "git lfs pull fail" }

Write-Host "[5/5] Final diagnostic..."
$finalArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $setup)
if ($OpenZingPlayPage) { $finalArgs += "-OpenZingPlayPage" }
& powershell.exe @finalArgs

if ($BuildRuntime) {
    $builder = Join-Path $TargetDirectory "packaging\suite-v0.15\BUILD_FULL_PACKAGE.ps1"
    if (-not (Test-Path -LiteralPath $builder -PathType Leaf)) { throw "Thieu builder: $builder" }
    Write-Host "[BUILD] Tao DEV runtime..." -ForegroundColor Cyan
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $builder
    if ($LASTEXITCODE -ne 0) { throw "BUILD_FULL_PACKAGE fail" }
}

Write-Host ""
Write-Host "BOOTSTRAP SOURCE COMPLETE" -ForegroundColor Green
Write-Host "Repo: $TargetDirectory"
Write-Host "Branch: $Branch"
Write-Host "Buoc tiep theo: cai/mo Sky Garden neu diagnostic bao thieu; sau do import file .kvtm bang KVTM_MACHINE_TRANSFER_CONTROL.bat." -ForegroundColor Cyan
