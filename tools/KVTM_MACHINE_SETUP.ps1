param(
    [switch]$InstallMissing,
    [switch]$OpenZingPlayPage
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ReportRoot = Join-Path $RepoRoot "data-machine-diagnostic"
New-Item -ItemType Directory -Path $ReportRoot -Force | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ReportPath = Join-Path $ReportRoot ("machine-diagnostic-" + $Stamp + ".txt")
$LatestPath = Join-Path $ReportRoot "LATEST.txt"
$ExpectedBranch = "develop/multi-auto-dev"
$Dist = Join-Path $RepoRoot "dist\KVTM-ClientJS-Suite-Multi-DEV"

function Resolve-Winget {
    $cmd = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    $candidate = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\winget.exe"
    if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    return $null
}

function Resolve-Git {
    $cmd = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    foreach ($candidate in @(
        (Join-Path $env:ProgramFiles "Git\cmd\git.exe"),
        (if (${env:ProgramFiles(x86)}) { Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe" })
    )) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) { return $candidate }
    }
    return $null
}

function Resolve-Python311 {
    $candidates = New-Object System.Collections.Generic.List[string]
    $known = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
    if (Test-Path -LiteralPath $known -PathType Leaf) { $candidates.Add($known) }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python -and $python.Source) { $candidates.Add($python.Source) }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py -and $py.Source) {
        try {
            $resolved = (& $py.Source -3.11 -c "import sys;print(sys.executable)" 2>$null | Select-Object -First 1)
            if ($LASTEXITCODE -eq 0 -and $resolved) { $candidates.Add($resolved.Trim()) }
        }
        catch { }
    }
    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        try {
            & $candidate -c "import sys,struct;raise SystemExit(0 if sys.version_info[:2]==(3,11) and struct.calcsize('P')*8==64 else 2)" 2>$null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        }
        catch { }
    }
    return $null
}

function Test-VCRuntime {
    param([ValidateSet("x86", "x64")][string]$Arch)
    $path = "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\$Arch"
    try {
        $item = Get-ItemProperty -LiteralPath $path -ErrorAction Stop
        return ([int]$item.Installed -eq 1)
    }
    catch { return $false }
}

function Find-GameClient {
    foreach ($candidate in @(
        (Join-Path $env:ProgramFiles "ZingPlay\data\flutter_assets\assets\runtime\GameClientJS.exe"),
        (if (${env:ProgramFiles(x86)}) { Join-Path ${env:ProgramFiles(x86)} "ZingPlay\data\flutter_assets\assets\runtime\GameClientJS.exe" })
    )) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) { return $candidate }
    }
    return $null
}

function Install-WingetPackage {
    param([string]$Winget, [string]$Id, [string]$Label, [string]$Architecture = "")
    if (-not $Winget) { return $false }
    Write-Host "[INSTALL] $Label ($Id)..." -ForegroundColor Cyan
    $args = @("install", "--id", $Id, "--exact", "--source", "winget", "--accept-package-agreements", "--accept-source-agreements", "--silent")
    if ($Architecture) { $args += @("--architecture", $Architecture) }
    & $Winget @args
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Winget khong cai duoc $Label, exit=$LASTEXITCODE" -ForegroundColor Yellow
        return $false
    }
    Write-Host "[OK] $Label install command completed." -ForegroundColor Green
    return $true
}

