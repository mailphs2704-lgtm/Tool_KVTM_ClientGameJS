param(
    [string]$Version = "",
    [string]$ManifestUrl = ""
)

$ErrorActionPreference = "Stop"
$ProductName = "Kvtm_tool_Cry"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$VersionFile = Join-Path $PSScriptRoot "VERSION"
$SuiteBuilder = Join-Path $RepoRoot "packaging\suite-v0.15\BUILD_FULL_PACKAGE_PS51.ps1"
$Verifier = Join-Path $RepoRoot "tools\verify_kvtm_tool_cry_packaging_contract.py"
$DistRoot = Join-Path $RepoRoot "dist"
$ChannelRoot = Join-Path $DistRoot "Kvtm_tool_Cry-channel"
$ManifestPath = Join-Path $ChannelRoot "stable-manifest.json"
$BuildOutputName = "Kvtm_tool_Cry-Runtime-BUILD"
$BuiltRoot = Join-Path $DistRoot $BuildOutputName

if ([string]::IsNullOrWhiteSpace($Version)) {
    if (-not (Test-Path -LiteralPath $VersionFile -PathType Leaf)) {
        throw "Missing version file: $VersionFile"
    }
    $Version = (Get-Content -LiteralPath $VersionFile -Raw -Encoding UTF8).Trim()
}
[void][version]$Version
if (-not (Test-Path -LiteralPath $SuiteBuilder -PathType Leaf)) {
    throw "Missing suite builder: $SuiteBuilder"
}
if (-not (Test-Path -LiteralPath $Verifier -PathType Leaf)) {
    throw "Missing Kvtm_tool_Cry packaging verifier: $Verifier"
}

