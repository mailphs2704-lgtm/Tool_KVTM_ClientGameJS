$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Data = Join-Path $Root 'local_data'
New-Item -ItemType Directory -Force -Path $Data | Out-Null

function Show-Message([string]$text, [string]$title = 'AUTO KVTM PUBLIC') {
    Add-Type -AssemblyName PresentationFramework -ErrorAction SilentlyContinue
    [System.Windows.MessageBox]::Show($text, $title) | Out-Null
}

function Test-Url([string]$url, [int]$seconds = 3) {
    try {
        Invoke-WebRequest -UseBasicParsing $url -TimeoutSec $seconds | Out-Null
        return $true
    } catch {
        return $false
    }
}

try {
    # Ensure normal local Web proxy + core are alive without leaving a CMD window.
    if (-not (Test-Url 'http://127.0.0.1:8080')) {
        Start-Process -FilePath 'wscript.exe' -ArgumentList ('"' + (Join-Path $Root 'launchers\run_web_hidden.vbs') + '"') -WindowStyle Hidden | Out-Null
        for ($i = 0; $i -lt 20; $i++) {
            Start-Sleep -Milliseconds 500
            if ((Test-Url 'http://127.0.0.1:8080' 2) -and (Test-Url 'http://127.0.0.1:18080' 2)) { break }
        }
    }
    if (-not (Test-Url 'http://127.0.0.1:8080') -or -not (Test-Url 'http://127.0.0.1:18080')) {
        throw 'Web local chưa sẵn sàng trên 8080/18080.'
    }

    # Stop only our previous public gateway and Quick Tunnel.
    Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -eq 'node.exe' -and $_.CommandLine -match 'web_control[\\/]public_gateway\.js') -or
        ($_.Name -eq 'cloudflared.exe' -and $_.CommandLine -match 'tunnel.*--url\s+http://127\.0\.0\.1:8081')
    } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 500

    $gatewayOut = Join-Path $Data 'public_gateway.log'
    $gatewayErr = Join-Path $Data 'public_gateway_error.log'
    Remove-Item $gatewayOut,$gatewayErr -Force -ErrorAction SilentlyContinue
    $gateway = Start-Process -FilePath 'node.exe' -ArgumentList @('web_control\public_gateway.js') -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput $gatewayOut -RedirectStandardError $gatewayErr
    Set-Content -Path (Join-Path $Data 'public_gateway.pid') -Value $gateway.Id -Encoding ascii

    for ($i = 0; $i -lt 16; $i++) {
        Start-Sleep -Milliseconds 250
        if (Test-Url 'http://127.0.0.1:8081' 1) { break }
    }
    if (-not (Test-Url 'http://127.0.0.1:8081')) {
        throw 'Public gateway không khởi động được trên 127.0.0.1:8081.'
    }

    $cloudflared = $null
    try { $cloudflared = (Get-Command cloudflared.exe -ErrorAction Stop).Source } catch {}
    if (-not $cloudflared) {
        $candidates = @(
            (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\cloudflared.exe'),
            (Join-Path $env:ProgramFiles 'cloudflared\cloudflared.exe')
        )
        if (${env:ProgramFiles(x86)}) { $candidates += (Join-Path ${env:ProgramFiles(x86)} 'cloudflared\cloudflared.exe') }
        $cloudflared = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    }

    if (-not $cloudflared) {
        $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if (-not $winget) { throw 'Chưa có cloudflared và máy không có winget để tự cài.' }
        Start-Process -FilePath $winget.Source -ArgumentList @('install','-e','--id','Cloudflare.cloudflared','--accept-package-agreements','--accept-source-agreements','--silent') -WindowStyle Hidden -Wait | Out-Null
        try { $cloudflared = (Get-Command cloudflared.exe -ErrorAction Stop).Source } catch {}
        if (-not $cloudflared) {
            $candidate = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\cloudflared.exe'
            if (Test-Path $candidate) { $cloudflared = $candidate }
        }
    }
    if (-not $cloudflared) { throw 'Không tìm thấy cloudflared.exe sau khi cài.' }

    $cfOut = Join-Path $Data 'cloudflared_public.log'
    $cfErr = Join-Path $Data 'cloudflared_public_error.log'
    Remove-Item $cfOut,$cfErr -Force -ErrorAction SilentlyContinue
    $cf = Start-Process -FilePath $cloudflared -ArgumentList @('tunnel','--no-autoupdate','--url','http://127.0.0.1:8081') -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput $cfOut -RedirectStandardError $cfErr
    Set-Content -Path (Join-Path $Data 'public_cloudflared.pid') -Value $cf.Id -Encoding ascii

    $url = $null
    for ($i = 0; $i -lt 60 -and -not $url; $i++) {
        Start-Sleep -Milliseconds 500
        $text = ''
        if (Test-Path $cfOut) { $text += (Get-Content $cfOut -Raw -ErrorAction SilentlyContinue) }
        if (Test-Path $cfErr) { $text += "`n" + (Get-Content $cfErr -Raw -ErrorAction SilentlyContinue) }
        $m = [regex]::Match($text, 'https://[a-zA-Z0-9-]+\.trycloudflare\.com')
        if ($m.Success) { $url = $m.Value }
        if ($cf.HasExited) { break }
    }

    if (-not $url) {
        throw "Cloudflare chưa trả URL public. Xem log: $cfErr"
    }

    Set-Content -Path (Join-Path $Data 'PUBLIC_URL.txt') -Value $url -Encoding utf8
    try { Set-Clipboard -Value $url } catch {}
    Show-Message "Public Web đã chạy nền.`n`n$url`n`nLink đã được copy vào clipboard và lưu tại local_data\PUBLIC_URL.txt.`n`nDùng STOP_PUBLIC.bat để tắt tunnel." 'AUTO KVTM PUBLIC - ĐÃ CHẠY'
} catch {
    $msg = $_.Exception.Message
    Add-Content -Path (Join-Path $Data 'public_launcher_error.log') -Value ((Get-Date).ToString('s') + ' ' + $msg)
    Show-Message "$msg`n`nXem local_data\public_launcher_error.log nếu cần." 'AUTO KVTM PUBLIC - LỖI'
}
