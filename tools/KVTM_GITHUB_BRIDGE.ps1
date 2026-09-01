param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("SendReport", "UpdateDev")]
    [string]$Mode,

    [string]$SyncBranch = "machine-sync/cry-pc"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RepoUrl = "https://github.com/mailphs2704-lgtm/Tool_KVTM_ClientGameJS.git"
$DevBranch = "develop/multi-auto-dev"
$SetupScript = Join-Path $PSScriptRoot "KVTM_MACHINE_SETUP.ps1"
$BootstrapScript = Join-Path $RepoRoot "KVTM_SECONDARY_BOOTSTRAP.ps1"
$LocalSyncDir = Join-Path $RepoRoot "data-machine-sync"

function Resolve-KvtmGit {
    $cmd = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd -and $cmd.Source) { return [string]$cmd.Source }
    $candidates = @()
    if ($env:ProgramFiles) { $candidates += (Join-Path $env:ProgramFiles "Git\cmd\git.exe") }
    if (${env:ProgramFiles(x86)}) { $candidates += (Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe") }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return [string]$candidate }
    }
    return $null
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    $parent = Split-Path -Parent $Path
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $utf8)
}

function Protect-LocalPaths {
    param([string]$Text)
    $result = [string]$Text
    foreach ($pair in @(
        @($env:LOCALAPPDATA, '%LOCALAPPDATA%'),
        @($env:APPDATA, '%APPDATA%'),
        @($env:USERPROFILE, '%USERPROFILE%')
    )) {
        if (-not [string]::IsNullOrWhiteSpace([string]$pair[0])) {
            $result = $result -replace [regex]::Escape([string]$pair[0]), [string]$pair[1]
        }
    }
    return $result
}

