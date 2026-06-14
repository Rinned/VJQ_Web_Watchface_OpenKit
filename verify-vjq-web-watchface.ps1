param(
    [string]$Sdb = "F:\Tizen\tools\sdb.exe",
    [string]$Gcc = "F:\Tizen\tools\arm-linux-gnueabi-gcc-9.2\bin\arm-linux-gnueabi-gcc.exe",
    [string]$PackageId = "VJQAyUfd52",
    [string]$AppId = "VJQAyUfd52.watch02",
    [string]$BuildDir = ".\vjq_web_watchface_build",
    [string]$RemoteAssetDir = "/home/owner/apps_rw/VJQAyUfd52/shared/data/r",
    [string]$RemoteGdbserver = "/opt/usr/home/owner/share/tmp/sdk_tools/gdbserver/gdbserver",
    [string]$RemotePayloadDump = "/home/owner/share/tmp/codex_vjq_000003_current.log",
    [string]$RemotePayloadDumpLog = "/home/owner/share/tmp/codex_vjq_leveldb_dump.log",
    [switch]$CheckAssets,
    [switch]$CheckPayload,
    [switch]$ColdStart,
    [switch]$Screenshot,
    [string]$ScreenshotPrefix = "codex_vjq_verify"
)

function Invoke-SdbShell {
    param([string]$Command)
    & $Sdb shell "$Command 2>&1"
}

if (-not (Test-Path -LiteralPath $Sdb)) {
    throw "sdb not found: $Sdb"
}

$devices = & $Sdb devices 2>&1
$deviceLine = $devices | Where-Object { $_ -match "\sdevice\s" } | Select-Object -First 1
if (-not $deviceLine) {
    $devices | ForEach-Object { Write-Host $_ }
    throw "No connected watch in device state"
}

Write-Host "Device: $deviceLine"

$pidLines = Invoke-SdbShell "aul_test get_pid $AppId"
$pidLines | ForEach-Object { Write-Host $_ }
$vjPid = $null
foreach ($line in $pidLines) {
    if ($line -match "ret\s*=\s*(\d+)") {
        $vjPid = $Matches[1]
    }
}

if ($ColdStart) {
    if (-not $vjPid) {
        throw "Cannot parse current pid for $AppId"
    }
    Write-Host "ColdStart: terminating pid $vjPid"
    Invoke-SdbShell "aul_test term_pid $vjPid" | ForEach-Object { Write-Host $_ }
    Start-Sleep -Seconds 3
    Write-Host "ColdStart: relaunching watchface through w-home"
    Invoke-SdbShell "aul_test launch com.samsung.w-home home_op set_watchface package_id $PackageId app_id $AppId" |
        ForEach-Object { Write-Host $_ }
    Start-Sleep -Seconds 8
}

Write-Host "Runtime status:"
Invoke-SdbShell "aul_test get_pid $AppId; aul_test is_run $AppId" | ForEach-Object { Write-Host $_ }

$pullRoot = $null
if ($CheckAssets -or $CheckPayload) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $pullRoot = Join-Path ".\verification_pulls" $stamp
    New-Item -ItemType Directory -Force -Path $pullRoot | Out-Null
}

if ($CheckAssets) {
    $assetDir = Join-Path $BuildDir "assets"
    if (-not (Test-Path -LiteralPath $assetDir)) {
        throw "Local asset directory not found: $assetDir"
    }

    Write-Host "Checking remote assets against: $((Resolve-Path -LiteralPath $assetDir).Path)"
    $localFiles = Get-ChildItem -LiteralPath $assetDir -File | Sort-Object Name
    foreach ($local in $localFiles) {
        $remote = "$RemoteAssetDir/$($local.Name)"
        $pulled = Join-Path $pullRoot $local.Name
        & $Sdb pull $remote $pulled | ForEach-Object { Write-Host $_ }
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $pulled)) {
            throw "Failed to pull remote asset: $remote"
        }

        $remoteFile = Get-Item -LiteralPath $pulled
        $localHash = (Get-FileHash -LiteralPath $local.FullName -Algorithm SHA256).Hash
        $remoteHash = (Get-FileHash -LiteralPath $remoteFile.FullName -Algorithm SHA256).Hash
        if ($local.Length -ne $remoteFile.Length -or $localHash -ne $remoteHash) {
            throw "Asset mismatch: $($local.Name) local=$($local.Length)/$localHash remote=$($remoteFile.Length)/$remoteHash"
        }
        Write-Host "Asset OK: $($local.Name) $($local.Length) bytes $localHash"
    }
    Write-Host "Asset check OK: $($localFiles.Count) files"
}

