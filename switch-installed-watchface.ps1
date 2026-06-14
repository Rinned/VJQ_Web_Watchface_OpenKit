param(
    [Parameter(Mandatory = $true)]
    [string]$PackageId,

    [string]$AppId = $PackageId,

    [string]$Sdb = 'F:\Tizen\tools\sdb.exe',

    [switch]$Screenshot
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Sdb)) {
    throw "sdb not found: $Sdb"
}

$pkgInfo = & $Sdb shell "pkginfo --app $AppId 2>&1"
$pkgInfo | ForEach-Object { Write-Host $_ }

if (($pkgInfo -join "`n") -match 'Failed to get handle|get app info failed') {
    throw "App is not installed/registered: $AppId"
}

$launch = & $Sdb shell "aul_test launch com.samsung.w-home home_op set_watchface package_id $PackageId app_id $AppId 2>&1"
$launch | ForEach-Object { Write-Host $_ }

if (($launch -join "`n") -notmatch 'test success') {
    throw "w-home did not report success for $PackageId / $AppId"
}

if ($Screenshot) {
    $safeName = ($AppId -replace '[^A-Za-z0-9_.-]', '_')
    $fileName = "watchface_switch_${safeName}_$(Get-Date -Format 'yyyyMMdd_HHmmss').png"
    & $Sdb shell "input_generator_tool screen_capture $fileName 2>&1" | ForEach-Object { Write-Host $_ }
    & $Sdb pull "/opt/usr/media/DCIM/Screenshots/$fileName" "$PSScriptRoot" | ForEach-Object { Write-Host $_ }
    Write-Host "Screenshot: $(Join-Path $PSScriptRoot $fileName)"
}

Write-Host "Switched to $AppId"
