param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Export", "Import")]
    [string]$Mode,

    [string]$ProfileFile = "",
    [string]$TransferFile = "",
    [switch]$IncludeSettings,
    [switch]$ImportSettings,
    [switch]$ReplaceProfiles
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Security

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DefaultProfile = Join-Path $RepoRoot "dist\KVTM-ClientJS-Suite-Multi-DEV\data-dev\profiles.json"
$Entropy = [System.Text.Encoding]::UTF8.GetBytes("KVTM-MULTI-v1")
$Iterations = 200000
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-Stage {
    param([string]$Name)
    Write-Host ("stage=" + $Name) -ForegroundColor DarkGray
}

function Read-PasswordText {
    param([string]$Prompt)
    $secure = Read-Host $Prompt -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally {
        if ($ptr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        }
    }
}

function Join-ThreeBytes {
    param([byte[]]$First, [byte[]]$Second, [byte[]]$Third)
    $result = New-Object byte[] ($First.Length + $Second.Length + $Third.Length)
    [Array]::Copy($First, 0, $result, 0, $First.Length)
    [Array]::Copy($Second, 0, $result, $First.Length, $Second.Length)
    [Array]::Copy($Third, 0, $result, $First.Length + $Second.Length, $Third.Length)
    return ,$result
}

function Test-BytesEqual {
    param([byte[]]$Left, [byte[]]$Right)
    if ($null -eq $Left -or $null -eq $Right -or $Left.Length -ne $Right.Length) {
        return $false
    }
    $diff = 0
    for ($i = 0; $i -lt $Left.Length; $i++) {
        $diff = $diff -bor ($Left[$i] -bxor $Right[$i])
    }
    return ($diff -eq 0)
}

function Get-KeyMaterial {
    param([string]$Password, [byte[]]$Salt, [int]$Count)
    $kdf = New-Object Security.Cryptography.Rfc2898DeriveBytes($Password, $Salt, $Count)
    try {
        $material = $kdf.GetBytes(64)
        return ,$material
    }
    finally {
        $kdf.Dispose()
    }
}

function Get-SplitKeys {
    param([byte[]]$Material)
    $enc = New-Object byte[] 32
    $mac = New-Object byte[] 32
    [Array]::Copy($Material, 0, $enc, 0, 32)
    [Array]::Copy($Material, 32, $mac, 0, 32)
    return [pscustomobject]@{ Enc = $enc; Mac = $mac }
}

function Protect-PortablePayload {
    param([string]$PlainText, [string]$Password)

    $salt = New-Object byte[] 32
    $iv = New-Object byte[] 16
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($salt)
        $rng.GetBytes($iv)
    }
    finally {
        $rng.Dispose()
    }

    $material = Get-KeyMaterial $Password $salt $Iterations
    $keys = Get-SplitKeys $material
    $plainBytes = [Text.Encoding]::UTF8.GetBytes($PlainText)

    $aes = [Security.Cryptography.Aes]::Create()
    $aes.KeySize = 256
    $aes.BlockSize = 128
    $aes.Mode = [Security.Cryptography.CipherMode]::CBC
    $aes.Padding = [Security.Cryptography.PaddingMode]::PKCS7
    $aes.Key = [byte[]]$keys.Enc
    $aes.IV = $iv
    try {
        $transform = $aes.CreateEncryptor()
        try {
            $cipher = $transform.TransformFinalBlock($plainBytes, 0, $plainBytes.Length)
        }
        finally {
            $transform.Dispose()
        }
    }
    finally {
        $aes.Dispose()
    }

    $authBytes = Join-ThreeBytes $salt $iv $cipher
    $hmac = New-Object Security.Cryptography.HMACSHA256 -ArgumentList (,[byte[]]$keys.Mac)
    try {
        $mac = $hmac.ComputeHash($authBytes)
    }
    finally {
        $hmac.Dispose()
    }

    return [pscustomobject]@{
        format = "KVTM_PROFILE_TRANSFER"
        version = 1
        crypto = "AES-256-CBC+HMAC-SHA256"
        kdf = "PBKDF2-HMAC-SHA1"
        iterations = $Iterations
        salt_b64 = [Convert]::ToBase64String($salt)
        iv_b64 = [Convert]::ToBase64String($iv)
        cipher_b64 = [Convert]::ToBase64String($cipher)
        mac_b64 = [Convert]::ToBase64String($mac)
    }
}

