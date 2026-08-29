$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Data = Join-Path $Root 'local_data'
$Script = Join-Path $Root 'local_launcher_v10.py'
New-Item -ItemType Directory -Force -Path $Data | Out-Null

function Show-Error([string]$text) {
    try {
        Add-Type -AssemblyName PresentationFramework -ErrorAction SilentlyContinue
        [System.Windows.MessageBox]::Show($text, 'AUTO KVTM PRO - LỖI') | Out-Null
    } catch {}
}

try {
    if (-not (Test-Path $Script)) { throw "Không tìm thấy $Script" }

    # Do not launch a second copy of the same AUTO launcher.
    $existing = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        ($_.Name -ieq 'pythonw.exe' -or $_.Name -ieq 'python.exe') -and
        $_.CommandLine -match 'local_launcher_v10\.py'
    } | Select-Object -First 1
    if ($existing) { exit 0 }

    $pythonw = $null

    # Preferred: resolve the exact Python 3.11 installation through py.exe.
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        $exe = (& $py.Source -3.11 -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1)
        if ($LASTEXITCODE -eq 0 -and $exe) {
            $candidate = Join-Path (Split-Path -Parent $exe.Trim()) 'pythonw.exe'
            if (Test-Path $candidate) { $pythonw = $candidate }
        }
    }

    # Fallback: python.exe in PATH, only when it is Python 3.11.
    if (-not $pythonw) {
        $python = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($python) {
            $ver = (& $python.Source -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null | Select-Object -First 1)
            if ($ver -eq '3.11') {
                $candidate = Join-Path (Split-Path -Parent $python.Source) 'pythonw.exe'
                if (Test-Path $candidate) { $pythonw = $candidate }
            }
        }
    }

    # Common per-user install location as a final fallback.
    if (-not $pythonw) {
        $candidate = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\pythonw.exe'
        if (Test-Path $candidate) { $pythonw = $candidate }
    }

    if (-not $pythonw) {
        throw "Không tìm thấy Python 3.11 / pythonw.exe.`n`nCài bằng:`nwinget install -e --id Python.Python.3.11"
    }

    Start-Process -FilePath $pythonw -ArgumentList @('"' + $Script + '"') -WorkingDirectory $Root -WindowStyle Hidden | Out-Null
} catch {
    $msg = $_.Exception.Message
    Add-Content -Path (Join-Path $Data 'launcher_start_error.log') -Value ((Get-Date).ToString('s') + ' ' + $msg) -Encoding utf8
    Show-Error $msg
    exit 1
}
