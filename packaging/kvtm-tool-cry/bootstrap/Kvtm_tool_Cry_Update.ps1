param(
    [switch]$UpdateOnly
)

$ErrorActionPreference = "Stop"
$ProductName = "Kvtm_tool_Cry"
$InstallRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DataRoot = Join-Path $env:APPDATA $ProductName
$LogRoot = Join-Path $DataRoot "logs"
$ChannelConfigPath = Join-Path $DataRoot "update-channel.json"
$CurrentPath = Join-Path $InstallRoot "current.json"
$VersionsRoot = Join-Path $InstallRoot "versions"
$StagingRoot = Join-Path $InstallRoot "staging"
$RuntimePidPath = Join-Path $DataRoot "runtime.pid.json"

New-Item -ItemType Directory -Path $DataRoot, $LogRoot, $VersionsRoot, $StagingRoot -Force | Out-Null
$LogPath = Join-Path $LogRoot "updater.log"

function Write-CryUpdateLog {
    param([Parameter(Mandatory = $true)][string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
}

function Test-CryRuntimeRunning {
    if (-not (Test-Path -LiteralPath $RuntimePidPath -PathType Leaf)) {
        return $false
    }
    try {
        $pidInfo = Get-Content -LiteralPath $RuntimePidPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $runtimePid = [int]$pidInfo.pid
        if ($runtimePid -le 0) { return $false }
        $process = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $runtimePid) -ErrorAction SilentlyContinue
        if ($null -eq $process) { return $false }
        $commandLine = [string]$process.CommandLine
        if ([string]::IsNullOrWhiteSpace($commandLine)) { return $false }
        $installNeedle = ([System.IO.Path]::GetFullPath($InstallRoot)).ToLowerInvariant()
        return $commandLine.ToLowerInvariant().Contains($installNeedle) -and $commandLine.Contains("kvtm_multi_owned_host.py")
    }
    catch {
        return $false
    }
}

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Write-AtomicJson {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value
    )
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $temp = "$Path.tmp-$([guid]::NewGuid().ToString('N'))"
    $json = $Value | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($temp, $json + [Environment]::NewLine, [System.Text.Encoding]::UTF8)
    Move-Item -LiteralPath $temp -Destination $Path -Force
}

function Read-Manifest {
    param($Channel)
    $provider = ([string]$Channel.provider).Trim().ToLowerInvariant()
    $manifestLocation = [string]$Channel.manifest
    if ([string]::IsNullOrWhiteSpace($manifestLocation)) {
        throw "Update channel manifest is empty"
    }

    if ($provider -eq "file") {
        $resolved = [System.IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($manifestLocation))
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "Local update manifest not found: $resolved"
        }
        return @{
            Provider = "file"
            Location = $resolved
            Manifest = (Read-JsonFile -Path $resolved)
        }
    }

    if ($provider -eq "https") {
        if (-not $manifestLocation.StartsWith("https://", [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "HTTPS provider requires an https:// manifest URL"
        }
        $response = Invoke-WebRequest -UseBasicParsing -Uri $manifestLocation -TimeoutSec 20
        return @{
            Provider = "https"
            Location = $manifestLocation
            Manifest = ($response.Content | ConvertFrom-Json)
        }
    }

    throw "Unsupported update provider: $provider"
}

function Resolve-PackageSource {
    param(
        [Parameter(Mandatory = $true)][string]$Provider,
        [Parameter(Mandatory = $true)][string]$ManifestLocation,
        [Parameter(Mandatory = $true)]$Manifest
    )
    if ($Provider -eq "file") {
        $packageFile = [string]$Manifest.package_file
        if ([string]::IsNullOrWhiteSpace($packageFile)) {
            throw "File manifest missing package_file"
        }
        if ([System.IO.Path]::IsPathRooted($packageFile)) {
            return [System.IO.Path]::GetFullPath($packageFile)
        }
        return [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $ManifestLocation) $packageFile))
    }

    $packageUrl = [string]$Manifest.package_url
    if ([string]::IsNullOrWhiteSpace($packageUrl) -or
        -not $packageUrl.StartsWith("https://", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "HTTPS manifest missing package_url"
    }
    return $packageUrl
}

function Get-PackageZip {
    param(
        [Parameter(Mandatory = $true)][string]$Provider,
        [Parameter(Mandatory = $true)][string]$PackageSource,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256
    )
    if ($Provider -eq "file") {
        if (-not (Test-Path -LiteralPath $PackageSource -PathType Leaf)) {
            throw "Update package not found: $PackageSource"
        }
        $zipPath = $PackageSource
        $ownedTemp = $false
    }
    else {
        $zipPath = Join-Path $env:TEMP ("Kvtm_tool_Cry-update-" + [guid]::NewGuid().ToString("N") + ".zip")
        Invoke-WebRequest -UseBasicParsing -Uri $PackageSource -OutFile $zipPath -TimeoutSec 120
        $ownedTemp = $true
    }

    $actual = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $ExpectedSha256.ToLowerInvariant()) {
        if ($ownedTemp) { Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue }
        throw "Update package SHA256 mismatch: expected=$ExpectedSha256 actual=$actual"
    }
    return @{
        Path = $zipPath
        OwnedTemp = $ownedTemp
    }
}