function Unprotect-PortablePayload {
    param([object]$Envelope, [string]$Password)

    if ($Envelope.format -ne "KVTM_PROFILE_TRANSFER" -or [int]$Envelope.version -ne 1) {
        throw "File transfer khong dung dinh dang KVTM_PROFILE_TRANSFER v1."
    }

    $salt = [Convert]::FromBase64String([string]$Envelope.salt_b64)
    $iv = [Convert]::FromBase64String([string]$Envelope.iv_b64)
    $cipher = [Convert]::FromBase64String([string]$Envelope.cipher_b64)
    $expectedMac = [Convert]::FromBase64String([string]$Envelope.mac_b64)
    $count = [int]$Envelope.iterations
    if ($count -lt 100000) {
        throw "KDF iterations khong hop le."
    }

    $material = Get-KeyMaterial $Password $salt $count
    $keys = Get-SplitKeys $material
    $authBytes = Join-ThreeBytes $salt $iv $cipher
    $hmac = New-Object Security.Cryptography.HMACSHA256 -ArgumentList (,[byte[]]$keys.Mac)
    try {
        $actualMac = $hmac.ComputeHash($authBytes)
    }
    finally {
        $hmac.Dispose()
    }

    if (-not (Test-BytesEqual $actualMac $expectedMac)) {
        throw "Sai mat khau hoac file transfer da bi thay doi."
    }

    $aes = [Security.Cryptography.Aes]::Create()
    $aes.KeySize = 256
    $aes.BlockSize = 128
    $aes.Mode = [Security.Cryptography.CipherMode]::CBC
    $aes.Padding = [Security.Cryptography.PaddingMode]::PKCS7
    $aes.Key = [byte[]]$keys.Enc
    $aes.IV = $iv
    try {
        $transform = $aes.CreateDecryptor()
        try {
            $plain = $transform.TransformFinalBlock($cipher, 0, $cipher.Length)
        }
        finally {
            $transform.Dispose()
        }
    }
    finally {
        $aes.Dispose()
    }

    return [Text.Encoding]::UTF8.GetString($plain)
}

function Unprotect-DpapiSecret {
    param([string]$Value)
    $cipher = [Convert]::FromBase64String($Value)
    $plain = [Security.Cryptography.ProtectedData]::Unprotect(
        $cipher,
        $Entropy,
        [Security.Cryptography.DataProtectionScope]::CurrentUser
    )
    return [Text.Encoding]::UTF8.GetString($plain)
}

function Protect-DpapiSecret {
    param([string]$Value)
    $plain = [Text.Encoding]::UTF8.GetBytes($Value)
    $cipher = [Security.Cryptography.ProtectedData]::Protect(
        $plain,
        $Entropy,
        [Security.Cryptography.DataProtectionScope]::CurrentUser
    )
    return [Convert]::ToBase64String($cipher)
}

function Find-LocalClient {
    $candidates = @()
    if ($env:ProgramFiles) {
        $candidates += (Join-Path $env:ProgramFiles "ZingPlay\data\flutter_assets\assets\runtime\GameClientJS.exe")
    }
    if (${env:ProgramFiles(x86)}) {
        $candidates += (Join-Path ${env:ProgramFiles(x86)} "ZingPlay\data\flutter_assets\assets\runtime\GameClientJS.exe")
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }
    return $null
}

function Backup-FileSafe {
    param([string]$Path, [string]$BackupDirectory, [string]$Prefix)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }
    New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Copy-Item -LiteralPath $Path -Destination (Join-Path $BackupDirectory "$Prefix-$stamp.json") -Force
}

if ([string]::IsNullOrWhiteSpace($ProfileFile)) {
    $ProfileFile = $DefaultProfile
}

