param(
    [string]$ProfileFile = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Security
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($ProfileFile)) {
    $ProfileFile = Join-Path $RepoRoot "dist\KVTM-ClientJS-Suite-Multi-DEV\data-dev\profiles.json"
}
$Entropy = [Text.Encoding]::UTF8.GetBytes("KVTM-MULTI-v1")

if (-not (Test-Path -LiteralPath $ProfileFile -PathType Leaf)) {
    throw "Khong tim thay profiles.json: $ProfileFile"
}

# Windows PowerShell 5.1 can preserve a top-level JSON array as one pipeline object.
# Cast explicitly to object[] so a profiles.json array is always enumerated correctly.
[object[]]$profiles = (Get-Content -LiteralPath $ProfileFile -Raw -Encoding UTF8 | ConvertFrom-Json)
$decryptable = 0
$validArgs = 0
$clientPaths = 0
$gamePaths = 0
$errors = New-Object System.Collections.Generic.List[string]

foreach ($profile in $profiles) {
    $label = if ([string]::IsNullOrWhiteSpace([string]$profile.name)) { [string]$profile.id } else { [string]$profile.name }
    try {
        $cipher = [Convert]::FromBase64String([string]$profile.secret)
        $plain = [Security.Cryptography.ProtectedData]::Unprotect(
            $cipher, $Entropy, [Security.Cryptography.DataProtectionScope]::CurrentUser
        )
        $decryptable++
        $text = [Text.Encoding]::UTF8.GetString($plain)
        $parsed = $text | ConvertFrom-Json
        if ($null -ne $parsed) { $validArgs++ }
    }
    catch {
        $errors.Add("profile=$label dpapi=FAIL error=$($_.Exception.GetType().Name)")
    }
    if (Test-Path -LiteralPath ([string]$profile.client) -PathType Leaf) { $clientPaths++ }
    if (Test-Path -LiteralPath ([string]$profile.game_dir) -PathType Container) { $gamePaths++ }
}

Write-Host "KVTM PROFILE VERIFY - READ ONLY" -ForegroundColor Cyan
Write-Host "Profile file: $ProfileFile"
Write-Host "profiles=$($profiles.Count)"
Write-Host "dpapi_decryptable=$decryptable"
Write-Host "secret_args_valid_json=$validArgs"
Write-Host "client_paths_found=$clientPaths"
Write-Host "game_paths_found=$gamePaths"
Write-Host "secret_values_printed=false"
foreach ($item in $errors) { Write-Host $item -ForegroundColor Yellow }

if ($profiles.Count -gt 0 -and $decryptable -eq $profiles.Count -and $validArgs -eq $profiles.Count) {
    Write-Host "DPAPI_RESULT=READY" -ForegroundColor Green
}
else {
    Write-Host "DPAPI_RESULT=NOT_READY" -ForegroundColor Red
    exit 2
}
if ($clientPaths -eq $profiles.Count -and $gamePaths -eq $profiles.Count) {
    Write-Host "LAUNCH_PATH_RESULT=READY" -ForegroundColor Green
    exit 0
}
Write-Host "LAUNCH_PATH_RESULT=NOT_READY - cai/mo ZingPlay Sky Garden tren may nay roi chay lai." -ForegroundColor Yellow
exit 3
