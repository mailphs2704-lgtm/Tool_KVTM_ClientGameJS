param()

$ErrorActionPreference = "Stop"
$ProductName = "Kvtm_tool_Cry"
$InstallRoot = Join-Path $env:LOCALAPPDATA "Programs\Kvtm_tool_Cry"
$LauncherRoot = Join-Path $InstallRoot "launcher"
$VersionsRoot = Join-Path $InstallRoot "versions"
$DataRoot = Join-Path $env:APPDATA $ProductName
$LogRoot = Join-Path $DataRoot "logs"
$ManifestPath = Join-Path $PSScriptRoot "stable-manifest.json"
$PayloadPath = Join-Path $PSScriptRoot "payload.zip"
$ChannelDefaultPath = Join-Path $PSScriptRoot "update-channel.default.json"
$CurrentPath = Join-Path $InstallRoot "current.json"

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Write-AtomicJson {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value
    )
    $temp = "$Path.tmp-$([guid]::NewGuid().ToString('N'))"
    [System.IO.File]::WriteAllText(
        $temp,
        (($Value | ConvertTo-Json -Depth 8) + [Environment]::NewLine),
        [System.Text.Encoding]::UTF8
    )
    Move-Item -LiteralPath $temp -Destination $Path -Force
}

foreach ($required in @(
    $ManifestPath,
    $PayloadPath,
    (Join-Path $PSScriptRoot "Kvtm_tool_Cry.exe"),
    (Join-Path $PSScriptRoot "Kvtm_tool_Cry_Updater.exe"),
    (Join-Path $PSScriptRoot "Kvtm_tool_Cry_Launch.ps1"),
    (Join-Path $PSScriptRoot "Kvtm_tool_Cry_Update.ps1"),
    (Join-Path $PSScriptRoot "Kvtm_tool_Cry_Runtime.ps1"),
    $ChannelDefaultPath
)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Kvtm_tool_Cry Setup is incomplete: $required"
    }
}

$manifest = Read-JsonFile -Path $ManifestPath
if ([string]$manifest.product -ne $ProductName -or [int]$manifest.schema -ne 1) {
    throw "Kvtm_tool_Cry Setup manifest identity mismatch"
}
$version = [string]$manifest.version
[void][version]$version
$expectedSha = ([string]$manifest.package_sha256).Trim().ToLowerInvariant()
$actualSha = (Get-FileHash -LiteralPath $PayloadPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSha -ne $expectedSha) {
    throw "Kvtm_tool_Cry Setup payload SHA256 mismatch"
}

New-Item -ItemType Directory -Path $InstallRoot, $LauncherRoot, $VersionsRoot, $DataRoot, $LogRoot -Force | Out-Null
$targetVersion = Join-Path $VersionsRoot $version
if (-not (Test-Path -LiteralPath $targetVersion -PathType Container)) {
    $stage = Join-Path $InstallRoot ("install-stage-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    try {
        Expand-Archive -LiteralPath $PayloadPath -DestinationPath $stage -Force
        $stampPath = Join-Path $stage ".product.json"
        if (-not (Test-Path -LiteralPath $stampPath -PathType Leaf)) {
            throw "Kvtm_tool_Cry payload missing .product.json"
        }
        $stamp = Read-JsonFile -Path $stampPath
        if ([string]$stamp.product -ne $ProductName -or [string]$stamp.version -ne $version) {
            throw "Kvtm_tool_Cry payload product/version mismatch"
        }
        Move-Item -LiteralPath $stage -Destination $targetVersion
    }
    finally {
        if (Test-Path -LiteralPath $stage -PathType Container) {
            Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

foreach ($name in @(
    "Kvtm_tool_Cry.exe",
    "Kvtm_tool_Cry_Updater.exe",
    "Kvtm_tool_Cry_Launch.ps1",
    "Kvtm_tool_Cry_Update.ps1",
    "Kvtm_tool_Cry_Runtime.ps1"
)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $LauncherRoot $name) -Force
}

$current = [ordered]@{
    schema = 1
    product = $ProductName
    version = $version
    source_head = [string]$manifest.source_head
    switched_at = (Get-Date).ToUniversalTime().ToString("o")
}
Write-AtomicJson -Path $CurrentPath -Value $current

$channelPath = Join-Path $DataRoot "update-channel.json"
if (-not (Test-Path -LiteralPath $channelPath -PathType Leaf)) {
    Copy-Item -LiteralPath $ChannelDefaultPath -Destination $channelPath -Force
}

# First install only: seed profiles/settings from Multi DEV, then Stable owns its
# copies forever. No running_clients.json, PID map, diagnostics or runtime state
# is migrated across products.
$DevDataRoot = Join-Path $env:APPDATA "KVTM Multi DEV"
foreach ($name in @("profiles.json", "settings.json", "clear-stall-history.jsonl")) {
    $stableFile = Join-Path $DataRoot $name
    $devFile = Join-Path $DevDataRoot $name
    if (-not (Test-Path -LiteralPath $stableFile -PathType Leaf) -and
        (Test-Path -LiteralPath $devFile -PathType Leaf)) {
        Copy-Item -LiteralPath $devFile -Destination $stableFile -Force
    }
}

$mainExe = Join-Path $LauncherRoot "Kvtm_tool_Cry.exe"
$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
foreach ($shortcutPath in @(
    (Join-Path $desktop "Kvtm_tool_Cry.lnk"),
    (Join-Path $startMenu "Kvtm_tool_Cry.lnk")
)) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $mainExe
    $shortcut.WorkingDirectory = $LauncherRoot
    $shortcut.Description = "Kvtm_tool_Cry"
    $shortcut.Save()
}

$installReceipt = [ordered]@{
    schema = 1
    product = $ProductName
    version = $version
    source_head = [string]$manifest.source_head
    install_root = $InstallRoot
    data_root = $DataRoot
    installed_at = (Get-Date).ToUniversalTime().ToString("o")
}
Write-AtomicJson -Path (Join-Path $DataRoot "install.json") -Value $installReceipt

Start-Process -FilePath $mainExe -WorkingDirectory $LauncherRoot | Out-Null
exit 0
