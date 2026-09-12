param()

$ErrorActionPreference = "Stop"
$ProductName = "Kvtm_tool_Cry"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$DistRoot = Join-Path $RepoRoot "dist"
$ChannelRoot = Join-Path $DistRoot "Kvtm_tool_Cry-channel"
$ManifestPath = Join-Path $ChannelRoot "stable-manifest.json"
$LauncherSourcePath = Join-Path $PSScriptRoot "Kvtm_tool_Cry_Launcher.cs"
$UpdaterSourcePath = Join-Path $PSScriptRoot "Kvtm_tool_Cry_Updater.cs"
$SetupSourcePath = Join-Path $PSScriptRoot "Kvtm_tool_Cry_Setup.cs"
$BootstrapRoot = Join-Path $PSScriptRoot "bootstrap"
$FooterMagic = "KVTMCRY1"

foreach ($required in @(
    $ManifestPath,
    $LauncherSourcePath,
    $UpdaterSourcePath,
    $SetupSourcePath,
    (Join-Path $BootstrapRoot "Install-KvtmToolCry.ps1"),
    (Join-Path $BootstrapRoot "Kvtm_tool_Cry_Launch.ps1"),
    (Join-Path $BootstrapRoot "Kvtm_tool_Cry_Update.ps1"),
    (Join-Path $BootstrapRoot "Kvtm_tool_Cry_Runtime.ps1")
)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Stable setup fallback missing input: $required"
    }
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ([int]$manifest.schema -ne 1 -or [string]$manifest.product -ne $ProductName -or [string]$manifest.channel -ne "stable") {
    throw "Stable setup fallback manifest identity mismatch"
}
$Version = [string]$manifest.version
[void][version]$Version
$sourceHead = [string]$manifest.source_head
if ($sourceHead -notmatch '^[0-9a-fA-F]{40}$') {
    throw "Stable setup fallback manifest source_head is invalid"
}
$currentHeadLines = @(& git -C $RepoRoot rev-parse HEAD 2>$null)
$currentHead = if ($currentHeadLines.Count -gt 0) { ([string]$currentHeadLines[0]).Trim() } else { "" }
if (-not [string]::Equals($currentHead, $sourceHead, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Stable setup fallback refuses stale package: manifest=$sourceHead current=$currentHead"
}

$packageFile = [string]$manifest.package_file
if ([string]::IsNullOrWhiteSpace($packageFile)) {
    throw "Stable setup fallback manifest package_file is empty"
}
$packagePath = Join-Path $ChannelRoot $packageFile
if (-not (Test-Path -LiteralPath $packagePath -PathType Leaf)) {
    throw "Stable setup fallback runtime package missing: $packagePath"
}
$expectedSha = ([string]$manifest.package_sha256).Trim().ToLowerInvariant()
$actualSha = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($expectedSha -notmatch '^[0-9a-f]{64}$' -or $actualSha -ne $expectedSha) {
    throw "Stable setup fallback runtime package SHA256 mismatch"
}

$setupPath = Join-Path $DistRoot ("Kvtm_tool_Cry_Setup_$Version.exe")
$stage = Join-Path $DistRoot (".Kvtm_tool_Cry-selfextract-stage-" + [guid]::NewGuid().ToString("N"))
$bundleRoot = Join-Path $stage "bundle"
New-Item -ItemType Directory -Path $bundleRoot -Force | Out-Null

try {
    $launcherExe = Join-Path $bundleRoot "Kvtm_tool_Cry.exe"
    $updaterExe = Join-Path $bundleRoot "Kvtm_tool_Cry_Updater.exe"
    $setupStub = Join-Path $stage "Kvtm_tool_Cry_Setup.stub.exe"

    $launcherSource = Get-Content -LiteralPath $LauncherSourcePath -Raw -Encoding UTF8
    $updaterSource = Get-Content -LiteralPath $UpdaterSourcePath -Raw -Encoding UTF8
    $setupSource = Get-Content -LiteralPath $SetupSourcePath -Raw -Encoding UTF8

    Add-Type -TypeDefinition $launcherSource -Language CSharp -OutputAssembly $launcherExe -OutputType WindowsApplication
    Add-Type -TypeDefinition $updaterSource -Language CSharp -OutputAssembly $updaterExe -OutputType WindowsApplication
    Add-Type -TypeDefinition $setupSource -Language CSharp -OutputAssembly $setupStub -OutputType WindowsApplication -ReferencedAssemblies @(
        "System.dll",
        "System.IO.Compression.dll",
        "System.IO.Compression.FileSystem.dll",
        "System.Windows.Forms.dll"
    )

    foreach ($name in @(
        "Install-KvtmToolCry.ps1",
        "Kvtm_tool_Cry_Launch.ps1",
        "Kvtm_tool_Cry_Update.ps1",
        "Kvtm_tool_Cry_Runtime.ps1"
    )) {
        Copy-Item -LiteralPath (Join-Path $BootstrapRoot $name) -Destination (Join-Path $bundleRoot $name) -Force
    }
    Copy-Item -LiteralPath $packagePath -Destination (Join-Path $bundleRoot "payload.zip") -Force
    Copy-Item -LiteralPath $ManifestPath -Destination (Join-Path $bundleRoot "stable-manifest.json") -Force

    $channelDefault = [ordered]@{
        schema = 1
        product = $ProductName
        channel = "stable"
        enabled = $true
        provider = "file"
        manifest = $ManifestPath
    }
    [System.IO.File]::WriteAllText(
        (Join-Path $bundleRoot "update-channel.default.json"),
        (($channelDefault | ConvertTo-Json -Depth 5) + [Environment]::NewLine),
        [System.Text.Encoding]::UTF8
    )

    $bundleZip = Join-Path $stage "Kvtm_tool_Cry_Setup.bundle.zip"
    Compress-Archive -Path (Join-Path $bundleRoot "*") -DestinationPath $bundleZip -CompressionLevel Optimal
    $bundleLength = (Get-Item -LiteralPath $bundleZip).Length
    if ($bundleLength -le 0) {
        throw "Stable setup fallback produced empty bundle"
    }

    if (Test-Path -LiteralPath $setupPath -PathType Leaf) {
        Remove-Item -LiteralPath $setupPath -Force
    }
    Copy-Item -LiteralPath $setupStub -Destination $setupPath -Force

    $out = [System.IO.File]::Open($setupPath, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try {
        $bundle = [System.IO.File]::OpenRead($bundleZip)
        try {
            $bundle.CopyTo($out)
        }
        finally {
            $bundle.Dispose()
        }
        $lengthBytes = [System.BitConverter]::GetBytes([Int64]$bundleLength)
        $magicBytes = [System.Text.Encoding]::ASCII.GetBytes($FooterMagic)
        if ($magicBytes.Length -ne 8) {
            throw "Stable setup footer magic must be exactly 8 bytes"
        }
        $out.Write($lengthBytes, 0, $lengthBytes.Length)
        $out.Write($magicBytes, 0, $magicBytes.Length)
        $out.Flush()
    }
    finally {
        $out.Dispose()
    }

    $setupInfo = Get-Item -LiteralPath $setupPath -ErrorAction Stop
    $stubLength = (Get-Item -LiteralPath $setupStub).Length
    $expectedLength = [Int64]$stubLength + [Int64]$bundleLength + 16L
    if ([Int64]$setupInfo.Length -ne $expectedLength) {
        throw "Stable setup self-extract length mismatch: expected=$expectedLength actual=$($setupInfo.Length)"
    }

    $verify = [System.IO.File]::OpenRead($setupPath)
    try {
        $verify.Seek(-16L, [System.IO.SeekOrigin]::End) | Out-Null
        $footer = New-Object byte[] 16
        $read = $verify.Read($footer, 0, 16)
        if ($read -ne 16) { throw "Stable setup footer read failed" }
        $footerLength = [System.BitConverter]::ToInt64($footer, 0)
        $footerMagic = [System.Text.Encoding]::ASCII.GetString($footer, 8, 8)
        if ($footerLength -ne $bundleLength -or $footerMagic -ne $FooterMagic) {
            throw "Stable setup footer verification failed"
        }
    }
    finally {
        $verify.Dispose()
    }

    $setupSha = (Get-FileHash -LiteralPath $setupPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $receipt = [ordered]@{
        schema = 1
        product = $ProductName
        version = $Version
        source_head = $sourceHead
        runtime_package = $packagePath
        runtime_sha256 = $actualSha
        installer = $setupPath
        installer_sha256 = $setupSha
        manifest = $ManifestPath
        update_provider = "file"
        setup_format = "kvtm-selfextract-v1"
        built_at = (Get-Date).ToUniversalTime().ToString("o")
    }
    [System.IO.File]::WriteAllText(
        (Join-Path $ChannelRoot "latest-build.json"),
        (($receipt | ConvertTo-Json -Depth 5) + [Environment]::NewLine),
        [System.Text.Encoding]::UTF8
    )

    Write-Host "Kvtm_tool_Cry SELF-EXTRACT SETUP VERIFIED" -ForegroundColor Green
    Write-Host "Installer : $setupPath" -ForegroundColor Cyan
    Write-Host "SHA256    : $setupSha" -ForegroundColor Cyan
    Write-Host "Source    : $sourceHead" -ForegroundColor Cyan
    Write-Host "Kvtm_tool_Cry RELEASE BUILD PASS" -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $stage -PathType Container) {
        Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    }
}
