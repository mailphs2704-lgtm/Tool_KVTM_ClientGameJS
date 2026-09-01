param()

$ErrorActionPreference = "Stop"
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$WorkspaceScript = Join-Path $PSScriptRoot "kvtm_workspace.py"
$MainDevRoot = if ($env:KVTM_MULTI_DEV_ROOT) {
    [IO.Path]::GetFullPath($env:KVTM_MULTI_DEV_ROOT)
} else {
    Join-Path $env:USERPROFILE "Desktop\Tool_KVTM_Multi_DEV"
}
$DriverRoot = Join-Path $MainDevRoot "dist\KVTM-ClientJS-Suite-Multi-DEV\Multi"
$LogRoot = Join-Path $WorkspaceRoot "data-workspace\logs"

foreach ($required in @($WorkspaceScript, (Join-Path $DriverRoot "pc_driver.py"))) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Missing Workspace runtime path: $required"
    }
}

$python = $null
$known = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
$candidates = @($known)
$py = Get-Command py.exe -ErrorAction SilentlyContinue
if ($py) {
    try {
        [object[]]$rows = @(& $py.Source -3.11 -c "import sys;print(sys.executable)" 2>$null)
        $rc = $LASTEXITCODE
        [string]$resolved = ($rows | Select-Object -First 1)
        if ($rc -eq 0 -and -not [string]::IsNullOrWhiteSpace($resolved)) {
            $candidates += $resolved.Trim()
        }
    } catch { }
}
foreach ($candidate in @($candidates | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
    & $candidate -c "import struct,sys;raise SystemExit(0 if sys.version_info[:2]==(3,11) and struct.calcsize('P')*8==64 else 2)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $python = $candidate
        break
    }
}
if (-not $python) { throw "CPython 3.11 x64 not found." }

$escaped = [Regex]::Escape($WorkspaceScript)
$existing = @(
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { [string]$_.CommandLine -match $escaped }
)
if ($existing.Count -gt 0) {
    Write-Host ("WORKSPACE ALREADY RUNNING pid={0}" -f $existing[0].ProcessId)
    exit 0
}

New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stdout = Join-Path $LogRoot ("workspace-" + $stamp + ".out.log")
$stderr = Join-Path $LogRoot ("workspace-" + $stamp + ".err.log")
$oldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $DriverRoot + ";" + $PSScriptRoot
try {
    $startOptions = @{
        FilePath = $python
        ArgumentList = @($WorkspaceScript)
        WorkingDirectory = $WorkspaceRoot
        WindowStyle = "Hidden"
        RedirectStandardOutput = $stdout
        RedirectStandardError = $stderr
        PassThru = $true
    }
    $process = Start-Process @startOptions
} finally {
    $env:PYTHONPATH = $oldPythonPath
}

Start-Sleep -Milliseconds 1000
if ($process.HasExited) {
    $tail = ""
    if (Test-Path -LiteralPath $stderr) {
        $tail = (Get-Content -LiteralPath $stderr -Tail 20 -ErrorAction SilentlyContinue) -join [Environment]::NewLine
    }
    throw ("Workspace exited early code={0}: {1}" -f $process.ExitCode, $tail)
}
Write-Host ("WORKSPACE SILENT STARTED pid={0}" -f $process.Id)
Write-Host ("Logs: {0}" -f $LogRoot)
