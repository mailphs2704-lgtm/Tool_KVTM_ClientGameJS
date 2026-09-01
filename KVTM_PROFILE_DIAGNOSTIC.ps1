param(
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $PSScriptRoot).Path
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $RepoRoot "data-profile-diagnostic"
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportPath = Join-Path $OutputDirectory ("profile-diagnostic-" + $stamp + ".txt")
$latestPath = Join-Path $OutputDirectory "LATEST.txt"

function Get-RelativeSafePath {
    param([string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    $desktop = [Environment]::GetFolderPath("Desktop")
    $appData = [Environment]::GetFolderPath("ApplicationData")
    if ($full.StartsWith($RepoRoot, [StringComparison]::OrdinalIgnoreCase)) {
        return "REPO:" + $full.Substring($RepoRoot.Length).TrimStart('\')
    }
    if ($full.StartsWith($desktop, [StringComparison]::OrdinalIgnoreCase)) {
        return "DESKTOP:" + $full.Substring($desktop.Length).TrimStart('\')
    }
    if ($full.StartsWith($appData, [StringComparison]::OrdinalIgnoreCase)) {
        return "APPDATA:" + $full.Substring($appData.Length).TrimStart('\')
    }
    return $full
}

function Read-ProfileMetadata {
    param([System.IO.FileInfo]$File)
    $valid = $false
    $count = 0
    $secretCount = 0
    $idCount = 0
    $errorText = ""
    try {
        $raw = Get-Content -LiteralPath $File.FullName -Raw -Encoding UTF8
        $parsed = $raw | ConvertFrom-Json
        $items = @($parsed)
        $count = $items.Count
        foreach ($item in $items) {
            if (-not [string]::IsNullOrWhiteSpace([string]$item.secret)) { $secretCount++ }
            if (-not [string]::IsNullOrWhiteSpace([string]$item.id)) { $idCount++ }
        }
        $valid = $true
    }
    catch {
        $errorText = $_.Exception.Message -replace "[\r\n]+", " "
    }
    $hash = "HASH_ERROR"
    try { $hash = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
    catch { }
    [pscustomobject]@{
        Path = Get-RelativeSafePath $File.FullName
        FullPath = $File.FullName
        Modified = $File.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
        ModifiedValue = $File.LastWriteTime
        Bytes = $File.Length
        Sha256 = $hash
        ValidJson = $valid
        Profiles = $count
        WithId = $idCount
        WithSecret = $secretCount
        Error = $errorText
    }
}

$roots = New-Object System.Collections.Generic.List[string]
$roots.Add($RepoRoot)
$appProfile = Join-Path ([Environment]::GetFolderPath("ApplicationData")) "KVTM Multi"
if (Test-Path -LiteralPath $appProfile -PathType Container) { $roots.Add($appProfile) }

$files = New-Object System.Collections.Generic.List[System.IO.FileInfo]
$seen = @{}
foreach ($root in $roots) {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
    Get-ChildItem -LiteralPath $root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -eq "profiles.json" -or
            $_.Name -match '^profiles\.bak[1-5]$' -or
            $_.Name -match '^profiles-before-import-.*\.json$' -or
            $_.Name -match '^profiles-\d{8}-\d{6}-\d+\.json$'
        } |
        ForEach-Object {
            $key = $_.FullName.ToLowerInvariant()
            if (-not $seen.ContainsKey($key)) {
                $seen[$key] = $true
                $files.Add($_)
            }
        }
}

$records = @($files | ForEach-Object { Read-ProfileMetadata $_ } | Sort-Object ModifiedValue -Descending)
$currentProfile = Join-Path $RepoRoot "dist\KVTM-ClientJS-Suite-Multi-DEV\data-dev\profiles.json"
$currentRecord = $records | Where-Object { $_.FullPath -eq $currentProfile } | Select-Object -First 1
$recovery = $records |
    Where-Object { $_.ValidJson -and $_.Profiles -gt 0 -and $_.WithSecret -eq $_.Profiles } |
    Sort-Object ModifiedValue -Descending

$profileRoots = @(
    (Join-Path $RepoRoot "pc_profiles"),
    (Join-Path $RepoRoot "dist\KVTM-ClientJS-Suite-Multi-DEV\pc_profiles")
)
$profileRootRows = @()
foreach ($root in $profileRoots) {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
    $allFiles = @(Get-ChildItem -LiteralPath $root -Recurse -File -ErrorAction SilentlyContinue)
    $sessionFiles = @($allFiles | Where-Object {
        $_.Name -in @("db3.sqlite", "flutter_secure_storage.dat", "shared_preferences.json", "jsb.sqlite", "UserDefault.xml")
    })
    $newest = $allFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $profileRootRows += [pscustomobject]@{
        Path = Get-RelativeSafePath $root
        Files = $allFiles.Count
        SessionFiles = $sessionFiles.Count
        Newest = if ($newest) { $newest.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss") } else { "none" }
    }
}

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("KVTM PROFILE DIAGNOSTIC - READ ONLY")
$lines.Add("timestamp=$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss K'))")
$lines.Add("repo_head=$(& git -C $RepoRoot rev-parse --short HEAD 2>$null)")
$lines.Add("repo_branch=$(& git -C $RepoRoot branch --show-current 2>$null)")
$lines.Add("current_expected=REPO:dist\KVTM-ClientJS-Suite-Multi-DEV\data-dev\profiles.json")
$lines.Add("secret_values_printed=false")
$lines.Add("files_changed=false")
$lines.Add("")
$lines.Add("=== PROFILE METADATA ===")
if ($records.Count -eq 0) {
    $lines.Add("NONE")
} else {
    foreach ($r in $records) {
        $lines.Add(("path={0}" -f $r.Path))
        $lines.Add(("modified={0} bytes={1} sha256={2}" -f $r.Modified, $r.Bytes, $r.Sha256))
        $lines.Add(("valid_json={0} profiles={1} with_id={2} with_secret={3}" -f $r.ValidJson, $r.Profiles, $r.WithId, $r.WithSecret))
        if ($r.Error) { $lines.Add(("parse_error={0}" -f $r.Error)) }
        $lines.Add("---")
    }
}
$lines.Add("")
$lines.Add("=== CURRENT DEV STATUS ===")
if ($null -eq $currentRecord) {
    $lines.Add("current_profiles_file=MISSING")
} else {
    $lines.Add(("current_profiles_file=FOUND profiles={0} with_secret={1} valid_json={2}" -f $currentRecord.Profiles, $currentRecord.WithSecret, $currentRecord.ValidJson))
}
$lines.Add("")
$lines.Add("=== RECOVERY CANDIDATES (NO AUTOMATIC RESTORE) ===")
if (@($recovery).Count -eq 0) {
    $lines.Add("NONE")
} else {
    $rank = 0
    foreach ($r in $recovery) {
        $rank++
        $lines.Add(("rank={0} path={1} modified={2} profiles={3} sha256={4}" -f $rank, $r.Path, $r.Modified, $r.Profiles, $r.Sha256))
    }
}
$lines.Add("")
$lines.Add("=== PC PROFILE / SESSION TREES ===")
if ($profileRootRows.Count -eq 0) {
    $lines.Add("NONE")
} else {
    foreach ($r in $profileRootRows) {
        $lines.Add(("path={0} files={1} known_session_files={2} newest={3}" -f $r.Path, $r.Files, $r.SessionFiles, $r.Newest))
    }
}
$lines.Add("")
$lines.Add("RESULT=READ_ONLY_COMPLETE")
$lines | Set-Content -LiteralPath $reportPath -Encoding UTF8
[System.IO.File]::WriteAllText($latestPath, ($reportPath + [Environment]::NewLine), [System.Text.Encoding]::UTF8)

Write-Host "PROFILE DIAGNOSTIC READ-ONLY COMPLETE" -ForegroundColor Green
Write-Host "Report: $reportPath"
Write-Host "Candidates: $(@($recovery).Count)"
Write-Host "No secret values printed. No profile/session files changed." -ForegroundColor Cyan
