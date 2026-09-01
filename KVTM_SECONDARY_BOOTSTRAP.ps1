param(
    [string]$TargetDirectory = (Join-Path ([Environment]::GetFolderPath("Desktop")) "Tool_KVTM_Multi_DEV"),
    [switch]$BuildRuntime,
    [switch]$OpenZingPlayPage
)

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/mailphs2704-lgtm/Tool_KVTM_ClientGameJS.git"
$Branch = "develop/multi-auto-dev"
$GitHubUser = "mailphs2704-lgtm"

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
    $candidates = @()
    if ($env:ProgramFiles) { $candidates += (Join-Path $env:ProgramFiles "Git\cmd\git.exe") }
    if (${env:ProgramFiles(x86)}) { $candidates += (Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe") }
    foreach ($path in $candidates) {
        if (Test-Path -LiteralPath $path -PathType Leaf) { return $path }
    }
    return $null
}

function Refresh-ProcessPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (($machine, $user) -join ";")
}

function Test-GitLfs {
    param([string]$Git)
    if (-not $Git) { return $false }
    try {
        & $Git lfs version *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch { return $false }
}

function Test-GitCredentialManager {
    param([string]$Git)
    if (-not $Git) { return $false }
    try {
        & $Git credential-manager --version *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch { return $false }
}

function Configure-GitHubAuth {
    param([string]$Git)
    if (-not (Test-GitCredentialManager $Git)) {
        throw "Git Credential Manager khong san sang. Hay cap nhat/cai lai Git for Windows moi nhat."
    }

    Write-Host "[AUTH] Cau hinh Git Credential Manager + GitHub browser OAuth..." -ForegroundColor Cyan
    & $Git credential-manager configure
    if ($LASTEXITCODE -ne 0) { throw "git credential-manager configure fail" }

    & $Git config --global credential.helper manager
    if ($LASTEXITCODE -ne 0) { throw "Khong cau hinh duoc credential.helper=manager" }
    & $Git config --global credential.gitHubAuthModes browser
    if ($LASTEXITCODE -ne 0) { throw "Khong cau hinh duoc GitHub browser auth mode" }
    & $Git config --global credential.https://github.com.username $GitHubUser
    if ($LASTEXITCODE -ne 0) { throw "Khong ghim duoc GitHub username" }

    Write-Host "[AUTH] Dang nhap GitHub bang trinh duyet. Khong nhap password GitHub vao console." -ForegroundColor Yellow
    & $Git credential-manager github login
    if ($LASTEXITCODE -ne 0) { throw "GitHub browser login qua Git Credential Manager fail." }

    Write-Host "[AUTH] Xac minh quyen doc private repo..." -ForegroundColor Cyan
    & $Git ls-remote --exit-code $RepoUrl ("refs/heads/" + $Branch) *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub auth xong nhung chua doc duoc repo/branch. Kiem tra dung account $GitHubUser co quyen repo."
    }
    Write-Host "[AUTH] GitHub private repo access READY." -ForegroundColor Green
}

function Install-WingetPackage {
    param([string]$Winget, [string]$Id, [string]$Label, [string]$Architecture = "")
    Write-Host "[INSTALL] $Label ($Id)..." -ForegroundColor Cyan
    $args = @("install", "--id", $Id, "--exact", "--source", "winget", "--accept-package-agreements", "--accept-source-agreements", "--silent")
    if ($Architecture) { $args += @("--architecture", $Architecture) }
    & $Winget @args
    if ($LASTEXITCODE -ne 0) { throw "WinGet cai $Label fail, exit=$LASTEXITCODE" }
    Refresh-ProcessPath
}

if ($env:OS -ne "Windows_NT" -or -not [Environment]::Is64BitOperatingSystem) {
    throw "Can Windows x64."
}

$winget = Resolve-Winget
if (-not $winget) {
    Write-Host "[BLOCK] Khong tim thay WinGet / Microsoft App Installer." -ForegroundColor Red
    Write-Host "Dang mo Microsoft Store den App Installer..." -ForegroundColor Yellow
    try { Start-Process "ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1" } catch { }
    throw "Cai/cap nhat Microsoft App Installer, sau do chay lai bootstrap."
}

Write-Host "=== KVTM SECONDARY MACHINE BOOTSTRAP ===" -ForegroundColor Cyan
Write-Host "Target: $TargetDirectory"
Write-Host "Branch: $Branch"

# Git and Git LFS must exist BEFORE clone/checkout on a blank machine.
$git = Resolve-Git
if (-not $git) {
    Write-Host "[1/7] Cai Git for Windows..."
    Install-WingetPackage $winget "Git.Git" "Git for Windows" "x64"
    $git = Resolve-Git
}
if (-not $git) { throw "Da cai Git nhung chua tim thay git.exe. Mo PowerShell moi va chay lai." }

Write-Host "[2/7] Kiem tra Git LFS truoc khi clone..."
if (-not (Test-GitLfs $git)) {
    Install-WingetPackage $winget "GitHub.GitLFS" "Git LFS"
    $git = Resolve-Git
}
if (-not (Test-GitLfs $git)) { throw "Git LFS chua san sang sau khi cai." }
& $git lfs install
if ($LASTEXITCODE -ne 0) { throw "git lfs install fail" }

Write-Host "[3/7] GitHub private-repo authentication..."
Configure-GitHubAuth $git

Write-Host "[4/7] Chuan bi repository dung branch..."
$previousSkipSmudge = $env:GIT_LFS_SKIP_SMUDGE
$env:GIT_LFS_SKIP_SMUDGE = "1"
try {
    if (Test-Path -LiteralPath (Join-Path $TargetDirectory ".git")) {
        [object[]]$dirty = @(& $git -C $TargetDirectory status --porcelain)
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
            [object[]]$items = @(Get-ChildItem -LiteralPath $TargetDirectory -Force -ErrorAction SilentlyContinue)
            if ($items.Count -gt 0) { throw "Thu muc dich da ton tai va khong rong: $TargetDirectory" }
        }
        else {
            New-Item -ItemType Directory -Path (Split-Path -Parent $TargetDirectory) -Force | Out-Null
        }
        & $git clone --branch $Branch --single-branch $RepoUrl $TargetDirectory
        if ($LASTEXITCODE -ne 0) { throw "git clone fail sau khi GitHub auth da READY." }
    }
}
finally {
    $env:GIT_LFS_SKIP_SMUDGE = $previousSkipSmudge
}

