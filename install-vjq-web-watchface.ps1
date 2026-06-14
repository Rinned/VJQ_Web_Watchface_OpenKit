param(
    [string]$Python = "python",
    [string]$Sdb = "F:\Tizen\tools\sdb.exe",
    [string]$Gcc = "F:\Tizen\tools\arm-linux-gnueabi-gcc-9.2\bin\arm-linux-gnueabi-gcc.exe",
    [string]$Source = ".\example_unpacked_watchface",
    [double]$ImageScale = 1.0,
    [double]$OuterUiScale = 1.03,
    [double]$HandScale = 1.0,
    [double]$HandWidthScale = 1.0,
    [int]$EdgeBlackout = 0,
    [int]$EdgeBlackoutTop = 0,
    [int]$EdgeBlackoutRight = 0,
    [int]$EdgeBlackoutBottom = 0,
    [int]$EdgeBlackoutLeft = 0,
    [int]$ShellMaskTop = 0,
    [int]$ShellMaskRight = 0,
    [int]$ShellMaskBottom = 0,
    [int]$ShellMaskLeft = 0,
    [bool]$OpaqueHands = $true,
    [int]$OuterBlankRingRadius = 0,
    [int]$OuterBlankRingPadding = 2,
    [int]$AlphaThreshold = 0,
    [int]$BlackMatteAlpha = 0,
    [double]$CardinalGapDeg = 0.0,
    [double]$CardinalGapInnerRadius = 148.0,
    [double]$CardinalDimDeg = 0.0,
    [double]$CardinalDimInnerRadius = 150.0,
    [double]$CardinalDimFactor = 0.35,
    [double]$FrameCardinalGapDeg = 0.0,
    [double]$FrameCardinalGapInnerRadius = 170.0,
    [double]$CompositionSafeScale = 1.0,
    [int]$LogicalCanvasSize = 360,
    [double]$ViewportCanvasScale = 1.0,
    [double]$WrapperTransformScale = 1.0,
    [double]$CanvasTransformScale = 1.0,
    [double]$SceneScale = 1.0,
    [double]$BatteryRadius = 178.4,
    [double]$BatteryGlowScale = 1.0,
    [switch]$SquareUi,
    [double]$SquareUiInset = 22.0,
    [double]$SquareArcInset = 22.0,
    [double]$SquareArcCornerRadius = 0.0,
    [double]$SparkScale = 1.0,
    [switch]$HideIndex,
    [switch]$HideArt,
    [switch]$HideHands,
    [switch]$HideFrame,
    [switch]$HideCorners,
    [switch]$HideBatteryArc,
    [switch]$HideBottomText,
    [switch]$WhiteIndex,
    [string]$IndexColor = "",
    [switch]$BatteryLabel,
    [string]$ParkingPackageId = "",
    [string]$ParkingAppId = "",
    [switch]$Apply,
    [switch]$Screenshot
)

$Args = @(
    ".\vjq_web_watchface_installer.py",
    "--sdb", $Sdb,
    "--gcc", $Gcc,
    "--source", $Source,
    "--image-scale", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $ImageScale)),
    "--outer-ui-scale", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $OuterUiScale)),
    "--hand-scale", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $HandScale)),
    "--hand-width-scale", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $HandWidthScale)),
    "--edge-blackout", "$EdgeBlackout",
    "--edge-blackout-top", "$EdgeBlackoutTop",
    "--edge-blackout-right", "$EdgeBlackoutRight",
    "--edge-blackout-bottom", "$EdgeBlackoutBottom",
    "--edge-blackout-left", "$EdgeBlackoutLeft",
    "--shell-mask-top", "$ShellMaskTop",
    "--shell-mask-right", "$ShellMaskRight",
    "--shell-mask-bottom", "$ShellMaskBottom",
    "--shell-mask-left", "$ShellMaskLeft",
    "--outer-blank-ring-radius", "$OuterBlankRingRadius",
    "--outer-blank-ring-padding", "$OuterBlankRingPadding",
    "--alpha-threshold", "$AlphaThreshold",
    "--black-matte-alpha", "$BlackMatteAlpha",
    "--cardinal-gap-deg", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $CardinalGapDeg)),
    "--cardinal-gap-inner-radius", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $CardinalGapInnerRadius)),
    "--cardinal-dim-deg", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $CardinalDimDeg)),
    "--cardinal-dim-inner-radius", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $CardinalDimInnerRadius)),
    "--cardinal-dim-factor", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $CardinalDimFactor)),
    "--frame-cardinal-gap-deg", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $FrameCardinalGapDeg)),
    "--frame-cardinal-gap-inner-radius", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $FrameCardinalGapInnerRadius)),
    "--composition-safe-scale", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $CompositionSafeScale)),
    "--logical-canvas-size", "$LogicalCanvasSize",
    "--viewport-canvas-scale", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $ViewportCanvasScale)),
    "--wrapper-transform-scale", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $WrapperTransformScale)),
    "--canvas-transform-scale", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $CanvasTransformScale)),
    "--scene-scale", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $SceneScale)),
    "--battery-radius", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $BatteryRadius)),
    "--battery-glow-scale", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $BatteryGlowScale)),
    "--square-ui-inset", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $SquareUiInset)),
    "--square-arc-inset", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $SquareArcInset)),
    "--square-arc-corner-radius", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $SquareArcCornerRadius)),
    "--spark-scale", ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $SparkScale))
)
if ($SquareUi) { $Args += "--square-ui" }
if ($OpaqueHands) { $Args += "--opaque-hands" }
if ($WhiteIndex) { $Args += "--white-index" }
if ($IndexColor) { $Args += @("--index-color", $IndexColor) }
if ($BatteryLabel) { $Args += "--battery-label" }
if ($HideIndex) { $Args += "--hide-index" }
if ($HideArt) { $Args += "--hide-art" }
if ($HideHands) { $Args += "--hide-hands" }
if ($HideFrame) { $Args += "--hide-frame" }
if ($HideCorners) { $Args += "--hide-corners" }
if ($HideBatteryArc) { $Args += "--hide-battery-arc" }
if ($HideBottomText) { $Args += "--hide-bottom-text" }
if ($ParkingPackageId) { $Args += @("--parking-package-id", $ParkingPackageId) }
if ($ParkingAppId) { $Args += @("--parking-app-id", $ParkingAppId) }
if ($Apply) { $Args += "--apply" }
if ($Screenshot) { $Args += "--screenshot" }

& $Python @Args
exit $LASTEXITCODE
