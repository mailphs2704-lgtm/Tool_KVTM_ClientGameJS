param(
    [string]$SourceProfile = (Join-Path $env:APPDATA "KVTM Multi\profiles.json")
)

$ErrorActionPreference = "Stop"
$DevData = Join-Path $PSScriptRoot "data-dev"
$Destination = Join-Path $DevData "profiles.json"

if (-not (Test-Path -LiteralPath $SourceProfile -PathType Leaf)) {
    throw "Khong tim thay profile ban chinh: $SourceProfile"
}

$profiles = Get-Content -LiteralPath $SourceProfile -Raw -Encoding UTF8 | ConvertFrom-Json
if ($null -eq $profiles) {
    throw "profiles.json khong co du lieu hop le."
}

New-Item -ItemType Directory -Path $DevData -Force | Out-Null
if (Test-Path -LiteralPath $Destination) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Copy-Item -LiteralPath $Destination -Destination (Join-Path $DevData "profiles-before-import-$stamp.json") -Force
}

Copy-Item -LiteralPath $SourceProfile -Destination $Destination -Force
$count = @($profiles).Count
Write-Host "IMPORT PROFILE DEV OK" -ForegroundColor Green
Write-Host "Source: $SourceProfile"
Write-Host "Destination: $Destination"
Write-Host "Accounts: $count"
Write-Host "Day la ban sao rieng; thay doi trong DEV khong ghi vao profile ban chinh."