Write-Host "[5/7] Cai/kiem tra dependency bang diagnostic chinh..."
$setup = Join-Path $TargetDirectory "tools\KVTM_MACHINE_SETUP.ps1"
if (-not (Test-Path -LiteralPath $setup -PathType Leaf)) { throw "Thieu $setup" }
$setupArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $setup, "-InstallMissing")
if ($OpenZingPlayPage) { $setupArgs += "-OpenZingPlayPage" }
& powershell.exe @setupArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Diagnostic/install tra ve exit=$LASTEXITCODE; van tiep tuc kiem tra thanh phan da cai." -ForegroundColor Yellow
}
Refresh-ProcessPath
$git = Resolve-Git
if (-not $git) { throw "Khong tim thay git.exe sau setup." }

Write-Host "[6/7] Materialize Git LFS..."
if (-not (Test-GitLfs $git)) { throw "Git LFS bi mat sau setup." }
& $git lfs install
if ($LASTEXITCODE -ne 0) { throw "git lfs install fail" }
& $git -C $TargetDirectory lfs pull
if ($LASTEXITCODE -ne 0) { throw "git lfs pull fail" }

if ($BuildRuntime) {
    Write-Host "[7/7] Build DEV runtime..."
    $builder = Join-Path $TargetDirectory "packaging\suite-v0.15\BUILD_FULL_PACKAGE.ps1"
    if (-not (Test-Path -LiteralPath $builder -PathType Leaf)) { throw "Thieu builder: $builder" }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $builder
    if ($LASTEXITCODE -ne 0) { throw "BUILD_FULL_PACKAGE fail" }
}
else {
    Write-Host "[7/7] Build DEV runtime: SKIPPED (khong co -BuildRuntime)"
}

Write-Host ""
Write-Host "=== FINAL MACHINE DIAGNOSTIC ===" -ForegroundColor Cyan
$finalArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $setup)
if ($OpenZingPlayPage) { $finalArgs += "-OpenZingPlayPage" }
& powershell.exe @finalArgs
$diagExit = $LASTEXITCODE

Write-Host ""
Write-Host "BOOTSTRAP SOURCE COMPLETE" -ForegroundColor Green
Write-Host "Repo: $TargetDirectory"
Write-Host "Branch: $Branch"
if ($diagExit -eq 0) {
    Write-Host "Environment diagnostic: READY" -ForegroundColor Green
}
else {
    Write-Host "Environment diagnostic: NOT_READY/PARTIAL - thuong la ZingPlay/game data chua cai." -ForegroundColor Yellow
}
Write-Host "Buoc tiep theo: cai/mo Sky Garden neu diagnostic bao thieu; sau do import file .kvtm bang KVTM_MACHINE_TRANSFER_CONTROL.bat." -ForegroundColor Cyan
