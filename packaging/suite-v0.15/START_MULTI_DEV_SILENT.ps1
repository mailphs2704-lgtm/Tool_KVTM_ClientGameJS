param()

$ErrorActionPreference = "Stop"
$PackageRoot = (Resolve-Path $PSScriptRoot).Path
$MultiRoot = Join-Path $PackageRoot "Multi"
$HostScript = Join-Path $MultiRoot "kvtm_multi_dev_host.py"
$DataRoot = Join-Path $PackageRoot "data-dev"
$LogRoot = Join-Path $DataRoot "logs"

foreach ($required in @(
    $HostScript,
    (Join-Path $MultiRoot "kvtm_multi_dev_entry.py"),
    (Join-Path $MultiRoot "clear_stall_probe_console.py"),
    (Join-Path $PackageRoot "AUTO_PRO"),
    (Join-Path $PackageRoot "components\clientjs-auto")
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Missing DEV runtime path: $required"
    }
}

$escapedHost = [Regex]::Escape($HostScript)
$existing = @(
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { [string]$_.CommandLine -match $escapedHost }
)
if ($existing.Count -gt 0) {
    Write-Host ("MULTI DEV ALREADY RUNNING pid={0}" -f $existing[0].ProcessId) -ForegroundColor Yellow
    exit 0
}

$python = $null
$candidates = New-Object System.Collections.Generic.List[string]
$knownUserPython = Join-Path $env:LOCALAPPDATA "Programs\\Python\\Python311\\python.exe"
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
        $python = $candidate
        break
    }
}
if ([string]::IsNullOrWhiteSpace($python)) {
    throw "CPython 3.11 x64 not found in LocalAppData, py.exe or PATH."
}

New-Item -ItemType Directory -Path $DataRoot, $LogRoot -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stdout = Join-Path $LogRoot ("multi-dev-host-" + $stamp + ".out.log")
$stderr = Join-Path $LogRoot ("multi-dev-host-" + $stamp + ".err.log")

$env:KVTM_MULTI_APP_DIR = $DataRoot
$env:KVTM_MULTI_INSTANCE_NAME = "KVTM Multi DEV"
$env:KVTM_MULTI_ISOLATED = "1"

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
    $errorTail = ""
    if (Test-Path -LiteralPath $stderr) {
        $errorTail = (Get-Content -LiteralPath $stderr -Tail 20 -ErrorAction SilentlyContinue) -join [Environment]::NewLine
    }
    throw "Multi DEV exited early code=$($process.ExitCode)`n$errorTail"
}

[System.IO.File]::WriteAllText(
    (Join-Path $LogRoot "LATEST.txt"),
    ("pid={0}`nout={1}`nerr={2}`n" -f $process.Id, $stdout, $stderr),
    [System.Text.Encoding]::UTF8
)
Write-Host ("MULTI DEV SILENT STARTED pid={0}" -f $process.Id) -ForegroundColor Green
Write-Host ("Logs: {0}" -f $LogRoot)
