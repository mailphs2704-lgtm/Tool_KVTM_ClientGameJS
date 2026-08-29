$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$OutRoot = Join-Path $RepoRoot 'AUTO_KVTM_PRO_CLEAN'

function Copy-RequiredFile([string]$RelativePath) {
    $src = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $src -PathType Leaf)) {
        throw "Required file is missing: $RelativePath"
    }
    $dst = Join-Path $OutRoot $RelativePath
    $parent = Split-Path -Parent $dst
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Copy-Item -LiteralPath $src -Destination $dst -Force
}

function Copy-RequiredDir([string]$RelativePath) {
    $src = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $src -PathType Container)) {
        throw "Required directory is missing: $RelativePath"
    }
    $dst = Join-Path $OutRoot $RelativePath
    $parent = Split-Path -Parent $dst
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force
}

Write-Host '[1/6] Checking source tree...'

$requiredDirs = @(
    '_internal',
    'assets',
    'runtime',
    'platform-tools',
    'launchers',
    'patches'
)

$requiredFiles = @(
    'local_api.py',
    'local_bridge.py',
    'local_options_bridge_v08.py',
    'local_settings_bridge.py',
    'local_function_actions_bridge_v5.py',
    'local_launcher.py',
    'local_launcher_v10.py',
    'local_ui_branding.py',
    'RUN_LOCAL.bat',
    'RUN_WEB.bat',
    'STOP_WEB.bat',
    'RUN_PUBLIC.bat',
    'STOP_PUBLIC.bat'
)

$webFiles = @(
    'web_control/server.js',
    'web_control/proxy_v10.js',
    'web_control/public_gateway.js',
    'web_control/function_catalog.json'
)

foreach ($p in $requiredDirs) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $p) -PathType Container)) {
        throw "Required directory is missing: $p"
    }
}
foreach ($p in ($requiredFiles + $webFiles)) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $p) -PathType Leaf)) {
        throw "Required file is missing: $p"
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot 'web_control/public') -PathType Container)) {
    throw 'Required directory is missing: web_control/public'
}

Write-Host '[2/6] Recreating clean output directory...'
if (Test-Path -LiteralPath $OutRoot) {
    Remove-Item -LiteralPath $OutRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

Write-Host '[3/6] Copying AUTO runtime...'
foreach ($p in $requiredDirs) { Copy-RequiredDir $p }
foreach ($p in $requiredFiles) { Copy-RequiredFile $p }

Write-Host '[4/6] Copying only the active Web stack...'
foreach ($p in $webFiles) { Copy-RequiredFile $p }
Copy-RequiredDir 'web_control/public'
New-Item -ItemType Directory -Force -Path (Join-Path $OutRoot 'web_control/data') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $OutRoot 'local_data') | Out-Null

# Never carry user/session/local runtime state into a distributable bundle.
$statePaths = @(
    'web_control/data/FIRST_LOGIN.txt',
    'local_data/bridge_token.txt',
    'local_data/local.db',
    'local_data/PUBLIC_URL.txt',
    'local_data/WEB_STATUS.txt'
)
foreach ($p in $statePaths) {
    $full = Join-Path $OutRoot $p
    if (Test-Path -LiteralPath $full) { Remove-Item -LiteralPath $full -Force }
}
Get-ChildItem -LiteralPath $OutRoot -Recurse -Force -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -LiteralPath $OutRoot -Recurse -Force -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Extension -in @('.log', '.tmp', '.bak')
} | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host '[5/6] Verifying bundle...'
$checks = @(
    '_internal',
    'runtime/pyc',
    'platform-tools/adb.exe',
    'assets/icon/app.ico',
    'local_launcher_v10.py',
    'local_launcher.py',
    'local_bridge.py',
    'local_options_bridge_v08.py',
    'local_settings_bridge.py',
    'local_function_actions_bridge_v5.py',
    'web_control/server.js',
    'web_control/proxy_v10.js',
    'web_control/public',
    'launchers/run_local_hidden.ps1'
)
$missing = @()
foreach ($p in $checks) {
    if (-not (Test-Path -LiteralPath (Join-Path $OutRoot $p))) { $missing += $p }
}
if ($missing.Count -gt 0) {
    throw ('Bundle verification failed. Missing: ' + ($missing -join ', '))
}

$pycCount = @(Get-ChildItem -LiteralPath (Join-Path $OutRoot 'runtime/pyc') -Recurse -File -Filter '*.pyc' -ErrorAction SilentlyContinue).Count
if ($pycCount -lt 1) { throw 'Bundle verification failed: runtime/pyc contains no .pyc files.' }

$files = @(Get-ChildItem -LiteralPath $OutRoot -Recurse -File -Force)
$totalBytes = ($files | Measure-Object -Property Length -Sum).Sum
if ($null -eq $totalBytes) { $totalBytes = 0 }

$manifest = Join-Path $OutRoot 'BUNDLE_MANIFEST.txt'
$header = @(
    'AUTO KVTM PRO CLEAN BUNDLE',
    ('Generated: ' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')),
    ('File count: ' + $files.Count),
    ('Size bytes: ' + $totalBytes),
    ('Recovered PYC count: ' + $pycCount),
    '',
    'ACTIVE ENTRY POINTS:',
    '  local_launcher_v10.py',
    '  web_control/proxy_v10.js',
    '',
    'STATE EXCLUDED:',
    '  local_data secrets/databases/logs',
    '  web_control/data user/session state',
    '  old launcher/bridge/proxy versions from the repository root',
    '',
    'FILES:'
)
$relativeFiles = $files | ForEach-Object { $_.FullName.Substring($OutRoot.Length + 1) } | Sort-Object
Set-Content -LiteralPath $manifest -Value ($header + $relativeFiles) -Encoding UTF8

$hashFile = Join-Path $OutRoot 'BUNDLE_SHA256.txt'
$hashLines = foreach ($f in (Get-ChildItem -LiteralPath $OutRoot -Recurse -File -Force | Where-Object { $_.FullName -ne $hashFile } | Sort-Object FullName)) {
    $h = Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256
    '{0}  {1}' -f $h.Hash.ToLowerInvariant(), $f.FullName.Substring($OutRoot.Length + 1)
}
Set-Content -LiteralPath $hashFile -Value $hashLines -Encoding ASCII

Write-Host '[6/6] Done.'
Write-Host ('Clean bundle: ' + $OutRoot)
Write-Host ('Files: ' + $files.Count)
Write-Host ('Recovered PYC: ' + $pycCount)
Write-Host ('Size MB: ' + [Math]::Round($totalBytes / 1MB, 2))
Write-Host ''
Write-Host 'Important: this is the clean packaging input. The current RUN_LOCAL/RUN_WEB launchers still resolve Python 3.11 and Node.js from Windows. The final EXE packaging step will bundle those runtimes so the target PC does not need them installed.'