try {
    Write-CryUpdateLog "CHECK start"
    if (Test-CryRuntimeRunning) {
        Write-CryUpdateLog "SKIP runtime is active; current running version is never modified"
        exit 0
    }

    if (-not (Test-Path -LiteralPath $CurrentPath -PathType Leaf)) {
        throw "Missing current.json: $CurrentPath"
    }
    if (-not (Test-Path -LiteralPath $ChannelConfigPath -PathType Leaf)) {
        Write-CryUpdateLog "SKIP no update-channel.json configured"
        exit 0
    }

    $channel = Read-JsonFile -Path $ChannelConfigPath
    if ($channel.enabled -eq $false) {
        Write-CryUpdateLog "SKIP channel disabled"
        exit 0
    }

    $current = Read-JsonFile -Path $CurrentPath
    $currentVersion = [version]([string]$current.version)
    $resolved = Read-Manifest -Channel $channel
    $manifest = $resolved.Manifest

    if ([string]$manifest.product -ne $ProductName) {
        throw "Manifest product mismatch: $($manifest.product)"
    }
    if ([int]$manifest.schema -ne 1) {
        throw "Unsupported manifest schema: $($manifest.schema)"
    }
    if ([string]$manifest.channel -ne "stable") {
        throw "Manifest channel mismatch: $($manifest.channel)"
    }

    $nextVersionText = [string]$manifest.version
    $nextVersion = [version]$nextVersionText
    if ($nextVersion -le $currentVersion) {
        Write-CryUpdateLog "PASS current=$currentVersion latest=$nextVersion"
        exit 0
    }

    $expectedSha = ([string]$manifest.package_sha256).Trim().ToLowerInvariant()
    if ($expectedSha -notmatch '^[0-9a-f]{64}$') {
        throw "Manifest package_sha256 is invalid"
    }

    $packageSource = Resolve-PackageSource -Provider $resolved.Provider -ManifestLocation $resolved.Location -Manifest $manifest
    Write-CryUpdateLog "UPDATE found current=$currentVersion next=$nextVersionText provider=$($resolved.Provider)"
    $package = Get-PackageZip -Provider $resolved.Provider -PackageSource $packageSource -ExpectedSha256 $expectedSha

    $stage = Join-Path $StagingRoot ($nextVersionText + "-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    try {
        Expand-Archive -LiteralPath $package.Path -DestinationPath $stage -Force
        $productStamp = Join-Path $stage ".product.json"
        if (-not (Test-Path -LiteralPath $productStamp -PathType Leaf)) {
            throw "Update archive missing .product.json"
        }
        $stamp = Read-JsonFile -Path $productStamp
        if ([string]$stamp.product -ne $ProductName -or [string]$stamp.version -ne $nextVersionText) {
            throw "Update archive product/version stamp mismatch"
        }

        $target = Join-Path $VersionsRoot $nextVersionText
        if (Test-Path -LiteralPath $target -PathType Container) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
        Move-Item -LiteralPath $stage -Destination $target

        $newCurrent = [ordered]@{
            schema = 1
            product = $ProductName
            version = $nextVersionText
            source_head = [string]$manifest.source_head
            switched_at = (Get-Date).ToUniversalTime().ToString("o")
        }
        Write-AtomicJson -Path $CurrentPath -Value $newCurrent
        Write-CryUpdateLog "SWITCH PASS version=$nextVersionText sha256=$expectedSha"

        $keep = @($nextVersionText, [string]$current.version)
        foreach ($dir in @(Get-ChildItem -LiteralPath $VersionsRoot -Directory -ErrorAction SilentlyContinue)) {
            if ($keep -notcontains $dir.Name) {
                Remove-Item -LiteralPath $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }
    finally {
        if (Test-Path -LiteralPath $stage -PathType Container) {
            Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
        }
        if ($package.OwnedTemp -and (Test-Path -LiteralPath $package.Path -PathType Leaf)) {
            Remove-Item -LiteralPath $package.Path -Force -ErrorAction SilentlyContinue
        }
    }

    exit 0
}
catch {
    Write-CryUpdateLog ("FAIL " + $_.Exception.Message)
    if ($UpdateOnly) {
        exit 2
    }
    # Launch path is fail-open to the last verified installed version. Update
    # failure must never destroy or disable a known-good Stable runtime.
    exit 1
}