if ($Mode -eq "Export") {
    Write-Stage "READ_PROFILE"
    if (-not (Test-Path -LiteralPath $ProfileFile -PathType Leaf)) {
        throw "Khong tim thay profiles.json active: $ProfileFile"
    }

    [object[]]$profiles = (Get-Content -LiteralPath $ProfileFile -Raw -Encoding UTF8 | ConvertFrom-Json)
    if ($profiles.Count -eq 0) {
        throw "profiles.json khong co profile."
    }

    Write-Host "Profiles detected: $($profiles.Count)"
    Write-Stage "DPAPI_DECRYPT"
    [object[]]$portableProfiles = @()
    foreach ($profile in $profiles) {
        if ([string]::IsNullOrWhiteSpace([string]$profile.id) -or [string]::IsNullOrWhiteSpace([string]$profile.secret)) {
            throw "Profile thieu id/secret; dung export de tranh mat login."
        }

        try {
            $secretText = Unprotect-DpapiSecret ([string]$profile.secret)
            [object[]]$secretArgs = ($secretText | ConvertFrom-Json)
            if ($secretArgs.Count -eq 0) {
                throw "secret_args rong"
            }
        }
        catch {
            throw "Khong giai ma/parse duoc DPAPI cho profile '$($profile.name)'. Hay export tren dung Windows user da luu profile. Chi tiet: $($_.Exception.Message)"
        }

        $portableProfile = [pscustomobject]@{
            id = [string]$profile.id
            name = [string]$profile.name
            client = [string]$profile.client
            game_dir = [string]$profile.game_dir
            updated_at = [string]$profile.updated_at
            secret_args = [object[]]$secretArgs
        }
        $portableProfiles += $portableProfile
    }

    if ($portableProfiles.Count -ne $profiles.Count) {
        throw "Preflight profile count mismatch: source=$($profiles.Count), portable=$($portableProfiles.Count)"
    }

    $settingsText = $null
    if ($IncludeSettings) {
        $settingsPath = Join-Path (Split-Path -Parent $ProfileFile) "settings.json"
        if (Test-Path -LiteralPath $settingsPath -PathType Leaf) {
            $settingsText = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8
            try {
                $null = $settingsText | ConvertFrom-Json
            }
            catch {
                throw "IncludeSettings duoc yeu cau nhung settings.json khong hop le."
            }
        }
    }

    Write-Stage "BUILD_PAYLOAD"
    $payloadObject = [pscustomobject]@{
        schema_version = 1
        created_at = (Get-Date).ToString("o")
        source_machine = $env:COMPUTERNAME
        profile_count = $portableProfiles.Count
        profiles = [object[]]$portableProfiles
        settings_text = $settingsText
    }
    $payload = ConvertTo-Json -InputObject $payloadObject -Depth 30 -Compress

    Write-Stage "PASSWORD"
    $password = Read-PasswordText "Nhap mat khau cho file chuyen may (toi thieu 10 ky tu)"
    if ($password.Length -lt 10) {
        throw "Mat khau phai co it nhat 10 ky tu."
    }
    $confirm = Read-PasswordText "Nhap lai mat khau"
    if ($password -cne $confirm) {
        throw "Hai mat khau khong khop."
    }

    Write-Stage "ENCRYPT"
    $envelope = Protect-PortablePayload $payload $password

    Write-Stage "MEMORY_ROUNDTRIP_VERIFY"
    $roundTripText = Unprotect-PortablePayload $envelope $password
    $roundTrip = $roundTripText | ConvertFrom-Json
    [object[]]$roundTripProfiles = $roundTrip.profiles
    if ([int]$roundTrip.profile_count -ne $profiles.Count -or $roundTripProfiles.Count -ne $profiles.Count) {
        throw "Encrypted payload round-trip count mismatch. File transfer se KHONG duoc ghi."
    }

    if ([string]::IsNullOrWhiteSpace($TransferFile)) {
        $TransferFile = Join-Path ([Environment]::GetFolderPath("Desktop")) ("KVTM-PROFILES-TRANSFER-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".kvtm")
    }

    $envelope | Add-Member -NotePropertyName created_at -NotePropertyValue (Get-Date).ToString("o")
    $envelope | Add-Member -NotePropertyName profile_count -NotePropertyValue $portableProfiles.Count
    $envelope | Add-Member -NotePropertyName includes_settings -NotePropertyValue ([bool]$IncludeSettings)

    Write-Stage "WRITE_TRANSFER_FILE"
    [IO.File]::WriteAllText(
        $TransferFile,
        (ConvertTo-Json -InputObject $envelope -Depth 10),
        $Utf8NoBom
    )

    Write-Host "PROFILE TRANSFER EXPORT OK" -ForegroundColor Green
    Write-Host "Profiles: $($portableProfiles.Count)"
    Write-Host "Settings included: $([bool]$IncludeSettings)"
    Write-Host "File: $TransferFile"
    Write-Host "Memory round-trip verified: True"
    Write-Host "Secret plaintext chi ton tai trong bo nho trong luc export; file tren dia da duoc ma hoa + HMAC." -ForegroundColor Cyan
    exit 0
}

Write-Stage "READ_TRANSFER_FILE"
if ([string]::IsNullOrWhiteSpace($TransferFile)) {
    throw "Import can -TransferFile duong dan den file .kvtm."
}
if (-not (Test-Path -LiteralPath $TransferFile -PathType Leaf)) {
    throw "Khong tim thay file transfer: $TransferFile"
}

$envelope = Get-Content -LiteralPath $TransferFile -Raw -Encoding UTF8 | ConvertFrom-Json
$password = Read-PasswordText "Nhap mat khau file chuyen may"

Write-Stage "DECRYPT_TRANSFER"
$payloadText = Unprotect-PortablePayload $envelope $password
$payload = $payloadText | ConvertFrom-Json
[object[]]$incoming = $payload.profiles
if ($incoming.Count -eq 0) {
    throw "File transfer khong co profile."
}
if ([int]$payload.profile_count -ne $incoming.Count) {
    throw "Profile count trong payload khong khop."
}

$localClient = Find-LocalClient
$localGame = Join-Path $env:APPDATA "VNG Corporation\ZingPlay\zpp\24\game"
$rewrittenClient = 0
$rewrittenGame = 0
[object[]]$outProfiles = @()

Write-Stage "DPAPI_REBIND"
foreach ($profile in $incoming) {
    [object[]]$incomingSecretArgs = $profile.secret_args
    if ($incomingSecretArgs.Count -eq 0) {
        throw "Profile '$($profile.name)' co secret_args rong."
    }

    $secretJson = ConvertTo-Json -InputObject ([object[]]$incomingSecretArgs) -Depth 30 -Compress
    $dpapi = Protect-DpapiSecret $secretJson
    if ((Unprotect-DpapiSecret $dpapi) -cne $secretJson) {
        throw "DPAPI round-trip fail cho profile '$($profile.name)'."
    }

    $clientPath = [string]$profile.client
    if ((-not (Test-Path -LiteralPath $clientPath -PathType Leaf)) -and $localClient) {
        $clientPath = $localClient
        $rewrittenClient++
    }

    $gamePath = [string]$profile.game_dir
    if ((-not (Test-Path -LiteralPath $gamePath -PathType Container)) -and (Test-Path -LiteralPath $localGame -PathType Container)) {
        $gamePath = $localGame
        $rewrittenGame++
    }

    $outProfile = [pscustomobject]@{
        id = [string]$profile.id
        name = [string]$profile.name
        client = $clientPath
        game_dir = $gamePath
        secret = $dpapi
        updated_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    }
    $outProfiles += $outProfile
}

if ($outProfiles.Count -ne $incoming.Count) {
    throw "Import profile count mismatch before merge."
}

$destination = $ProfileFile
$dataRoot = Split-Path -Parent $destination
New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null

$incomingCount = $outProfiles.Count
$existingCount = 0
$preservedLocalCount = 0
$incomingKeys = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)
foreach ($incomingProfile in $outProfiles) {
    $incomingId = ([string]$incomingProfile.id).Trim()
    if ([string]::IsNullOrWhiteSpace($incomingId) -or
        -not $incomingKeys.Add($incomingId)) {
        throw "File transfer co profile thieu/trung id '$incomingId'; khong import."
    }
}
if (-not $ReplaceProfiles -and (Test-Path -LiteralPath $destination -PathType Leaf)) {
    Write-Stage "MERGE_EXISTING_PROFILES"
    [object[]]$existingProfiles = (
        Get-Content -LiteralPath $destination -Raw -Encoding UTF8 | ConvertFrom-Json
    )
    $existingCount = $existingProfiles.Count
    $mergedById = [ordered]@{}
    foreach ($existingProfile in $existingProfiles) {
        $existingId = ([string]$existingProfile.id).Trim()
        if ([string]::IsNullOrWhiteSpace($existingId) -or
            [string]::IsNullOrWhiteSpace([string]$existingProfile.secret)) {
            throw "Profile hien co thieu id/secret; khong merge de tranh mat login."
        }
        $key = $existingId.ToLowerInvariant()
        if ($mergedById.Contains($key)) {
            throw "Profile hien co trung id '$existingId'; khong merge."
        }
        $mergedById.Add($key, $existingProfile)
    }

    foreach ($incomingProfile in $outProfiles) {
        $incomingId = ([string]$incomingProfile.id).Trim()
        $key = $incomingId.ToLowerInvariant()
        if (-not $mergedById.Contains($key)) {
            $mergedById.Add($key, $incomingProfile)
        }
        else {
            $mergedById[$key] = $incomingProfile
        }
    }
    $preservedLocalCount = @(
        $existingProfiles | Where-Object {
            -not $incomingKeys.Contains(([string]$_.id).Trim())
        }
    ).Count
    [object[]]$outProfiles = @($mergedById.Values)
}
elseif ($ReplaceProfiles) {
    Write-Stage "REPLACE_PROFILES_REQUESTED"
}

