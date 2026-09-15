param(
    [ValidateSet("Start", "Watch", "Stop", "Status")]
    [string]$Mode = "Start",
    [string]$SessionId = "",
    [int]$PollMilliseconds = 1500,
    [int]$LookbackHours = 24,
    [int]$BeforeLines = 10,
    [int]$AfterLines = 12
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$DataRoot = Join-Path $env:APPDATA "KVTM Multi DEV"
$CaptureRoot = Join-Path $DataRoot "error-captures"
$PidPath = Join-Path $CaptureRoot "collector.pid"
$LatestPath = Join-Path $CaptureRoot "LATEST.txt"
$ScriptPath = $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$UploadScript = Join-Path $PSScriptRoot "KVTM_ERROR_LOG_UPLOAD.ps1"

function Get-CollectorPid {
    if (-not (Test-Path -LiteralPath $PidPath -PathType Leaf)) {
        return 0
    }
    try {
        $value = [int]((Get-Content -LiteralPath $PidPath -Raw).Trim())
        $process = Get-Process -Id $value -ErrorAction Stop
        if ($null -ne $process) {
            return $value
        }
    }
    catch {
        Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
    }
    return 0
}

function Get-SourceFiles {
    $cutoff = (Get-Date).AddHours(-1 * [Math]::Abs($LookbackHours))
    $roots = @(
        (Join-Path $DataRoot "auto-multi-dev"),
        (Join-Path $DataRoot "auto-logs"),
        (Join-Path $DataRoot "logs")
    )
    $items = New-Object System.Collections.Generic.List[System.IO.FileInfo]
    foreach ($root in $roots) {
        if (-not (Test-Path -LiteralPath $root -PathType Container)) {
            continue
        }
        Get-ChildItem -LiteralPath $root -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object {
                $_.LastWriteTime -ge $cutoff -and (
                    $_.Name -eq "action.log" -or
                    $_.Name -eq "detail.log" -or
                    $_.Extension -eq ".jsonl" -or
                    $_.Name -like "*.out.log" -or
                    $_.Name -like "*.err.log"
                )
            } |
            ForEach-Object { [void]$items.Add($_) }
    }
    return @($items)
}

function Add-OutputLine {
    param([string]$Path, [string]$Text)
    [System.IO.File]::AppendAllText(
        $Path,
        $Text + [Environment]::NewLine,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

if ($Mode -eq "Status") {
    $runningPid = Get-CollectorPid
    if ($runningPid -gt 0) {
        Write-Host ("KVTM ERROR COLLECTOR RUNNING pid={0}" -f $runningPid) -ForegroundColor Green
        if (Test-Path -LiteralPath $LatestPath) {
            Get-Content -LiteralPath $LatestPath
        }
        exit 0
    }
    Write-Host "KVTM ERROR COLLECTOR NOT RUNNING" -ForegroundColor Yellow
    exit 1
}

if ($Mode -eq "Stop") {
    $runningPid = Get-CollectorPid
    if ($runningPid -le 0) {
        Write-Host "KVTM ERROR COLLECTOR NOT RUNNING" -ForegroundColor Yellow
        exit 0
    }
    Stop-Process -Id $runningPid -ErrorAction Stop
    Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
    Write-Host ("STOPPED ERROR COLLECTOR pid={0}; Multi/Auto untouched" -f $runningPid) -ForegroundColor Green
    exit 0
}

if ($Mode -eq "Start") {
    New-Item -ItemType Directory -Path $CaptureRoot -Force | Out-Null
    $runningPid = Get-CollectorPid
    if ($runningPid -gt 0) {
        Write-Host ("ERROR COLLECTOR ALREADY RUNNING pid={0}" -f $runningPid) -ForegroundColor Yellow
        if (Test-Path -LiteralPath $LatestPath) {
            Get-Content -LiteralPath $LatestPath
        }
        exit 0
    }

    if ([string]::IsNullOrWhiteSpace($SessionId)) {
        $SessionId = Get-Date -Format "yyyyMMdd-HHmmss"
    }
    $sessionRoot = Join-Path $CaptureRoot $SessionId
    New-Item -ItemType Directory -Path $sessionRoot -Force | Out-Null
    $quotedScript = '"' + $ScriptPath + '"'
    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $quotedScript,
        "-Mode", "Watch",
        "-SessionId", $SessionId,
        "-PollMilliseconds", [string]$PollMilliseconds,
        "-LookbackHours", [string]$LookbackHours,
        "-BeforeLines", [string]$BeforeLines,
        "-AfterLines", [string]$AfterLines
    )
    $child = Start-Process -FilePath "powershell.exe" -ArgumentList $arguments -WindowStyle Hidden -PassThru
    Start-Sleep -Milliseconds 500
    if ($child.HasExited) {
        throw "Error collector exited early with code $($child.ExitCode)"
    }
    Write-Host ("KVTM ERROR COLLECTOR STARTED IN BACKGROUND pid={0}" -f $child.Id) -ForegroundColor Green
    Write-Host ("Output: {0}" -f (Join-Path $sessionRoot "errors.log")) -ForegroundColor Cyan
    Write-Host "Multi, Auto and ClientJS were not stopped or controlled."
    exit 0
}

New-Item -ItemType Directory -Path $CaptureRoot -Force | Out-Null
if ([string]::IsNullOrWhiteSpace($SessionId)) {
    $SessionId = Get-Date -Format "yyyyMMdd-HHmmss"
}
$SessionRoot = Join-Path $CaptureRoot $SessionId
New-Item -ItemType Directory -Path $SessionRoot -Force | Out-Null
$OutputPath = Join-Path $SessionRoot "errors.log"
$StatusPath = Join-Path $SessionRoot "collector-status.log"
$ErrorPattern = "(?i)(ERROR|FAIL|SAFE_ABORT|ScreenTimeout|Timeout|Exception|Traceback|worker_stopped|unregistered_runtime_error|STORAGE_FULL|KHO_QUA_TAI|fatal|exited early)"
$states = @{}
$UploadPending = $false
$UploadDueAt = [DateTime]::MinValue
$LastUploadAt = [DateTime]::MinValue

[System.IO.File]::WriteAllText($PidPath, [string]$PID, (New-Object System.Text.UTF8Encoding($false)))
[System.IO.File]::WriteAllText(
    $LatestPath,
    ("pid={0}`nsession={1}`nerrors={2}`nstatus={3}`n" -f $PID, $SessionRoot, $OutputPath, $StatusPath),
    (New-Object System.Text.UTF8Encoding($false))
)
Add-OutputLine -Path $StatusPath -Text ("START {0:yyyy-MM-dd HH:mm:ss} pid={1}" -f (Get-Date), $PID)
Add-OutputLine -Path $StatusPath -Text "READ-ONLY sources: action.log, detail.log, auto JSONL, host stdout/stderr"
Add-OutputLine -Path $StatusPath -Text "NO process control: Multi/Auto/ClientJS are untouched"
Add-OutputLine -Path $StatusPath -Text "AUTO UPLOAD: sanitized text only -> diagnostics/runtime-errors"

try {
    while ($true) {
        foreach ($file in Get-SourceFiles) {
            $key = $file.FullName.ToLowerInvariant()
            if (-not $states.ContainsKey($key)) {
                $queue = New-Object "System.Collections.Generic.Queue[string]"
                $initialOffset = [Math]::Max(0L, [int64]$file.Length - 1048576L)
                $states[$key] = [pscustomobject]@{
                    Path = $file.FullName
                    Offset = $initialOffset
                    Carry = ""
                    Before = $queue
                    After = 0
                    StartedMidFile = ($initialOffset -gt 0)
                }
            }

            $state = $states[$key]
            try {
                $info = Get-Item -LiteralPath $state.Path -ErrorAction Stop
                if ([int64]$info.Length -lt [int64]$state.Offset) {
                    $state.Offset = 0L
                    $state.Carry = ""
                    $state.Before.Clear()
                    $state.After = 0
                    $state.StartedMidFile = $false
                }
                if ([int64]$info.Length -eq [int64]$state.Offset) {
                    continue
                }

                $share = [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
                $stream = [System.IO.File]::Open(
                    $state.Path,
                    [System.IO.FileMode]::Open,
                    [System.IO.FileAccess]::Read,
                    $share
                )
                try {
                    [void]$stream.Seek([int64]$state.Offset, [System.IO.SeekOrigin]::Begin)
                    $remaining = [int]($stream.Length - $stream.Position)
                    if ($remaining -le 0) {
                        continue
                    }
                    $buffer = New-Object byte[] $remaining
                    $read = $stream.Read($buffer, 0, $remaining)
                    $state.Offset = [int64]$stream.Position
                }
                finally {
                    $stream.Dispose()
                }

                $text = $state.Carry + [System.Text.Encoding]::UTF8.GetString($buffer, 0, $read)
                $parts = [regex]::Split($text, "\r?\n")
                $state.Carry = $parts[$parts.Count - 1]
                $complete = @($parts[0..([Math]::Max(0, $parts.Count - 2))])
                if ($parts.Count -le 1) {
                    $complete = @()
                }
                if ($state.StartedMidFile -and $complete.Count -gt 0) {
                    $complete = @($complete | Select-Object -Skip 1)
                    $state.StartedMidFile = $false
                }

                foreach ($line in $complete) {
                    $isError = $line -match $ErrorPattern
                    if ($state.After -gt 0) {
                        Add-OutputLine -Path $OutputPath -Text $line
                        $state.After -= 1
                        if ($isError) {
                            $state.After = $AfterLines
                        }
                        continue
                    }

                    if ($isError) {
                        Add-OutputLine -Path $OutputPath -Text ""
                        Add-OutputLine -Path $OutputPath -Text ("===== ERROR {0:yyyy-MM-dd HH:mm:ss} =====" -f (Get-Date))
                        Add-OutputLine -Path $OutputPath -Text ("SOURCE: {0}" -f $state.Path)
                        foreach ($previous in $state.Before) {
                            Add-OutputLine -Path $OutputPath -Text $previous
                        }
                        Add-OutputLine -Path $OutputPath -Text $line
                        $state.After = $AfterLines
                        # Allow the configured after-lines to arrive before a
                        # separate process sanitizes and uploads this session.
                        if ((Get-Date) -ge $LastUploadAt.AddSeconds(60)) {
                            $UploadPending = $true
                            $UploadDueAt = (Get-Date).AddSeconds(5)
                        }
                    }
                    else {
                        $state.Before.Enqueue($line)
                        while ($state.Before.Count -gt $BeforeLines) {
                            [void]$state.Before.Dequeue()
                        }
                    }
                }
            }
            catch {
                Add-OutputLine -Path $StatusPath -Text (
                    "READ WARNING {0:yyyy-MM-dd HH:mm:ss} file={1} error={2}" -f
                    (Get-Date), $state.Path, $_.Exception.Message
                )
            }
        }
        if (
            $UploadPending -and
            (Get-Date) -ge $UploadDueAt -and
            (Test-Path -LiteralPath $UploadScript -PathType Leaf)
        ) {
            try {
                $uploadArgs = @(
                    "-NoProfile",
                    "-ExecutionPolicy", "Bypass",
                    "-File", ('"' + $UploadScript + '"'),
                    "-RepoRoot", ('"' + $RepoRoot + '"'),
                    "-SessionRoot", ('"' + $SessionRoot + '"')
                )
                [void](Start-Process -FilePath "powershell.exe" -ArgumentList $uploadArgs -WindowStyle Hidden -PassThru)
                $LastUploadAt = Get-Date
                Add-OutputLine -Path $StatusPath -Text (
                    "AUTO UPLOAD QUEUED {0:yyyy-MM-dd HH:mm:ss} branch=diagnostics/runtime-errors" -f
                    $LastUploadAt
                )
            }
            catch {
                Add-OutputLine -Path $StatusPath -Text (
                    "AUTO UPLOAD WARNING {0:yyyy-MM-dd HH:mm:ss} error={1}" -f
                    (Get-Date), $_.Exception.Message
                )
            }
            $UploadPending = $false
        }
        Start-Sleep -Milliseconds ([Math]::Max(500, $PollMilliseconds))
    }
}
finally {
    $recorded = Get-CollectorPid
    if ($recorded -eq $PID) {
        Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
    }
    Add-OutputLine -Path $StatusPath -Text ("STOP {0:yyyy-MM-dd HH:mm:ss} pid={1}" -f (Get-Date), $PID)
}
