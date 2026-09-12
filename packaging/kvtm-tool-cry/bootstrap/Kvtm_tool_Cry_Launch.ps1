param()

$ErrorActionPreference = "Stop"
$ProductName = "Kvtm_tool_Cry"
$InstallRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DataRoot = Join-Path $env:APPDATA $ProductName
$LogRoot = Join-Path $DataRoot "logs"
$UpdateScript = Join-Path $PSScriptRoot "Kvtm_tool_Cry_Update.ps1"
$RuntimeScript = Join-Path $PSScriptRoot "Kvtm_tool_Cry_Runtime.ps1"
New-Item -ItemType Directory -Path $DataRoot, $LogRoot -Force | Out-Null
$LogPath = Join-Path $LogRoot "launcher.log"

function Write-CryLaunchLog {
    param([Parameter(Mandatory = $true)][string]$Message)
    Add-Content -LiteralPath $LogPath -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message) -Encoding UTF8
}

function Invoke-CryBootstrapChild {
    param(
        [Parameter(Mandatory = $true)][string]$Script,
        [string[]]$Arguments = @()
    )
    $quotedScript = '"' + $Script + '"'
    $argumentLine = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-WindowStyle", "Hidden",
        "-File", $quotedScript
    ) + $Arguments
    $process = Start-Process -FilePath "powershell.exe" -ArgumentList $argumentLine -WindowStyle Hidden -PassThru -Wait
    return [int]$process.ExitCode
}

try {
    if (-not (Test-Path -LiteralPath $RuntimeScript -PathType Leaf)) {
        throw "Missing runtime bootstrap: $RuntimeScript"
    }

    # Update is intentionally attempted only before runtime launch. Run it in a
    # child PowerShell because updater uses exit codes; it must never terminate
    # this launch orchestrator before the known-good runtime gets a chance to run.
    if (Test-Path -LiteralPath $UpdateScript -PathType Leaf) {
        $updateRc = Invoke-CryBootstrapChild -Script $UpdateScript
        if ($updateRc -eq 0) {
            Write-CryLaunchLog "update check PASS"
        }
        else {
            Write-CryLaunchLog "update check failed rc=$updateRc; launching last verified version"
        }
    }

    $runtimeRc = Invoke-CryBootstrapChild -Script $RuntimeScript
    if ($runtimeRc -ne 0) {
        throw "Runtime bootstrap failed rc=$runtimeRc"
    }
    Write-CryLaunchLog "launch PASS"
    exit 0
}
catch {
    Write-CryLaunchLog ("FAIL " + $_.Exception.Message)
    exit 2
}