if ($outProfiles.Count -lt $incomingCount) {
    throw "Profile count sau merge nho hon file transfer; khong ghi de profile active."
}
Backup-FileSafe $destination (Join-Path $dataRoot "profile-backups") "profiles-before-machine-import"

Write-Stage "WRITE_PROFILE_TEMP"
$temp = "$destination.transfer.tmp"
try {
    $outJson = ConvertTo-Json -InputObject ([object[]]$outProfiles) -Depth 20
    [IO.File]::WriteAllText($temp, $outJson, $Utf8NoBom)
    [object[]]$check = (Get-Content -LiteralPath $temp -Raw -Encoding UTF8 | ConvertFrom-Json)
    if ($check.Count -ne $outProfiles.Count) {
        throw "File profiles tam khong hop le; khong ghi de profile active."
    }

    Write-Stage "ACTIVATE_PROFILE"
    Move-Item -LiteralPath $temp -Destination $destination -Force
}
catch {
    Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
    throw
}

$settingsImported = $false
if ($ImportSettings -and -not [string]::IsNullOrWhiteSpace([string]$payload.settings_text)) {
    $settingsPath = Join-Path $dataRoot "settings.json"
    Backup-FileSafe $settingsPath (Join-Path $dataRoot "profile-backups") "settings-before-machine-import"
    [IO.File]::WriteAllText($settingsPath, [string]$payload.settings_text, $Utf8NoBom)
    $settingsImported = $true
}

