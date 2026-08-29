$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Data = Join-Path $Root 'local_data'
New-Item -ItemType Directory -Force -Path $Data | Out-Null

function Show-Error([string]$text) {
    try {
        Add-Type -AssemblyName PresentationFramework -ErrorAction SilentlyContinue
        [System.Windows.MessageBox]::Show($text, 'AUTO KVTM WEB - ERROR') | Out-Null
    } catch {}
}

function Resolve-Node {
    try { return (Get-Command node.exe -ErrorAction Stop).Source } catch {}
    $candidates = @(
        (Join-Path $env:ProgramFiles 'nodejs\node.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\nodejs\node.exe')
    )
    if (${env:ProgramFiles(x86)}) {
        $candidates += (Join-Path ${env:ProgramFiles(x86)} 'nodejs\node.exe')
    }
    return ($candidates | Where-Object { Test-Path $_ } | Select-Object -First 1)
}

try {
    $node = Resolve-Node
    if (-not $node) { throw 'Node.js was not found. Install Node.js LTS first.' }

    $proxy = Join-Path $Root 'web_control\proxy_v10.js'
    if (-not (Test-Path $proxy)) { throw ('Missing file: ' + $proxy) }

    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -ieq 'node.exe' -and $_.CommandLine -match 'web_control[\\/](server|proxy_v10)\.js'
    } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 700

    $log = Join-Path $Data 'web_console.log'
    Remove-Item $log -Force -ErrorAction SilentlyContinue

    $quotedNode = '"' + $node + '"'
    $quotedProxy = '"' + $proxy + '"'
    $quotedLog = '"' + $log + '"'
    $command = "$quotedNode $quotedProxy >> $quotedLog 2>&1"
    $cmd = Join-Path $env:SystemRoot 'System32\cmd.exe'

    $proc = Start-Process -FilePath $cmd `
        -ArgumentList @('/d','/s','/c',('"' + $command + '"')) `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -PassThru

    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 300
        try {
            $r = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8080' -TimeoutSec 1
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) {
                $ready = $true
                break
            }
        } catch {}
        if ($proc.HasExited) { break }
    }

    if (-not $ready) {
        $tail = ''
        if (Test-Path $log) {
            try {
                $tail = (Get-Content $log -Tail 40 -ErrorAction SilentlyContinue | Out-String).Trim()
            } catch {}
        }
        if ($tail) {
            throw ("Web failed to start on 127.0.0.1:8080.`r`n`r`n" + $tail)
        }
        throw 'Web failed to start on 127.0.0.1:8080. Check local_data\web_console.log.'
    }

    Set-Content -Path (Join-Path $Data 'WEB_STATUS.txt') `
        -Value ((Get-Date).ToString('s') + ' RUNNING http://127.0.0.1:8080') `
        -Encoding ASCII

    Start-Process 'http://127.0.0.1:8080' | Out-Null
} catch {
    $msg = $_.Exception.Message
    Add-Content -Path (Join-Path $Data 'web_start_error.log') `
        -Value ((Get-Date).ToString('s') + ' ' + $msg) `
        -Encoding ASCII
    Show-Error $msg
    exit 1
}