function Get-SafeDiagnosticText {
    param([Parameter(Mandatory = $true)][string]$DiagnosticPath)

    $allowedKeys = @{
        'timestamp' = $true
        'computer' = $true
        'windows64' = $true
        'powershell' = $true
        'install_missing_requested' = $true
        'winget' = $true
        'git' = $true
        'git_lfs' = $true
        'python311_x64' = $true
        'vc_redist_x64' = $true
        'vc_redist_x86' = $true
        'game_client' = $true
        'game_data' = $true
        'repo' = $true
        'branch' = $true
        'expected_branch' = $true
        'head' = $true
        'working_tree' = $true
        'runtime' = $true
        'RESULT' = $true
        'blocking' = $true
        'secret_values_printed' = $true
    }

    $safe = New-Object System.Collections.Generic.List[string]
    foreach ($rawLine in (Get-Content -LiteralPath $DiagnosticPath -Encoding UTF8)) {
        $line = [string]$rawLine
        if ([string]::IsNullOrWhiteSpace($line)) {
            $safe.Add('')
            continue
        }
        if ($line -eq 'KVTM SECONDARY MACHINE DIAGNOSTIC' -or $line -match '^=== [A-Z0-9 /+_-]+ ===$') {
            $safe.Add($line)
            continue
        }
        $eq = $line.IndexOf('=')
        if ($eq -le 0) { continue }
        $key = $line.Substring(0, $eq).Trim()
        if (-not $allowedKeys.ContainsKey($key)) { continue }
        $value = $line.Substring($eq + 1)
        if ($key -eq 'secret_values_printed' -and $value.Trim().ToLowerInvariant() -ne 'false') {
            throw 'Diagnostic bi chan: secret_values_printed khong phai false.'
        }
        $safe.Add((Protect-LocalPaths ($key + '=' + $value)))
    }

    if (-not ($safe -contains 'secret_values_printed=false')) {
        $safe.Add('secret_values_printed=false')
    }

    $text = ($safe -join "`r`n") + "`r`n"
    foreach ($blocked in @('.kvtm', 'profiles.json', 'authorization:', 'password=', 'cookie=', 'token=')) {
        if ($text.IndexOf($blocked, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            throw "Diagnostic bi chan boi safety filter: $blocked"
        }
    }
    return $text
}

function Invoke-SendReport {
    $git = Resolve-KvtmGit
    if ([string]::IsNullOrWhiteSpace($git)) { throw 'Khong tim thay git.exe.' }
    if (-not (Test-Path -LiteralPath $SetupScript -PathType Leaf)) { throw "Thieu $SetupScript" }

    Write-Host '=== KVTM GITHUB BRIDGE - SEND REPORT ===' -ForegroundColor Cyan
    Write-Host '[1/4] Tao diagnostic moi (READ-ONLY)...'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SetupScript
    $diagExit = $LASTEXITCODE
    if ($diagExit -ne 0) {
        Write-Host "[INFO] Diagnostic tra exit=$diagExit; van gui report de ChatGPT doc blocker." -ForegroundColor Yellow
    }

    $latestPointer = Join-Path $RepoRoot 'data-machine-diagnostic\LATEST.txt'
    if (-not (Test-Path -LiteralPath $latestPointer -PathType Leaf)) { throw 'Khong tim thay LATEST.txt cua diagnostic.' }
    $diagPath = (Get-Content -LiteralPath $latestPointer -Raw -Encoding UTF8).Trim()
    if (-not (Test-Path -LiteralPath $diagPath -PathType Leaf)) { throw "Diagnostic file khong ton tai: $diagPath" }
    $safeDiagnostic = Get-SafeDiagnosticText -DiagnosticPath $diagPath

    [object[]]$headOutput = @(& $git -C $RepoRoot rev-parse HEAD 2>$null)
    $headExit = $LASTEXITCODE
    [string]$head = ($headOutput | Select-Object -First 1)
    if ($headExit -ne 0 -or [string]::IsNullOrWhiteSpace($head)) { throw 'Khong doc duoc repo HEAD.' }
    [string]$branch = (& $git -C $RepoRoot branch --show-current | Select-Object -First 1)
    [object[]]$dirty = @(& $git -C $RepoRoot status --porcelain)

    $machine = [regex]::Replace([string]$env:COMPUTERNAME, '[^A-Za-z0-9._-]', '_')
    if ([string]::IsNullOrWhiteSpace($machine)) { $machine = 'SECONDARY' }
    $meta = @(
        '',
        '=== GITHUB BRIDGE META ===',
        ('sent_at=' + [DateTimeOffset]::Now.ToString('yyyy-MM-dd HH:mm:ss zzz')),
        ('source_branch=' + $branch),
        ('source_head=' + $head),
        ('working_tree_entry_count=' + $dirty.Count),
        'payload=SAFE_DIAGNOSTIC_ONLY',
        'profile_data_uploaded=false',
        'transfer_file_uploaded=false'
    ) -join "`r`n"
    $reportText = $safeDiagnostic.TrimEnd() + "`r`n" + $meta + "`r`n"

    Write-Host '[2/4] Tao temp Git repo tach biet khoi DEV working tree...'
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('kvtm-github-bridge-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
    $oldSkip = $env:GIT_LFS_SKIP_SMUDGE
    $env:GIT_LFS_SKIP_SMUDGE = '1'
    try {
        & $git -C $tempRoot init | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'git init temp fail' }
        & $git -C $tempRoot remote add origin $RepoUrl
        if ($LASTEXITCODE -ne 0) { throw 'git remote add fail' }
        & $git -C $tempRoot config user.name 'KVTM Secondary Machine'
        & $git -C $tempRoot config user.email 'kvtm-secondary@local.invalid'

        Write-Host "[3/4] Cap nhat branch report rieng: $SyncBranch"
        & $git -C $tempRoot ls-remote --exit-code origin ("refs/heads/" + $SyncBranch) *> $null
        $remoteExists = ($LASTEXITCODE -eq 0)
        if ($remoteExists) {
            & $git -C $tempRoot fetch --depth=1 origin $SyncBranch
            if ($LASTEXITCODE -ne 0) { throw 'git fetch sync branch fail' }
            & $git -C $tempRoot checkout -B $SyncBranch FETCH_HEAD | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'git checkout sync branch fail' }
        }
        else {
            & $git -C $tempRoot checkout --orphan $SyncBranch | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'git checkout --orphan sync branch fail' }
        }

        $reportRel = ('machine-reports/' + $machine + '/LATEST.txt')
        $reportPath = Join-Path $tempRoot ($reportRel -replace '/', '\')
        Write-Utf8NoBom -Path $reportPath -Text $reportText
        & $git -C $tempRoot add -- $reportRel
        if ($LASTEXITCODE -ne 0) { throw 'git add report fail' }

        & $git -C $tempRoot diff --cached --quiet
        if ($LASTEXITCODE -eq 0) {
            Write-Host '[INFO] Report khong thay doi; GitHub da co cung noi dung.' -ForegroundColor Yellow
            [string]$commit = (& $git -C $tempRoot rev-parse HEAD | Select-Object -First 1)
        }
        else {
            & $git -C $tempRoot commit -m ("Secondary report " + $machine + " " + [DateTimeOffset]::Now.ToString('yyyy-MM-dd HH:mm:ss zzz')) | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'git commit report fail' }
            & $git -C $tempRoot push origin ("HEAD:refs/heads/" + $SyncBranch)
            if ($LASTEXITCODE -ne 0) { throw 'git push report fail. Kiem tra GitHub credential/quyen push.' }
            [string]$commit = (& $git -C $tempRoot rev-parse HEAD | Select-Object -First 1)
        }

        Write-Host '[4/4] Luu receipt local...'
        New-Item -ItemType Directory -Path $LocalSyncDir -Force | Out-Null
        $receipt = @(
            ('branch=' + $SyncBranch),
            ('report=' + $reportRel),
            ('commit=' + $commit),
            ('sent_at=' + [DateTimeOffset]::Now.ToString('yyyy-MM-dd HH:mm:ss zzz')),
            'safe_diagnostic_only=true'
        ) -join "`r`n"
        Write-Utf8NoBom -Path (Join-Path $LocalSyncDir 'LAST_SEND.txt') -Text ($receipt + "`r`n")

        Write-Host ''
        Write-Host 'REPORT PUSHED OK' -ForegroundColor Green
        Write-Host "Branch: $SyncBranch"
        Write-Host "Report: $reportRel"
        Write-Host "Commit: $commit"
        Write-Host 'Chi can nhan ChatGPT: da gui report may phu.' -ForegroundColor Cyan
        Write-Host 'Khong co .kvtm / profiles.json / secret duoc upload.' -ForegroundColor Green
    }
    finally {
        $env:GIT_LFS_SKIP_SMUDGE = $oldSkip
        if (Test-Path -LiteralPath $tempRoot) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-UpdateDev {
    if (-not (Test-Path -LiteralPath $BootstrapScript -PathType Leaf)) { throw "Thieu $BootstrapScript" }
    Write-Host '=== KVTM GITHUB BRIDGE - UPDATE DEV ===' -ForegroundColor Cyan
    Write-Host "Source: origin/$DevBranch"
    Write-Host 'Se pull fast-forward, cai dependency con thieu, Git LFS pull va build DEV runtime.' -ForegroundColor Yellow
    Write-Host 'data-dev/profile cua runtime duoc builder bao toan theo co che hien tai.' -ForegroundColor Cyan
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $BootstrapScript -TargetDirectory $RepoRoot -BuildRuntime
    $rc = $LASTEXITCODE
    if ($rc -ne 0) {
        Write-Host ''
        Write-Host "[FAIL] UPDATE DEV exit=$rc" -ForegroundColor Red
        Write-Host 'Chon [8] Gui report may phu de ChatGPT doc blocker moi.' -ForegroundColor Yellow
        exit $rc
    }

    $git = Resolve-KvtmGit
    [string]$head = ''
    if ($git) { $head = (& $git -C $RepoRoot rev-parse --short HEAD | Select-Object -First 1) }
    New-Item -ItemType Directory -Path $LocalSyncDir -Force | Out-Null
    Write-Utf8NoBom -Path (Join-Path $LocalSyncDir 'LAST_UPDATE.txt') -Text ((@(
        ('updated_at=' + [DateTimeOffset]::Now.ToString('yyyy-MM-dd HH:mm:ss zzz')),
        ('branch=' + $DevBranch),
        ('head=' + $head),
        'result=PASS'
    ) -join "`r`n") + "`r`n")

    Write-Host ''
    Write-Host 'DEV UPDATE OK' -ForegroundColor Green
    Write-Host "HEAD: $head"
}

switch ($Mode) {
    'SendReport' { Invoke-SendReport }
    'UpdateDev' { Invoke-UpdateDev }
}