Write-Host "PROFILE TRANSFER IMPORT OK" -ForegroundColor Green
Write-Host "Incoming profiles: $incomingCount"
Write-Host "Existing profiles: $existingCount"
Write-Host "Preserved local-only profiles: $preservedLocalCount"
Write-Host "Profiles after merge: $($outProfiles.Count)"
Write-Host "Import mode: $(if ($ReplaceProfiles) { 'REPLACE' } else { 'MERGE_BY_ID' })"
Write-Host "Destination: $destination"
Write-Host "Client paths rewritten: $rewrittenClient"
Write-Host "Game paths rewritten: $rewrittenGame"
Write-Host "Settings imported: $settingsImported"
if (-not $localClient) {
    Write-Host "[CANH BAO] Chua tim thay GameClientJS.exe local. Hay cai ZingPlay truoc khi mo profile." -ForegroundColor Yellow
}
if (-not (Test-Path -LiteralPath $localGame -PathType Container)) {
    Write-Host "[CANH BAO] Chua tim thay game data KVTM local. Mo/cai Sky Garden tren ZingPlay mot lan truoc khi launch." -ForegroundColor Yellow
}
Write-Host "Tat ca secret da duoc DPAPI ma hoa lai cho Windows user hien tai." -ForegroundColor Cyan
exit 0
