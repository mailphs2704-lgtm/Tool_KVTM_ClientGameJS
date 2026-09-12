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

function Read-LogTail {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return ""
    }
    return (@(Get-Content -LiteralPath $Path -Tail 30 -ErrorAction SilentlyContinue) -join " | ").Trim()
}

function Invoke-CryBootstrapChild {
    param(
        [Parameter(Mandatory = $true)][string]$Script,
        [Parameter(Mandatory = $true)][string]$Label,
        [string[]]$Arguments = @()
    )
    $quotedScript = '"' + $Script + '"'
    $argumentLine = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-WindowStyle", "Hidden",
        "-File", $quotedScript
    ) + $Arguments
    # Label=runtime resolves to bootstrap-runtime.err.log / bootstrap-runtime.out.log.
    $stdout = Join-Path $LogRoot ("bootstrap-" + $Label + ".out.log")
    $stderr = Join-Path $LogRoot ("bootstrap-" + $Label + ".err.log")
    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    $process = Start-Process -FilePath "powershell.exe" -ArgumentList $argumentLine -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -Wait
    return @{
        ExitCode = [int]$process.ExitCode
        Stdout = $stdout
        Stderr = $stderr
    }
}

try {
    if (-not (Test-Path -LiteralPath $RuntimeScript -PathType Leaf)) {
        throw "Missing runtime bootstrap: $RuntimeScript"
    }

    # Update is intentionally attempted only before runtime launch. Run it in a
    # child PowerShell because updater uses exit codes; it must never terminate
    # this launch orchestrator before the known-good runtime gets a chance to run.
    if (Test-Path -LiteralPath $UpdateScript -PathType Leaf) {
        $updateResult = Invoke-CryBootstrapChild -Script $UpdateScript -Label "update"
        if ($updateResult.ExitCode -eq 0) {
            Write-CryLaunchLog "update check PASS"
        }
        else {
            $updateTail = Read-LogTail -Path $updateResult.Stderr
            Write-CryLaunchLog "update check failed rc=$($updateResult.ExitCode); launching last verified version; stderr=$updateTail"
        }
    }

    $runtimeResult = Invoke-CryBootstrapChild -Script $RuntimeScript -Label "runtime"
    if ($runtimeResult.ExitCode -ne 0) {
        $runtimeTail = Read-LogTail -Path $runtimeResult.Stderr
        throw "Runtime bootstrap failed rc=$($runtimeResult.ExitCode); stderr=$runtimeTail"
    }
    Write-CryLaunchLog "launch PASS"
    exit 0
}
catch {
    Write-CryLaunchLog ("FAIL " + $_.Exception.Message)
    exit 2
}
