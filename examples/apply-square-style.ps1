param(
    [string]$Python = "python",
    [string]$Sdb = "C:\path\to\sdb.exe",
    [string]$Gcc = "C:\path\to\arm-linux-gnueabi-gcc.exe",
    [Parameter(Mandatory = $true)]
    [string]$Source
)

$root = Split-Path -Parent $PSScriptRoot

powershell -ExecutionPolicy Bypass -File (Join-Path $root "install-vjq-web-watchface.ps1") `
  -Python $Python `
  -Sdb $Sdb `
  -Gcc $Gcc `
  -Source $Source `
  -IndexColor '#756644' `
  -SquareUi `
  -SquareUiInset 24 `
  -SquareArcInset 36 `
  -SquareArcCornerRadius 30 `
  -SparkScale 1.35 `
  -HandScale 0.84 `
  -HandWidthScale 0.68 `
  -BatteryRadius 168 `
  -BatteryGlowScale 0.72 `
  -CardinalDimDeg 24 `
  -CardinalDimInnerRadius 150 `
  -CardinalDimFactor 0.12 `
  -LogicalCanvasSize 360 `
  -ViewportCanvasScale 1.0 `
  -WrapperTransformScale 1.0 `
  -CanvasTransformScale 1.0 `
  -CardinalGapDeg 0 `
  -FrameCardinalGapDeg 0 `
  -Apply `
  -Screenshot

