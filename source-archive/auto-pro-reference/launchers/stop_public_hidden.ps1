$ErrorActionPreference = 'SilentlyContinue'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Data = Join-Path $Root 'local_data'

Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -eq 'node.exe' -and $_.CommandLine -match 'web_control[\\/]public_gateway\.js') -or
    ($_.Name -eq 'cloudflared.exe' -and $_.CommandLine -match 'tunnel.*--url\s+http://127\.0\.0\.1:8081')
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

Remove-Item (Join-Path $Data 'public_gateway.pid'),(Join-Path $Data 'public_cloudflared.pid') -Force -ErrorAction SilentlyContinue
Set-Content -Path (Join-Path $Data 'PUBLIC_URL.txt') -Value 'PUBLIC TUNNEL STOPPED' -Encoding utf8
