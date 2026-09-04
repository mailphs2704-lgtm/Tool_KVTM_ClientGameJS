[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class KVTMRecorderNative {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
    [DllImport("ntdll.dll")] public static extern int NtSuspendProcess(IntPtr handle);
    [DllImport("ntdll.dll")] public static extern int NtResumeProcess(IntPtr handle);
}
"@

function Find-FFmpeg {
    $root = Split-Path $PSScriptRoot -Parent
    foreach ($candidate in @(
        (Join-Path $PSScriptRoot "ffmpeg.exe"),
        (Join-Path $root "ffmpeg.exe"),
        (Join-Path $root "AUTO_PRO\ffmpeg.exe")
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    $command = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    return $null
}

function Add-Label($form, $text, $x, $y) {
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $text
    $label.AutoSize = $true
    $label.Location = New-Object System.Drawing.Point($x, $y)
    $form.Controls.Add($label)
}

function Add-Number($form, $x, $y, $min, $max, $value, $width = 105) {
    $box = New-Object System.Windows.Forms.NumericUpDown
    $box.Location = New-Object System.Drawing.Point($x, $y)
    $box.Size = New-Object System.Drawing.Size($width, 28)
    $box.Minimum = $min
    $box.Maximum = $max
    $box.Value = [decimal]$value
    $form.Controls.Add($box)
    return $box
}

$script:Recorder = $null
$script:Paused = $false
$script:OutputFile = $null
$repoRoot = Split-Path $PSScriptRoot -Parent
$outputRoot = Join-Path $repoRoot "recordings"
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

$form = New-Object System.Windows.Forms.Form
$form.Text = "KVTM - Quay video MP4 60 FPS"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(650, 475)
$form.MinimumSize = $form.Size
$form.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$title = New-Object System.Windows.Forms.Label
$title.Text = "QUAY VIDEO MP4 SẮC NÉT"
$title.Font = New-Object System.Drawing.Font("Segoe UI Semibold", 16)
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(20, 16)
$form.Controls.Add($title)

$hint = New-Object System.Windows.Forms.Label
$hint.Text = "H.264 - 60 FPS - CRF 16 - điều chỉnh được vùng quay"
$hint.AutoSize = $true
$hint.ForeColor = [System.Drawing.Color]::DimGray
$hint.Location = New-Object System.Drawing.Point(22, 52)
$form.Controls.Add($hint)

Add-Label $form "Chế độ" 22 94
$mode = New-Object System.Windows.Forms.ComboBox
$mode.DropDownStyle = "DropDownList"
[void]$mode.Items.Add("Toàn màn hình")
[void]$mode.Items.Add("Khung tùy chỉnh")
$mode.SelectedIndex = 0
$mode.Location = New-Object System.Drawing.Point(120, 90)
$mode.Size = New-Object System.Drawing.Size(190, 28)
$form.Controls.Add($mode)

Add-Label $form "FPS" 340 94
$fps = Add-Number $form 380 90 10 120 60 90
Add-Label $form "CRF" 500 94
$crf = Add-Number $form 540 90 10 30 16 70

$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
Add-Label $form "X" 22 143
$xBox = Add-Number $form 55 139 -10000 10000 $bounds.X
Add-Label $form "Y" 180 143
$yBox = Add-Number $form 213 139 -10000 10000 $bounds.Y
Add-Label $form "Rộng" 340 143
$wBox = Add-Number $form 390 139 16 16384 $bounds.Width
Add-Label $form "Cao" 510 143
$hBox = Add-Number $form 550 139 16 16384 $bounds.Height 70

$pick = New-Object System.Windows.Forms.Button
$pick.Text = "Lấy khung cửa sổ (chờ 3 giây)"
$pick.Location = New-Object System.Drawing.Point(22, 183)
$pick.Size = New-Object System.Drawing.Size(260, 35)
$form.Controls.Add($pick)

$folder = New-Object System.Windows.Forms.Button
$folder.Text = "Mở thư mục video"
$folder.Location = New-Object System.Drawing.Point(295, 183)
$folder.Size = New-Object System.Drawing.Size(170, 35)
$form.Controls.Add($folder)

$quality = New-Object System.Windows.Forms.Label
$quality.Text = "CRF thấp hơn = nét hơn và file lớn hơn. Khuyến nghị: 16."
$quality.AutoSize = $true
$quality.ForeColor = [System.Drawing.Color]::DimGray
$quality.Location = New-Object System.Drawing.Point(22, 232)
$form.Controls.Add($quality)

$start = New-Object System.Windows.Forms.Button
$start.Text = "BẮT ĐẦU"
$start.Location = New-Object System.Drawing.Point(22, 275)
$start.Size = New-Object System.Drawing.Size(180, 48)
$start.BackColor = [System.Drawing.Color]::FromArgb(34, 139, 94)
$start.ForeColor = [System.Drawing.Color]::White
$start.FlatStyle = "Flat"
$form.Controls.Add($start)

$pause = New-Object System.Windows.Forms.Button
$pause.Text = "TẠM DỪNG"
$pause.Location = New-Object System.Drawing.Point(222, 275)
$pause.Size = New-Object System.Drawing.Size(180, 48)
$pause.Enabled = $false
$form.Controls.Add($pause)

$stop = New-Object System.Windows.Forms.Button
$stop.Text = "DỪNG VÀ LƯU MP4"
$stop.Location = New-Object System.Drawing.Point(422, 275)
$stop.Size = New-Object System.Drawing.Size(180, 48)
$stop.Enabled = $false
$form.Controls.Add($stop)

$status = New-Object System.Windows.Forms.Label
$status.Text = "Sẵn sàng"
$status.Location = New-Object System.Drawing.Point(22, 350)
$status.Size = New-Object System.Drawing.Size(580, 55)
$status.BorderStyle = "FixedSingle"
$status.Padding = New-Object System.Windows.Forms.Padding(8)
$form.Controls.Add($status)

$mode.Add_SelectedIndexChanged({
    $custom = $mode.SelectedIndex -eq 1
    foreach ($control in @($xBox, $yBox, $wBox, $hBox)) { $control.Enabled = $custom }
})
$mode.SelectedIndex = 1
$mode.SelectedIndex = 0

$pick.Add_Click({
    $status.Text = "Trong 3 giây, hãy click vào cửa sổ cần quay..."
    $form.Refresh()
    Start-Sleep -Seconds 3
    $hwnd = [KVTMRecorderNative]::GetForegroundWindow()
    $rect = New-Object KVTMRecorderNative+RECT
    if ($hwnd -eq [IntPtr]::Zero -or -not [KVTMRecorderNative]::GetWindowRect($hwnd, [ref]$rect)) {
        [System.Windows.Forms.MessageBox]::Show("Không lấy được khung cửa sổ.", $form.Text) | Out-Null
        return
    }
    $mode.SelectedIndex = 1
    $xBox.Value = [decimal]$rect.Left
    $yBox.Value = [decimal]$rect.Top
    $wBox.Value = [decimal]([Math]::Max(16, $rect.Right - $rect.Left))
    $hBox.Value = [decimal]([Math]::Max(16, $rect.Bottom - $rect.Top))
    $status.Text = "Đã lấy khung cửa sổ: $($rect.Left),$($rect.Top) $($rect.Right-$rect.Left)x$($rect.Bottom-$rect.Top)"
})

$folder.Add_Click({ Start-Process explorer.exe -ArgumentList ('"' + $outputRoot + '"') })

$start.Add_Click({
    try {
        $ffmpeg = Find-FFmpeg
        if (-not $ffmpeg) {
            throw "Không tìm thấy ffmpeg.exe. Hãy cài FFmpeg vào PATH hoặc đặt ffmpeg.exe cạnh BAT."
        }
        $frameRate = [int]$fps.Value
        $qualityValue = [int]$crf.Value
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $script:OutputFile = Join-Path $outputRoot "KVTM-$stamp.mp4"

        $arguments = @("-hide_banner", "-loglevel", "warning", "-f", "gdigrab", "-framerate", "$frameRate")
        if ($mode.SelectedIndex -eq 1) {
            $width = [int]$wBox.Value
            $height = [int]$hBox.Value
            if ($width % 2) { $width-- }
            if ($height % 2) { $height-- }
            $arguments += @("-offset_x", "$([int]$xBox.Value)", "-offset_y", "$([int]$yBox.Value)", "-video_size", "$($width)x$($height)")
        }
        $arguments += @(
            "-draw_mouse", "1", "-i", "desktop",
            "-c:v", "libx264", "-preset", "fast", "-crf", "$qualityValue",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y", $script:OutputFile
        )

        $info = New-Object System.Diagnostics.ProcessStartInfo
        $info.FileName = $ffmpeg
        $info.Arguments = ($arguments | ForEach-Object {
            if ($_ -match '[\s"]') { '"' + ($_ -replace '"','\"') + '"' } else { $_ }
        }) -join " "
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.RedirectStandardInput = $true
        $info.RedirectStandardError = $false
        $script:Recorder = New-Object System.Diagnostics.Process
        $script:Recorder.StartInfo = $info
        if (-not $script:Recorder.Start()) { throw "FFmpeg không khởi động." }
        $script:Paused = $false
        $start.Enabled = $false
        $pause.Enabled = $true
        $stop.Enabled = $true
        $status.Text = "ĐANG QUAY - $frameRate FPS - MP4" + [Environment]::NewLine + $script:OutputFile
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, $form.Text, "OK", "Error") | Out-Null
    }
})

$pause.Add_Click({
    if (-not $script:Recorder -or $script:Recorder.HasExited) { return }
    if ($script:Paused) {
        [void][KVTMRecorderNative]::NtResumeProcess($script:Recorder.Handle)
        $script:Paused = $false
        $pause.Text = "TẠM DỪNG"
        $status.Text = "ĐANG QUAY LẠI" + [Environment]::NewLine + $script:OutputFile
    } else {
        [void][KVTMRecorderNative]::NtSuspendProcess($script:Recorder.Handle)
        $script:Paused = $true
        $pause.Text = "TIẾP TỤC"
        $status.Text = "ĐÃ TẠM DỪNG" + [Environment]::NewLine + $script:OutputFile
    }
})

function Stop-Recorder {
    if ($script:Recorder -and -not $script:Recorder.HasExited) {
        if ($script:Paused) {
            [void][KVTMRecorderNative]::NtResumeProcess($script:Recorder.Handle)
            $script:Paused = $false
        }
        try {
            $script:Recorder.StandardInput.WriteLine("q")
            if (-not $script:Recorder.WaitForExit(10000)) { $script:Recorder.Kill() }
        } catch { try { $script:Recorder.Kill() } catch {} }
    }
}

$stop.Add_Click({
    Stop-Recorder
    $start.Enabled = $true
    $pause.Enabled = $false
    $pause.Text = "TẠM DỪNG"
    $stop.Enabled = $false
    $status.Text = "ĐÃ LƯU MP4" + [Environment]::NewLine + $script:OutputFile
    $script:Recorder = $null
})

$form.Add_FormClosing({
    if ($script:Recorder -and -not $script:Recorder.HasExited) {
        $answer = [System.Windows.Forms.MessageBox]::Show(
            "Đang quay video. Dừng và lưu MP4 trước khi thoát?",
            $form.Text, "YesNo", "Question"
        )
        if ($answer -ne "Yes") { $_.Cancel = $true; return }
        Stop-Recorder
    }
})

[void]$form.ShowDialog()