# Do not trust $LASTEXITCODE for this read-only branch probe. On Windows PowerShell
# a native command used inside a pipeline can leave an unrelated/stale exit code
# even when the branch text is returned correctly. The authoritative condition is
# the normalized branch name itself; detached HEAD or a real wrong branch still
# fail closed because they cannot equal the expected branch.
$expectedBranch = "develop/multi-auto-dev"
$branchLines = @(& git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>$null)
$branch = ""
if ($branchLines.Count -gt 0) {
    $branch = ([string]($branchLines | Select-Object -First 1)).Trim()
}
if (-not [string]::Equals(
    $branch,
    $expectedBranch,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    $branchCodes = if ([string]::IsNullOrEmpty($branch)) {
        "<empty>"
    } else {
        (($branch.ToCharArray() | ForEach-Object { [int][char]$_ }) -join ",")
    }
    throw "Kvtm_tool_Cry release must be built from $expectedBranch; current=[$branch]; charcodes=$branchCodes"
}
Write-Host "Branch : $branch" -ForegroundColor Green

$sourceHeadLines = @(& git -C $RepoRoot rev-parse HEAD 2>$null)
$sourceHead = ""
if ($sourceHeadLines.Count -gt 0) {
    $sourceHead = ([string]($sourceHeadLines | Select-Object -First 1)).Trim()
}
if ([string]::IsNullOrWhiteSpace($sourceHead) -or $sourceHead -notmatch '^[0-9a-fA-F]{40}$') {
    throw "Cannot determine valid source HEAD; value=[$sourceHead]"
}
$dirty = @(& git -C $RepoRoot status --porcelain --untracked-files=no 2>$null)
if ($LASTEXITCODE -ne 0) {
    throw "Cannot inspect repository working tree"
}
if ($dirty.Count -gt 0) {
    throw "Refuse Stable release from a dirty tracked working tree. Commit/pull first."
}

New-Item -ItemType Directory -Path $DistRoot, $ChannelRoot -Force | Out-Null
if (Test-Path -LiteralPath $ManifestPath -PathType Leaf) {
    try {
        $previous = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ([string]$previous.version -eq $Version -and [string]$previous.source_head -ne $sourceHead) {
            throw "Stable version $Version already points to another source HEAD. Bump packaging/kvtm-tool-cry/VERSION before publishing."
        }
    }
    catch {
        if ($_.Exception.Message -like "Stable version*") { throw }
    }
}

Write-Host "Kvtm_tool_Cry RELEASE" -ForegroundColor Cyan
Write-Host "Version: $Version"
Write-Host "Source : $sourceHead"
Write-Host "Stable installed app is NOT an input/output of this build." -ForegroundColor Green

& py.exe -3.11 $Verifier
if ($LASTEXITCODE -ne 0) {
    throw "Kvtm_tool_Cry packaging contract failed; exit=$LASTEXITCODE"
}

# Reuse the authoritative package builder. Its process cleanup is scoped to this
# exact dist output path, not to %LOCALAPPDATA%\Programs\Kvtm_tool_Cry.
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SuiteBuilder -OutputName $BuildOutputName
if ($LASTEXITCODE -ne 0) {
    throw "Base runtime build failed; exit=$LASTEXITCODE"
}

foreach ($required in @(
    (Join-Path $BuiltRoot "AUTO_PRO"),
    (Join-Path $BuiltRoot "Multi"),
    (Join-Path $BuiltRoot "components\clientjs-auto"),
    (Join-Path $BuiltRoot ".source-head.txt")
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Base runtime incomplete: $required"
    }
}

$releaseStage = Join-Path $DistRoot (".Kvtm_tool_Cry-runtime-stage-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $releaseStage -Force | Out-Null
try {
    foreach ($name in @("AUTO_PRO", "Multi", "components")) {
        Copy-Item -LiteralPath (Join-Path $BuiltRoot $name) -Destination (Join-Path $releaseStage $name) -Recurse -Force
    }
    Copy-Item -LiteralPath (Join-Path $BuiltRoot ".source-head.txt") -Destination (Join-Path $releaseStage ".source-head.txt") -Force

    $productStamp = [ordered]@{
        schema = 1
        product = $ProductName
        channel = "stable"
        version = $Version
        source_head = $sourceHead
        built_at = (Get-Date).ToUniversalTime().ToString("o")
    }
    [System.IO.File]::WriteAllText(
        (Join-Path $releaseStage ".product.json"),
        (($productStamp | ConvertTo-Json -Depth 5) + [Environment]::NewLine),
        [System.Text.Encoding]::UTF8
    )

    $packageName = "Kvtm_tool_Cry-$Version.zip"
    $packagePath = Join-Path $ChannelRoot $packageName
    if (Test-Path -LiteralPath $packagePath -PathType Leaf) {
        Remove-Item -LiteralPath $packagePath -Force
    }
    Compress-Archive -Path (Join-Path $releaseStage "*") -DestinationPath $packagePath -CompressionLevel Optimal
    $sha256 = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()

    $manifest = [ordered]@{
        schema = 1
        product = $ProductName
        channel = "stable"
        version = $Version
        source_head = $sourceHead
        package_file = $packageName
        package_url = ""
        package_sha256 = $sha256
        published_at = (Get-Date).ToUniversalTime().ToString("o")
    }
    [System.IO.File]::WriteAllText(
        $ManifestPath,
        (($manifest | ConvertTo-Json -Depth 5) + [Environment]::NewLine),
        [System.Text.Encoding]::UTF8
    )
}
finally {
    if (Test-Path -LiteralPath $releaseStage -PathType Container) {
        Remove-Item -LiteralPath $releaseStage -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$setupStage = Join-Path $DistRoot (".Kvtm_tool_Cry-setup-stage-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $setupStage -Force | Out-Null
try {
    $launcherSource = Get-Content -LiteralPath (Join-Path $PSScriptRoot "Kvtm_tool_Cry_Launcher.cs") -Raw -Encoding UTF8
    $updaterSource = Get-Content -LiteralPath (Join-Path $PSScriptRoot "Kvtm_tool_Cry_Updater.cs") -Raw -Encoding UTF8
    $launcherExe = Join-Path $setupStage "Kvtm_tool_Cry.exe"
    $updaterExe = Join-Path $setupStage "Kvtm_tool_Cry_Updater.exe"
    Add-Type -TypeDefinition $launcherSource -Language CSharp -OutputAssembly $launcherExe -OutputType WindowsApplication
    Add-Type -TypeDefinition $updaterSource -Language CSharp -OutputAssembly $updaterExe -OutputType WindowsApplication

    foreach ($name in @(
        "Install-KvtmToolCry.ps1",
        "Kvtm_tool_Cry_Launch.ps1",
        "Kvtm_tool_Cry_Update.ps1",
        "Kvtm_tool_Cry_Runtime.ps1"
    )) {
        Copy-Item -LiteralPath (Join-Path (Join-Path $PSScriptRoot "bootstrap") $name) -Destination (Join-Path $setupStage $name) -Force
    }
    Copy-Item -LiteralPath (Join-Path $ChannelRoot ("Kvtm_tool_Cry-$Version.zip")) -Destination (Join-Path $setupStage "payload.zip") -Force
    Copy-Item -LiteralPath $ManifestPath -Destination (Join-Path $setupStage "stable-manifest.json") -Force

    if ([string]::IsNullOrWhiteSpace($ManifestUrl)) {
        $channelDefault = [ordered]@{
            schema = 1
            product = $ProductName
            channel = "stable"
            enabled = $true
            provider = "file"
            manifest = $ManifestPath
        }
    }
    else {
        if (-not $ManifestUrl.StartsWith("https://", [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "ManifestUrl must use https://"
        }
        $channelDefault = [ordered]@{
            schema = 1
            product = $ProductName
            channel = "stable"
            enabled = $true
            provider = "https"
            manifest = $ManifestUrl
        }
    }
    [System.IO.File]::WriteAllText(
        (Join-Path $setupStage "update-channel.default.json"),
        (($channelDefault | ConvertTo-Json -Depth 5) + [Environment]::NewLine),
        [System.Text.Encoding]::UTF8
    )

    $setupPath = Join-Path $DistRoot ("Kvtm_tool_Cry_Setup_$Version.exe")
    if (Test-Path -LiteralPath $setupPath -PathType Leaf) {
        Remove-Item -LiteralPath $setupPath -Force
    }
    $iexpress = Join-Path $env:SystemRoot "System32\iexpress.exe"
    if (-not (Test-Path -LiteralPath $iexpress -PathType Leaf)) {
        throw "Windows IExpress not found: $iexpress"
    }

    $files = @(
        "Kvtm_tool_Cry.exe",
        "Kvtm_tool_Cry_Updater.exe",
        "Install-KvtmToolCry.ps1",
        "Kvtm_tool_Cry_Launch.ps1",
        "Kvtm_tool_Cry_Update.ps1",
        "Kvtm_tool_Cry_Runtime.ps1",
        "payload.zip",
        "stable-manifest.json",
        "update-channel.default.json"
    )
    $strings = New-Object System.Collections.Generic.List[string]
    $sourceEntries = New-Object System.Collections.Generic.List[string]
    for ($i = 0; $i -lt $files.Count; $i++) {
        $strings.Add(('FILE{0}="{1}"' -f $i, $files[$i]))
        $sourceEntries.Add(('%FILE{0}%=' -f $i))
    }
    $sourceDir = $setupStage.TrimEnd('\') + '\'
    $sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=%InstallPrompt%
DisplayLicense=%DisplayLicense%
FinishMessage=%FinishMessage%
TargetName=%TargetName%
FriendlyName=%FriendlyName%
AppLaunched=%AppLaunched%
PostInstallCmd=%PostInstallCmd%
AdminQuietInstCmd=%AdminQuietInstCmd%
UserQuietInstCmd=%UserQuietInstCmd%
SourceFiles=SourceFiles
[Strings]
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=$setupPath
FriendlyName=Kvtm_tool_Cry $Version Setup
AppLaunched=powershell.exe -NoProfile -ExecutionPolicy Bypass -File Install-KvtmToolCry.ps1
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
$($strings -join "`r`n")
[SourceFiles]
SourceFiles0=$sourceDir
[SourceFiles0]
$($sourceEntries -join "`r`n")
"@
    $sedPath = Join-Path $setupStage "Kvtm_tool_Cry_Setup.sed"
    [System.IO.File]::WriteAllText($sedPath, $sed, [System.Text.Encoding]::Default)
    & $iexpress /N /Q $sedPath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $setupPath -PathType Leaf)) {
        throw "IExpress setup build failed; exit=$LASTEXITCODE"
    }

    $setupSha = (Get-FileHash -LiteralPath $setupPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $receipt = [ordered]@{
        schema = 1
        product = $ProductName
        version = $Version
        source_head = $sourceHead
        runtime_package = (Join-Path $ChannelRoot ("Kvtm_tool_Cry-$Version.zip"))
        runtime_sha256 = (Get-FileHash -LiteralPath (Join-Path $ChannelRoot ("Kvtm_tool_Cry-$Version.zip")) -Algorithm SHA256).Hash.ToLowerInvariant()
        installer = $setupPath
        installer_sha256 = $setupSha
        manifest = $ManifestPath
        update_provider = [string]$channelDefault.provider
        built_at = (Get-Date).ToUniversalTime().ToString("o")
    }
    [System.IO.File]::WriteAllText(
        (Join-Path $ChannelRoot "latest-build.json"),
        (($receipt | ConvertTo-Json -Depth 5) + [Environment]::NewLine),
        [System.Text.Encoding]::UTF8
    )

    Write-Host "Kvtm_tool_Cry RELEASE BUILD PASS" -ForegroundColor Green
    Write-Host "Installer : $setupPath" -ForegroundColor Cyan
    Write-Host "Channel   : $ManifestPath" -ForegroundColor Cyan
    Write-Host "Runtime   : $(Join-Path $ChannelRoot ("Kvtm_tool_Cry-$Version.zip"))" -ForegroundColor Cyan
    Write-Host "Source    : $sourceHead" -ForegroundColor Cyan
    Write-Host "Stable running install was not stopped or modified." -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $setupStage -PathType Container) {
        Remove-Item -LiteralPath $setupStage -Recurse -Force -ErrorAction SilentlyContinue
    }
}
