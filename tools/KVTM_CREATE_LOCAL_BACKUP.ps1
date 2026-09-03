param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
$git = (Get-Command git.exe -ErrorAction Stop).Source
$head = (& $git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or -not $head) {
    throw "Khong doc duoc Git HEAD."
}
$short = $head.Substring(0, [Math]::Min(8, $head.Length))
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $repo "local-backups"
$destination = Join-Path $backupRoot ("KVTM-" + $stamp + "-" + $short)
$runtimeSource = Join-Path $repo "dist\KVTM-ClientJS-Suite-Multi-DEV"
$runtimeTarget = Join-Path $destination "runtime"
$privateTarget = Join-Path $destination "private-data"

New-Item -ItemType Directory -Force -Path $destination | Out-Null
$bundle = Join-Path $destination "source.bundle"
& $git -C $repo bundle create $bundle HEAD
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $bundle)) {
    throw "Khong tao duoc source.bundle."
}

if (Test-Path -LiteralPath $runtimeSource) {
    New-Item -ItemType Directory -Force -Path $runtimeTarget | Out-Null
    & robocopy $runtimeSource $runtimeTarget /E /R:1 /W:1 /XD data-dev /XF *.log *.tmp | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "Khong sao luu duoc runtime; robocopy=$LASTEXITCODE"
    }

    $dataSource = Join-Path $runtimeSource "data-dev"
    New-Item -ItemType Directory -Force -Path $privateTarget | Out-Null
    foreach ($name in @("profiles.json", "settings.json")) {
        $source = Join-Path $dataSource $name
        if (Test-Path -LiteralPath $source) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $privateTarget $name) -Force
        }
    }
}

$manifest = [ordered]@{
    schema_version = 1
    created_at = (Get-Date).ToString("o")
    source_head = $head
    branch = (& $git -C $repo branch --show-current).Trim()
    runtime_copied = (Test-Path -LiteralPath $runtimeTarget)
    private_data_local_only = $true
    restore_note = "Source bundle + runtime snapshot. profiles/settings chi dung noi bo tren cung may Windows."
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $destination "manifest.json") -Encoding UTF8

Write-Host ""
Write-Host "[PASS] Da tao backup cuc bo:" -ForegroundColor Green
Write-Host $destination
Write-Host "[SAFE] Backup khong duoc upload len GitHub."
Start-Process explorer.exe -ArgumentList $destination
