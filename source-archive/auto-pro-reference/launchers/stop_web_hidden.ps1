$ErrorActionPreference = 'SilentlyContinue'
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -ieq 'node.exe' -and $_.CommandLine -match 'web_control[\\/](server|proxy_v10)\.js'
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
