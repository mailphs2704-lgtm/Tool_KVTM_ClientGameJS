$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Data = Join-Path $Root 'local_data'
New-Item -ItemType Directory -Force -Path $Data | Out-Null
$Log = Join-Path $Data 'update.log'

function Show-Message([string]$text, [string]$title) {
    Add-Type -AssemblyName PresentationFramework -ErrorAction SilentlyContinue
    [System.Windows.MessageBox]::Show($text, $title) | Out-Null
}

try {
    if (-not (Test-Path (Join-Path $Root '.git'))) {
        throw 'Thư mục hiện tại chưa được setup Git.'
    }
    $git = (Get-Command git.exe -ErrorAction Stop).Source
    Push-Location $Root
    try {
        $pullText = (& $git pull --ff-only origin main 2>&1 | Out-String)
        $pullCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    $stamp = (Get-Date).ToString('s')
    Set-Content -Path $Log -Value ("[$stamp] git pull`r`n" + $pullText) -Encoding utf8
    if ($pullCode -ne 0) {
        throw ('Git pull thất bại. Xem local_data\update.log.' + "`n`n" + $pullText.Trim())
    }

    $shortcutScript = Join-Path $Root 'launchers\install_shortcuts.ps1'
    if (Test-Path $shortcutScript) {
        & powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File $shortcutScript | Out-Null
    }

    Push-Location $Root
    try {
        $line = (& $git log -1 --oneline 2>&1 | Out-String).Trim()
    } finally {
        Pop-Location
    }
    Show-Message "Cập nhật xong.`n`n$line`n`nShortcut Desktop cũng đã được làm mới." 'AUTO KVTM - UPDATE XONG'
} catch {
    Add-Content -Path $Log -Value ("`r`n[ERROR] " + $_.Exception.Message) -Encoding utf8
    Show-Message ($_.Exception.Message + "`n`nXem local_data\update.log nếu cần.") 'AUTO KVTM - UPDATE LỖI'
}
