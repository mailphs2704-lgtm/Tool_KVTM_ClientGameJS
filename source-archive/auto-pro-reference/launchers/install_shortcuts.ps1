$ErrorActionPreference = 'SilentlyContinue'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Data = Join-Path $Root 'local_data'
New-Item -ItemType Directory -Force -Path $Data | Out-Null

function Resolve-BrandIcon {
    $overrideIco = Join-Path $Data 'launcher_icon.ico'
    if (Test-Path $overrideIco) { return $overrideIco }

    $originalIco = Join-Path $Root 'assets\icon\app.ico'
    if (Test-Path $originalIco) { return $originalIco }

    $internalIco = Join-Path $Root '_internal\assets\icon\app.ico'
    if (Test-Path $internalIco) { return $internalIco }

    return $null
}

$brandIcon = Resolve-BrandIcon
$desktop = [Environment]::GetFolderPath('Desktop')
$powershell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$ws = New-Object -ComObject WScript.Shell

function New-KvtmShortcut([string]$name, [string]$scriptRelative, [string]$description) {
    $lnk = Join-Path $desktop ($name + '.lnk')
    Remove-Item $lnk -Force -ErrorAction SilentlyContinue
    $script = Join-Path $Root $scriptRelative
    $s = $ws.CreateShortcut($lnk)
    $s.TargetPath = $powershell
    $s.Arguments = '-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $script + '"'
    $s.WorkingDirectory = $Root
    $s.Description = $description
    if ($brandIcon) { $s.IconLocation = $brandIcon + ',0' }
    $s.WindowStyle = 7
    $s.Save()
}

New-KvtmShortcut 'AUTO KVTM PRO' 'launchers\run_local_hidden.ps1' 'Mở AUTO KVTM PRO không hiện CMD'
New-KvtmShortcut 'AUTO KVTM WEB' 'launchers\run_web_hidden.ps1' 'Mở Web AUTO KVTM không hiện CMD'
New-KvtmShortcut 'STOP AUTO KVTM WEB' 'launchers\stop_web_hidden.ps1' 'Tắt Web AUTO KVTM không hiện CMD'
New-KvtmShortcut 'AUTO KVTM PUBLIC' 'launchers\run_public_hidden.ps1' 'Mở Public Tunnel AUTO KVTM không hiện CMD'
New-KvtmShortcut 'STOP AUTO KVTM PUBLIC' 'launchers\stop_public_hidden.ps1' 'Tắt Public Tunnel AUTO KVTM không hiện CMD'
New-KvtmShortcut 'UPDATE AUTO KVTM' 'launchers\update_hidden.ps1' 'Cập nhật AUTO KVTM từ GitHub không hiện CMD'

try {
    $shell = New-Object -ComObject Shell.Application
    $shell.NameSpace($desktop).Self.InvokeVerb('Refresh')
} catch {}
