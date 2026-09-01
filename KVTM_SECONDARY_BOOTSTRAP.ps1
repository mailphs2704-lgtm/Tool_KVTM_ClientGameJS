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

function Install-Package {
    param([string]$Winget, [string]$Id, [string]$Arch = "")
    $args = @("install", "--id", $Id, "--exact", "--source", "winget", "--accept-package-agreements", "--accept-source-agreements", "--silent")
    if ($Arch) { $args += @("--architecture", $Arch) }
    & $Winget @args
    if ($LASTEXITCODE -ne 0) { throw "WinGet install fail: $Id exit=$LASTEXITCODE" }
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
    Install-Package $winget "Git.Git" "x64"
    $git = Resolve-Git
}
if (-not $git) { throw "Da cai Git nhung chua tim thay git.exe. Mo PowerShell moi va chay lai." }

Write-Host "[2/5] Dam bao Git LFS / Python / VC++..."
try { & $git lfs version *> $null } catch { }
if ($LASTEXITCODE -ne 0) { Install-Package $winget "GitHub.GitLFS" }
Install-Package $winget "Python.Python.3.11" "x64"
Install-Package $winget "Microsoft.VCRedist.2015+.x64" "x64"
Install-Package $winget "Microsoft.VCRedist.2015+.x86" "x86"
try { & $git lfs install | Out-Null } catch { }

Write-Host "[3/5] Chuan bi repository..."
if (Test-Path -LiteralPath (Join-Path $TargetDirectory ".git")) {
    $dirty = @(& $git -C $TargetDirectory status --porcelain)
    if ($dirty.Count -gt 0) { throw "Repo may phu co thay doi chua commit. Khong pull de tranh ghi de: $TargetDirectory" }
    $current = (& $git -C $TargetDirectory branch --show-current | Select-Object -First 1)
    if ($current -ne $Branch) {
        & $git -C $TargetDirectory fetch origin $Branch
        if ($LASTEXITCODE -ne 0) { throw "git fetch fail" }
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

Write-Host "[4/5] Tai Git LFS..."
& $git -C $TargetDirectory lfs pull
if ($LASTEXITCODE -ne 0) { throw "git lfs pull fail" }

$setup = Join-Path $TargetDirectory "tools\KVTM_MACHINE_SETUP.ps1"
if (-not (Test-Path -LiteralPath $setup -PathType Leaf)) { throw "Thieu $setup" }
Write-Host "[5/5] Chay diagnostic sau cai dat..."
$setupArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $setup, "-InstallMissing")
if ($OpenZingPlayPage) { $setupArgs += "-OpenZingPlayPage" }
& powershell.exe @setupArgs

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
Write-Host "Buoc tiep theo: cai/mo Sky Garden neu diagnostic bao thieu, build runtime neu chua build, sau do import file .kvtm bang Control Center." -ForegroundColor Cyan
