param()

$ErrorActionPreference = "Stop"
$ProductName = "Kvtm_tool_Cry"
$InstallRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DataRoot = Join-Path $env:APPDATA $ProductName
$LogRoot = Join-Path $DataRoot "logs"
$CurrentPath = Join-Path $InstallRoot "current.json"
$RuntimePidPath = Join-Path $DataRoot "runtime.pid.json"

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Test-CryRuntimeRunning {
    if (-not (Test-Path -LiteralPath $RuntimePidPath -PathType Leaf)) {
        return $false
    }
    try {
        $pidInfo = Read-JsonFile -Path $RuntimePidPath
        $runtimePid = [int]$pidInfo.pid
        if ($runtimePid -le 0) { return $false }
        $process = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $runtimePid) -ErrorAction SilentlyContinue
        if ($null -eq $process) { return $false }
        $commandLine = [string]$process.CommandLine
        if ([string]::IsNullOrWhiteSpace($commandLine)) { return $false }
        $installNeedle = ([System.IO.Path]::GetFullPath($InstallRoot)).ToLowerInvariant()
        return $commandLine.ToLowerInvariant().Contains($installNeedle) -and $commandLine.Contains("kvtm_multi_dev_host.py")
    }
    catch {
        return $false
    }
}

function Resolve-Python311X64 {
    $candidates = New-Object System.Collections.Generic.List[string]
    $knownUserPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
    if (Test-Path -LiteralPath $knownUserPython -PathType Leaf) {
        $candidates.Add($knownUserPython)
    }
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -ne $pythonCommand -and -not [string]::IsNullOrWhiteSpace($pythonCommand.Source)) {
        $candidates.Add($pythonCommand.Source)
    }
    $pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($null -ne $pyCommand) {
        try {
            $resolved = (& $pyCommand.Source "-3.11" "-c" "import sys;print(sys.executable)" 2>$null | Select-Object -First 1)
            if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($resolved)) {
                $candidates.Add($resolved.Trim())
            }
        }
        catch { }
    }

    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        & $candidate -c "import struct,sys;raise SystemExit(0 if sys.version_info[:2]==(3,11) and struct.calcsize('P')*8==64 else 2)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $candidate
        }
    }
    throw "Kvtm_tool_Cry requires CPython 3.11 x64."
}

if (Test-CryRuntimeRunning) {
    exit 0
}
if (Test-Path -LiteralPath $RuntimePidPath -PathType Leaf) {
    Remove-Item -LiteralPath $RuntimePidPath -Force -ErrorAction SilentlyContinue
}
if (-not (Test-Path -LiteralPath $CurrentPath -PathType Leaf)) {
    throw "Kvtm_tool_Cry install is missing current.json"
}

$current = Read-JsonFile -Path $CurrentPath
$version = [string]$current.version
$RuntimeRoot = Join-Path (Join-Path $InstallRoot "versions") $version
$MultiRoot = Join-Path $RuntimeRoot "Multi"
$HostScript = Join-Path $MultiRoot "kvtm_multi_dev_host.py"

foreach ($required in @(
    $HostScript,
    (Join-Path $MultiRoot "kvtm_multi_dev_entry.py"),
    (Join-Path $RuntimeRoot "AUTO_PRO"),
    (Join-Path $RuntimeRoot "components\clientjs-auto")
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Kvtm_tool_Cry runtime is incomplete: $required"
    }
}

$python = Resolve-Python311X64
New-Item -ItemType Directory -Path $DataRoot, $LogRoot -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stdout = Join-Path $LogRoot ("kvtm-tool-cry-" + $version + "-" + $stamp + ".out.log")
$stderr = Join-Path $LogRoot ("kvtm-tool-cry-" + $version + "-" + $stamp + ".err.log")

$env:KVTM_MULTI_APP_DIR = $DataRoot
$env:KVTM_MULTI_INSTANCE_NAME = $ProductName
$env:KVTM_MULTI_ISOLATED = "1"
$env:KVTM_PRODUCT_CHANNEL = "stable"
$env:KVTM_PRODUCT_VERSION = $version

# Stable redirects Python stdout/stderr to files. On Windows, CPython otherwise
# inherits the active ANSI code page (for example cp1252), which cannot encode
# Vietnamese UI/log text and can crash the whole resident host during startup.
# These variables are process-local to this bootstrap and inherited by the
# Stable Python child only; they do not modify the user's global environment.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"

$startOptions = @{
    FilePath = $python
    ArgumentList = @($HostScript)
    WorkingDirectory = $MultiRoot
    WindowStyle = "Hidden"
    RedirectStandardOutput = $stdout
    RedirectStandardError = $stderr
    PassThru = $true
}
$process = Start-Process @startOptions
Start-Sleep -Milliseconds 1200
if ($process.HasExited) {
    $tail = ""
    if (Test-Path -LiteralPath $stderr -PathType Leaf) {
        $tail = (Get-Content -LiteralPath $stderr -Tail 30 -ErrorAction SilentlyContinue) -join [Environment]::NewLine
    }
    throw "Kvtm_tool_Cry exited early code=$($process.ExitCode)`n$tail"
}

$pidPayload = [ordered]@{
    schema = 1
    product = $ProductName
    pid = [int]$process.Id
    version = $version
    runtime_root = $RuntimeRoot
    started_at = (Get-Date).ToUniversalTime().ToString("o")
}
[System.IO.File]::WriteAllText(
    $RuntimePidPath,
    (($pidPayload | ConvertTo-Json -Depth 5) + [Environment]::NewLine),
    [System.Text.Encoding]::UTF8
)
[System.IO.File]::WriteAllText(
    (Join-Path $LogRoot "LATEST.txt"),
    ("pid={0}`nversion={1}`nout={2}`nerr={3}`n" -f $process.Id, $version, $stdout, $stderr),
    [System.Text.Encoding]::UTF8
)
exit 0
