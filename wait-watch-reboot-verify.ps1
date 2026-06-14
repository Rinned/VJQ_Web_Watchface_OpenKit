param(
    [string]$Sdb = "F:\Tizen\tools\sdb.exe",
    [int]$TimeoutSeconds = 900,
    [int]$PollSeconds = 5,
    [string]$ScreenshotPrefix = "codex_vjq_after_manual_reboot",
    [switch]$ColdStartAfterReconnect,
    [switch]$SkipAssetCheck,
    [switch]$SkipPayloadCheck
)

if (-not (Test-Path -LiteralPath $Sdb)) {
    throw "sdb not found: $Sdb"
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$seenDisconnected = $false

Write-Host "Waiting for watch reboot/disconnect. Press reboot on the watch now if you have not already."
while ((Get-Date) -lt $deadline) {
    $devices = & $Sdb devices 2>&1
    $deviceLine = $devices | Where-Object { $_ -match "\sdevice\s" } | Select-Object -First 1
    $elapsed = [int]($TimeoutSeconds - ($deadline - (Get-Date)).TotalSeconds)

    if ($deviceLine) {
        if ($seenDisconnected) {
            Write-Host "[$elapsed s] Reconnected: $deviceLine"
            Start-Sleep -Seconds 12
            $verifyArgs = @(
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", ".\verify-vjq-web-watchface.ps1",
                "-Sdb", $Sdb,
                "-Screenshot",
                "-ScreenshotPrefix", $ScreenshotPrefix
            )
            if (-not $SkipAssetCheck) {
                $verifyArgs += "-CheckAssets"
            }
            if (-not $SkipPayloadCheck) {
                $verifyArgs += "-CheckPayload"
            }
            if ($ColdStartAfterReconnect) {
                $verifyArgs += "-ColdStart"
            }
            & powershell @verifyArgs
            exit $LASTEXITCODE
        }
        Write-Host "[$elapsed s] Still connected; waiting for disconnect..."
    } else {
        if (-not $seenDisconnected) {
            Write-Host "[$elapsed s] Disconnected; reboot likely in progress."
        }
        $seenDisconnected = $true
    }

    Start-Sleep -Seconds $PollSeconds
}

throw "Timed out waiting for reboot/reconnect after $TimeoutSeconds seconds"