function Get-State {
    $winget = Resolve-Winget
    $git = Resolve-Git
    $gitVersion = ""
    $lfsOk = $false
    $lfsVersion = ""
    if ($git) {
        try { $gitVersion = (& $git --version 2>$null | Select-Object -First 1) }
        catch { }
        try {
            $lfsVersion = (& $git lfs version 2>$null | Select-Object -First 1)
            $lfsOk = ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($lfsVersion))
        }
        catch { }
    }
    $python = Resolve-Python311
    $client = Find-GameClient
    $gameDir = Join-Path $env:APPDATA "VNG Corporation\ZingPlay\zpp\24\game"
    $branch = "NOT_A_GIT_REPO"
    $head = ""
    $dirty = "unknown"
    if ($git -and (Test-Path -LiteralPath (Join-Path $RepoRoot ".git"))) {
        try {
            $branch = (& $git -C $RepoRoot branch --show-current 2>$null | Select-Object -First 1)
            $head = (& $git -C $RepoRoot rev-parse --short HEAD 2>$null | Select-Object -First 1)
            $porcelain = @(& $git -C $RepoRoot status --porcelain 2>$null)
            $dirty = if ($porcelain.Count -eq 0) { "clean" } else { "dirty" }
        }
        catch { }
    }

    $runtimeRequired = @(
        (Join-Path $Dist "Multi\kvtm_multi_dev_host.py"),
        (Join-Path $Dist "Multi\kvtm_multi_dev_entry.py"),
        (Join-Path $Dist "AUTO_PRO\local_launcher.py"),
        (Join-Path $Dist "AUTO_PRO\bin\kvtm_loader.exe"),
        (Join-Path $Dist "AUTO_PRO\bin\kvtm_bridge.dll")
    )
    $runtimeMissing = @($runtimeRequired | Where-Object { -not (Test-Path -LiteralPath $_) })

    return [pscustomobject]@{
        winget = $winget
        git = $git
        git_version = $gitVersion
        lfs_ok = $lfsOk
        lfs_version = $lfsVersion
        python311 = $python
        vc_x64 = Test-VCRuntime x64
        vc_x86 = Test-VCRuntime x86
        game_client = $client
        game_dir = if (Test-Path -LiteralPath $gameDir -PathType Container) { $gameDir } else { $null }
        branch = $branch
        head = $head
        dirty = $dirty
        runtime_missing = $runtimeMissing
    }
}

if ($env:OS -ne "Windows_NT") {
    throw "KVTM Multi chi ho tro Windows."
}
if (-not [Environment]::Is64BitOperatingSystem) {
    throw "Can Windows x64."
}

$before = Get-State
if ($InstallMissing) {
    if (-not $before.winget) {
        Write-Host "[BLOCK] Khong co WinGet. Cai 'App Installer' tu Microsoft Store, sau do chay lai." -ForegroundColor Red
    }
    else {
        if (-not $before.git) {
            Install-WingetPackage $before.winget "Git.Git" "Git for Windows" "x64" | Out-Null
        }
        $midGit = Resolve-Git
        if ($midGit) {
            try {
                & $midGit lfs version *> $null
                if ($LASTEXITCODE -ne 0) {
                    Install-WingetPackage $before.winget "GitHub.GitLFS" "Git LFS" | Out-Null
                }
            }
            catch {
                Install-WingetPackage $before.winget "GitHub.GitLFS" "Git LFS" | Out-Null
            }
        }
        if (-not (Resolve-Python311)) {
            Install-WingetPackage $before.winget "Python.Python.3.11" "CPython 3.11 x64" "x64" | Out-Null
        }
        if (-not (Test-VCRuntime x64)) {
            Install-WingetPackage $before.winget "Microsoft.VCRedist.2015+.x64" "Visual C++ 2015-2022 x64" "x64" | Out-Null
        }
        if (-not (Test-VCRuntime x86)) {
            Install-WingetPackage $before.winget "Microsoft.VCRedist.2015+.x86" "Visual C++ 2015-2022 x86" "x86" | Out-Null
        }
        $gitAfterInstall = Resolve-Git
        if ($gitAfterInstall) {
            try { & $gitAfterInstall lfs install | Out-Null }
            catch { }
        }
    }
}