if ($CheckPayload) {
    $texturePath = Join-Path $BuildDir "payload_texture.txt"
    if (-not (Test-Path -LiteralPath $texturePath)) {
        throw "Local payload texture not found: $texturePath"
    }
    $source = ".\fake_gdbserver_webhost_leveldb_dump.c"
    $helper = ".\fake_gdbserver_webhost_leveldb_dump"
    if (-not (Test-Path -LiteralPath $helper) -or
        ((Get-Item -LiteralPath $helper).LastWriteTime -lt (Get-Item -LiteralPath $source).LastWriteTime)) {
        if (-not (Test-Path -LiteralPath $Gcc)) {
            throw "gcc not found: $Gcc"
        }
        & $Gcc -nostdlib -static -Os -fno-stack-protector -o $helper $source
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to compile LevelDB dump helper"
        }
    }

    Write-Host "Dumping VJQ LevelDB payload through app debug helper"
    & $Sdb push $helper $RemoteGdbserver | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to push LevelDB dump helper"
    }
    Invoke-SdbShell "chmod 755 $RemoteGdbserver" | ForEach-Object { Write-Host $_ }
    Invoke-SdbShell "rm -f $RemotePayloadDump $RemotePayloadDumpLog; launch_debug $AppId __AUL_SDK__ DEBUG __DLP_DEBUG_ARG__ :10003" |
        ForEach-Object { Write-Host $_ }
    Start-Sleep -Seconds 2

    $dumpLocal = Join-Path $pullRoot "leveldb_current.log"
    $dumpLogLocal = Join-Path $pullRoot "leveldb_dump_helper.log"
    & $Sdb pull $RemotePayloadDump $dumpLocal | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $dumpLocal)) {
        throw "Failed to pull LevelDB dump: $RemotePayloadDump"
    }
    & $Sdb pull $RemotePayloadDumpLog $dumpLogLocal | ForEach-Object { Write-Host $_ }

    $payloadTexture = Get-Content -LiteralPath $texturePath -Raw -Encoding UTF8
    $dumpText = [Text.Encoding]::UTF8.GetString([IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $dumpLocal).Path))
    if (-not $dumpText.Contains($payloadTexture)) {
        throw "Current LevelDB log does not contain expected payload texture"
    }
    $dumpHash = (Get-FileHash -LiteralPath $dumpLocal -Algorithm SHA256).Hash
    Write-Host "Payload OK: current LevelDB log contains expected texture payload"
    Write-Host "Dumped LevelDB log: $((Resolve-Path -LiteralPath $dumpLocal).Path)"
    Write-Host "Dumped LevelDB SHA256: $dumpHash"
}

if ($Screenshot) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $name = "${ScreenshotPrefix}_${stamp}.png"
    Invoke-SdbShell "input_generator_tool device_wakeup" | ForEach-Object { Write-Host $_ }
    Start-Sleep -Seconds 2
    Invoke-SdbShell "input_generator_tool screen_capture $name" | ForEach-Object { Write-Host $_ }
    $remote = "/opt/usr/media/DCIM/Screenshots/$name"
    & $Sdb pull $remote ".\$name" | ForEach-Object { Write-Host $_ }
    Write-Host "Screenshot: $((Resolve-Path -LiteralPath ".\$name").Path)"
}