$state = Get-State
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("KVTM SECONDARY MACHINE DIAGNOSTIC")
$lines.Add("timestamp=$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss K'))")
$lines.Add("computer=$env:COMPUTERNAME")
$lines.Add("windows64=$([Environment]::Is64BitOperatingSystem)")
$lines.Add("powershell=$($PSVersionTable.PSVersion)")
$lines.Add("install_missing_requested=$InstallMissing")
$lines.Add("")
$lines.Add("=== REQUIRED SOFTWARE ===")
$lines.Add("winget=" + $(if ($state.winget) { "FOUND $($state.winget)" } else { "MISSING - install Microsoft App Installer" }))
$lines.Add("git=" + $(if ($state.git) { "FOUND $($state.git) [$($state.git_version)]" } else { "MISSING" }))
$lines.Add("git_lfs=" + $(if ($state.lfs_ok) { "FOUND $($state.lfs_version)" } else { "MISSING" }))
$lines.Add("python311_x64=" + $(if ($state.python311) { "FOUND $($state.python311)" } else { "MISSING" }))
$lines.Add("vc_redist_x64=" + $(if ($state.vc_x64) { "FOUND" } else { "MISSING" }))
$lines.Add("vc_redist_x86=" + $(if ($state.vc_x86) { "FOUND" } else { "MISSING" }))
$lines.Add("")
$lines.Add("=== ZINGPLAY / KVTM ===")
$lines.Add("game_client=" + $(if ($state.game_client) { "FOUND $($state.game_client)" } else { "MISSING - official: https://zingplay.com/games/sky-garden.html" }))
$lines.Add("game_data=" + $(if ($state.game_dir) { "FOUND $($state.game_dir)" } else { "MISSING - install/open Sky Garden once" }))
$lines.Add("")
$lines.Add("=== REPOSITORY ===")
$lines.Add("repo=$RepoRoot")
$lines.Add("branch=$($state.branch)")
$lines.Add("expected_branch=$ExpectedBranch")
$lines.Add("head=$($state.head)")
$lines.Add("working_tree=$($state.dirty)")
$lines.Add("")
$lines.Add("=== DEV RUNTIME ===")
if ($state.runtime_missing.Count -eq 0) {
    $lines.Add("runtime=READY")
}
else {
    $lines.Add("runtime=NOT_BUILT_OR_INCOMPLETE")
    foreach ($path in $state.runtime_missing) { $lines.Add("missing=$path") }
    $lines.Add("action=Run KVTM_DEV_CONTROL.bat -> [9] Full rebuild after Git LFS is ready")
}

$blocking = New-Object System.Collections.Generic.List[string]
if (-not $state.git) { $blocking.Add("Git") }
if (-not $state.lfs_ok) { $blocking.Add("Git LFS") }
if (-not $state.python311) { $blocking.Add("CPython 3.11 x64") }
if (-not $state.vc_x64) { $blocking.Add("VC++ x64") }
if (-not $state.vc_x86) { $blocking.Add("VC++ x86") }
if (-not $state.game_client) { $blocking.Add("ZingPlay/GameClientJS") }
if (-not $state.game_dir) { $blocking.Add("KVTM game data") }
if ($state.branch -ne $ExpectedBranch) { $blocking.Add("Correct Git branch") }

$lines.Add("")
$lines.Add("=== RESULT ===")
if ($blocking.Count -eq 0) {
    $lines.Add("RESULT=ENVIRONMENT_READY")
}
else {
    $lines.Add("RESULT=NOT_READY")
    $lines.Add("blocking=" + ($blocking -join "; "))
}
$lines.Add("secret_values_printed=false")
$lines | Set-Content -LiteralPath $ReportPath -Encoding UTF8
[IO.File]::WriteAllText($LatestPath, $ReportPath + [Environment]::NewLine, [Text.Encoding]::UTF8)

Write-Host ""
Write-Host "KVTM MACHINE DIAGNOSTIC COMPLETE" -ForegroundColor Green
Write-Host "Report: $ReportPath"
if ($blocking.Count -eq 0) {
    Write-Host "RESULT: ENVIRONMENT_READY" -ForegroundColor Green
}
else {
    Write-Host ("RESULT: NOT_READY - " + ($blocking -join ", ")) -ForegroundColor Yellow
}
if (-not $state.game_client) {
    Write-Host "ZingPlay/Sky Garden can cai tu nguon chinh thuc: https://zingplay.com/games/sky-garden.html" -ForegroundColor Yellow
    if ($OpenZingPlayPage) { Start-Process "https://zingplay.com/games/sky-garden.html" }
}
